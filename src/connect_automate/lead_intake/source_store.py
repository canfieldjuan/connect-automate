"""Local administrative authority store. No source admission or application API.

The host provisions a private root and supplies deployment scope. Every operation
opens and validates that scope under one SQLite transaction owner. Public keys,
not signing secrets, are retained in immutable publication history. The OS user
is the trust boundary; this cannot detect replacement of the entire database.
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
from functools import wraps
from pathlib import Path

from pydantic import TypeAdapter

from ..entitlement import UuidV4
from .auth import SourceTrustSnapshot


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


_SCHEMA = (
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
)
_SCHEMA_VERSION = 1
_UUID = TypeAdapter(UuidV4)


def _boundary(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except SourceStoreError:
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
    """Opt-in local host authority, separate from the future source-facing boundary.

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

    def _schema(self, db: sqlite3.Connection, *, allow_empty: bool = False) -> bool:
        found = sorted(
            row[0]
            for row in db.execute(
                "SELECT sql FROM sqlite_master WHERE substr(name, 1, 7) != 'sqlite_'"
            )
        )
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if not found and version == 0 and allow_empty:
            return False
        if found != sorted(_SCHEMA) or version != _SCHEMA_VERSION:
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
    def _transaction(self, *, initialize: bool = False) -> Iterator[sqlite3.Connection]:
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
            present = self._schema(db, allow_empty=initialize)
            if present:
                self._authority(db)
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
