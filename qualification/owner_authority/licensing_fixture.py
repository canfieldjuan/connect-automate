"""Disposable OFFLINE_CONFORMANCE issuer; never a live licensing service.

Only explicit fresh fixture roots and in-memory test signers are accepted. Native
identity, installed trust, network access and product stores have no entrypoint.
"""

import base64
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from . import protocol as p


class FixtureCorrupt(RuntimeError):
    """Missing, wrong-owner or malformed disposable storage; never initialize it."""


class FixtureLocked(RuntimeError):
    """Restored fixture has no qualified journal-continuity proof."""


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def checkpoint(hook, name, db):
    if hook is not None:
        hook(name, db)


def connect_store(root):
    root = Path(root)
    path = root / "fixture.sqlite"
    if root.is_symlink() or root.is_junction() or path.is_symlink() or path.is_junction():
        raise FixtureCorrupt("fixture path is indirect")
    if (root / "restore.lock").exists():
        raise FixtureLocked("RECOVERY_LOCKED")
    # mode=rw prevents a missing database becoming an empty replacement owner.
    db = sqlite3.connect(path.absolute().as_uri() + "?mode=rw", uri=True,
                         isolation_level=None, timeout=5)
    db.execute("PRAGMA foreign_keys=ON")
    return db


def identity(db, kind):
    try:
        row = db.execute("SELECT kind, version FROM fixture_identity WHERE singleton=1").fetchone()
    except sqlite3.DatabaseError as exc:
        raise FixtureCorrupt("fixture identity unavailable") from exc
    if row != (kind, "offline-fixture/1"):
        raise FixtureCorrupt("wrong fixture owner/version")


def create_store(root, kind, ddl, *, restored=False):
    if kind not in ("issuer", "host") or type(restored) is not bool:
        raise FixtureCorrupt("invalid fixture kind")
    root = Path(root)
    root.mkdir(mode=0o700)  # Refuse every existing root, including symlinks.
    if restored:
        os.close(os.open(root / "restore.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    path = root / "fixture.sqlite"
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.executescript("BEGIN IMMEDIATE; CREATE TABLE fixture_identity ("
                         "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                         "kind TEXT NOT NULL CHECK(kind IN ('issuer','host')),"
                         "version TEXT NOT NULL CHECK(version='offline-fixture/1'));" + ddl)
        db.execute("INSERT INTO fixture_identity VALUES(1,?,?)", (kind, "offline-fixture/1"))
        db.commit()
    finally:
        db.close()


@contextmanager
def transaction(root, kind, hook=None, validate=None):
    db = connect_store(root)
    try:
        checkpoint(hook, "before_writer", db)
        db.execute("BEGIN IMMEDIATE")
        checkpoint(hook, "writer", db)
        if validate is not None:
            validate()  # After writer waits, before any state lookup.
        identity(db, kind)
        yield db
        checkpoint(hook, "before_commit", db)
        if validate is not None:
            validate()
        db.commit()
        checkpoint(hook, "after_commit", db)
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def read_store(root, kind):
    db = connect_store(root)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        identity(db, kind)
        yield db
    finally:
        db.close()


def signed(kind, payload, signer):
    key_id, key = signer
    raw = p.canonical(payload)
    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    return p.canonical({"version": "owner-bootstrap/1", "key_id": key_id,
                        "payload_base64url": encode(raw),
                        "signature_base64url": encode(key.sign(p.prefix(kind) + raw))})


ISSUER_SQL = """
CREATE TABLE claims (
 claim_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, entitlement_id TEXT NOT NULL,
 generation INTEGER NOT NULL CHECK(typeof(generation)='integer'
 AND generation BETWEEN 1 AND 2147483647),
 envelope BLOB NOT NULL, state TEXT NOT NULL CHECK(state IN ('ACTIVE','REVOKED','SUPERSEDED')),
 UNIQUE(organization_id,entitlement_id,generation));
CREATE UNIQUE INDEX one_active_claim ON claims(organization_id,entitlement_id) WHERE state='ACTIVE';
CREATE TABLE consumptions (
 claim_id TEXT PRIMARY KEY REFERENCES claims(claim_id), operation_id TEXT NOT NULL UNIQUE,
 binding BLOB NOT NULL, receipt BLOB NOT NULL);
CREATE TABLE journal (
 sequence INTEGER PRIMARY KEY,
 event TEXT NOT NULL CHECK(event IN ('ISSUE','CONSUME','REVOKE','REISSUE')),
 claim_id TEXT NOT NULL REFERENCES claims(claim_id));
"""


class IssuerFixture:
    def __init__(self, root, manifest, keys, release_ids, claim_signer, receipt_signer,
                 *, hook=None):
        self.root, self.manifest = Path(root), manifest
        self.keys, self.release_ids = dict(keys), frozenset(release_ids)
        self.claim_signer, self.receipt_signer, self.hook = claim_signer, receipt_signer, hook
        value = p.verify_signed(manifest, "manifest", self.keys, self.release_ids)
        for signer, allowed in ((claim_signer, value.claim_key_ids),
                                (receipt_signer, value.receipt_key_ids)):
            key_id, key = signer
            if key_id not in allowed or key.public_key().public_bytes_raw() != self.keys[key_id]:
                raise p.ProtocolInputError()

    def create(self):
        create_store(self.root, "issuer", ISSUER_SQL)
        return self

    def _claim(self, claim, now):
        claim = p.OwnerClaim.model_validate(claim)
        if type(now) is not datetime or now.tzinfo is not UTC or p._date(claim.issued_at) != now:
            raise p.ProtocolInputError()
        manifest = p.verify_signed(self.manifest, "manifest", self.keys, self.release_ids)
        if not p._date(manifest.issued_at) <= now < p._date(manifest.expires_at):
            raise p.ProtocolInputError()
        return claim, signed("claim", claim.model_dump(), self.claim_signer)

    def _insert(self, db, claim, raw):
        db.execute("INSERT INTO claims VALUES(?,?,?,?,?,'ACTIVE')", (
            claim.claim_id, claim.organization_id, claim.entitlement_id, claim.generation, raw))
        checkpoint(self.hook, "claim_write", db)

    def _journal(self, db, event, claim_id):
        db.execute("INSERT INTO journal(event,claim_id) VALUES(?,?)", (event, claim_id))
        checkpoint(self.hook, "journal_write", db)

    def issue(self, claim, now):
        claim, raw = self._claim(claim, now)
        with transaction(self.root, "issuer", self.hook) as db:
            if db.execute("SELECT 1 FROM claims WHERE organization_id=? AND entitlement_id=?",
                          (claim.organization_id, claim.entitlement_id)).fetchone():
                raise Refused("OWNER_BINDING_CONFLICT")
            self._insert(db, claim, raw)
            self._journal(db, "ISSUE", claim.claim_id)
        return raw

    def consume(self, raw, clock):
        request, claim = p.check_consume_request(
            raw, self.manifest, self.keys, self.release_ids, clock())
        new = False

        def validate():
            now = clock()
            p.check_consume_request(raw, self.manifest, self.keys, self.release_ids, now)
            if new:
                if now < p._date(claim.not_before):
                    raise Refused("OWNER_AUTHORIZATION_INVALID")
                if now >= p._date(claim.expires_at):
                    raise Refused("OWNER_AUTHORIZATION_EXPIRED")

        try:
            with transaction(self.root, "issuer", self.hook, validate) as db:
                old = db.execute("SELECT binding,receipt FROM consumptions "
                                 "WHERE claim_id=? OR operation_id=?",
                                 (claim.claim_id, request.binding.operation_id)).fetchone()
                if old is not None:
                    if old[0] != p.canonical(request.binding.model_dump()):
                        raise Refused("OWNER_BINDING_CONFLICT")
                    p.check_receipt(old[1], raw, self.manifest, self.keys,
                                    self.release_ids, clock())
                    return old[1]
                row = db.execute("SELECT envelope,state FROM claims WHERE claim_id=?",
                                 (claim.claim_id,)).fetchone()
                if row is None or row[0] != p.canonical(request.owner_claim.model_dump()):
                    raise Refused("OWNER_AUTHORIZATION_INVALID")
                if row[1] != "ACTIVE":
                    raise Refused("OWNER_AUTHORIZATION_REVOKED")
                new = True
                validate()
                payload = p.ConsumedReceipt.model_validate({
                    "version": "owner-bootstrap/1", "purpose": "owner-bootstrap-receipt",
                    "state": "CONSUMED", "receipt_id": str(uuid4()),
                    "binding": request.binding.model_dump(),
                    "consumed_at": clock().isoformat(timespec="seconds").replace("+00:00", "Z"),
                })
                receipt = signed("receipt", payload.model_dump(), self.receipt_signer)
                p.check_receipt(receipt, raw, self.manifest, self.keys, self.release_ids, clock())
                db.execute("INSERT INTO consumptions VALUES(?,?,?,?)", (
                    claim.claim_id, request.binding.operation_id,
                    p.canonical(request.binding.model_dump()), receipt))
                checkpoint(self.hook, "consumption_write", db)
                self._journal(db, "CONSUME", claim.claim_id)
                return receipt
        except (Refused, FixtureLocked) as exc:
            code = exc.code if isinstance(exc, Refused) else "LICENSING_UNAVAILABLE"
            return p.canonical(p.Refusal.model_validate({
                "version": "owner-bootstrap/1", "code": code,
                "operation_id": request.binding.operation_id, "completion": "NOT_COMMITTED",
            }).model_dump())

    def revoke(self, claim_id):
        claim_id = TypeAdapter(p.UuidV4).validate_python(claim_id)
        with transaction(self.root, "issuer", self.hook) as db:
            row = db.execute("SELECT 1 FROM consumptions WHERE claim_id=?", (claim_id,)).fetchone()
            if row is not None:
                return "CONSUMED"
            result = db.execute("UPDATE claims SET state='REVOKED' "
                                "WHERE claim_id=? AND state='ACTIVE' RETURNING state",
                                (claim_id,)).fetchone()
            if result is not None:
                checkpoint(self.hook, "revocation_write", db)
                self._journal(db, "REVOKE", claim_id)
            else:
                result = db.execute("SELECT state FROM claims WHERE claim_id=?",
                                    (claim_id,)).fetchone()
                if result != ("REVOKED",):
                    raise Refused("OWNER_BINDING_CONFLICT")
            return result[0]

    def reissue(self, claim_id, replacement, now):
        claim_id = TypeAdapter(p.UuidV4).validate_python(claim_id)
        replacement, raw = self._claim(replacement, now)
        with transaction(self.root, "issuer", self.hook) as db:
            row = db.execute("SELECT organization_id,entitlement_id,generation,state FROM claims "
                             "WHERE claim_id=?", (claim_id,)).fetchone()
            consumed = db.execute("SELECT 1 FROM consumptions WHERE claim_id=?",
                                  (claim_id,)).fetchone()
            if (row is None or consumed is not None or row[3] == "SUPERSEDED"
                    or (replacement.organization_id, replacement.entitlement_id) != row[:2]
                    or replacement.generation <= row[2] or replacement.claim_id == claim_id):
                raise Refused("OWNER_BINDING_CONFLICT")
            db.execute("UPDATE claims SET state='SUPERSEDED' WHERE claim_id=?", (claim_id,))
            checkpoint(self.hook, "supersession_write", db)
            self._insert(db, replacement, raw)
            self._journal(db, "REISSUE", replacement.claim_id)
        return raw

    def snapshot(self):
        with read_store(self.root, "issuer") as db:
            return {
                "consumptions": db.execute("SELECT count(*) FROM consumptions").fetchone()[0],
                "claims": db.execute(
                    "SELECT claim_id,state FROM claims ORDER BY claim_id").fetchall(),
                "journal": db.execute(
                    "SELECT event,claim_id FROM journal ORDER BY sequence").fetchall(),
            }

    def restore_to(self, root):
        """Synthetic backup restore refuses all use; no continuity/unlock claim."""
        create_store(root, "issuer", ISSUER_SQL, restored=True)
        with read_store(self.root, "issuer") as source:
            destination = sqlite3.connect(Path(root) / "fixture.sqlite")
            try:
                source.backup(destination)
            finally:
                destination.close()
        return IssuerFixture(root, self.manifest, self.keys, self.release_ids,
                             self.claim_signer, self.receipt_signer)
