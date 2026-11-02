"""Disposable local bootstrap model. All observations/results are offline-only.

Synthetic principal references deliberately replace native accounts here. Keys
stay in caller-owned test memory; this module cannot authenticate or enroll users.
"""

import base64
import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from . import protocol as p
from .licensing_fixture import (
    FixtureCorrupt,
    Refused,
    checkpoint,
    create_store,
    read_store,
    transaction,
)

HOST_SQL = """
CREATE TABLE configuration (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), installation_id TEXT NOT NULL,
 host_id TEXT NOT NULL, organization_id TEXT NOT NULL, public_key TEXT NOT NULL);
CREATE TABLE pending (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), operation_id TEXT NOT NULL UNIQUE,
 binding BLOB NOT NULL, claim BLOB NOT NULL, salt BLOB NOT NULL CHECK(length(salt)=32),
 principal BLOB NOT NULL);
CREATE TABLE receipts (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), operation_id TEXT NOT NULL UNIQUE
 REFERENCES pending(operation_id), envelope BLOB NOT NULL);
CREATE TABLE admins (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), operation_id TEXT NOT NULL UNIQUE
 REFERENCES receipts(operation_id), principal_commitment TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role='admin'));
CREATE TABLE audit (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), operation_id TEXT NOT NULL UNIQUE
 REFERENCES admins(operation_id), event TEXT NOT NULL CHECK(event='FIXTURE_BOOTSTRAP'));
"""


class HostFixture:
    def __init__(self, root, manifest, keys, release_ids, installation_key, *, hook=None):
        self.root, self.manifest = Path(root), manifest
        self.keys, self.release_ids = dict(keys), frozenset(release_ids)
        self.key, self.hook = installation_key, hook

    def _public_key(self):
        raw = self.key.public_key().public_bytes_raw()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    def create(self, installation_id, host_id, organization_id):
        ids = [TypeAdapter(p.UuidV4).validate_python(v)
               for v in (installation_id, host_id, organization_id)]
        create_store(self.root, "host", HOST_SQL)
        with transaction(self.root, "host") as db:
            db.execute("INSERT INTO configuration VALUES(1,?,?,?,?)", (*ids, self._public_key()))
        return self

    def _hook(self, phase):
        return lambda name, db: checkpoint(self.hook, phase + "_" + name, db)

    def _observe(self, observe, expected=None):
        value = p.FixtureObservation.model_validate(observe())
        if not value.active:
            raise Refused("NATIVE_SESSION_INACTIVE")
        if not 0 <= value.observed_at_ns - value.authenticated_at_ns <= 60000000000:
            raise Refused("NATIVE_AUTH_DENIED")
        principal = p.canonical({"principal_ref": value.principal_ref,
                                 "authority_generation": value.authority_generation})
        if expected is not None and principal != expected:
            raise Refused("NATIVE_AUTH_DENIED")
        return principal

    def _configuration(self, db):
        value = db.execute("SELECT installation_id,host_id,organization_id,public_key "
                           "FROM configuration WHERE singleton=1").fetchone()
        if value is None or value[3] != self._public_key():
            raise FixtureCorrupt("missing deployment or changed installation key")
        return value

    def _pending(self, db):
        configuration = self._configuration(db)
        row = db.execute("SELECT operation_id,binding,claim,salt,principal FROM pending "
                         "WHERE singleton=1").fetchone()
        if row is None:
            raise FixtureCorrupt("no frozen pending operation")
        binding = p._wire(row[1], p.ConsumeBinding, p.SMALL.payload)
        if ((binding.installation_id, binding.host_id, binding.organization_id,
             binding.installation_public_key) != configuration or binding.operation_id != row[0]
                or binding.claim_sha256 != hashlib.sha256(row[2]).hexdigest()
                or binding.principal_commitment != hashlib.sha256(row[3] + row[4]).hexdigest()
                or binding.initialization_sha256 != self._initialization(binding.model_dump())):
            raise FixtureCorrupt("inconsistent pending commitment")
        return binding, *row[2:]

    @staticmethod
    def _initialization(values):
        selected = {key: values[key] for key in ("installation_id", "host_id", "organization_id",
                                                 "principal_commitment", "operation_id")}
        return hashlib.sha256(p.canonical(selected | {"initial_role": "admin"})).hexdigest()

    def _stored_commit(self, db, binding):
        receipt = db.execute(
            "SELECT operation_id,envelope FROM receipts WHERE singleton=1").fetchone()
        admin = db.execute("SELECT operation_id,principal_commitment,role FROM admins "
                           "WHERE singleton=1").fetchone()
        audit = db.execute("SELECT operation_id,event FROM audit WHERE singleton=1").fetchone()
        rows = (receipt, admin, audit)
        if all(row is None for row in rows):
            return None
        if (any(row is None for row in rows)
                or any(row[0] != binding.operation_id for row in rows)
                or admin[1:] != (binding.principal_commitment, "admin")
                or audit[1] != "FIXTURE_BOOTSTRAP"):
            raise FixtureCorrupt("partial or conflicting stored bootstrap")
        return receipt[1]

    def _request(self, binding, claim, now):
        if type(now) is not datetime or now.tzinfo is not UTC:
            raise p.ProtocolInputError()
        envelope = p._wire(claim, p.SmallEnvelope, p.SMALL.envelope)
        data = {"version": "owner-bootstrap/1", "binding": binding.model_dump(),
                "attempt_id": str(uuid4()),
                "requested_at": now.isoformat(timespec="seconds").replace("+00:00", "Z")}
        signature = self.key.sign(p.prefix("consume") + p.canonical(data))
        raw = p.canonical(data | {"owner_claim": envelope.model_dump(),
            "installation_signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode()})
        p.check_consume_request(raw, self.manifest, self.keys, self.release_ids, now)
        return raw

    def prepare(self, claim, operation_id, observe, now):
        if claim is None:
            raise Refused("OWNER_AUTHORIZATION_REQUIRED")
        operation_id = TypeAdapter(p.UuidV4).validate_python(operation_id)
        manifest = p.verify_signed(self.manifest, "manifest", self.keys, self.release_ids)
        value = p.verify_signed(claim, "claim", self.keys, frozenset(manifest.claim_key_ids))
        principal = self._observe(observe)
        def validate():
            self._observe(observe, principal)
        with transaction(self.root, "host", self._hook("prepare"), validate) as db:
            installation, host, organization, key = self._configuration(db)
            if organization != value.organization_id:
                raise Refused("OWNER_BINDING_CONFLICT")
            old = db.execute("SELECT 1 FROM pending WHERE singleton=1").fetchone()
            if old is not None:
                binding, old_claim, _, old_principal = self._pending(db)
                if (binding.operation_id != operation_id or old_claim != claim
                        or old_principal != principal):
                    raise Refused("OWNER_BINDING_CONFLICT")
                return binding
            salt = secrets.token_bytes(32)
            commitment = hashlib.sha256(salt + principal).hexdigest()
            initialization = {"installation_id": installation, "host_id": host,
                              "organization_id": organization, "principal_commitment": commitment,
                              "operation_id": operation_id}
            binding = p.ConsumeBinding.model_validate({
                "version": "owner-bootstrap/1", "operation_id": operation_id,
                "installation_id": installation, "host_id": host, "organization_id": organization,
                "claim_id": value.claim_id, "entitlement_id": value.entitlement_id,
                "generation": value.generation, "claim_sha256": hashlib.sha256(claim).hexdigest(),
                "principal_commitment": commitment,
                "initialization_sha256": self._initialization(initialization),
                "installation_public_key": key,
            })
            self._request(binding, claim, now)
            db.execute("INSERT INTO pending VALUES(1,?,?,?,?,?)", (
                operation_id, p.canonical(binding.model_dump()), claim, salt, principal))
            checkpoint(self.hook, "pending_write", db)
            return binding

    def _result(self, binding, code, committed, observe, principal):
        try:
            self._observe(observe, principal)
        except Refused as exc:
            code = exc.code
        return p.FixtureHostResult.model_validate({
            "evidence_class": "OFFLINE_CONFORMANCE", "qualification_pass": False,
            "operation_id": binding.operation_id, "code": code, "committed": committed,
        })

    def bootstrap(self, consume, observe, clock):
        with read_store(self.root, "host") as db:
            binding, claim, _, principal = self._pending(db)
            stored = self._stored_commit(db, binding)
            committed = stored is not None
        try:
            self._observe(observe, principal)
            request = self._request(binding, claim, clock())
            if committed:
                p.check_receipt(stored, request, self.manifest, self.keys,
                                self.release_ids, clock())
                return self._result(binding, "COMMITTED", True, observe, principal)
            checkpoint(self.hook, "before_dispatch", None)
            try:
                response = consume(request)  # Exactly one call, outside every host transaction.
            except (OSError, TimeoutError):
                return self._result(binding, "LICENSING_UNAVAILABLE", False, observe, principal)
            checkpoint(self.hook, "after_response", None)
            try:
                p.check_receipt(response, request, self.manifest, self.keys,
                                self.release_ids, clock())
            except p.ProtocolInputError:
                try:
                    refusal = p.parse_refusal(response)
                except p.ProtocolInputError:
                    return self._result(binding, "LICENSING_UNAVAILABLE", False, observe, principal)
                if refusal.operation_id != binding.operation_id:
                    return self._result(binding, "LICENSING_UNAVAILABLE", False, observe, principal)
                # An unsigned refusal never clears even an apparently uncommitted intent.
                return self._result(binding, refusal.code, False, observe, principal)

            def validate():
                self._observe(observe, principal)
                _, owner_claim = p.check_consume_request(
                    request, self.manifest, self.keys, self.release_ids, clock())
                if clock() < p._date(owner_claim.not_before):
                    raise Refused("OWNER_AUTHORIZATION_INVALID")
                if clock() >= p._date(owner_claim.expires_at):
                    raise Refused("OWNER_AUTHORIZATION_EXPIRED")
                p.check_receipt(response, request, self.manifest, self.keys,
                                self.release_ids, clock())

            with transaction(self.root, "host", self._hook("publish"), validate) as db:
                current, current_claim, _, current_principal = self._pending(db)
                if (current != binding or current_claim != claim or current_principal != principal):
                    raise FixtureCorrupt("pending identity changed during recovery")
                old = self._stored_commit(db, binding)
                if old is None:
                    db.execute("INSERT INTO receipts VALUES(1,?,?)",
                               (binding.operation_id, response))
                    checkpoint(self.hook, "receipt_write", db)
                    db.execute("INSERT INTO admins VALUES(1,?,?,'admin')", (
                        binding.operation_id, binding.principal_commitment))
                    checkpoint(self.hook, "admin_write", db)
                    db.execute("INSERT INTO audit VALUES(1,?,'FIXTURE_BOOTSTRAP')",
                               (binding.operation_id,))
                    checkpoint(self.hook, "audit_write", db)
                elif old != response:
                    raise FixtureCorrupt("conflicting local receipt")
            committed = True
            return self._result(binding, "COMMITTED", True, observe, principal)
        except Refused as exc:
            return self._result(binding, exc.code, committed, observe, principal)
        except p.ClockSkewError:
            return self._result(binding, "OWNER_CLOCK_SKEW", committed, observe, principal)

    def snapshot(self):
        with read_store(self.root, "host") as db:
            counts = {name: db.execute("SELECT count(*) FROM " + name).fetchone()[0]
                      for name in ("pending", "receipts", "admins", "audit")}
            row = db.execute("SELECT operation_id FROM pending WHERE singleton=1").fetchone()
            receipt = db.execute("SELECT envelope FROM receipts WHERE singleton=1").fetchone()
            return counts | {"operation_id": None if row is None else row[0],
                             "receipt_sha256": None if receipt is None else
                             hashlib.sha256(receipt[0]).hexdigest()}
