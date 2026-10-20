"""Durable workflow record, lifecycle ledger, and stage engine for the Automate host.

This is the host's own application-private store (ADR-0005 keeps app databases outside
the Connect interoperability contract). It reuses proven production-store patterns: a
``BEGIN IMMEDIATE`` writer, an append-only event log with
``UNIQUE(record_id, sequence_no)`` and ``UNIQUE(record_id, state_version)``, a
``sequence_no = 0`` bootstrap row, immutable-log triggers, and optimistic concurrency on
``state_version``.

A workflow record is free-standing: it is not anchored to a single source message, unlike
``automation_runs``. Slice 1 provided create plus a single transition primitive with
operation-key idempotency. Slice 2 generalizes that single write path into
:meth:`WorkflowStore.apply_effects`, which applies a batch of effects
(``record.transition`` and ``overlay.set``) atomically under one transaction, one ledger
event, and one compare-and-set. :meth:`WorkflowStore.transition` is now the single-effect
case of that primitive, so the ledger stays the single source of truth and every mutation
still advances ``state_version`` exactly once.

Each operation key is bound to a canonical operation name, a request fingerprint, and the
canonical effect batch: an identical replay is a no-op that returns the prior outcome, and
the same key with a changed request or changed effects is a conflict. The store is
unreleased, so the schema is extended in place rather than migrated. The host gates
admission of any mutation behind ``AutomateHost.require_license``.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from ..entitlement import UuidV4
from ..lead_intake.receipts import ReceiptReference
from .events import (
    Event,
    EventBindingError,
    EventConflict,
    EventInputError,
    SourceBinding,
    canonical_event,
    lead_deployment_scope,
    parse_event,
)
from .events import (
    occurrence as event_occurrence,
)

CREATE_OPERATION_NAME = "create"

# The effect kinds the executor can apply. Kept as module constants so the store, the
# definition model, and the engine name the same closed vocabulary.
RECORD_TRANSITION = "record.transition"
OVERLAY_SET = "overlay.set"

# The maximum number of effects the store applies in one batch. The definition model
# imports this so its per-definition cap and the store primitive's cap stay in lockstep,
# and a direct apply_effects caller cannot exceed it.
MAX_EFFECTS_PER_BATCH = 8

# The maximum size of a canonical effect batch. Workflow-originated batches are already
# bounded by the 16 KiB canonical-definition limit; this bounds a direct apply_effects
# caller so a single overlay value cannot persist an unbounded payload in the immutable
# event and the overlay projection.
MAX_EFFECT_BATCH_BYTES = 16 * 1024

# The maximum size of a canonical action request or result persisted in the action outbox.
MAX_ACTION_BYTES = 16 * 1024

# The maximum number of actions one decision may emit. A definition's action list and this
# store bound are kept in lockstep (the definition model imports this), so a direct
# apply_effects caller cannot exceed it either.
MAX_ACTIONS_PER_DECISION = 8

# The reserved namespace for a decision-emitted action's dedupe key: the committed ledger
# event id and the action's index within the decision. Owned by the store so a decision's
# actions are admitted with a key no external caller of the outbox can collide with.
ACTION_DEDUPE_PREFIX = "pack.action:"

# Action outbox statuses. An action is admitted 'pending' before its side effect runs, then
# settled to a terminal state. A 'pending' row surviving a crash is durable intent to be
# re-dispatched (the runtime resumes it after the decision and a startup sweep reconciles it),
# not a silent re-dispatch.
ACTION_PENDING = "pending"
ACTION_SETTLED = "settled"
ACTION_FAILED = "failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_records (
    record_id TEXT PRIMARY KEY CHECK (length(record_id) = 36),
    workflow TEXT NOT NULL CHECK (workflow <> ''),
    pack_id TEXT CHECK (pack_id IS NULL OR pack_id <> ''),
    pack_version INTEGER CHECK (pack_version IS NULL OR pack_version >= 1),
    stage TEXT NOT NULL CHECK (stage <> ''),
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- A pack-bound record carries both its pack identity and version, or neither (a
    -- bare-workflow record); a version without an identity is meaningless.
    CHECK ((pack_id IS NULL) = (pack_version IS NULL))
);
CREATE TABLE IF NOT EXISTS workflow_events (
    event_id TEXT PRIMARY KEY CHECK (length(event_id) = 36),
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 0),
    previous_stage TEXT CHECK (previous_stage IS NULL OR previous_stage <> ''),
    next_stage TEXT NOT NULL CHECK (next_stage <> ''),
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    operation_name TEXT NOT NULL CHECK (operation_name <> ''),
    operation_key TEXT CHECK (operation_key IS NULL OR operation_key <> ''),
    request_fingerprint TEXT CHECK (
        request_fingerprint IS NULL OR length(request_fingerprint) = 64
    ),
    effects TEXT CHECK (effects IS NULL OR effects <> ''),
    created_at TEXT NOT NULL,
    UNIQUE (record_id, sequence_no),
    UNIQUE (record_id, state_version),
    CHECK (
        (previous_stage IS NULL AND sequence_no = 0 AND state_version = 1
            AND operation_name = 'create' AND operation_key IS NULL AND effects IS NULL)
        OR (previous_stage IS NOT NULL AND sequence_no >= 1
            AND state_version = sequence_no + 1 AND effects IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_workflow_events_record
    ON workflow_events(record_id, sequence_no);
CREATE TABLE IF NOT EXISTS workflow_operations (
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    operation_key TEXT NOT NULL CHECK (operation_key <> ''),
    operation_name TEXT NOT NULL CHECK (operation_name <> ''),
    request_fingerprint TEXT NOT NULL CHECK (length(request_fingerprint) = 64),
    -- NULL event_id records a no-match: the decision was made under this key but no
    -- definition applied, so no event exists. Reserving the key keeps a retry idempotent
    -- across later stage changes instead of re-applying.
    event_id TEXT CHECK (event_id IS NULL OR length(event_id) = 36),
    created_at TEXT NOT NULL,
    PRIMARY KEY (record_id, operation_key)
);
CREATE TABLE IF NOT EXISTS workflow_overlays (
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    key TEXT NOT NULL CHECK (key <> ''),
    value_json TEXT NOT NULL,
    state_version INTEGER NOT NULL CHECK (state_version >= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (record_id, key)
);
CREATE TABLE IF NOT EXISTS workflow_actions (
    action_id TEXT PRIMARY KEY CHECK (length(action_id) = 36),
    record_id TEXT NOT NULL CHECK (record_id <> ''),
    -- A caller-minted idempotency key for the action's intent, unique per record (not
    -- globally) so the same key on two records is two independent actions. Modeled on the
    -- outbound outbox's dedupe_key but scoped to the owning record.
    dedupe_key TEXT NOT NULL CHECK (dedupe_key <> ''),
    kind TEXT NOT NULL CHECK (kind <> ''),
    request TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'settled', 'failed')),
    result TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (record_id, dedupe_key),
    CHECK (
        (status = 'pending' AND result IS NULL)
        OR (status = 'settled' AND result IS NOT NULL)
        OR (status = 'failed')
    )
);
CREATE INDEX IF NOT EXISTS idx_workflow_actions_record
    ON workflow_actions(record_id, created_at);
CREATE TABLE IF NOT EXISTS workflow_binding_sets (
    subject TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    bindings_json TEXT NOT NULL,
    PRIMARY KEY (subject, pack_id)
);
CREATE TABLE IF NOT EXISTS workflow_source_bindings (
    subject TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    binding TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    policy TEXT NOT NULL,
    PRIMARY KEY (subject, pack_id, binding),
    UNIQUE (subject, pack_id, source_id),
    FOREIGN KEY (subject, pack_id) REFERENCES workflow_binding_sets(subject, pack_id)
);
CREATE TABLE IF NOT EXISTS workflow_event_receipts (
    subject TEXT NOT NULL,
    pack_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    occurrence TEXT NOT NULL CHECK (occurrence <> ''),
    pack_version INTEGER NOT NULL CHECK (pack_version >= 1),
    binding TEXT NOT NULL,
    fingerprint TEXT NOT NULL CHECK (length(fingerprint) = 64),
    payload TEXT NOT NULL,
    record_id TEXT REFERENCES workflow_records(record_id),
    event_id TEXT REFERENCES workflow_events(event_id),
    created_at TEXT NOT NULL,
    CHECK ((record_id IS NULL) = (event_id IS NULL)),
    PRIMARY KEY (subject, pack_id, source_id, source_kind, occurrence),
    FOREIGN KEY (subject, pack_id, binding)
        REFERENCES workflow_source_bindings(subject, pack_id, binding)
);
CREATE TRIGGER IF NOT EXISTS workflow_receipts_no_update
BEFORE UPDATE ON workflow_event_receipts BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
CREATE TRIGGER IF NOT EXISTS workflow_receipts_no_delete
BEFORE DELETE ON workflow_event_receipts BEGIN SELECT RAISE(ABORT, 'immutable receipt'); END;
CREATE TRIGGER IF NOT EXISTS workflow_bindings_no_update
BEFORE UPDATE ON workflow_source_bindings BEGIN SELECT RAISE(ABORT, 'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS workflow_bindings_no_delete
BEFORE DELETE ON workflow_source_bindings BEGIN SELECT RAISE(ABORT, 'immutable source'); END;
CREATE TRIGGER IF NOT EXISTS workflow_binding_sets_no_update
BEFORE UPDATE ON workflow_binding_sets BEGIN SELECT RAISE(ABORT, 'immutable binding set'); END;
CREATE TRIGGER IF NOT EXISTS workflow_binding_sets_no_delete
BEFORE DELETE ON workflow_binding_sets BEGIN SELECT RAISE(ABORT, 'immutable binding set'); END;
CREATE TRIGGER IF NOT EXISTS workflow_events_no_update
BEFORE UPDATE ON workflow_events
BEGIN
    SELECT RAISE(ABORT, 'workflow_events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS workflow_events_no_delete
BEFORE DELETE ON workflow_events
BEGIN
    SELECT RAISE(ABORT, 'workflow_events are immutable');
END;
"""

_EVENT_TABLES = frozenset(
    {"workflow_binding_sets", "workflow_source_bindings", "workflow_event_receipts"}
)


class WorkflowStoreError(RuntimeError):
    """Base class for workflow store errors."""


def _event_schema_shape(db, expected_names=frozenset()):
    objects = tuple(
        sorted(
            (kind, name, table, " ".join(sql.split()) if sql else None)
            for kind, name, table, sql in db.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master"
            )
            if name in _EVENT_TABLES or table in _EVENT_TABLES or name in expected_names
        )
    )
    tables = []
    for table in sorted(_EVENT_TABLES):
        columns = tuple(tuple(row) for row in db.execute(f'PRAGMA table_info("{table}")'))
        foreign_keys = tuple(
            sorted(tuple(row) for row in db.execute(f'PRAGMA foreign_key_list("{table}")'))
        )
        indexes = []
        for row in db.execute(f'PRAGMA index_list("{table}")'):
            name = row[1]
            # Index names are SQLite schema data, so bind them as a table-valued pragma.
            keys = tuple(
                tuple(item) for item in db.execute("SELECT * FROM pragma_index_info(?)", (name,))
            )
            indexes.append((row[2], row[3], row[4], keys))
        tables.append((table, columns, foreign_keys, tuple(sorted(indexes))))
    return objects, tuple(tables)


@lru_cache(maxsize=1)
def _expected_event_schema():
    # Derive the shape from the one DDL owner, using this SQLite version's own metadata.
    with contextlib.closing(sqlite3.connect(":memory:")) as reference:
        reference.executescript(_SCHEMA)
        return _event_schema_shape(reference)


def _verify_event_schema(db, *, allow_absent=False):
    expected = _expected_event_schema()
    actual = _event_schema_shape(db, frozenset(item[1] for item in expected[0]))
    if allow_absent and not actual[0]:
        return
    if actual != expected:
        raise WorkflowStoreError("incompatible event schema")


def _read_authorizer(action, _first, _second, _database, _trigger):
    # Internal SELECTs only: in particular, ATTACH can create another file even
    # when main is mode=ro, and COMMIT would discard the validated read snapshot.
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


def _schema_statements():
    statement = ""
    for line in _SCHEMA.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            yield statement
            statement = ""
    if statement.strip():
        raise WorkflowStoreError("incomplete workflow schema")


class _EventVersionConflict(WorkflowStoreError):
    """Origin signal translated to the existing pack-version error by the engine."""


class UnknownRecord(WorkflowStoreError):
    """Raised when a mutation names a record that does not exist."""


class InvalidEffect(WorkflowStoreError):
    """Raised when an effect batch is structurally invalid."""


class StaleRecord(WorkflowStoreError):
    """Raised when the caller's expected state_version does not match the record.

    This is the optimistic-concurrency (compare-and-set) conflict.
    """

    def __init__(self, *, expected: int, actual: int):
        super().__init__(f"record is at state_version {actual}, not the expected {expected}")
        self.expected = expected
        self.actual = actual


class OperationConflict(WorkflowStoreError):
    """Raised when an operation key is reused with a different name, request, or effects.

    The portal's equivalent is a 409: a key is rotated for changed intent, so a mismatched
    fingerprint or effect batch must be refused rather than silently replaying the earlier
    outcome.
    """

    def __init__(self, *, operation_key: str):
        super().__init__(
            f"operation key {operation_key!r} was already used with a different "
            "operation, request, or effect batch"
        )
        self.operation_key = operation_key


class ActionConflict(WorkflowStoreError):
    """Raised when an action dedupe key is reused with a different kind or request."""

    def __init__(self, *, dedupe_key: str):
        super().__init__(
            f"action dedupe key {dedupe_key!r} was already used with a different intent"
        )
        self.dedupe_key = dedupe_key


class UnresolvedAction(WorkflowStoreError):
    """Raised when an action dedupe key is still pending from an earlier, unsettled dispatch.

    Its side effect may or may not have run (accept-then-crash), so the store refuses to
    silently re-dispatch. Reconciling a pending action is deferred hardening.
    """

    def __init__(self, *, dedupe_key: str):
        super().__init__(f"action {dedupe_key!r} is pending from an unsettled dispatch")
        self.dedupe_key = dedupe_key


@dataclass(frozen=True)
class RecordView:
    record_id: str
    workflow: str
    stage: str
    state_version: int
    created_at: str
    updated_at: str
    # The identity of the signed pack that created this record, when it was created through a
    # PackRuntime. None for a record created directly against a bare workflow (the pre-pack
    # slices). Write-once at creation, so an ownership check that reads it is race-free.
    pack_id: str | None = None
    # The version of that pack, frozen at creation alongside pack_id (both-or-neither). A
    # record stays on the version it began under, so in-flight work is not driven by an
    # upgraded pack; also write-once, so the freeze check that reads it is race-free.
    pack_version: int | None = None


@dataclass(frozen=True)
class TransitionOutcome:
    record: RecordView
    event_id: str
    # False when an idempotent replay returned the prior outcome without a new event.
    applied: bool


@dataclass(frozen=True)
class EventAdmission:
    matched: bool
    applied: bool
    record: RecordView | None
    event_id: str | None


@dataclass(frozen=True)
class SourceEventReceipt:
    """Historical workflow metadata, never source submission or content authority."""

    source_receipt: ReceiptReference
    outcome: EventAdmission


@dataclass(frozen=True)
class _EventReceipt:
    event: Event
    outcome: EventAdmission


@dataclass(frozen=True)
class _SourceReceiptQuery:
    source: SourceBinding
    payload_digest: str


_SOURCE_EVENT_ID = TypeAdapter(UuidV4)


@dataclass(frozen=True)
class OperationReplay:
    """The recorded outcome of a prior operation, for replay-before-matching lookups.

    For a matched operation, ``record`` reconstructs the state it produced (not the current
    projection), so a replay after the record has advanced still reports the stage and
    version this operation yielded, and ``event_id`` is its event. For a recorded no-match,
    ``matched`` is False, ``event_id`` is None, and ``record`` is the current projection.
    """

    record: RecordView
    event_id: str | None
    operation_name: str
    request_fingerprint: str
    matched: bool


@dataclass(frozen=True)
class ActionView:
    action_id: str
    record_id: str
    dedupe_key: str
    kind: str
    request: dict[str, object]
    status: str
    result: dict[str, object] | None
    last_error: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ActionAdmission:
    """The outcome of admitting an action to the outbox.

    ``admitted`` is True only when this call inserted a fresh pending row and the caller
    should now run the side effect. When it is False the dedupe key already reached a
    terminal state and ``view`` carries that recorded outcome to replay.
    """

    view: ActionView
    admitted: bool


def request_fingerprint(request: Mapping[str, object]) -> str:
    """A stable SHA-256 over the canonical JSON of a request payload.

    Keys are sorted and separators are fixed so the same logical request always yields the
    same fingerprint, and any change to the request yields a different one.
    """
    if not isinstance(request, Mapping):
        raise ValueError("request must be a mapping")
    canonical = json.dumps(dict(request), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event_operation_key(identity: tuple[str, str, str, str, str]) -> str:
    """Bind both receipt replay and creation to the same intake operation."""
    canonical = json.dumps(identity, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "pack.event:" + hashlib.sha256(canonical).hexdigest()


def _stored_event_payload(prior: sqlite3.Row, source_kind: str, occurrence: str) -> Event:
    """Validate stored bytes at their owner, before either replay consumer sees them."""
    try:
        raw = prior["payload"].encode("utf-8")
        parsed = parse_event(raw)
        if (
            canonical_event(parsed) == raw
            and hashlib.sha256(raw).hexdigest() == prior["fingerprint"]
            and parsed.source_kind == source_kind
            and event_occurrence(parsed) == occurrence
        ):
            return parsed
    except (ValueError, TypeError, AttributeError, RecursionError):
        pass
    raise WorkflowStoreError("invalid event receipt payload")


def _validate_event_lookup(identity, binding, pack_version, expected_payload_digest) -> None:
    if (
        any(not isinstance(value, str) or not value for value in (*identity, binding))
        or type(pack_version) is not int
        or pack_version < 1
        or not isinstance(expected_payload_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_payload_digest) is None
    ):
        raise EventInputError()


def _read_event_receipt(
    db: sqlite3.Connection,
    *,
    identity: tuple[str, str, str, str, str],
    pack_version: int,
    binding: str,
    fingerprint: str | _SourceReceiptQuery,
) -> _EventReceipt | None:
    """Single owner for binding, receipt integrity and historical replay checks."""
    subject, pack_id, source_id, source_kind, occurrence = identity
    owner = db.execute(
        (
            "SELECT source_id, source_kind FROM workflow_source_bindings WHERE "
            "subject = ? AND pack_id = ? AND binding = ?"
        ),
        (subject, pack_id, binding),
    ).fetchone()
    if owner is None or (owner["source_id"], owner["source_kind"]) != (
        source_id,
        source_kind,
    ):
        raise EventBindingError()
    if isinstance(fingerprint, _SourceReceiptQuery):
        # Reuse the registration owner's persisted policy/snapshot/deployment checks.
        # This runs in the caller's read snapshot and never opens a writer.
        WorkflowStore._check_lead_deployment(
            db, [{**fingerprint.source.model_dump(), "policy": {"schema_version": "1.0"}}]
        )
    prior = db.execute(
        (
            "SELECT * FROM workflow_event_receipts WHERE subject = ? AND pack_id = ? "
            "AND source_id = ? AND source_kind = ? AND occurrence = ?"
        ),
        identity,
    ).fetchone()
    if prior is None:
        return None
    if prior["pack_version"] != pack_version:
        raise _EventVersionConflict("event belongs to another pack revision")
    if prior["binding"] != binding or (
        not isinstance(fingerprint, _SourceReceiptQuery) and prior["fingerprint"] != fingerprint
    ):
        raise EventConflict()
    parsed = _stored_event_payload(prior, source_kind, occurrence)
    if isinstance(fingerprint, _SourceReceiptQuery):
        # The shared parser above has already enforced the lead event kind.
        reference = parsed.source_receipt
        scope = lead_deployment_scope(fingerprint.source.scope, fingerprint.source.source_id)
        if (reference.host_id, reference.organization_id, reference.namespace_id) != (
            scope.host_id,
            scope.organization_id,
            scope.namespace_id,
        ):
            raise WorkflowStoreError("invalid source receipt scope")
        if reference.payload_digest != fingerprint.payload_digest:
            raise EventConflict()
    payload = parsed.model_dump(mode="json")
    if (prior["record_id"] is None) != (prior["event_id"] is None):
        raise WorkflowStoreError("invalid event receipt ownership")
    if prior["record_id"] is None:
        return _EventReceipt(parsed, EventAdmission(False, False, None, None))
    record = db.execute(
        "SELECT * FROM workflow_records WHERE record_id = ?", (prior["record_id"],)
    ).fetchone()
    event = db.execute(
        "SELECT * FROM workflow_events WHERE event_id = ?", (prior["event_id"],)
    ).fetchone()
    if (
        record is None
        or event is None
        or event["record_id"] != prior["record_id"]
        or event["operation_key"] != _event_operation_key(identity)
        or event["operation_name"] != source_kind
        or event["request_fingerprint"] != request_fingerprint(payload)
        or record["pack_id"] != pack_id
        or record["pack_version"] != pack_version
    ):
        raise WorkflowStoreError("invalid event receipt ownership")
    return _EventReceipt(
        parsed, EventAdmission(True, False, _replay_view(record, event), prior["event_id"])
    )


def _normalize_effects(effects: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Validate an effect batch and return it in a canonical, minimal form.

    Structural validation lives here so the store is a self-contained primitive: the
    definition model validates the same rules semantically, but the store never trusts its
    caller. A batch must be non-empty, carry at most one ``record.transition``, and use
    distinct ``overlay.set`` keys.
    """
    if isinstance(effects, (str, bytes, Mapping)) or not isinstance(effects, Sequence):
        raise InvalidEffect("effects must be a sequence of effect objects")
    normalized: list[dict[str, object]] = []
    seen_overlay_keys: set[str] = set()
    transition_count = 0
    for raw in effects:
        if not isinstance(raw, Mapping):
            raise InvalidEffect("each effect must be an object")
        kind = raw.get("kind")
        if kind == RECORD_TRANSITION:
            # An exact key set: an unrecognized member (e.g. an "overlay.set" key smuggled
            # onto a transition) is changed or malformed intent and must fail closed rather
            # than be silently dropped while the operation keeps the same identity.
            if set(raw.keys()) != {"kind", "to_stage"}:
                raise InvalidEffect("record.transition accepts only 'kind' and 'to_stage'")
            transition_count += 1
            to_stage = raw.get("to_stage")
            if not isinstance(to_stage, str) or not to_stage:
                raise InvalidEffect("record.transition requires a non-empty to_stage")
            normalized.append({"kind": RECORD_TRANSITION, "to_stage": to_stage})
        elif kind == OVERLAY_SET:
            if set(raw.keys()) != {"kind", "key", "value"}:
                raise InvalidEffect("overlay.set accepts only 'kind', 'key', and 'value'")
            key = raw.get("key")
            if not isinstance(key, str) or not key:
                raise InvalidEffect("overlay.set requires a non-empty key")
            if key in seen_overlay_keys:
                raise InvalidEffect(f"overlay.set key {key!r} is repeated in one batch")
            seen_overlay_keys.add(key)
            value = raw.get("value")
            # bool is a subclass of int, so this admits str, int, and bool while rejecting
            # floats and any other type; overlay values are simple scalars.
            if not isinstance(value, (str, int)):
                raise InvalidEffect("overlay.set value must be a string, integer, or boolean")
            normalized.append({"kind": OVERLAY_SET, "key": key, "value": value})
        else:
            raise InvalidEffect(f"unknown effect kind {kind!r}")
    if not normalized:
        raise InvalidEffect("an effect batch must contain at least one effect")
    if transition_count > 1:
        raise InvalidEffect("an effect batch may contain at most one record.transition")
    if len(normalized) > MAX_EFFECTS_PER_BATCH:
        raise InvalidEffect(f"an effect batch may contain at most {MAX_EFFECTS_PER_BATCH} effects")
    return normalized


def _canonical_effects(normalized: Sequence[Mapping[str, object]]) -> str:
    """Canonical JSON for the effect batch, stored on the event and compared on replay."""
    return json.dumps(list(normalized), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_operation_identity(operation_key: str, operation_name: str) -> None:
    """Reject a non-string or empty operation key or name before it is persisted.

    Both are stored as TEXT under constraints that forbid the empty string, and SQLite would
    silently coerce a non-string (so a retry with int ``7`` would not match stored ``"7"``);
    validating here turns malformed input (for example an empty decision name) into a domain
    ValueError at the primitive boundary rather than a raw sqlite3.IntegrityError.
    """
    if not isinstance(operation_key, str) or not operation_key:
        raise ValueError("operation_key must be a non-empty string")
    if not isinstance(operation_name, str) or not operation_name:
        raise ValueError("operation_name must be a non-empty string")


def _new_id() -> str:
    return str(uuid.uuid4())


def _restrict(path: Path, mode: int) -> None:
    """Best-effort chmod; tolerated where the platform cannot honor POSIX modes."""
    with contextlib.suppress(OSError, NotImplementedError):
        path.chmod(mode)


def _record_view(row: sqlite3.Row) -> RecordView:
    return RecordView(
        record_id=row["record_id"],
        workflow=row["workflow"],
        stage=row["stage"],
        state_version=row["state_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        pack_id=row["pack_id"],
        pack_version=row["pack_version"],
    )


def _replay_view(record: sqlite3.Row, event: sqlite3.Row) -> RecordView:
    """Reconstruct the record state a prior operation produced from its event row."""
    return RecordView(
        record_id=record["record_id"],
        workflow=record["workflow"],
        stage=event["next_stage"],
        state_version=event["state_version"],
        created_at=record["created_at"],
        updated_at=event["created_at"],
        pack_id=record["pack_id"],
        pack_version=record["pack_version"],
    )


def _action_view(row: sqlite3.Row) -> ActionView:
    return ActionView(
        action_id=row["action_id"],
        record_id=row["record_id"],
        dedupe_key=row["dedupe_key"],
        kind=row["kind"],
        request=json.loads(row["request"]),
        status=row["status"],
        result=json.loads(row["result"]) if row["result"] is not None else None,
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _safe_error_text(error: str, *, limit: int = 500) -> str:
    """Truncate adapter error text, then make it safe to persist.

    ``fail_action`` is a fail-closed terminalizer: it must always be able to record a failure.
    But its ``error`` comes from ``str(exc)``, which can carry lone surrogates (for example an
    exception message built from bytes decoded with ``errors="surrogateescape"``). SQLite
    binds text as UTF-8, and a lone surrogate raises ``UnicodeEncodeError`` mid-statement,
    which would abort ``fail_action`` and leave the action stuck ``pending`` -- the opposite of
    terminalizing it.

    Truncate to ``limit`` code points *before* transcoding, so a pathologically large provider
    error cannot allocate a full-size bytes plus str on this failure path (which would defeat
    the terminalizer just as surely). Slicing a Python string is by code point and never splits
    a character, so it is safe to slice first; the UTF-8 round trip with ``errors="replace"``
    then maps every unencodable code point to U+FFFD (a 1:1 code-point substitution, so the
    result stays within ``limit``).
    """
    return error[:limit].encode("utf-8", "replace").decode("utf-8")


def _reject_non_string_keys(
    value: object, *, label: str, _path: frozenset[int] = frozenset()
) -> None:
    """Recursively reject mappings whose keys are not strings, and circular references.

    ``json.dumps`` silently coerces a non-string object key to its string form, so
    ``{1: "a"}`` and ``{"1": "a"}`` would serialize identically (colliding the dedupe
    identity) and ``{1: "a", "1": "b"}`` would persist duplicate ``"1"`` members and read
    back with one value dropped. Reject non-string keys before serialization so a payload's
    canonical bytes are a faithful, injective encoding of its logical content.

    ``json.dumps`` detects a circular reference itself (a clean ``ValueError``), but this
    walk runs first, so it must detect the cycle too, via the set of container ids on the
    current recursion path; otherwise a self-referential payload recurses until it exhausts
    the stack (see the ``RecursionError`` catch in :func:`_canonical_payload`).
    """
    if isinstance(value, Mapping):
        if id(value) in _path:
            raise InvalidEffect(f"action {label} contains a circular reference")
        deeper = _path | {id(value)}
        for key, sub in value.items():
            if not isinstance(key, str):
                raise InvalidEffect(f"action {label} contains a non-string object key {key!r}")
            _reject_non_string_keys(sub, label=label, _path=deeper)
    elif isinstance(value, (list, tuple)):
        if id(value) in _path:
            raise InvalidEffect(f"action {label} contains a circular reference")
        deeper = _path | {id(value)}
        for item in value:
            _reject_non_string_keys(item, label=label, _path=deeper)


def _canonical_payload(payload: Mapping[str, object], *, label: str) -> str:
    """Canonical JSON for an action request or result, size-bounded and fail-closed.

    Rejects a non-mapping payload and a value that cannot be serialized within the size
    bound, so the action outbox never persists an unbounded or unencodable payload.
    """
    if not isinstance(payload, Mapping):
        raise InvalidEffect(f"action {label} must be a mapping")
    try:
        _reject_non_string_keys(payload, label=label)
        canonical = json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        size = len(canonical.encode("utf-8"))
    except InvalidEffect:
        # Deliberate rejections from the walk (non-string key, circular reference) carry their
        # own message; let them through unchanged.
        raise
    except Exception as exc:
        # This is a trust boundary: canonicalizing a caller- or adapter-supplied payload must
        # yield canonical bytes or InvalidEffect, never leak. Any other failure of the walk or
        # of json.dumps over that data is such a leak -- a non-JSON value (TypeError), a
        # non-portable number or unencodable string (ValueError), a payload too deeply nested
        # (RecursionError), a mapping that misbehaves while being traversed (RuntimeError), and
        # so on. Terminalize the whole class as InvalidEffect so the runner records a terminal
        # failure rather than leaving the action stuck pending.
        raise InvalidEffect(f"action {label} could not be canonicalized: {exc}") from exc
    if size > MAX_ACTION_BYTES:
        raise InvalidEffect(f"action {label} exceeds {MAX_ACTION_BYTES} bytes")
    return canonical


def _normalize_action_intents(
    actions: Sequence[Mapping[str, object]] | None,
    *,
    allowed_kinds: frozenset[str] | None = None,
) -> list[tuple[str, str]]:
    """Validate a decision's action intents and canonicalize each request.

    Returns ``(kind, canonical_request)`` pairs to admit alongside the decision. Fails closed
    (``InvalidEffect``) on a malformed batch so an unserializable, oversized, over-count, or
    unsupported-kind intent is rejected before any write, exactly like the effect batch. Only
    ``None`` means "no actions": a non-``None`` non-sequence (a mapping, ``str``, ``bytes``)
    is a malformed batch and is rejected rather than silently dropped. When ``allowed_kinds``
    is given, each kind must be in it, so a typo or unsupported kind cannot commit a row that
    could never be delivered.
    """
    if actions is None:
        return []
    if isinstance(actions, str | bytes) or not isinstance(actions, Sequence):
        raise InvalidEffect("actions must be a sequence")
    if len(actions) > MAX_ACTIONS_PER_DECISION:
        raise InvalidEffect(f"a decision may emit at most {MAX_ACTIONS_PER_DECISION} actions")
    intents: list[tuple[str, str]] = []
    for action in actions:
        if not isinstance(action, Mapping):
            raise InvalidEffect("each action intent must be a mapping")
        if not set(action.keys()) <= {"kind", "request"}:
            # Exact key set, like the effect normalizer: an unknown member (a typo such as
            # "requests") must fail rather than be ignored while a missing request silently
            # defaults to {}.
            raise InvalidEffect("an action intent may contain only 'kind' and 'request'")
        kind = action.get("kind")
        request = action.get("request", {})
        if not isinstance(kind, str) or not kind:
            raise InvalidEffect("action kind must be a non-empty string")
        if allowed_kinds is not None and kind not in allowed_kinds:
            raise InvalidEffect(f"unsupported action kind {kind!r}")
        if not isinstance(request, Mapping):
            raise InvalidEffect("action request must be a mapping")
        intents.append((kind, _canonical_payload(request, label="action request")))
    return intents


class WorkflowStore:
    """SQLite-backed durable store for workflow records and their lifecycle ledger."""

    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    @contextmanager
    def read_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a validated, consistent SELECT snapshot of an existing store.

        This is an internal query primitive, not a license/organization boundary
        or a sandbox for hostile Python. Keep URI mode=ro (not immutable) so live
        WAL commits are visible. No initialization, repair or checkpoint occurs.
        """
        connection = None
        try:
            connection = sqlite3.connect(
                self.path.absolute().as_uri() + "?mode=ro", uri=True, isolation_level=None
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            # This first read pins the snapshot before the caller sees it.
            _verify_event_schema(connection)
            connection.set_authorizer(_read_authorizer)
            yield connection
            return
        except sqlite3.Error:
            pass
        finally:
            if connection is not None:
                connection.close()
        # contextmanager throws a caller's SQL error into this generator while
        # that exception is still active. Detach it explicitly before a bare
        # re-raise; leaving the local handler alone does not remove that context.
        try:
            raise WorkflowStoreError("workflow store read unavailable") from None
        except WorkflowStoreError as error:
            error.__context__ = None
            raise

    def initialize(self) -> None:
        # mode=0o700 applies only when mkdir creates the directory, so a dedicated parent
        # is created private and an existing, possibly shared, parent is left untouched.
        # SQLite otherwise creates the database under the process umask (often 0644), so
        # restrict the database and its WAL sidecars to the owner: this ledger holds
        # private record names and stages, and 0600 files protect it even under a shared
        # parent without changing that parent's permissions.
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connection() as db:
            # WAL negotiation cannot run in a transaction, and SQLite may skip its
            # busy handler during the required lock upgrade. Own this phase's retry
            # budget here, without multiplying it by a native wait on each attempt.
            busy_timeout_ms = db.execute("PRAGMA busy_timeout").fetchone()[0]
            deadline = time.monotonic() + busy_timeout_ms / 1000
            last_busy: sqlite3.OperationalError | None = None
            db.execute("PRAGMA busy_timeout=0")
            try:
                while True:
                    if last_busy is not None and time.monotonic() >= deadline:
                        raise WorkflowStoreError(
                            "workflow store initialization busy"
                        ) from last_busy
                    try:
                        mode = db.execute("PRAGMA journal_mode=WAL").fetchone()
                    except sqlite3.OperationalError as exc:
                        code = getattr(exc, "sqlite_errorcode", None)
                        if code is None or (code & 0xFF) not in (
                            sqlite3.SQLITE_BUSY,
                            sqlite3.SQLITE_LOCKED,
                        ):
                            raise
                        last_busy = exc
                        remaining = deadline - time.monotonic()
                        if remaining > 0:
                            time.sleep(min(0.01, remaining))
                    else:
                        if mode is None or mode[0] != "wal":
                            raise WorkflowStoreError("workflow store WAL mode unavailable")
                        break
            finally:
                db.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            db.execute("BEGIN IMMEDIATE")
            _verify_event_schema(db, allow_absent=True)
            for statement in _schema_statements():
                db.execute(statement)
            # Internal postcondition: the preflight above owns malformed-store refusal;
            # absent event objects have just been created from the expected schema.
            _verify_event_schema(db)
        _restrict(self.path, 0o600)
        for suffix in ("-wal", "-shm"):
            sidecar = self.path.with_name(self.path.name + suffix)
            if sidecar.exists():
                _restrict(sidecar, 0o600)

    @staticmethod
    def _check_lead_deployment(db: sqlite3.Connection, sources: list[dict]) -> None:
        """Validate deployment scope in the caller's transaction, across subjects."""
        incoming = [item for item in sources if item["source_kind"] == "lead.source.received"]
        if not incoming:
            return
        try:
            persisted = []
            configurations = {}
            for row in db.execute("SELECT * FROM workflow_source_bindings"):
                policy = json.loads(row["policy"])
                if row["policy"] != json.dumps(policy, sort_keys=True, separators=(",", ":")):
                    raise ValueError("inconsistent binding policy")
                stored = {key: row[key] for key in ("source_id", "source_kind", "scope")}
                stored["policy"] = policy
                configurations.setdefault((row["subject"], row["pack_id"]), {})[row["binding"]] = (
                    stored
                )
                if row["source_kind"] == "lead.source.received":
                    persisted.append(stored)
            for row in db.execute("SELECT * FROM workflow_binding_sets"):
                actual = configurations.pop((row["subject"], row["pack_id"]), {})
                # Compare exact canonical bytes to the COMPLETE row map. This also
                # refuses non-object snapshots and snapshot-only phantom bindings.
                if row["bindings_json"] != json.dumps(
                    actual, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ):
                    raise ValueError("inconsistent deployment binding")
            if configurations:
                raise ValueError("missing deployment snapshot")
            deployments = set()
            for source in [*incoming, *persisted]:
                scope = lead_deployment_scope(source["scope"], source["source_id"])
                if source["policy"] != {"schema_version": "1.0"}:
                    raise ValueError("invalid receipt policy")
                deployments.add((scope.host_id, scope.organization_id))
            if len(deployments) != 1:
                raise ValueError("conflicting deployment")
        except (ValueError, TypeError, KeyError, RecursionError):
            raise EventBindingError() from None

    def register_bindings(self, subject: str, pack_id: str, bindings: Mapping[str, dict]) -> None:
        """Freeze the complete configuration, atomically, across runtime revisions."""
        canonical = json.dumps(
            dict(bindings), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            sources = list(bindings.values())
            if len({source["source_id"] for source in sources}) != len(sources) or len(
                {(source["source_kind"], source["scope"]) for source in sources}
            ) != len(sources):
                raise EventBindingError()
            self._check_lead_deployment(db, sources)
            for binding in sources:
                owners = db.execute(
                    "SELECT source_id, source_kind, scope, policy FROM workflow_source_bindings "
                    "WHERE subject = ? AND (source_id = ? OR (source_kind = ? AND scope = ?))",
                    (subject, binding["source_id"], binding["source_kind"], binding["scope"]),
                ).fetchall()
                policy = json.dumps(binding["policy"], sort_keys=True, separators=(",", ":"))
                if any(
                    (row["source_id"], row["source_kind"], row["scope"], row["policy"])
                    != (binding["source_id"], binding["source_kind"], binding["scope"], policy)
                    for row in owners
                ):
                    raise EventBindingError()
            prior = db.execute(
                "SELECT bindings_json FROM workflow_binding_sets WHERE subject = ? AND pack_id = ?",
                (subject, pack_id),
            ).fetchone()
            rows = db.execute(
                "SELECT * FROM workflow_source_bindings WHERE subject = ? AND pack_id = ?",
                (subject, pack_id),
            ).fetchall()
            if prior is not None:
                actual = {
                    row["binding"]: {
                        "source_id": row["source_id"],
                        "source_kind": row["source_kind"],
                        "scope": row["scope"],
                        "policy": json.loads(row["policy"]),
                    }
                    for row in rows
                }
                if prior["bindings_json"] != canonical or actual != dict(bindings):
                    raise EventBindingError()
                return
            if rows:
                raise EventBindingError()
            db.execute(
                "INSERT INTO workflow_binding_sets VALUES (?, ?, ?)", (subject, pack_id, canonical)
            )
            for name, binding in bindings.items():
                db.execute(
                    "INSERT INTO workflow_source_bindings VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        subject,
                        pack_id,
                        name,
                        binding["source_id"],
                        binding["source_kind"],
                        binding["scope"],
                        json.dumps(binding["policy"], sort_keys=True, separators=(",", ":")),
                    ),
                )

    def lookup_event(
        self,
        *,
        subject: str,
        pack_id: str,
        pack_version: int,
        binding: str,
        source_id: str,
        source_kind: str,
        occurrence: str,
        expected_payload_digest: str,
    ) -> EventAdmission | None:
        """Read the original workflow outcome; None means a valid binding has no receipt.

        Internal storage primitive, not a licensed/organization-authorized host API.
        The digest identifies canonical workflow event bytes, not source body bytes.
        Never use admission or action dispatch to implement historical lookup.
        """
        identity = (subject, pack_id, source_id, source_kind, occurrence)
        _validate_event_lookup(identity, binding, pack_version, expected_payload_digest)
        with self.read_connection() as db:
            receipt = _read_event_receipt(
                db,
                identity=identity,
                pack_version=pack_version,
                binding=binding,
                fingerprint=expected_payload_digest,
            )
            return receipt.outcome if receipt is not None else None

    def lookup_source_event(
        self,
        *,
        subject: str,
        pack_id: str,
        pack_version: int,
        binding: str,
        source: SourceBinding,
        event_id: str,
        expected_payload_digest: str,
    ) -> SourceEventReceipt | None:
        """Read a source reference and original workflow outcome under configured scope.

        Internal persistence primitive, not a licensed host or submission boundary.
        The required digest identifies the source payload, NOT the canonical workflow
        event; the stored event fingerprint is independently checked by the shared reader.
        None means scoped absence at this read, not a guarantee against a later commit.
        """
        valid = False
        try:
            if not isinstance(source, SourceBinding):
                raise ValueError("missing configured source")
            source = SourceBinding.model_validate(source)
            if source.source_kind != "lead.source.received":
                raise ValueError("wrong source kind")
            event_id = _SOURCE_EVENT_ID.validate_python(event_id)
            valid = True
        except (ValueError, TypeError, RecursionError):
            pass
        if not valid:
            raise EventInputError()
        identity = (subject, pack_id, source.source_id, source.source_kind, event_id)
        _validate_event_lookup(identity, binding, pack_version, expected_payload_digest)
        with self.read_connection() as db:
            receipt = _read_event_receipt(
                db,
                identity=identity,
                pack_version=pack_version,
                binding=binding,
                fingerprint=_SourceReceiptQuery(source, expected_payload_digest),
            )
            if receipt is None:
                return None
            return SourceEventReceipt(receipt.event.source_receipt, receipt.outcome)

    def admit_event(
        self,
        *,
        subject: str,
        pack_id: str,
        pack_version: int,
        binding: str,
        source_id: str,
        source_kind: str,
        occurrence: str,
        payload: bytes,
        workflow: str,
        initial_stage: str,
        allowed_stages: frozenset[str],
        allowed_action_kinds: frozenset[str],
        now: datetime,
        select: Callable[
            [], tuple[str, Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]] | None
        ],
    ) -> EventAdmission:
        """One commit owns the receipt, record, effect ledger and action outbox."""
        fingerprint = hashlib.sha256(payload).hexdigest()
        identity = (subject, pack_id, source_id, source_kind, occurrence)
        operation_key = _event_operation_key(identity)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = _read_event_receipt(
                db,
                identity=identity,
                pack_version=pack_version,
                binding=binding,
                fingerprint=fingerprint,
            )
            if prior is not None:
                return prior.outcome
            selection = select()
            outcome = None
            if selection is not None:
                _, effects, actions = selection
                record = self._create_record(
                    db,
                    workflow,
                    initial_stage,
                    now=now,
                    allowed_stages=allowed_stages,
                    pack_id=pack_id,
                    pack_version=pack_version,
                )
                outcome = self._apply_effects(
                    db,
                    record.record_id,
                    effects,
                    operation_key=operation_key,
                    operation_name=source_kind,
                    request=json.loads(payload),
                    expected_version=1,
                    now=now,
                    allowed_stages=allowed_stages,
                    actions=actions,
                    allowed_action_kinds=allowed_action_kinds,
                )
            db.execute(
                (
                    "INSERT INTO workflow_event_receipts (subject, pack_id, source_id, "
                    "source_kind, occurrence, pack_version, binding, fingerprint, payload, "
                    "record_id, event_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?)"
                ),
                (
                    *identity,
                    pack_version,
                    binding,
                    fingerprint,
                    payload.decode(),
                    outcome.record.record_id if outcome else None,
                    outcome.event_id if outcome else None,
                    now.isoformat(),
                ),
            )
            return EventAdmission(
                outcome is not None,
                outcome is not None,
                outcome.record if outcome else None,
                outcome.event_id if outcome else None,
            )

    def create_record(
        self,
        workflow: str,
        initial_stage: str,
        *,
        now: datetime,
        allowed_stages: frozenset[str] | None = None,
        pack_id: str | None = None,
        pack_version: int | None = None,
    ) -> RecordView:
        """Create a record and bootstrap event under the shared transaction owner."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._create_record(
                db,
                workflow,
                initial_stage,
                now=now,
                allowed_stages=allowed_stages,
                pack_id=pack_id,
                pack_version=pack_version,
            )

    def _create_record(
        self,
        db: sqlite3.Connection,
        workflow: str,
        initial_stage: str,
        *,
        now: datetime,
        allowed_stages: frozenset[str] | None = None,
        pack_id: str | None = None,
        pack_version: int | None = None,
    ) -> RecordView:
        """Create a workflow record with a bootstrap ledger event at state_version 1.

        ``pack_id`` and ``pack_version`` bind the record to the signed pack (and its version)
        that created it, set by a PackRuntime. Both are stored once and never changed, so a
        later ownership or version-freeze check can rely on them. Pass both or neither: a
        version without an identity is meaningless, and ``None``/``None`` leaves the record
        unbound, for a bare-workflow record.
        """
        if allowed_stages is not None and initial_stage not in allowed_stages:
            raise ValueError(f"stage {initial_stage!r} is not in the allowed set")
        if pack_id is not None and (not isinstance(pack_id, str) or not pack_id):
            raise ValueError("pack_id must be a non-empty string or None")
        if pack_version is not None and (not isinstance(pack_version, int) or pack_version < 1):
            raise ValueError("pack_version must be an integer >= 1 or None")
        if (pack_id is None) != (pack_version is None):
            raise ValueError("pack_id and pack_version must be given together or both omitted")
        record_id = _new_id()
        timestamp = now.isoformat()
        db.execute(
            "INSERT INTO workflow_records "
            "(record_id, workflow, pack_id, pack_version, stage, state_version, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (record_id, workflow, pack_id, pack_version, initial_stage, timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO workflow_events "
            "(event_id, record_id, sequence_no, previous_stage, next_stage, "
            "state_version, operation_name, operation_key, request_fingerprint, "
            "effects, created_at) "
            "VALUES (?, ?, 0, NULL, ?, 1, ?, NULL, NULL, NULL, ?)",
            (_new_id(), record_id, initial_stage, CREATE_OPERATION_NAME, timestamp),
        )
        row = db.execute(
            "SELECT * FROM workflow_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return _record_view(row)

    def get_record(self, record_id: str) -> RecordView:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM workflow_records WHERE record_id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord(record_id)
        return _record_view(row)

    def get_overlays(self, record_id: str) -> dict[str, object]:
        """Return the record's current overlay projection (last-writer-wins per key)."""
        with self.connection() as db:
            exists = db.execute(
                "SELECT 1 FROM workflow_records WHERE record_id = ?", (record_id,)
            ).fetchone()
            if exists is None:
                raise UnknownRecord(record_id)
            rows = db.execute(
                "SELECT key, value_json FROM workflow_overlays WHERE record_id = ?",
                (record_id,),
            ).fetchall()
        return {row["key"]: json.loads(row["value_json"]) for row in rows}

    def lookup_operation(self, record_id: str, operation_key: str) -> OperationReplay | None:
        """Return the recorded outcome for an operation key, or None if it is unused.

        The engine consults this before evaluating a decision's conditions, so an operator
        retrying the same decision after the record has advanced replays the recorded
        outcome instead of re-matching against the new stage. The returned name and
        fingerprint let the caller detect a rotated key (same key, changed intent).

        The key must be a non-empty string: SQLite's TEXT affinity would otherwise match a
        non-string key (int 7 against a stored "7") and misreport a replay.
        """
        if not isinstance(operation_key, str) or not operation_key:
            raise ValueError("operation_key must be a non-empty string")
        with self.connection() as db:
            record = db.execute(
                "SELECT * FROM workflow_records WHERE record_id = ?", (record_id,)
            ).fetchone()
            if record is None:
                raise UnknownRecord(record_id)
            operation = db.execute(
                "SELECT operation_name, request_fingerprint, event_id "
                "FROM workflow_operations WHERE record_id = ? AND operation_key = ?",
                (record_id, operation_key),
            ).fetchone()
            if operation is None:
                return None
            if operation["event_id"] is None:
                # A recorded no-match: no event, current projection, matched=False.
                return OperationReplay(
                    record=_record_view(record),
                    event_id=None,
                    operation_name=operation["operation_name"],
                    request_fingerprint=operation["request_fingerprint"],
                    matched=False,
                )
            event = db.execute(
                "SELECT next_stage, state_version, created_at "
                "FROM workflow_events WHERE event_id = ?",
                (operation["event_id"],),
            ).fetchone()
        return OperationReplay(
            record=_replay_view(record, event),
            event_id=operation["event_id"],
            operation_name=operation["operation_name"],
            request_fingerprint=operation["request_fingerprint"],
            matched=True,
        )

    def reserve_no_match(
        self,
        record_id: str,
        operation_key: str,
        *,
        operation_name: str,
        request: Mapping[str, object],
        expected_version: int,
        now: datetime,
    ) -> OperationReplay | None:
        """Bind an operation key to a no-match outcome, or replay a same-identity winner.

        This keeps a decision that matched no definition idempotent: a later retry of the
        same key replays the no-match through :meth:`lookup_operation` instead of applying
        effects because the record has since moved into a stage where the decision matches.

        Returns None when a fresh no-match is recorded. When the key is already bound with
        the same operation name and request fingerprint, returns its recorded outcome as an
        :class:`OperationReplay`: this covers both an identical no-match already reserved and
        the race where an identical concurrent submission matched and committed an event
        between this caller's no-match decision and this reservation. Only a key bound with a
        different name or request is an :class:`OperationConflict`.

        The reservation is compare-and-set on ``expected_version``, the same version the
        decision was matched against, so a no-match cannot be recorded against a record
        another writer advanced after matching; a stale caller raises :class:`StaleRecord`
        and re-evaluates against the new stage rather than pinning the key to a wrong
        no-match. The replay check precedes the compare-and-set so a genuine retry is not
        rejected merely because the record has since advanced.
        """
        _require_operation_identity(operation_key, operation_name)
        fingerprint = request_fingerprint(request)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            record = db.execute(
                "SELECT * FROM workflow_records WHERE record_id = ?", (record_id,)
            ).fetchone()
            if record is None:
                raise UnknownRecord(record_id)
            prior = db.execute(
                "SELECT operation_name, request_fingerprint, event_id "
                "FROM workflow_operations WHERE record_id = ? AND operation_key = ?",
                (record_id, operation_key),
            ).fetchone()
            if prior is not None:
                if (
                    prior["operation_name"] != operation_name
                    or prior["request_fingerprint"] != fingerprint
                ):
                    raise OperationConflict(operation_key=operation_key)
                # Same identity: replay whatever it resolved to. An event_id means an
                # identical concurrent submission matched and committed while this caller was
                # mid-flight; None means an identical no-match is already reserved.
                if prior["event_id"] is None:
                    return OperationReplay(
                        record=_record_view(record),
                        event_id=None,
                        operation_name=prior["operation_name"],
                        request_fingerprint=prior["request_fingerprint"],
                        matched=False,
                    )
                event = db.execute(
                    "SELECT next_stage, state_version, created_at "
                    "FROM workflow_events WHERE event_id = ?",
                    (prior["event_id"],),
                ).fetchone()
                return OperationReplay(
                    record=_replay_view(record, event),
                    event_id=prior["event_id"],
                    operation_name=prior["operation_name"],
                    request_fingerprint=prior["request_fingerprint"],
                    matched=True,
                )
            if record["state_version"] != expected_version:
                raise StaleRecord(expected=expected_version, actual=record["state_version"])
            db.execute(
                "INSERT INTO workflow_operations "
                "(record_id, operation_key, operation_name, request_fingerprint, "
                "event_id, created_at) VALUES (?, ?, ?, ?, NULL, ?)",
                (record_id, operation_key, operation_name, fingerprint, now.isoformat()),
            )
        return None

    def transition(
        self,
        record_id: str,
        to_stage: str,
        *,
        operation_key: str,
        operation_name: str,
        request: Mapping[str, object],
        expected_version: int,
        now: datetime,
        allowed_stages: frozenset[str] | None = None,
    ) -> TransitionOutcome:
        """Advance a record to ``to_stage`` under compare-and-set and operation-key rules.

        This is the single-effect case of :meth:`apply_effects`: a batch of exactly one
        ``record.transition``. See that method for the full ordering and guarantees.
        """
        return self.apply_effects(
            record_id,
            ({"kind": RECORD_TRANSITION, "to_stage": to_stage},),
            operation_key=operation_key,
            operation_name=operation_name,
            request=request,
            expected_version=expected_version,
            now=now,
            allowed_stages=allowed_stages,
        )

    def apply_effects(
        self,
        record_id: str,
        effects: Sequence[Mapping[str, object]],
        *,
        operation_key: str,
        operation_name: str,
        request: Mapping[str, object],
        expected_version: int,
        now: datetime,
        allowed_stages: frozenset[str] | None = None,
        actions: Sequence[Mapping[str, object]] | None = None,
        allowed_action_kinds: frozenset[str] | None = None,
    ) -> TransitionOutcome:
        """Apply a batch using the same transaction owner as source-event admission."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._apply_effects(
                db,
                record_id,
                effects,
                operation_key=operation_key,
                operation_name=operation_name,
                request=request,
                expected_version=expected_version,
                now=now,
                allowed_stages=allowed_stages,
                actions=actions,
                allowed_action_kinds=allowed_action_kinds,
            )

    def _apply_effects(
        self,
        db: sqlite3.Connection,
        record_id: str,
        effects: Sequence[Mapping[str, object]],
        *,
        operation_key: str,
        operation_name: str,
        request: Mapping[str, object],
        expected_version: int,
        now: datetime,
        allowed_stages: frozenset[str] | None = None,
        actions: Sequence[Mapping[str, object]] | None = None,
        allowed_action_kinds: frozenset[str] | None = None,
    ) -> TransitionOutcome:
        """Apply an effect batch atomically under compare-and-set and operation-key rules.

        Ordering inside one ``BEGIN IMMEDIATE`` transaction:

        1. The operation key is looked up first. An exact match (same operation name,
           request fingerprint, and canonical effect batch) is an idempotent replay and
           returns the prior outcome with ``applied=False`` and no new event, regardless of
           ``expected_version``. A mismatch on any of the three raises
           :class:`OperationConflict`.
        2. Only a genuinely new operation enforces compare-and-set: ``expected_version``
           must equal the record's current ``state_version`` or :class:`StaleRecord` is
           raised.
        3. The batch then appends exactly one immutable event, advances the record by one
           ``state_version`` (its stage changes only if the batch carries a
           ``record.transition``), upserts each ``overlay.set``, binds the operation key to
           its name, fingerprint, and event, and admits each of ``actions`` as a ``pending``
           outbox row keyed by the committed event id. Admitting the action intents in this
           same transaction is what makes a decision's declared side effects durable: a crash
           after the commit leaves recoverable pending rows rather than losing the intent.

        Because the action intents are admitted only on a genuinely new operation, an
        idempotent replay does not re-admit them (the original apply's rows persist); the
        caller resumes any still-pending rows rather than re-inserting.
        """
        _require_operation_identity(operation_key, operation_name)
        normalized = _normalize_effects(effects)
        action_intents = _normalize_action_intents(actions, allowed_kinds=allowed_action_kinds)
        try:
            canonical_effects = _canonical_effects(normalized)
            batch_bytes = len(canonical_effects.encode("utf-8"))
        except ValueError as exc:
            # A value that cannot be serialized or UTF-8 encoded (a lone surrogate such as
            # "\ud800", or an integer past the interpreter digit limit such as 10**5000) is
            # rejected on the store's domain path rather than leaking a raw ValueError or
            # UnicodeEncodeError (the latter is a ValueError subclass).
            raise InvalidEffect(f"effect batch contains an unserializable value: {exc}") from exc
        if batch_bytes > MAX_EFFECT_BATCH_BYTES:
            raise InvalidEffect(f"the effect batch exceeds {MAX_EFFECT_BATCH_BYTES} bytes")
        fingerprint = request_fingerprint(request)
        record = db.execute(
            "SELECT * FROM workflow_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        if record is None:
            raise UnknownRecord(record_id)

        prior = db.execute(
            "SELECT operation_name, request_fingerprint, event_id "
            "FROM workflow_operations WHERE record_id = ? AND operation_key = ?",
            (record_id, operation_key),
        ).fetchone()
        if prior is not None:
            if prior["event_id"] is None:
                # The key was reserved as a no-match (no event). Reusing it to apply an
                # effect batch is changed intent, so it conflicts rather than replaying.
                raise OperationConflict(operation_key=operation_key)
            prior_event = db.execute(
                "SELECT next_stage, state_version, created_at, effects "
                "FROM workflow_events WHERE event_id = ?",
                (prior["event_id"],),
            ).fetchone()
            # The effect batch is part of the operation's identity: the same key with a
            # changed name, request, or effect batch is a different intent and must
            # conflict rather than replay.
            if (
                prior["operation_name"] != operation_name
                or prior["request_fingerprint"] != fingerprint
                or prior_event["effects"] != canonical_effects
            ):
                raise OperationConflict(operation_key=operation_key)
            # Return the prior outcome reconstructed from the event, not the current
            # projection, so a replay after the record has advanced still reports the
            # stage and version this operation produced.
            return TransitionOutcome(
                record=_replay_view(record, prior_event),
                event_id=prior["event_id"],
                applied=False,
            )

        if record["state_version"] != expected_version:
            raise StaleRecord(expected=expected_version, actual=record["state_version"])

        to_stage = next(
            (effect["to_stage"] for effect in normalized if effect["kind"] == RECORD_TRANSITION),
            None,
        )
        if to_stage is not None and allowed_stages is not None and to_stage not in allowed_stages:
            raise ValueError(f"stage {to_stage!r} is not in the allowed set")
        # An overlay-only batch does not change the stage but still advances the record
        # by one version so the ledger stays a total order and compare-and-set is
        # meaningful for concurrent writers.
        next_stage = to_stage if to_stage is not None else record["stage"]

        next_version = record["state_version"] + 1
        sequence_no = next_version - 1
        event_id = _new_id()
        timestamp = now.isoformat()
        db.execute(
            "INSERT INTO workflow_events "
            "(event_id, record_id, sequence_no, previous_stage, next_stage, "
            "state_version, operation_name, operation_key, request_fingerprint, "
            "effects, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                record_id,
                sequence_no,
                record["stage"],
                next_stage,
                next_version,
                operation_name,
                operation_key,
                fingerprint,
                canonical_effects,
                timestamp,
            ),
        )
        # Compare-and-set again in SQL so a concurrent writer cannot race between the
        # read above and this update; BEGIN IMMEDIATE already serializes writers, and
        # this makes the guard explicit and self-documenting.
        updated = db.execute(
            "UPDATE workflow_records SET stage = ?, state_version = ?, updated_at = ? "
            "WHERE record_id = ? AND state_version = ?",
            (next_stage, next_version, timestamp, record_id, expected_version),
        )
        if updated.rowcount != 1:
            raise StaleRecord(expected=expected_version, actual=record["state_version"])
        for effect in normalized:
            if effect["kind"] == OVERLAY_SET:
                db.execute(
                    "INSERT INTO workflow_overlays "
                    "(record_id, key, value_json, state_version, updated_at) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(record_id, key) DO UPDATE SET "
                    "value_json = excluded.value_json, "
                    "state_version = excluded.state_version, "
                    "updated_at = excluded.updated_at",
                    (
                        record_id,
                        effect["key"],
                        json.dumps(effect["value"]),
                        next_version,
                        timestamp,
                    ),
                )
        db.execute(
            "INSERT INTO workflow_operations "
            "(record_id, operation_key, operation_name, request_fingerprint, "
            "event_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                record_id,
                operation_key,
                operation_name,
                fingerprint,
                event_id,
                timestamp,
            ),
        )
        # Admit the decision's action intents in the same transaction as the ledger commit,
        # keyed by the committed event id and their index. They cannot collide with a
        # caller-minted outbox key (reserved namespace) and are unique to this decision.
        for index, (kind, canonical_request) in enumerate(action_intents):
            db.execute(
                "INSERT INTO workflow_actions "
                "(action_id, record_id, dedupe_key, kind, request, status, result, "
                "last_error, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)",
                (
                    _new_id(),
                    record_id,
                    f"{ACTION_DEDUPE_PREFIX}{event_id}:{index}",
                    kind,
                    canonical_request,
                    timestamp,
                    timestamp,
                ),
            )
        refreshed = db.execute(
            "SELECT * FROM workflow_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return TransitionOutcome(record=_record_view(refreshed), event_id=event_id, applied=True)

    def admit_action(
        self,
        record_id: str,
        *,
        kind: str,
        dedupe_key: str,
        request: Mapping[str, object],
        now: datetime,
    ) -> ActionAdmission:
        """Admit an action to the outbox, deduplicated by ``dedupe_key``.

        The dedupe key persists the intent before the side effect runs, so a completed
        action is never dispatched twice. Behavior by prior state of the key:

        - unused: insert a fresh ``pending`` row and return ``admitted=True``; the caller
          runs the side effect and then calls :meth:`settle_action` or :meth:`fail_action`.
        - ``settled`` or ``failed``: return ``admitted=False`` with the recorded outcome to
          replay. A reuse with a different kind or request is an :class:`ActionConflict`.
        - ``pending``: raise :class:`UnresolvedAction`; a prior dispatch did not settle and
          its side effect may have run (reconciliation is deferred hardening).
        """
        if not dedupe_key or not isinstance(dedupe_key, str):
            raise ValueError("dedupe_key must be a non-empty string")
        if dedupe_key.startswith(ACTION_DEDUPE_PREFIX):
            # The decision-emitted namespace is reserved for apply_effects (which admits a
            # decision's actions keyed by its committed event id). An external admission must
            # not squat it, or a later runtime dispatch by that prefix could run a row the
            # signed pack never declared.
            raise ValueError(
                f"dedupe_key must not use the reserved {ACTION_DEDUPE_PREFIX!r} namespace"
            )
        if not kind or not isinstance(kind, str):
            raise ValueError("kind must be a non-empty string")
        canonical_request = _canonical_payload(request, label="request")
        timestamp = now.isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "SELECT 1 FROM workflow_records WHERE record_id = ?", (record_id,)
                ).fetchone()
                is None
            ):
                raise UnknownRecord(record_id)
            prior = db.execute(
                "SELECT * FROM workflow_actions WHERE record_id = ? AND dedupe_key = ?",
                (record_id, dedupe_key),
            ).fetchone()
            if prior is not None:
                if prior["kind"] != kind or prior["request"] != canonical_request:
                    raise ActionConflict(dedupe_key=dedupe_key)
                if prior["status"] == ACTION_PENDING:
                    raise UnresolvedAction(dedupe_key=dedupe_key)
                return ActionAdmission(view=_action_view(prior), admitted=False)
            action_id = _new_id()
            db.execute(
                "INSERT INTO workflow_actions "
                "(action_id, record_id, dedupe_key, kind, request, status, result, "
                "last_error, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)",
                (action_id, record_id, dedupe_key, kind, canonical_request, timestamp, timestamp),
            )
            row = db.execute(
                "SELECT * FROM workflow_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
        return ActionAdmission(view=_action_view(row), admitted=True)

    def settle_action(
        self, action_id: str, *, result: Mapping[str, object], now: datetime
    ) -> ActionView:
        """Record a pending action's successful result, moving it to ``settled``."""
        canonical_result = _canonical_payload(result, label="result")
        timestamp = now.isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            updated = db.execute(
                "UPDATE workflow_actions SET status = 'settled', result = ?, updated_at = ? "
                "WHERE action_id = ? AND status = 'pending'",
                (canonical_result, timestamp, action_id),
            )
            if updated.rowcount != 1:
                raise UnknownRecord(action_id)
            row = db.execute(
                "SELECT * FROM workflow_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
        return _action_view(row)

    def fail_action(self, action_id: str, *, error: str, now: datetime) -> ActionView:
        """Record a pending action's failure, moving it to the terminal ``failed`` state."""
        timestamp = now.isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            updated = db.execute(
                "UPDATE workflow_actions SET status = 'failed', last_error = ?, updated_at = ? "
                "WHERE action_id = ? AND status = 'pending'",
                (_safe_error_text(error), timestamp, action_id),
            )
            if updated.rowcount != 1:
                raise UnknownRecord(action_id)
            row = db.execute(
                "SELECT * FROM workflow_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
        return _action_view(row)

    def release_action(self, action_id: str) -> None:
        """Delete a pending action so its dedupe key is free to admit again.

        Used when a newly admitted action cannot be dispatched (for example no adapter is
        configured for its kind): releasing the row avoids poisoning the dedupe key with a
        terminal failure that a later, correctly configured retry could not recover from.
        Only a pending row may be released; a terminal row raises.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            deleted = db.execute(
                "DELETE FROM workflow_actions WHERE action_id = ? AND status = 'pending'",
                (action_id,),
            )
            if deleted.rowcount != 1:
                raise UnknownRecord(action_id)

    def get_action(self, action_id: str) -> ActionView:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM workflow_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
        if row is None:
            raise UnknownRecord(action_id)
        return _action_view(row)

    def list_actions(self, record_id: str) -> list[ActionView]:
        """Return a record's actions in creation order (the local-notification feed too)."""
        with self.connection() as db:
            if (
                db.execute(
                    "SELECT 1 FROM workflow_records WHERE record_id = ?", (record_id,)
                ).fetchone()
                is None
            ):
                raise UnknownRecord(record_id)
            # Order by rowid, the durable admission sequence. rowid is monotonic with
            # insertion under the single-threaded admission model (ADR-0006), so it is the
            # creation order. created_at is display text (an ISO string carrying the caller's
            # UTC offset) and cannot be the ordering key: differing offsets or a backward
            # clock jump make its lexicographic order disagree with admission order.
            rows = db.execute(
                "SELECT * FROM workflow_actions WHERE record_id = ? ORDER BY rowid",
                (record_id,),
            ).fetchall()
        return [_action_view(row) for row in rows]

    def list_pending_actions(self) -> list[ActionView]:
        """Return every ``pending`` action across all records, in global admission order.

        This is the cross-restart reconciliation feed: an action intent is admitted durably
        in the decision's transaction and dispatched afterwards, so a crash between the commit
        and the dispatch leaves a ``pending`` row with no in-flight dispatcher. On the next
        start the host sweeps this feed and re-drives each safely recoverable row (see
        :meth:`ActionRunner.recover_pending`); a settled or failed row is terminal and never
        appears here, so a completed action is not re-dispatched. Ordered by rowid, the durable
        admission sequence (as in :meth:`list_actions`), so recovery replays in admission order.
        """
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM workflow_actions WHERE status = 'pending' ORDER BY rowid"
            ).fetchall()
        return [_action_view(row) for row in rows]
