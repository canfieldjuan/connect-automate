"""Local authority and source custody transaction owner. No application API.

The host provisions a private root and supplies deployment scope. Every operation
opens and validates that scope under one SQLite transaction owner. Public keys,
not signing secrets, are retained in immutable publication history. The OS user
is the trust boundary. An expected incarnation detects a newly initialized
replacement, not restoration of an older copy with the same identity.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from ..entitlement import UuidV4
from .auth import SourceAuthenticationError, SourceTrustSnapshot
from .source import Digest, Instant, SourceIdentity, _canonical


class SourceStoreError(ValueError):
    """Fixed public errors never contain SQL, paths or authority data."""

    message = "lead source store rejected"

    def __init__(self):
        super().__init__(self.message)


class SourceStoreInputError(SourceStoreError):
    message = "invalid lead source store input"


class SourceStoreConflict(SourceStoreError):
    message = "lead source authority conflict"


class SourceStoreBusy(SourceStoreError):
    message = "lead source store busy"


class SourceStoreUnavailable(SourceStoreError):
    message = "lead source store unavailable"


class SourceStoreUncertain(SourceStoreError):
    message = "lead source store commit uncertain"


_SCHEMA_V4 = (
    "CREATE TABLE deployment (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
    "host_id TEXT NOT NULL, organization_id TEXT NOT NULL) STRICT",
    "CREATE TABLE authority_history (generation INTEGER PRIMARY KEY "
    "CHECK(generation BETWEEN 1 AND 2147483647), snapshot TEXT NOT NULL, "
    "sha256 TEXT NOT NULL) STRICT",
    "CREATE TRIGGER deployment_no_update BEFORE UPDATE ON deployment "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER deployment_no_delete BEFORE DELETE ON deployment "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER history_no_update BEFORE UPDATE ON authority_history "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER history_no_delete BEFORE DELETE ON authority_history "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TABLE source_receipts (admission_id TEXT PRIMARY KEY NOT NULL, "
    "organization_id TEXT NOT NULL, namespace_id TEXT NOT NULL, event_id TEXT NOT NULL, "
    "receipt TEXT NOT NULL, envelope_sha256 TEXT NOT NULL, "
    "UNIQUE(organization_id, namespace_id, event_id)) STRICT",
    "CREATE TABLE source_content (admission_id TEXT PRIMARY KEY NOT NULL REFERENCES "
    "source_receipts(admission_id) DEFERRABLE INITIALLY DEFERRED, envelope BLOB NOT NULL) STRICT",
    "CREATE TABLE source_custody (admission_id TEXT PRIMARY KEY NOT NULL REFERENCES "
    "source_receipts(admission_id) DEFERRABLE INITIALLY DEFERRED, identity TEXT NOT NULL, "
    "captured_at TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('retained','purged'))) STRICT",
    "CREATE TRIGGER receipt_no_update BEFORE UPDATE ON source_receipts "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER receipt_no_delete BEFORE DELETE ON source_receipts "
    "WHEN NOT EXISTS (SELECT 1 FROM source_retired WHERE namespace_id=OLD.namespace_id) "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER content_no_update BEFORE UPDATE ON source_content "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER custody_identity_no_update BEFORE UPDATE ON source_custody "
    "WHEN NEW.admission_id != OLD.admission_id OR NEW.identity != OLD.identity "
    "OR NEW.captured_at != OLD.captured_at OR OLD.state = 'purged' "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER custody_no_delete BEFORE DELETE ON source_custody "
    "WHEN NOT EXISTS (SELECT 1 FROM source_receipts r JOIN source_retired n "
    "ON r.namespace_id=n.namespace_id WHERE r.admission_id=OLD.admission_id) "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TABLE authority_clock_history (sequence INTEGER PRIMARY KEY, "
    "kind TEXT NOT NULL CHECK(kind IN ('sample','reconcile')), old_floor TEXT, "
    "new_floor TEXT NOT NULL, generation INTEGER NOT NULL "
    "REFERENCES authority_history(generation), "
    "operation_id TEXT UNIQUE) STRICT",
    "CREATE TRIGGER clock_no_update BEFORE UPDATE ON authority_clock_history "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER clock_no_delete BEFORE DELETE ON authority_clock_history "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TABLE source_retired (namespace_id TEXT PRIMARY KEY NOT NULL, "
    "retired_at TEXT NOT NULL) STRICT",
    "CREATE TRIGGER retired_no_update BEFORE UPDATE ON source_retired "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER retired_no_delete BEFORE DELETE ON source_retired "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TABLE source_purge_horizons (identity TEXT PRIMARY KEY NOT NULL, "
    "namespace_id TEXT NOT NULL, cutoff TEXT NOT NULL) STRICT",
    "CREATE TRIGGER horizon_monotonic BEFORE UPDATE ON source_purge_horizons "
    "WHEN NEW.identity != OLD.identity OR NEW.namespace_id != OLD.namespace_id "
    "OR NEW.cutoff <= OLD.cutoff BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER horizon_no_delete BEFORE DELETE ON source_purge_horizons "
    "WHEN NOT EXISTS (SELECT 1 FROM source_retired WHERE namespace_id=OLD.namespace_id) "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
)
_CUSTODY_SCHEMA = (
    "CREATE TABLE source_store_identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
    "incarnation TEXT NOT NULL UNIQUE) STRICT",
    "CREATE TRIGGER incarnation_no_update BEFORE UPDATE ON source_store_identity "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER incarnation_no_delete BEFORE DELETE ON source_store_identity "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TABLE source_handoffs (handoff_id TEXT PRIMARY KEY NOT NULL, "
    "incarnation TEXT NOT NULL REFERENCES source_store_identity(incarnation), "
    "host_id TEXT NOT NULL, organization_id TEXT NOT NULL, namespace_id TEXT NOT NULL, "
    "event_id TEXT NOT NULL, route_digest TEXT NOT NULL, enrolled_machine_id TEXT NOT NULL, "
    "intent TEXT NOT NULL, intent_sha256 TEXT NOT NULL, reservation_expires_at TEXT NOT NULL, "
    "capture TEXT, generation INTEGER NOT NULL CHECK(generation IN (1,2)), "
    "revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 2147483647), "
    "closed INTEGER NOT NULL CHECK(closed IN (0,1)), admission_id TEXT UNIQUE, "
    "ever_custodied INTEGER NOT NULL CHECK(ever_custodied IN (0,1)), "
    "UNIQUE(organization_id, namespace_id, event_id), "
    "CHECK(generation=closed+1 AND revision>=generation), "
    "CHECK(ever_custodied=(admission_id IS NOT NULL)), "
    "CHECK(ever_custodied=0 OR capture IS NOT NULL)) STRICT",
    "CREATE TRIGGER handoff_no_delete BEFORE DELETE ON source_handoffs "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER handoff_progress BEFORE UPDATE ON source_handoffs WHEN "
    "NEW.handoff_id != OLD.handoff_id OR NEW.incarnation != OLD.incarnation OR "
    "NEW.host_id != OLD.host_id OR NEW.organization_id != OLD.organization_id OR "
    "NEW.namespace_id != OLD.namespace_id OR NEW.event_id != OLD.event_id OR "
    "NEW.route_digest != OLD.route_digest OR NEW.enrolled_machine_id != OLD.enrolled_machine_id OR "
    "NEW.intent != OLD.intent OR NEW.intent_sha256 != OLD.intent_sha256 OR "
    "NEW.reservation_expires_at != OLD.reservation_expires_at OR "
    "(OLD.capture IS NOT NULL AND NEW.capture IS NOT OLD.capture) OR "
    "(OLD.admission_id IS NOT NULL AND NEW.admission_id IS NOT OLD.admission_id) OR "
    "NEW.closed < OLD.closed OR NEW.ever_custodied < OLD.ever_custodied OR "
    "NEW.revision <= OLD.revision BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TABLE source_handoff_operations (control_id TEXT PRIMARY KEY NOT NULL, "
    "job_id TEXT NOT NULL UNIQUE, handoff_id TEXT NOT NULL REFERENCES source_handoffs(handoff_id), "
    "kind TEXT NOT NULL CHECK(kind IN ('prepare','upload','settle')), "
    "request TEXT NOT NULL, request_sha256 TEXT NOT NULL, "
    "phase TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 2147483647), "
    "UNIQUE(handoff_id, kind), CHECK((kind='prepare' AND phase='prepared') OR "
    "(kind='upload' AND phase IN ('bound','admitted')) OR "
    "(kind='settle' AND phase='closed'))) STRICT",
    "CREATE TRIGGER operation_no_delete BEFORE DELETE ON source_handoff_operations "
    "BEGIN SELECT RAISE(ABORT, 'immutable'); END",
    "CREATE TRIGGER operation_progress BEFORE UPDATE ON source_handoff_operations WHEN "
    "NEW.control_id != OLD.control_id OR NEW.job_id != OLD.job_id OR "
    "NEW.handoff_id != OLD.handoff_id OR NEW.kind != OLD.kind OR "
    "NEW.request != OLD.request OR NEW.request_sha256 != OLD.request_sha256 OR "
    "OLD.phase != 'bound' OR NEW.phase != 'admitted' OR "
    "NEW.revision <= OLD.revision BEGIN SELECT RAISE(ABORT, 'immutable'); END",
)
_SCHEMA = _SCHEMA_V4 + _CUSTODY_SCHEMA
_SCHEMA_VERSION = 5
_UUID = TypeAdapter(UuidV4)
_DIGEST = TypeAdapter(Digest)
_INSTANT = TypeAdapter(Instant)


@dataclass(frozen=True)
class SourceMigration:
    applied: bool
    incarnation: str


@dataclass(frozen=True)
class _ReceiptMetadata:
    receipt: object
    identity: SourceIdentity
    captured_at: str
    state: str
    envelope_sha256: str


@dataclass(frozen=True)
class CustodyObservation:
    """Source facts, never an R1 result or authorization to access content."""

    handoff_id: str
    scope: object
    capture: object
    fence_generation: int
    state_revision: int
    closed: bool
    ever_custodied: bool
    receipt: object | None
    content_state: str


def _metadata_authorizer(action, first, second, _database, _trigger):
    if action == sqlite3.SQLITE_READ and first == "source_content" and second == "envelope":
        return sqlite3.SQLITE_DENY
    return (
        sqlite3.SQLITE_OK
        if action
        in (
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        )
        else sqlite3.SQLITE_DENY
    )


@dataclass(frozen=True)
class SourceClockState:
    sequence: int
    floor: datetime | None


def _utc(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("invalid UTC sample")
    return value.astimezone(UTC)


def _clock_text(value: datetime) -> str:
    return _utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _capture_at_or_before(captured_at: str, cutoff: datetime) -> bool:
    """One UTC comparison for source admission denial and authorized purge."""
    return datetime.fromisoformat(captured_at) <= cutoff


def _identity_text(value: SourceIdentity) -> str:
    value = SourceIdentity.model_validate(value)
    return json.dumps(value.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _boundary(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (SourceStoreError, SourceAuthenticationError):
            raise
        except sqlite3.Error as exc:
            failure = SourceStoreBusy if _busy(exc) else SourceStoreUnavailable
        except (OSError, ValueError, TypeError, RecursionError):
            failure = SourceStoreUnavailable
        # Raise after leaving the handler: no leaked internal exception chain.
        raise failure()

    return call


def _snapshot(value: object) -> SourceTrustSnapshot:
    try:
        if isinstance(value, SourceTrustSnapshot):
            return SourceTrustSnapshot.model_validate(value)
    except (ValueError, TypeError, RecursionError):
        pass
    raise SourceStoreInputError()


def _encode(value: SourceTrustSnapshot) -> str:
    data = value.model_dump()
    for grant in data["key_grants"]:
        grant["public_key"] = base64.b64encode(grant["public_key"]).decode("ascii")
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(raw: str) -> SourceTrustSnapshot:
    data = json.loads(raw)
    for grant in data["key_grants"]:
        grant["public_key"] = base64.b64decode(grant["public_key"], validate=True)
    value = SourceTrustSnapshot.model_validate(data)
    if _encode(value) != raw:
        raise SourceStoreUnavailable()
    return value


def _busy(error: sqlite3.Error) -> bool:
    return (getattr(error, "sqlite_errorcode", 0) & 0xFF) in (
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    )


@_boundary
def _stored_request(raw, digest, kind):
    """One decoder for immutable intent and operation fingerprints."""
    from .custody_protocol import canonical_request, parse_untrusted_request

    if kind not in ("prepare", "upload", "settle"):
        raise SourceStoreUnavailable()
    value = parse_untrusted_request(raw.encode())
    if value.operation != kind:
        raise SourceStoreUnavailable()
    if canonical_request(value).decode() != raw:
        raise SourceStoreUnavailable()
    if hashlib.sha256(raw.encode()).hexdigest() != digest:
        raise SourceStoreUnavailable()
    return value


@_boundary
def _handoff_state(capture, generation, revision, closed, admission, ever):
    """Storage state invariant, before any cross-row or caller comparisons."""
    if (
        closed not in (0, 1)
        or ever not in (0, 1)
        or generation != closed + 1
        or revision > 2147483647
        or bool(ever) != (admission is not None)
        or (ever and capture is None)
        or revision < 1 + int(capture is not None) + ever + closed
    ):
        raise SourceStoreUnavailable()
    if admission is not None:
        _UUID.validate_python(admission)


class _IdentityHistory:
    """One invariant owner for replaying stored history and accepting publication."""

    def __init__(self):
        self.keys = {}
        self.public_keys = {}
        self.policies = {}
        self.terminal = set()
        self.previous_keys = set()

    def append(self, authority: SourceTrustSnapshot) -> None:
        current = {g.key_id for g in authority.key_grants}
        self.terminal.update(self.previous_keys - current)
        for grant in authority.key_grants:
            binding = (grant.public_key, grant.namespace_id)
            if grant.key_id in self.keys and self.keys[grant.key_id] != binding:
                raise SourceStoreConflict()
            if (
                grant.public_key in self.public_keys
                and self.public_keys[grant.public_key] != grant.key_id
            ):
                raise SourceStoreConflict()
            if grant.key_id in self.terminal and grant.status == "active":
                raise SourceStoreConflict()
            self.keys[grant.key_id] = binding
            self.public_keys[grant.public_key] = grant.key_id
            if grant.status == "revoked":
                self.terminal.add(grant.key_id)
        for policy in authority.retention_policies:
            identity = (policy.policy_id, policy.policy_version)
            if identity in self.policies and self.policies[identity] != policy:
                raise SourceStoreConflict()
            self.policies[identity] = policy
        self.previous_keys = current


class SourceStore:
    """Opt-in local host authority and transaction owner for source custody.

    The root must already exist and be private, including inheritable Windows
    ACLs. No directory repair, implicit enrollment, database upgrade or caller-
    supplied trust on source admission is provided. ``initialize`` is explicit;
    ordinary reads/publications never create an absent store.
    """

    @_boundary
    def __init__(
        self,
        path: Path,
        *,
        private_root: Path,
        host_id: str,
        organization_id: str,
        busy_timeout_ms: int = 5000,
    ):
        valid = False
        try:
            host_id = _UUID.validate_python(host_id)
            organization_id = _UUID.validate_python(organization_id)
            valid = type(busy_timeout_ms) is int and 1 <= busy_timeout_ms <= 30000
        except (ValueError, TypeError):
            pass
        if not valid:
            raise SourceStoreInputError()
        self.path, self.root = Path(path), Path(private_root)
        if (
            not self.path.is_absolute()
            or not self.root.is_absolute()
            or self.path.parent != self.root
            or ".." in self.path.parts
            or self.path.name in ("", ".", "..")
        ):
            raise SourceStoreInputError()
        self.host_id, self.organization_id = host_id, organization_id
        self.busy_timeout_ms = busy_timeout_ms

    def _paths(self, *, allow_missing: bool = False) -> None:
        # Reject links in ancestors too. A same-user process remains trusted;
        # a separate user must never control the private directory namespace.
        for directory in (*reversed(self.root.parents), self.root):
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise SourceStoreUnavailable()
        if os.name == "nt":
            from ..connect_windows import validate_private_directory, validate_private_regular_file

            validate_private_directory(self.root, root=self.root)
        else:
            info = self.root.lstat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise SourceStoreUnavailable()
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = self.path.with_name(self.path.name + suffix)
            info = None
            with suppress(FileNotFoundError):
                info = path.lstat()
            if info is None:
                if suffix or allow_missing:
                    continue
                raise SourceStoreUnavailable()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SourceStoreUnavailable()
            if os.name == "nt":
                validate_private_regular_file(path, root=self.root)
            elif info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise SourceStoreUnavailable()

    def _create(self) -> None:
        self._paths(allow_missing=True)
        try:
            fd = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except FileExistsError:
            pass
        else:
            os.close(fd)
        self._paths()

    def _wait(self, db: sqlite3.Connection, sql: str, deadline: float):
        while True:
            blocked = False
            try:
                return db.execute(sql)
            except sqlite3.Error as exc:
                if not _busy(exc):
                    raise
                blocked = True
            if blocked:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SourceStoreBusy()
                time.sleep(min(0.01, remaining))

    def _schema(
        self, db: sqlite3.Connection, *, allow_empty: bool = False, allow_v4: bool = False
    ) -> bool:
        found = sorted(
            row[0]
            for row in db.execute(
                "SELECT sql FROM sqlite_master WHERE substr(name, 1, 7) != 'sqlite_'"
            )
        )
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if not found and version == 0 and allow_empty:
            return False
        expected = _SCHEMA_V4 if allow_v4 and version == 4 else _SCHEMA
        versions = (4, _SCHEMA_VERSION) if allow_v4 else (_SCHEMA_VERSION,)
        if found != sorted(expected) or version not in versions:
            raise SourceStoreUnavailable()
        return True

    def _authority(self, db: sqlite3.Connection):
        scope = list(db.execute("SELECT host_id, organization_id FROM deployment"))
        if len(scope) != 1 or tuple(scope[0]) != (self.host_id, self.organization_id):
            raise SourceStoreUnavailable()
        history = _IdentityHistory()
        last = None
        # Full replay makes incomplete/rebound authority history fail closed,
        # and preserves removed identities without a second mutable index.
        try:
            for generation, raw, digest in db.execute(
                "SELECT generation, snapshot, sha256 FROM authority_history ORDER BY generation"
            ):
                value = _decode(raw)
                if (
                    generation != (1 if last is None else last.generation + 1)
                    or value.generation != generation
                    or value.host_id != self.host_id
                    or value.organization_id != self.organization_id
                    or hashlib.sha256(raw.encode()).hexdigest() != digest
                ):
                    raise SourceStoreUnavailable()
                history.append(value)
                last = value
        except (SourceStoreConflict, KeyError, TypeError, ValueError):
            last = None
        if last is None:
            raise SourceStoreUnavailable()
        return last, history

    @contextmanager
    def _transaction(
        self, *, initialize: bool = False, migrate: bool = False
    ) -> Iterator[sqlite3.Connection]:
        if initialize:
            self._create()
        self._paths()
        db = sqlite3.connect(
            self.path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None
        )
        try:
            deadline = time.monotonic() + self.busy_timeout_ms / 1000
            self._wait(db, "PRAGMA foreign_keys=ON", deadline)
            self._wait(db, "PRAGMA synchronous=FULL", deadline)
            if self._wait(db, "PRAGMA foreign_keys", deadline).fetchone()[0] != 1:
                raise SourceStoreUnavailable()
            if self._wait(db, "PRAGMA synchronous", deadline).fetchone()[0] != 2:
                raise SourceStoreUnavailable()
            if initialize:
                # Read preflight before WAL negotiation; do not change the mode
                # of an unrelated, damaged or foreign deployment database.
                self._wait(db, "BEGIN", deadline)
                if self._schema(db, allow_empty=True):
                    self._authority(db)
                db.rollback()
                if self._wait(db, "PRAGMA journal_mode=WAL", deadline).fetchone()[0] != "wal":
                    raise SourceStoreUnavailable()
            elif self._wait(db, "PRAGMA journal_mode", deadline).fetchone()[0] != "wal":
                raise SourceStoreUnavailable()
            self._wait(db, "BEGIN IMMEDIATE", deadline)
            self._paths()
            present = self._schema(db, allow_empty=initialize, allow_v4=migrate)
            if present:
                self._authority(db)
                self._clock_history(db)
                self._lifecycle(db)
                if db.execute("PRAGMA user_version").fetchone()[0] == _SCHEMA_VERSION:
                    self._incarnation(db)
            yield db
            self._paths()
            failed = False
            try:
                db.commit()
            except sqlite3.Error:
                failed = True
            if failed:
                raise SourceStoreUncertain()
        finally:
            with suppress(sqlite3.Error):
                db.rollback()
            db.close()

    def _incarnation(self, db: sqlite3.Connection, expected: str | None = None) -> str:
        rows = db.execute("SELECT incarnation FROM source_store_identity").fetchall()
        if len(rows) != 1:
            raise SourceStoreUnavailable()
        value = _UUID.validate_python(rows[0][0])
        if expected is not None and value != expected:
            raise SourceStoreConflict()
        return value

    @contextmanager
    def _read_snapshot(self, *, expected_incarnation: str | None = None):
        db = None
        failure = None
        try:
            self._paths()
            db = sqlite3.connect(
                self.path.as_uri() + "?mode=ro", uri=True, timeout=0, isolation_level=None
            )
            deadline = time.monotonic() + self.busy_timeout_ms / 1000
            self._wait(db, "PRAGMA query_only=ON", deadline)
            self._wait(db, "BEGIN", deadline)
            # Pin the snapshot before inspecting its version or yielding it.
            self._wait(db, "SELECT sql FROM sqlite_master LIMIT 1", deadline)
            self._schema(db)
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                raise SourceStoreUnavailable()
            db.set_authorizer(_metadata_authorizer)
            self._incarnation(db, expected_incarnation)
            self._authority(db)
            self._clock_history(db)
            self._lifecycle(db)
            yield db
            self._paths()
        except SourceStoreError as exc:
            failure = type(exc)
        except sqlite3.Error as exc:
            failure = SourceStoreBusy if _busy(exc) else SourceStoreUnavailable
        except (OSError, ValueError, TypeError, RecursionError):
            failure = SourceStoreUnavailable
        finally:
            if db is not None:
                db.close()
        if failure is not None:
            # A contextmanager receives a caller's active exception. Clear it.
            try:
                raise failure() from None
            except SourceStoreError as error:
                error.__context__ = None
                raise

    def _receipt_metadata(self, db, row) -> _ReceiptMetadata:
        # Lazy import preserves the existing public receipt owner and import graph.
        from .admission import SourceReceipt

        ident, org, namespace, event, raw_receipt, envelope_hash = row
        receipt = SourceReceipt.model_validate_json(raw_receipt)
        if (
            _canonical(receipt.model_dump(by_alias=True)).decode() != raw_receipt
            or (
                receipt.admission_id,
                receipt.organization_id,
                receipt.namespace_id,
                receipt.event_id,
            )
            != (ident, org, namespace, event)
            or (receipt.host_id, receipt.organization_id) != (self.host_id, self.organization_id)
        ):
            raise SourceStoreUnavailable()
        _DIGEST.validate_python(envelope_hash)
        custody = db.execute(
            "SELECT identity, captured_at, state FROM source_custody WHERE admission_id=?",
            (ident,),
        ).fetchone()
        if custody is None:
            raise SourceStoreUnavailable()
        identity_raw, captured_at, state = custody
        identity = SourceIdentity.model_validate_json(identity_raw)
        if _identity_text(identity) != identity_raw or identity.namespace_id != namespace:
            raise SourceStoreUnavailable()
        _INSTANT.validate_python(captured_at)
        if datetime.fromisoformat(captured_at) > datetime.fromisoformat(receipt.accepted_at):
            raise SourceStoreUnavailable()
        exists = (
            db.execute("SELECT 1 FROM source_content WHERE admission_id=?", (ident,)).fetchone()
            is not None
        )
        if state not in ("retained", "purged") or exists != (state == "retained"):
            raise SourceStoreUnavailable()
        if (
            db.execute(
                "SELECT 1 FROM authority_history WHERE generation=?", (receipt.trust_generation,)
            ).fetchone()
            is None
        ):
            raise SourceStoreUnavailable()
        return _ReceiptMetadata(receipt, identity, captured_at, state, envelope_hash)

    def _validate_migration_rows(self, db):
        from .admission import SourceAdmission

        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise SourceStoreUnavailable()
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise SourceStoreUnavailable()
        for row in db.execute(
            "SELECT admission_id, organization_id, namespace_id, event_id, receipt, "
            "envelope_sha256 FROM source_receipts"
        ):
            metadata = self._receipt_metadata(db, row)
            SourceAdmission._validate_content(db, metadata)
        if db.execute("PRAGMA user_version").fetchone()[0] == _SCHEMA_VERSION:
            for (ident,) in db.execute("SELECT handoff_id FROM source_handoffs"):
                self._handoff_metadata(db, ident)

    def _handoff_metadata(self, db, ident):
        from .custody_protocol import CaptureReference

        row = db.execute("SELECT * FROM source_handoffs WHERE handoff_id=?", (ident,)).fetchone()
        if row is None:
            return None
        (
            handoff,
            incarnation,
            host,
            org,
            namespace,
            event,
            route,
            machine,
            intent_raw,
            intent_hash,
            deadline,
            capture_raw,
            generation,
            revision,
            closed,
            admission,
            ever,
        ) = row
        prepared = _stored_request(intent_raw, intent_hash, "prepare")
        scope = prepared.scope
        if (handoff, host, org, namespace, event, route, machine) != (
            prepared.handoff_id,
            scope.host_id,
            scope.organization_id,
            scope.namespace_id,
            scope.event_id,
            scope.route_digest,
            prepared.enrolled_machine_id,
        ):
            raise SourceStoreUnavailable()
        if (host, org) != (self.host_id, self.organization_id):
            raise SourceStoreUnavailable()
        if incarnation != self._incarnation(db):
            raise SourceStoreUnavailable()
        _INSTANT.validate_python(deadline)
        capture = None
        if capture_raw is not None:
            capture = CaptureReference.model_validate_json(capture_raw)
            if _canonical(capture.model_dump()).decode() != capture_raw:
                raise SourceStoreUnavailable()
            if datetime.fromisoformat(capture.captured_at) >= datetime.fromisoformat(deadline):
                raise SourceStoreUnavailable()
        _handoff_state(capture, generation, revision, closed, admission, ever)
        operations = {}
        for control, job, op_handoff, kind, raw, digest, phase, op_revision in db.execute(
            "SELECT * FROM source_handoff_operations WHERE handoff_id=?", (ident,)
        ):
            request = _stored_request(raw, digest, kind)
            # UNIQUE(handoff_id, kind) in the exact manifest owns slot uniqueness.
            if (control, job, op_handoff) != (
                request.control_id,
                request.job_id,
                request.handoff_id,
            ):
                raise SourceStoreUnavailable()
            if request.scope != scope or request.enrolled_machine_id != machine:
                raise SourceStoreUnavailable()
            if not 1 <= op_revision <= revision:
                raise SourceStoreUnavailable()
            if kind == "prepare":
                if raw != intent_raw or phase != "prepared" or op_revision != 1:
                    raise SourceStoreUnavailable()
            elif kind == "upload":
                if (
                    request.payload.capture != capture
                    or request.expected_fence_generation != 1
                    or phase != ("admitted" if ever else "bound")
                    or op_revision < 2 + ever
                ):
                    raise SourceStoreUnavailable()
            elif (
                not closed
                or phase != "closed"
                or request.expected_fence_generation not in (1, 2)
                or (request.payload.capture is not None and request.payload.capture != capture)
            ):
                raise SourceStoreUnavailable()
            operations[kind] = request
        if "prepare" not in operations or (capture is not None and "upload" not in operations):
            raise SourceStoreUnavailable()
        receipt_row = db.execute(
            "SELECT admission_id, organization_id, namespace_id, event_id, receipt, "
            "envelope_sha256 FROM source_receipts "
            "WHERE organization_id=? AND namespace_id=? AND event_id=?",
            (org, namespace, event),
        ).fetchone()
        receipt = None
        content_state = "unknown" if ever else "not_received"
        if receipt_row is not None:
            if receipt_row[0] != admission:
                raise SourceStoreUnavailable()
            metadata = self._receipt_metadata(db, receipt_row)
            receipt = metadata.receipt
            if (
                metadata.envelope_sha256 != capture.envelope_sha256
                or receipt.payload_digest != capture.payload_digest
                or metadata.identity != prepared.payload.source
                or metadata.captured_at != capture.captured_at
                or receipt.recovery_deadline != capture.recovery_deadline
                or receipt.policy_id != prepared.payload.policy_id
                or receipt.policy_version != prepared.payload.policy_version
            ):
                raise SourceStoreUnavailable()
            content_state = metadata.state
        elif admission is not None:
            retired, _ = self._lifecycle(db)
            if namespace not in retired:
                raise SourceStoreUnavailable()
        return CustodyObservation(
            handoff,
            scope,
            capture,
            generation,
            revision,
            bool(closed),
            bool(ever),
            receipt,
            content_state,
        ), prepared.enrolled_machine_id

    def _observe_custody(self, db, handoff_id, scope, machine, capture):
        result = self._handoff_metadata(db, handoff_id)
        if result is None:
            return None
        facts, recorded_machine = result
        if facts.scope != scope or recorded_machine != machine:
            raise SourceStoreConflict()
        if capture is not None and facts.capture != capture:
            raise SourceStoreConflict()
        return facts

    def _lookup_receipt(self, db, identity, event_id, payload_digest, envelope_sha256):
        row = db.execute(
            "SELECT admission_id, organization_id, namespace_id, event_id, receipt, "
            "envelope_sha256 FROM source_receipts "
            "WHERE organization_id=? AND namespace_id=? AND event_id=?",
            (self.organization_id, identity.namespace_id, event_id),
        ).fetchone()
        if row is None:
            return None
        metadata = self._receipt_metadata(db, row)
        if (
            metadata.identity != identity
            or metadata.receipt.payload_digest != payload_digest
            or metadata.envelope_sha256 != envelope_sha256
        ):
            raise SourceStoreConflict()
        return metadata

    @_boundary
    def migrate(self) -> SourceMigration:
        """Explicit privileged upgrade; never initializes or repairs invalid storage."""
        with self._transaction(migrate=True) as db:
            self._validate_migration_rows(db)
            applied = db.execute("PRAGMA user_version").fetchone()[0] == 4
            if applied:
                for statement in _CUSTODY_SCHEMA:
                    db.execute(statement)
                db.execute("INSERT INTO source_store_identity VALUES (1, ?)", (str(uuid4()),))
                db.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            self._schema(db)
            result = SourceMigration(applied, self._incarnation(db))
        return result

    @_boundary
    def read_incarnation(self) -> str:
        """Explicit host setup only; never substitute this for an expected binding."""
        with self._read_snapshot() as db:
            return self._incarnation(db)

    def _lifecycle(self, db: sqlite3.Connection):
        retired, horizons = set(), {}
        for namespace, stamp in db.execute("SELECT namespace_id, retired_at FROM source_retired"):
            if (
                _UUID.validate_python(namespace) != namespace
                or _clock_text(datetime.fromisoformat(stamp)) != stamp
            ):
                raise SourceStoreUnavailable()
            retired.add(namespace)
        for identity, namespace, stamp in db.execute(
            "SELECT identity, namespace_id, cutoff FROM source_purge_horizons"
        ):
            parsed = SourceIdentity.model_validate_json(identity)
            if (
                _identity_text(parsed) != identity
                or parsed.namespace_id != namespace
                or _clock_text(datetime.fromisoformat(stamp)) != stamp
            ):
                raise SourceStoreUnavailable()
            horizons[identity] = datetime.fromisoformat(stamp)
        return retired, horizons

    def _admission_policy(
        self, db: sqlite3.Connection, identity: SourceIdentity, captured_at: str
    ) -> None:
        retired, horizons = self._lifecycle(db)
        cutoff = horizons.get(_identity_text(identity))
        if identity.namespace_id in retired or (
            cutoff is not None and _capture_at_or_before(captured_at, cutoff)
        ):
            raise SourceAuthenticationError()

    def _clock_history(self, db: sqlite3.Connection):
        rows = list(
            db.execute(
                "SELECT sequence, kind, old_floor, new_floor, generation, operation_id "
                "FROM authority_clock_history ORDER BY sequence"
            )
        )
        generations = {r[0] for r in db.execute("SELECT generation FROM authority_history")}
        previous, prior_generation = None, 0
        operations = set()
        for expected, (seq, kind, old, new, generation, operation) in enumerate(rows, 1):
            parsed = datetime.fromisoformat(new)
            if (
                seq != expected
                or old != previous
                or _clock_text(parsed) != new
                or generation not in generations
                or generation < prior_generation
            ):
                raise SourceStoreUnavailable()
            if kind == "sample":
                if operation is not None or (old is not None and new < old):
                    raise SourceStoreUnavailable()
            elif kind == "reconcile":
                if old is None or new > old or _UUID.validate_python(operation) != operation:
                    raise SourceStoreUnavailable()
                if operation in operations:
                    raise SourceStoreUnavailable()
                operations.add(operation)
            else:
                raise SourceStoreUnavailable()
            previous, prior_generation = new, generation
        if not rows and db.execute("SELECT 1 FROM source_receipts LIMIT 1").fetchone():
            raise SourceStoreUnavailable()
        return rows

    def _check_clock(self, db: sqlite3.Connection, sample: datetime) -> datetime:
        try:
            sample = _utc(sample)
        except (ValueError, TypeError):
            sample = None
        if sample is None:
            raise SourceAuthenticationError()
        rows = self._clock_history(db)
        if rows and sample < datetime.fromisoformat(rows[-1][3]):
            raise SourceAuthenticationError()
        return sample

    def _record_clock(self, db: sqlite3.Connection, sample: datetime, generation: int) -> None:
        rows = self._clock_history(db)
        # The final sample was checked before staging the immutable receipt.
        old = rows[-1][3] if rows else None
        new = _clock_text(sample)
        if new == old:
            return
        db.execute(
            "INSERT INTO authority_clock_history VALUES (?, 'sample', ?, ?, ?, NULL)",
            (len(rows) + 1, old, new, generation),
        )

    def _scope(self, authority: SourceTrustSnapshot) -> None:
        if (authority.host_id, authority.organization_id) != (self.host_id, self.organization_id):
            raise SourceStoreConflict()

    @staticmethod
    def _insert(db: sqlite3.Connection, authority: SourceTrustSnapshot) -> None:
        raw = _encode(authority)
        db.execute(
            "INSERT INTO authority_history VALUES (?, ?, ?)",
            (authority.generation, raw, hashlib.sha256(raw.encode()).hexdigest()),
        )

    @_boundary
    def initialize(self, authority: SourceTrustSnapshot) -> bool:
        authority = _snapshot(authority)
        self._scope(authority)
        if authority.generation != 1:
            raise SourceStoreConflict()
        with self._transaction(initialize=True) as db:
            if self._schema(db, allow_empty=True):
                current, _ = self._authority(db)
                if current != authority:
                    raise SourceStoreConflict()
                return False
            for statement in _SCHEMA:
                db.execute(statement)
            db.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            db.execute(
                "INSERT INTO deployment VALUES (1, ?, ?)", (self.host_id, self.organization_id)
            )
            self._insert(db, authority)
            db.execute("INSERT INTO source_store_identity VALUES (1, ?)", (str(uuid4()),))
            self._schema(db)
            self._authority(db)
        return True

    @_boundary
    def read_authority(self) -> SourceTrustSnapshot:
        """Replay full history under BEGIN IMMEDIATE, serializing with writers."""
        with self._transaction() as db:
            current, _ = self._authority(db)
            return current

    @_boundary
    def publish_authority(
        self, authority: SourceTrustSnapshot, *, expected_generation: int
    ) -> bool:
        authority = _snapshot(authority)
        self._scope(authority)
        if type(expected_generation) is not int or not 1 <= expected_generation <= 2147483647:
            raise SourceStoreInputError()
        with self._transaction() as db:
            current, history = self._authority(db)
            retired, _ = self._lifecycle(db)
            if any(grant.namespace_id in retired for grant in authority.key_grants):
                raise SourceStoreConflict()
            # Lost-response replay preserves the original precondition; a new
            # caller may also confirm the already committed current generation.
            if current == authority and expected_generation in (
                current.generation,
                current.generation - 1,
            ):
                return False
            if (
                expected_generation != current.generation
                or authority.generation != current.generation + 1
            ):
                raise SourceStoreConflict()
            history.append(authority)
            self._insert(db, authority)
        return True


class SourceClockAdmin:
    """Privileged local host API, never a source-facing capability.

    Like authority publication, construction/access must be restricted by the
    embedding host and private OS-user boundary. This is not employee auth.
    """

    def __init__(self, store: SourceStore):
        if not isinstance(store, SourceStore):
            raise SourceStoreInputError()
        self._store = store

    @_boundary
    def read(self) -> SourceClockState:
        with self._store._transaction() as db:
            rows = self._store._clock_history(db)
            return SourceClockState(
                len(rows), datetime.fromisoformat(rows[-1][3]) if rows else None
            )

    @_boundary
    def reconcile(
        self, *, operation_id: str, expected_sequence: int, corrected_at: datetime
    ) -> SourceClockState:
        valid = False
        try:
            operation_id = _UUID.validate_python(operation_id)
            new = _clock_text(corrected_at)
            valid = type(expected_sequence) is int and expected_sequence >= 1
        except (ValueError, TypeError):
            pass
        if not valid:
            raise SourceStoreInputError()
        with self._store._transaction() as db:
            rows = self._store._clock_history(db)
            for row in rows:
                if row[5] == operation_id:
                    if row[0] != expected_sequence + 1 or row[3] != new:
                        raise SourceStoreConflict()
                    return SourceClockState(row[0], datetime.fromisoformat(row[3]))
            if len(rows) != expected_sequence or not rows or new > rows[-1][3]:
                raise SourceStoreConflict()
            authority, _ = self._store._authority(db)
            db.execute(
                "INSERT INTO authority_clock_history VALUES (?, 'reconcile', ?, ?, ?, ?)",
                (len(rows) + 1, rows[-1][3], new, authority.generation, operation_id),
            )
            return SourceClockState(len(rows) + 1, _utc(corrected_at))
