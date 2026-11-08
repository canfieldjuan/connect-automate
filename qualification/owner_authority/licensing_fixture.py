"""Disposable OFFLINE_CONFORMANCE issuer; never a live licensing service.

Only explicit fresh fixture roots and in-memory test signers are accepted. Native
identity, installed trust, network access and product stores have no entrypoint.
"""

import base64
import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from . import protocol as p

FIXTURE_VERSION = "offline-fixture/4"


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
        row = db.execute("SELECT kind,version,contract_commit FROM fixture_identity "
                         "WHERE singleton=1").fetchone()
    except sqlite3.DatabaseError as exc:
        raise FixtureCorrupt("fixture identity unavailable") from exc
    if row != (kind, FIXTURE_VERSION, p.CONTRACT_COMMIT):
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
                         f"version TEXT NOT NULL CHECK(version='{FIXTURE_VERSION}'),"
                         "contract_commit TEXT NOT NULL "
                         f"CHECK(contract_commit='{p.CONTRACT_COMMIT}'));"
                         + ddl)
        db.execute("INSERT INTO fixture_identity VALUES(1,?,?,?)",
                   (kind, FIXTURE_VERSION, p.CONTRACT_COMMIT))
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
            validate(db)  # Actual writer snapshot after waits, before effects.
        identity(db, kind)
        yield db
        checkpoint(hook, "before_commit", db)
        if validate is not None:
            validate(db)
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


def snapshot_digest(db, tables):
    """Hash owner-selected complete rows without exporting private fixture bytes."""
    rows = {table: [[{"bytes": v.hex()} if type(v) is bytes else v for v in row]
                    for row in db.execute("SELECT * FROM " + table + " ORDER BY rowid")]
            for table in tables}
    return hashlib.sha256(p.canonical(rows)).hexdigest()


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
CREATE TABLE recovery_cases (
 case_id TEXT PRIMARY KEY NOT NULL,
 predecessor_operation TEXT NOT NULL UNIQUE REFERENCES consumptions(operation_id),
 document BLOB NOT NULL CHECK(typeof(document)='blob'),
 state TEXT NOT NULL CHECK(state='EVIDENCE_CASE_ONLY'));
CREATE TABLE recovery_admissions (
 case_id TEXT PRIMARY KEY NOT NULL REFERENCES recovery_cases(case_id),
 evidence_id TEXT NOT NULL UNIQUE,
 evidence BLOB NOT NULL CHECK(typeof(evidence)='blob'),
 admission BLOB NOT NULL CHECK(typeof(admission)='blob'),
 state TEXT NOT NULL CHECK(state='EVIDENCE_RECORDED_ONLY'));
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

    def adopt_manifest(self, candidate, now):
        """Explicit synthetic release publication; no issuer ledger or signer changes."""
        p.check_manifest_renewal(candidate, self.manifest, self.manifest,
                                 self.keys, self.release_ids, now)
        self.manifest = candidate

    def _claim(self, claim, now):
        claim = p.OwnerClaim.model_validate(claim)
        if type(now) is not datetime or now.tzinfo is not UTC or p._date(claim.issued_at) != now:
            raise p.ProtocolInputError()
        p.verify_active_manifest(self.manifest, self.keys, self.release_ids, now)
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

    def exchange(self, raw, clock):
        """Fixture-only metadata adapter; the consume owner keeps all effects."""
        try:
            body = self.consume(raw, clock)
        except p.MalformedConsumeRequest:
            return p.fixture_response(400, "application/json", p.MALFORMED_BODY)
        try:
            status = p.REFUSAL_STATUS[p.parse_refusal(body).code]
        except p.ProtocolInputError:
            status = 200
        return p.fixture_response(status, "application/json", body)

    def consume(self, raw, clock):
        request, claim = p.check_consume_request(
            raw, self.manifest, self.keys, self.release_ids, clock())
        new = False

        def validate(db):
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
                validate(db)
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

    @staticmethod
    def _recovery_id(value):
        try:
            return TypeAdapter(p.UuidV4).validate_python(value)
        except (ValueError, TypeError):
            raise p.ProtocolInputError() from None

    @staticmethod
    def _recovery_value(model, **fields):
        return model.model_validate({"version": "offline-recovery-evidence/1",
                                    "evidence_class": "OFFLINE_CONFORMANCE",
                                    "qualification_pass": False, **fields})

    def _recovery_result(self, case_id, action):
        try:
            return action()
        except (p.ManifestUnavailable, p.RecoveryEvidenceExpired,
                p.RecoveryEvidenceInvalid, Refused) as error:
            if isinstance(error, p.ManifestUnavailable):
                code = "RECOVERY_CONFIGURATION_UNAVAILABLE"
            elif isinstance(error, p.RecoveryEvidenceExpired):
                code = "RECOVERY_EVIDENCE_EXPIRED"
            elif isinstance(error, p.RecoveryEvidenceInvalid):
                code = "RECOVERY_EVIDENCE_INVALID"
            else:
                code = error.code
            return p.recovery_bytes(self._recovery_value(
                p.RecoveryEvidenceRefusal, case_id=case_id, code=code))

    def _recovery_predecessor(self, db, claim_id, operation_id, now):
        # Configuration/time errors are separate from damaged stored evidence.
        p.verify_active_manifest(self.manifest, self.keys, self.release_ids, now)
        rows = db.execute("SELECT claim_id,operation_id,binding,receipt FROM consumptions "
                          "WHERE claim_id=? OR operation_id=?", (claim_id, operation_id)).fetchall()
        if not rows:
            raise Refused("RECOVERY_PREDECESSOR_UNAVAILABLE")
        if len(rows) != 1 or rows[0][:2] != (claim_id, operation_id):
            raise Refused("RECOVERY_BINDING_CONFLICT")
        claim = db.execute("SELECT envelope FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        if claim is None:
            raise FixtureCorrupt("recovery predecessor claim missing")
        try:
            binding = p._wire(rows[0][2], p.ConsumeBinding, p.SMALL.payload)
            if (binding.claim_id, binding.operation_id) != (claim_id, operation_id):
                raise p.ProtocolInputError()
            p.check_stored_receipt(rows[0][3], binding, claim[0], self.manifest,
                                   self.keys, self.release_ids, now)
        except p.ManifestUnavailable:
            raise
        except (ValueError, TypeError):
            raise FixtureCorrupt("recovery predecessor evidence corrupt") from None
        return binding, rows[0][3]

    def _recovery_case(self, db, case_id, now):
        row = db.execute("SELECT predecessor_operation,document,state FROM recovery_cases "
                         "WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise Refused("RECOVERY_PREDECESSOR_UNAVAILABLE")
        try:
            case = p.parse_recovery(row[1], "case")
            if (case.case_id != case_id or row[0] != case.predecessor_binding.operation_id
                    or row[2] != "EVIDENCE_CASE_ONLY"):
                raise p.ProtocolInputError()
        except p.ProtocolInputError:
            raise FixtureCorrupt("recovery case corrupt") from None
        try:
            binding, receipt = self._recovery_predecessor(
                db, case.predecessor_binding.claim_id, row[0], now)
        except Refused:
            raise FixtureCorrupt("recovery case predecessor missing or changed") from None
        if (binding != case.predecessor_binding
                or hashlib.sha256(receipt).hexdigest() != case.predecessor_receipt_sha256):
            raise FixtureCorrupt("recovery case predecessor changed")
        return case

    def open_recovery_case(self, case_id, predecessor_claim_id, predecessor_operation_id,
                           replacement, opened_at, expires_at, *, clock):
        case_id = self._recovery_id(case_id)
        claim_id = self._recovery_id(predecessor_claim_id)
        operation_id = self._recovery_id(predecessor_operation_id)

        def build(db, now):
            binding, receipt = self._recovery_predecessor(db, claim_id, operation_id, now)
            try:
                case = self._recovery_value(
                    p.RecoveryEvidenceCase, case_id=case_id, predecessor_binding=binding,
                    predecessor_receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                    replacement=replacement, opened_at=opened_at, expires_at=expires_at)
            except (ValueError, TypeError):
                raise p.RecoveryEvidenceInvalid() from None
            return p.check_recovery_case(case, now)

        def action():
            with read_store(self.root, "issuer") as db:
                selected = build(db, clock())
            raw = p.recovery_bytes(selected)

            def validate(db):
                now = clock()
                if build(db, now) != selected:
                    raise Refused("RECOVERY_BINDING_CONFLICT")
                rows = db.execute("SELECT case_id FROM recovery_cases "
                                  "WHERE case_id=? OR predecessor_operation=?",
                                  (case_id, operation_id)).fetchall()
                for (existing_id,) in rows:
                    existing = self._recovery_case(db, existing_id, now)
                    if p.recovery_bytes(existing) != raw:
                        raise Refused("RECOVERY_BINDING_CONFLICT")

            with transaction(self.root, "issuer", self.hook, validate) as db:
                if not db.execute("SELECT 1 FROM recovery_cases WHERE case_id=?",
                                  (case_id,)).fetchone():
                    db.execute("INSERT INTO recovery_cases VALUES(?,?,?,'EVIDENCE_CASE_ONLY')",
                               (case_id, operation_id, raw))
                    checkpoint(self.hook, "recovery_case_write", db)
            return raw

        return self._recovery_result(case_id, action)

    def select_recovery_evidence(self, case_id, clock):
        case_id = self._recovery_id(case_id)

        def action():
            with read_store(self.root, "issuer") as db:
                now = clock()
                case = self._recovery_case(db, case_id, now)
                p.check_recovery_case(case, now)
                return p.recovery_bytes(p.recovery_selection(case))

        return self._recovery_result(case_id, action)

    def _recovery_admission(self, db, case, selected, now):
        row = db.execute("SELECT evidence_id,evidence,admission,state FROM recovery_admissions "
                         "WHERE case_id=?", (case.case_id,)).fetchone()
        if row is None:
            return None
        try:
            evidence = p.check_recovery_evidence(row[1], case, selected, now)
            admission = p.parse_recovery(row[2], "admission")
            expected = (case.case_id, evidence.evidence_id, selected.case_sha256,
                        hashlib.sha256(row[1]).hexdigest(), case.predecessor_receipt_sha256,
                        evidence.replacement_sha256)
            actual = (admission.case_id, admission.evidence_id, admission.case_sha256,
                      admission.evidence_sha256, admission.predecessor_receipt_sha256,
                      admission.replacement_sha256)
            if (actual != expected or row[0] != evidence.evidence_id
                    or row[3] != admission.state
                    or not p._date(evidence.asserted_at) <= p._date(admission.admitted_at)
                    < p._date(evidence.expires_at)):
                raise p.ProtocolInputError()
        except p.RecoveryEvidenceExpired:
            raise
        except (ValueError, TypeError):
            raise FixtureCorrupt("recovery admission corrupt") from None
        return row[1], row[2]

    def admit_recovery_evidence(self, selected, evidence_raw, clock):
        try:
            selected = p.RecoveryEvidenceSelection.model_validate(selected)
        except (ValueError, TypeError):
            raise p.ProtocolInputError() from None

        def action():
            with read_store(self.root, "issuer") as db:
                now = clock()
                case = self._recovery_case(db, selected.case_id, now)
                evidence = p.check_recovery_evidence(evidence_raw, case, selected, now)

            def validate(db):
                now = clock()
                current = self._recovery_case(db, selected.case_id, now)
                p.check_recovery_evidence(evidence_raw, current, selected, now)
                existing = self._recovery_admission(db, current, selected, now)
                if existing is not None and existing[0] != evidence_raw:
                    raise Refused("RECOVERY_BINDING_CONFLICT")
                other = db.execute("SELECT case_id FROM recovery_admissions WHERE evidence_id=?",
                                   (evidence.evidence_id,)).fetchone()
                if other is not None and other[0] != selected.case_id:
                    raise Refused("RECOVERY_BINDING_CONFLICT")

            with transaction(self.root, "issuer", self.hook, validate) as db:
                existing = self._recovery_admission(db, case, selected, clock())
                if existing is not None:
                    return existing[1]
                admission = self._recovery_value(
                    p.RecoveryEvidenceAdmission, admission_id=str(uuid4()),
                    case_id=case.case_id, evidence_id=evidence.evidence_id,
                    case_sha256=selected.case_sha256,
                    evidence_sha256=hashlib.sha256(evidence_raw).hexdigest(),
                    predecessor_receipt_sha256=case.predecessor_receipt_sha256,
                    replacement_sha256=evidence.replacement_sha256,
                    admitted_at=clock().isoformat(timespec="seconds").replace("+00:00", "Z"),
                    state="EVIDENCE_RECORDED_ONLY")
                raw = p.recovery_bytes(admission)
                db.execute("INSERT INTO recovery_admissions "
                           "VALUES(?,?,?,?,'EVIDENCE_RECORDED_ONLY')",
                           (case.case_id, evidence.evidence_id, evidence_raw, raw))
                checkpoint(self.hook, "recovery_admission_write", db)
                return raw

        return self._recovery_result(selected.case_id, action)

    def recovery_snapshot(self):
        with read_store(self.root, "issuer") as db:
            return {"sha256": snapshot_digest(db, ("recovery_cases", "recovery_admissions")),
                    "cases": db.execute("SELECT count(*) FROM recovery_cases").fetchone()[0],
                    "admissions": db.execute(
                        "SELECT count(*) FROM recovery_admissions").fetchone()[0]}

    def snapshot(self):
        with read_store(self.root, "issuer") as db:
            return {
                "ledger_sha256": snapshot_digest(db, ("claims", "consumptions", "journal")),
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
