"""Internal receipt lookup: synthetic records, real SQLite and process boundaries."""

import hashlib
import json
import multiprocessing
from contextlib import contextmanager

import pytest
from test_automate_events import (
    NOW,
    SOURCE,
    encoded,
    event_runtime,
    event_workflow,
    mail_event,
    source_binding,
)
from test_automate_runtime import PACK_ID, SUBJECT

from connect_automate.automate.actions import ActionRunner
from connect_automate.automate.events import EventBindingError, EventConflict, EventInputError
from connect_automate.automate.store import (
    WorkflowStore,
    WorkflowStoreError,
    _EventVersionConflict,
    request_fingerprint,
)


def lookup_args(event=None, **updates):
    event = mail_event() if event is None else event
    return {
        "subject": SUBJECT,
        "pack_id": PACK_ID,
        "pack_version": 1,
        "binding": "inbox",
        "source_id": SOURCE,
        "source_kind": event["source_kind"],
        "occurrence": event.get("message_id", event.get("scheduled_at")),
        "expected_payload_digest": hashlib.sha256(encoded(event)).hexdigest(),
        **updates,
    }


def test_lookup_returns_original_receipt_after_reopen(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    intake = runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    runtime.submit_decision(
        intake.record.record_id,
        decision="approve",
        operation_key="advance",
        request={},
        expected_version=2,
        now=NOW,
    )
    result = WorkflowStore(store.path).lookup_event(**lookup_args())
    assert result is not None
    assert result.matched and not result.applied
    assert result.event_id == intake.event_id
    assert result.record == intake.record
    assert store.get_record(intake.record.record_id).stage == "completed"


def test_lookup_distinguishes_persisted_no_match_from_absence(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    event = mail_event(sender="unmatched@example.invalid")
    runtime.submit_event(binding="inbox", event=encoded(event), now=NOW)
    result = store.lookup_event(**lookup_args(event))
    assert result is not None
    assert (result.matched, result.applied, result.record, result.event_id) == (
        False,
        False,
        None,
        None,
    )
    assert store.lookup_event(**lookup_args(mail_event(message_id="absent"))) is None


def replay(store, event=None, **updates):
    event = mail_event() if event is None else event
    args = lookup_args(event, **updates)
    args.pop("expected_payload_digest")
    return store.admit_event(
        **args,
        payload=encoded(event),
        workflow="event-proof",
        initial_stage="waiting",
        allowed_stages=frozenset({"waiting", "ready", "completed"}),
        allowed_action_kinds=frozenset({"notify.local"}),
        now=NOW,
        select=lambda: pytest.fail("receipt replay invoked selection"),
    )


def observe(store, entry, event=None, **updates):
    if entry == "lookup":
        return store.lookup_event(**lookup_args(event, **updates))
    return replay(store, event, **updates)


def corrupt(store, table, assignments="", values=(), *, delete=False):
    # Alter only synthetic rows; put the exact triggers back before reading so
    # schema validation cannot substitute for the row-integrity check under test.
    with store.connection() as db:
        db.execute("PRAGMA foreign_keys=OFF")
        triggers = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
            (table,),
        ).fetchall()
        for name, _ in triggers:
            db.execute(f'DROP TRIGGER "{name}"')
        db.execute("PRAGMA ignore_check_constraints=ON")
        where = " WHERE sequence_no > 0" if table == "workflow_events" else ""
        if delete:
            db.execute(f"DELETE FROM {table}{where}")
        else:
            db.execute(f"UPDATE {table} SET {assignments}{where}", values)
        for _, sql in triggers:
            db.execute(sql)


@pytest.mark.parametrize("entry", ["lookup", "replay"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("subject", "foreign"),
        ("pack_id", "foreign"),
        ("binding", "foreign"),
        ("source_id", "foreign"),
        ("source_kind", "schedule.tick"),
    ],
)
def test_binding_identity_is_checked_before_absence(tmp_path, entry, field, value):
    _, store, _ = event_runtime(tmp_path)
    with pytest.raises(EventBindingError):
        observe(store, entry, **{field: value})


@pytest.mark.parametrize("entry", ["lookup", "replay"])
def test_revision_and_payload_conflicts(tmp_path, entry):
    runtime, store, _ = event_runtime(tmp_path)
    runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    with pytest.raises(_EventVersionConflict):
        observe(store, entry, pack_version=2)
    with pytest.raises(EventConflict):
        observe(store, entry, mail_event(subject="changed"))


@pytest.mark.parametrize(
    "field",
    [
        "subject",
        "pack_id",
        "binding",
        "source_id",
        "source_kind",
        "occurrence",
    ],
)
@pytest.mark.parametrize("value", [None, "", False, 0, [], b"bytes"])
def test_lookup_rejects_invalid_identity_before_open(tmp_path, monkeypatch, field, value):
    store = WorkflowStore(tmp_path / "missing.db")
    monkeypatch.setattr(store, "read_connection", lambda: pytest.fail("invalid input opened store"))
    with pytest.raises(EventInputError):
        store.lookup_event(**lookup_args(**{field: value}))


@pytest.mark.parametrize("value", [None, "", False, True, 0, -1, 1.0, "1"])
def test_lookup_rejects_invalid_version(tmp_path, value):
    with pytest.raises(EventInputError):
        WorkflowStore(tmp_path / "missing.db").lookup_event(**lookup_args(pack_version=value))


@pytest.mark.parametrize("value", [None, "", False, 0, "a" * 63, "a" * 65, "A" * 64, "g" * 64])
def test_lookup_rejects_invalid_digest(tmp_path, value):
    with pytest.raises(EventInputError):
        WorkflowStore(tmp_path / "missing.db").lookup_event(
            **lookup_args(expected_payload_digest=value)
        )


@pytest.mark.parametrize("entry", ["lookup", "replay"])
@pytest.mark.parametrize(
    "table,assignment,value",
    [
        ("workflow_event_receipts", "binding=?", "different"),
        ("workflow_event_receipts", "fingerprint=?", "0" * 64),
    ],
)
def test_receipt_conflict_checks_are_independent(tmp_path, entry, table, assignment, value):
    runtime, store, _ = event_runtime(tmp_path)
    runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    corrupt(store, table, assignment, (value,))
    with pytest.raises(EventConflict):
        observe(store, entry)


@pytest.mark.parametrize("entry", ["lookup", "replay"])
@pytest.mark.parametrize(
    "table,assignment,value",
    [
        ("workflow_event_receipts", "record_id=?", None),
        ("workflow_event_receipts", "event_id=?", None),
        ("workflow_event_receipts", "record_id=?", "missing"),
        ("workflow_event_receipts", "event_id=?", "missing"),
        ("workflow_events", "record_id=?", "different"),
        ("workflow_events", "operation_key=?", "different"),
        ("workflow_events", "operation_name=?", "different"),
        ("workflow_events", "request_fingerprint=?", "0" * 64),
        ("workflow_records", "pack_id=?", "different"),
        ("workflow_records", "pack_version=?", 2),
    ],
)
def test_each_ownership_guard_rejects_its_own_corruption(tmp_path, entry, table, assignment, value):
    runtime, store, _ = event_runtime(tmp_path)
    runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    corrupt(store, table, assignment, (value,))
    with pytest.raises(WorkflowStoreError, match="^invalid event receipt ownership$"):
        observe(store, entry)


@pytest.mark.parametrize("entry", ["lookup", "replay"])
@pytest.mark.parametrize("table", ["workflow_records", "workflow_events"])
def test_deleted_owner_row_is_bounded_ownership_error(tmp_path, entry, table):
    runtime, store, _ = event_runtime(tmp_path)
    intake = runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    before = rows(store)
    corrupt(store, table, delete=True)
    damaged = rows(store)
    assert damaged[table] != before[table]
    for name in before.keys() - {table}:
        assert damaged[name] == before[name]
    # Preserve both receipt pointers. In particular, a missing record must not
    # also break the event's record_id comparison and mask the missing-row guard.
    with store.read_connection() as db:
        receipt = db.execute("SELECT * FROM workflow_event_receipts").fetchone()
        assert receipt["record_id"] == intake.record.record_id
        assert receipt["event_id"] == intake.event_id
        record = db.execute(
            "SELECT * FROM workflow_records WHERE record_id=?", (receipt["record_id"],)
        ).fetchone()
        event = db.execute(
            "SELECT * FROM workflow_events WHERE event_id=?", (receipt["event_id"],)
        ).fetchone()
        if table == "workflow_records":
            assert record is None
            assert event is not None and event["record_id"] == receipt["record_id"]
        else:
            assert event is None and record is not None
    error = None
    try:
        observe(store, entry)
    except Exception as caught:
        error = caught
    assert type(error) is WorkflowStoreError
    assert str(error) == "invalid event receipt ownership"
    assert error.__context__ is None and error.__cause__ is None
    assert rows(store) == damaged


@pytest.mark.parametrize("entry", ["lookup", "replay"])
@pytest.mark.parametrize("matched", [False, True])
@pytest.mark.parametrize(
    "fault", ["malformed", "noncanonical", "wrong_digest", "wrong_kind", "wrong_occurrence"]
)
def test_stored_payload_checks_before_any_outcome(tmp_path, entry, matched, fault):
    runtime, store, _ = event_runtime(tmp_path)
    event = mail_event(
        sender="sender@example.invalid" if matched else "other@example.invalid",
        message_id="2026-01-01T00:00:00Z" if fault == "wrong_kind" else "message-1",
    )
    runtime.submit_event(binding="inbox", event=encoded(event), now=NOW)
    changed = dict(event)
    if fault == "wrong_kind":
        changed = {"source_kind": "schedule.tick", "scheduled_at": event["received_at"]}
    elif fault == "wrong_occurrence":
        changed["message_id"] = "another-message"
    raw = encoded(changed)
    if fault == "malformed":
        raw = b'{"private-sentinel":'
    elif fault == "noncanonical":
        raw += b" "
    elif fault == "wrong_digest":
        raw = encoded({**event, "subject": "private-sentinel"})
    # Except the digest fault, make both caller and stored digest match the bad
    # bytes, so a different check cannot hide the one under test.
    digest = hashlib.sha256(encoded(event) if fault == "wrong_digest" else raw).hexdigest()
    corrupt(store, "workflow_event_receipts", "payload=?, fingerprint=?", (raw.decode(), digest))
    if matched and fault != "malformed":
        # Keep ledger fingerprint consistent so only the payload check can reject.
        corrupt(
            store,
            "workflow_events",
            "request_fingerprint=?",
            (request_fingerprint(json.loads(raw)),),
        )
    if entry == "lookup":

        def call():
            return store.lookup_event(**lookup_args(event, expected_payload_digest=digest))
    else:
        args = lookup_args(event)
        args.pop("expected_payload_digest")

        def call():
            return store.admit_event(
                **args,
                payload=encoded(event) if fault == "wrong_digest" else raw,
                workflow="event-proof",
                initial_stage="waiting",
                allowed_stages=frozenset({"waiting", "ready", "completed"}),
                allowed_action_kinds=frozenset(),
                now=NOW,
                select=lambda: pytest.fail("corrupt replay invoked selection"),
            )

    with pytest.raises(WorkflowStoreError, match="^invalid event receipt payload$") as error:
        call()
    assert error.value.__context__ is None
    assert error.value.__cause__ is None
    assert "private-sentinel" not in str(error.value)


@pytest.mark.parametrize("kind", ["mail-unicode", "mail-max", "schedule"])
def test_supported_event_boundaries(tmp_path, kind):
    if kind == "schedule":
        trigger = {
            "source_kind": "schedule.tick",
            "binding": "timer",
            "anchor": "2026-01-01T00:00:00Z",
            "every_seconds": 60,
        }
        runtime, store, _ = event_runtime(
            tmp_path,
            workflow=event_workflow(trigger),
            bindings={"timer": source_binding("schedule.tick")},
        )
        event = {"source_kind": "schedule.tick", "scheduled_at": trigger["anchor"]}
        binding = "timer"
    else:
        runtime, store, _ = event_runtime(tmp_path)
        event = mail_event(
            message_id="é-message" if kind == "mail-unicode" else "é" * 256, subject="é" * 512
        )
        binding = "inbox"
    intake = runtime.submit_event(binding=binding, event=encoded(event), now=NOW)
    result = store.lookup_event(**lookup_args(event, binding=binding))
    assert result.record == intake.record
    assert result.event_id == intake.event_id


def rows(store):
    with store.read_connection() as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {
            table: list(map(tuple, db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')))
            for table in tables
        }


def test_lookup_never_uses_writer_or_dispatch_and_leaves_rows_unchanged(tmp_path, monkeypatch):
    runtime, store, _ = event_runtime(tmp_path)
    runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    before = rows(store)
    monkeypatch.setattr(store, "connection", lambda: pytest.fail("lookup opened writer"))
    monkeypatch.setattr(store, "admit_event", lambda **kw: pytest.fail("lookup admitted event"))
    monkeypatch.setattr(ActionRunner, "dispatch", lambda *a, **kw: pytest.fail("lookup dispatched"))
    for event in (mail_event(), mail_event(message_id="absent")):
        store.lookup_event(**lookup_args(event))
    assert rows(store) == before


@pytest.mark.parametrize("fault", ["missing", "empty", "corrupt"])
def test_invalid_store_is_error_not_absence(tmp_path, fault):
    path = tmp_path / "invalid.db"
    if fault != "missing":
        path.write_bytes(b"" if fault == "empty" else b"private-sentinel")
    with pytest.raises(WorkflowStoreError):
        WorkflowStore(path).lookup_event(**lookup_args())
    if fault == "missing":
        assert not path.exists()


def _process_admit(path, queue):
    try:
        store = WorkflowStore(path)
        args = lookup_args()
        args.pop("expected_payload_digest")
        result = store.admit_event(
            **args,
            payload=encoded(mail_event()),
            workflow="event-proof",
            initial_stage="waiting",
            allowed_stages=frozenset({"waiting", "ready", "completed"}),
            allowed_action_kinds=frozenset(),
            now=NOW,
            select=lambda: ("intake", [{"kind": "record.transition", "to_stage": "ready"}], []),
        )
        queue.put(("committed", result.event_id))
    except Exception as error:
        queue.put((type(error).__name__, str(error)))


def test_lookup_snapshot_before_concurrent_process_commit(tmp_path, monkeypatch):
    _, store, _ = event_runtime(tmp_path)
    native = store.read_connection
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    writer = context.Process(target=_process_admit, args=(store.path, queue))
    committed = []

    @contextmanager
    def concurrent_read():
        with native() as db:
            writer.start()  # read_connection has already pinned the schema snapshot
            state, event_id = queue.get(timeout=30)
            assert state == "committed", event_id
            writer.join(timeout=30)
            assert writer.exitcode == 0
            committed.append(event_id)
            yield db

    try:
        with monkeypatch.context() as patch:
            patch.setattr(store, "read_connection", concurrent_read)
            assert store.lookup_event(**lookup_args()) is None
        assert WorkflowStore(store.path).lookup_event(**lookup_args()).event_id == committed[0]
    finally:
        if writer.is_alive():
            writer.terminate()
            writer.join(timeout=30)
        queue.close()
        queue.join_thread()
