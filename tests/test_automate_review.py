"""Behavioral regressions for the exact-head intake review (synthetic data only)."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager

import pytest
from test_automate_events import (
    NOW,
    counts,
    encoded,
    event_runtime,
    event_workflow,
    mail_event,
    source_binding,
)

from connect_automate.automate import ActionRunner, AdapterRegistry, Workflow, WorkflowStore
from connect_automate.automate import actions as action_module
from connect_automate.automate import store as store_module
from connect_automate.automate.events import EventBindingError
from connect_automate.automate.store import WorkflowStoreError


def pending_action(tmp_path, adapter):
    registry = AdapterRegistry.with_defaults()
    registry.register("mail.send", adapter)
    runtime, store, host = event_runtime(tmp_path, registry=registry)
    record = runtime.create_record(now=NOW)
    view = store.admit_action(
        record.record_id, kind="mail.send", dedupe_key="review", request={}, now=NOW
    ).view
    return ActionRunner(store=store, registry=registry, host=host), view, store


def test_waiter_rechecks_status_after_another_dispatch_settles(tmp_path, monkeypatch):
    reached, resume = threading.Event(), threading.Event()
    calls = []

    class NonIdempotent:
        idempotent = False

        def deliver(self, request):
            calls.append(dict(request))
            return {"ok": True}

    runner, view, _ = pending_action(tmp_path, NonIdempotent())
    native_lock = action_module.operation_lock

    @contextmanager
    def ordered_lock(*args, **kwargs):
        if threading.current_thread().name.startswith("waiter"):
            reached.set()
            assert resume.wait(10)
        with native_lock(*args, **kwargs):
            yield

    monkeypatch.setattr(action_module, "operation_lock", ordered_lock)
    error = None
    result = None
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="waiter") as pool:
        waiting = pool.submit(runner.dispatch, view, now=NOW)
        assert reached.wait(10)  # B has passed the pre-lock pending check.
        try:
            assert runner.dispatch(view, now=NOW).delivered
        finally:
            resume.set()
        try:
            result = waiting.result(timeout=10)
        except Exception as exc:
            error = exc
    assert calls == [{}]
    if error is not None:
        raise error
    assert result is not None
    assert result.status == "settled" and not result.delivered


@pytest.mark.parametrize("entry", ["recovery", "safe-replay"])
def test_unsafe_sweep_does_not_obstruct_fresh_dispatch(tmp_path, entry):
    evaluating, resume = threading.Event(), threading.Event()
    calls = []

    class NonIdempotent:
        @property
        def idempotent(self):
            if threading.current_thread().name.startswith("sweep"):
                evaluating.set()
                assert resume.wait(10)
            return False

        def deliver(self, request):
            calls.append(dict(request))
            return {"ok": True}

    runner, view, store = pending_action(tmp_path, NonIdempotent())
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="sweep") as pool:
        sweep = pool.submit(
            runner.recover_pending if entry == "recovery" else runner.dispatch,
            *([] if entry == "recovery" else [view]),
            **({"now": NOW} if entry == "recovery" else {"now": NOW, "safe_replay": True}),
        )
        assert evaluating.wait(10)
        try:
            fresh = runner.dispatch(view, now=NOW)
        finally:
            resume.set()
        sweep.result(timeout=10)
    assert fresh.delivered and fresh.status == "settled"
    assert calls == [{}]
    assert store.get_action(view.action_id).status == "settled"


def test_intake_operation_key_preserves_persisted_bytes():
    identity = ("subject", "pack", "source", "mail.received", "é-message")
    assert store_module._event_operation_key(identity) == (
        "pack.event:b2ee9d2cfba9603df64af74c9ab6ca9a6094e2301cbfdf955fa484362273ad68"
    )


def test_receipt_refuses_event_from_another_record(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    raw = encoded(mail_event())
    first = runtime.submit_event(binding="inbox", event=raw, now=NOW)
    other = runtime.submit_event(
        binding="inbox", event=encoded(mail_event(message_id="other")), now=NOW
    )
    decision = runtime.submit_decision(
        other.record.record_id,
        decision="approve",
        operation_key="other-approval",
        request={},
        expected_version=2,
        now=NOW,
    )
    with store.connection() as db:
        trigger = db.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'workflow_receipts_no_update'"
        ).fetchone()[0]
        db.execute("DROP TRIGGER workflow_receipts_no_update")
        db.execute(
            "UPDATE workflow_event_receipts SET event_id = ? WHERE record_id = ?",
            (decision.outcome.event_id, first.record.record_id),
        )
        db.execute(trigger)
    before = counts(store)
    with pytest.raises(WorkflowStoreError, match="invalid event receipt ownership"):
        result = runtime.submit_event(binding="inbox", event=raw, now=NOW)
        print("fabricated replay:", result.record)
    assert counts(store) == before


def test_receipt_refuses_decision_event_on_same_record(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    raw = encoded(mail_event())
    first = runtime.submit_event(binding="inbox", event=raw, now=NOW)
    decision = runtime.submit_decision(
        first.record.record_id,
        decision="approve",
        operation_key="same-record-approval",
        request={},
        expected_version=2,
        now=NOW,
    )
    with store.connection() as db:
        trigger = db.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'workflow_receipts_no_update'"
        ).fetchone()[0]
        db.execute("DROP TRIGGER workflow_receipts_no_update")
        db.execute(
            "UPDATE workflow_event_receipts SET event_id = ? WHERE record_id = ?",
            (decision.outcome.event_id, first.record.record_id),
        )
        db.execute(trigger)
    before = counts(store)
    with pytest.raises(WorkflowStoreError, match="invalid event receipt ownership"):
        runtime.submit_event(binding="inbox", event=raw, now=NOW)
    assert counts(store) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("record_id", "another-record"),
        ("operation_key", "different-intake"),
        ("operation_key", None),
        ("operation_name", "schedule.tick"),
        ("operation_name", "approve"),
        ("request_fingerprint", "0" * 64),
        ("request_fingerprint", None),
    ],
)
def test_receipt_refuses_mismatched_intake_operation_field(tmp_path, field, value):
    runtime, store, _ = event_runtime(tmp_path)
    raw = encoded(mail_event())
    first = runtime.submit_event(binding="inbox", event=raw, now=NOW)
    with store.connection() as db:
        trigger = db.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'workflow_events_no_update'"
        ).fetchone()[0]
        db.execute("DROP TRIGGER workflow_events_no_update")
        db.execute(
            f"UPDATE workflow_events SET {field} = ? WHERE event_id = ?",
            (value, first.event_id),
        )
        db.execute(trigger)
    before = counts(store)
    with pytest.raises(WorkflowStoreError, match="invalid event receipt ownership"):
        runtime.submit_event(binding="inbox", event=raw, now=NOW)
    assert counts(store) == before


@pytest.mark.parametrize("source", ["mail-ascii", "mail-unicode", "schedule"])
def test_intake_operation_replays_original_view_after_record_advances(tmp_path, source):
    if source == "schedule":
        trigger = {
            "source_kind": "schedule.tick",
            "binding": "timer",
            "anchor": "2026-01-01T00:00:00Z",
            "every_seconds": 60,
        }
        workflow = event_workflow(trigger)
        binding = "timer"
        bindings = {binding: source_binding("schedule.tick")}
        raw = encoded({"source_kind": "schedule.tick", "scheduled_at": trigger["anchor"]})
    else:
        workflow = event_workflow()
        binding = "inbox"
        bindings = {binding: source_binding()}
        raw = encoded(mail_event(message_id="é-message" if source == "mail-unicode" else "m"))
    runtime, store, host = event_runtime(tmp_path, workflow=workflow, bindings=bindings)
    intake = runtime.submit_event(binding=binding, event=raw, now=NOW)
    decision = runtime.submit_decision(
        intake.record.record_id,
        decision="approve",
        operation_key="approve-original",
        request={},
        expected_version=2,
        now=NOW,
    )
    assert (decision.outcome.record.stage, decision.outcome.record.state_version) == (
        "completed",
        3,
    )
    reopened, _, _ = event_runtime(
        tmp_path, workflow=workflow, bindings=bindings, store=store, host=host
    )
    before = counts(store)
    replay = reopened.submit_event(binding=binding, event=raw, now=NOW)
    assert (replay.matched, replay.applied, replay.event_id) == (True, False, intake.event_id)
    assert (replay.record.stage, replay.record.state_version) == ("ready", 2)
    assert store.get_record(intake.record.record_id).stage == "completed"
    assert counts(store) == before


SCHEMA_FAULTS = [
    (",\n    PRIMARY KEY (subject, pack_id)", ""),
    (",\n    PRIMARY KEY (subject, pack_id, binding)", ""),
    (",\n    PRIMARY KEY (subject, pack_id, source_id, source_kind, occurrence)", ""),
    (",\n    UNIQUE (subject, pack_id, source_id)", ""),
    (
        ",\n    FOREIGN KEY (subject, pack_id) REFERENCES workflow_binding_sets(subject, pack_id)",
        "",
    ),
    (" REFERENCES workflow_records(record_id)", ""),
    (" REFERENCES workflow_events(event_id)", ""),
    (
        ",\n    FOREIGN KEY (subject, pack_id, binding)\n"
        "        REFERENCES workflow_source_bindings(subject, pack_id, binding)",
        "",
    ),
    (" CHECK (occurrence <> '')", ""),
    (" CHECK (pack_version >= 1)", ""),
    (" CHECK (length(fingerprint) = 64)", ""),
    (",\n    CHECK ((record_id IS NULL) = (event_id IS NULL))", ""),
]


def schema_objects(db):
    return db.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name").fetchall()


@pytest.mark.parametrize("before,after", SCHEMA_FAULTS)
def test_initialize_refuses_weakened_event_schema(tmp_path, before, after):
    path = tmp_path / "malformed.db"
    assert before in store_module._SCHEMA
    with closing(sqlite3.connect(path)) as db:
        db.executescript(store_module._SCHEMA.replace(before, after))
        original = schema_objects(db)
    with pytest.raises(WorkflowStoreError, match="incompatible event schema"):
        WorkflowStore(path).initialize()
    with closing(sqlite3.connect(path)) as db:
        assert schema_objects(db) == original


@pytest.mark.parametrize(
    "trigger",
    [
        "workflow_receipts_no_update",
        "workflow_receipts_no_delete",
        "workflow_bindings_no_update",
        "workflow_bindings_no_delete",
        "workflow_binding_sets_no_update",
        "workflow_binding_sets_no_delete",
    ],
)
@pytest.mark.parametrize("fault", ["missing", "neutralized"])
def test_initialize_refuses_missing_or_weakened_event_trigger(tmp_path, trigger, fault):
    path = tmp_path / "malformed.db"
    with closing(sqlite3.connect(path)) as db:
        db.executescript(store_module._SCHEMA)
        table = db.execute(
            "SELECT tbl_name FROM sqlite_master WHERE name = ?", (trigger,)
        ).fetchone()[0]
        db.execute(f"DROP TRIGGER {trigger}")
        if fault == "neutralized":
            db.execute(f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table} BEGIN SELECT 1; END")
        db.commit()
        original = schema_objects(db)
    with pytest.raises(WorkflowStoreError, match="incompatible event schema"):
        WorkflowStore(path).initialize()
    with closing(sqlite3.connect(path)) as db:
        assert schema_objects(db) == original


def test_initialize_refuses_partial_event_schema(tmp_path):
    path = tmp_path / "partial.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            "CREATE TABLE workflow_binding_sets (subject TEXT, pack_id TEXT, bindings_json TEXT)"
        )
        original = schema_objects(db)
    with pytest.raises(WorkflowStoreError, match="incompatible event schema"):
        WorkflowStore(path).initialize()
    with closing(sqlite3.connect(path)) as db:
        assert schema_objects(db) == original


def test_failed_initialize_rolls_back_all_new_tables(tmp_path, monkeypatch):
    path = tmp_path / "initializing.db"
    statements = store_module._schema_statements

    def fail_mid_schema():
        yield next(statements())
        raise sqlite3.OperationalError("injected schema failure")

    monkeypatch.setattr(store_module, "_schema_statements", fail_mid_schema)
    with pytest.raises(sqlite3.OperationalError, match="injected schema failure"):
        WorkflowStore(path).initialize()
    with closing(sqlite3.connect(path)) as db:
        assert schema_objects(db) == []


@pytest.fixture
def held_legacy_store(tmp_path):
    from pathlib import Path

    path = tmp_path / "held-legacy.db"
    fixture = Path(__file__).parent / "fixtures" / "pack_events" / "v1-store.sql"
    with closing(sqlite3.connect(path)) as holder:
        holder.executescript(fixture.read_text())
        before = list(holder.iterdump())
        assert holder.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        holder.execute("BEGIN IMMEDIATE")
        try:
            yield path, holder, before
        finally:
            holder.rollback()


def wal_clock(monkeypatch, release=None):
    class Clock:
        now = 0.0

        def __init__(self):
            self.sleeps = []

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            assert seconds > 0
            self.sleeps.append(seconds)
            if release is not None:
                release()
            self.now += seconds

    clock = Clock()
    monkeypatch.setattr(store_module, "time", clock, raising=False)
    return clock


def observe_wal_connections(monkeypatch, *, timeout=5.0, on_wal=None):
    connect = sqlite3.connect
    restored_timeouts = []

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql == "PRAGMA journal_mode=WAL":
                assert not self.in_transaction
                if on_wal is not None:
                    sql = on_wal(self) or sql
            return super().execute(sql, parameters)

        def close(self):
            restored_timeouts.append(self.execute("PRAGMA busy_timeout").fetchone()[0])
            super().close()

    def observed(*args, **kwargs):
        return connect(*args, **{**kwargs, "timeout": timeout, "factory": ObservedConnection})

    monkeypatch.setattr(store_module.sqlite3, "connect", observed)
    return restored_timeouts


def test_wal_switch_retries_when_write_lock_releases_inside_budget(held_legacy_store, monkeypatch):
    path, holder, before = held_legacy_store
    restored = observe_wal_connections(monkeypatch)
    clock = wal_clock(monkeypatch, release=holder.rollback)
    WorkflowStore(path).initialize()
    assert clock.sleeps and clock.now < 5.0
    assert restored and set(restored) == {5000}
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        for statement in before:
            if statement.startswith("INSERT INTO"):
                assert statement in list(db.iterdump())


@pytest.mark.parametrize("timeout", [0.0, 0.025])
def test_wal_switch_exhaustion_is_typed_and_preserves_schema(
    held_legacy_store, monkeypatch, timeout
):
    path, holder, before = held_legacy_store
    restored = observe_wal_connections(monkeypatch, timeout=timeout)
    clock = wal_clock(monkeypatch)
    with pytest.raises(WorkflowStoreError, match="^workflow store initialization busy$"):
        WorkflowStore(path).initialize()
    assert clock.now == pytest.approx(timeout)
    assert restored and set(restored) == {int(timeout * 1000)}
    assert list(holder.iterdump()) == before


@pytest.mark.parametrize(
    "code",
    [
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
        sqlite3.SQLITE_BUSY_SNAPSHOT,
        sqlite3.SQLITE_LOCKED_SHAREDCACHE,
    ],
)
def test_wal_switch_retries_only_transient_primary_codes(tmp_path, monkeypatch, code):
    attempts = []

    def busy_once(db):
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 0
        attempts.append(1)
        if len(attempts) == 1:
            error = sqlite3.OperationalError("synthetic transient WAL failure")
            error.sqlite_errorcode = code
            raise error

    restored = observe_wal_connections(monkeypatch, on_wal=busy_once)
    clock = wal_clock(monkeypatch)
    WorkflowStore(tmp_path / "retry.db").initialize()
    assert len(attempts) == 2 and len(clock.sleeps) == 1
    assert restored and set(restored) == {5000}


@pytest.mark.parametrize("code", [None, sqlite3.SQLITE_ERROR, sqlite3.SQLITE_IOERR])
def test_wal_switch_does_not_retry_other_errors(tmp_path, monkeypatch, code):
    error = sqlite3.OperationalError("synthetic non-transient WAL failure")
    if code is not None:
        error.sqlite_errorcode = code
    attempts = []

    def fail(db):
        attempts.append(1)
        raise error

    restored = observe_wal_connections(monkeypatch, on_wal=fail)
    clock = wal_clock(monkeypatch)
    with pytest.raises(sqlite3.OperationalError) as caught:
        WorkflowStore(tmp_path / "error.db").initialize()
    assert caught.value is error
    assert attempts == [1] and not clock.sleeps
    assert restored and set(restored) == {5000}


@pytest.mark.parametrize("statement", ["PRAGMA journal_mode=DELETE", "SELECT 'wal' WHERE 0"])
def test_initialize_requires_confirmed_wal_before_ddl(tmp_path, monkeypatch, statement):
    path = tmp_path / "not-wal.db"
    restored = observe_wal_connections(monkeypatch, on_wal=lambda db: statement)
    with pytest.raises(WorkflowStoreError, match="^workflow store WAL mode unavailable$"):
        WorkflowStore(path).initialize()
    assert restored and set(restored) == {5000}
    with closing(sqlite3.connect(path)) as db:
        assert schema_objects(db) == []


def test_concurrent_legacy_initializers_preserve_rows(tmp_path):
    from pathlib import Path

    path = tmp_path / "legacy.db"
    fixture = Path(__file__).parent / "fixtures" / "pack_events" / "v1-store.sql"
    names = ["workflow_records", "workflow_events", "workflow_actions"]
    with closing(sqlite3.connect(path)) as db:
        db.executescript(fixture.read_text())
        before = {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in names}
    ready = threading.Barrier(3)

    def initialize():
        ready.wait(10)
        WorkflowStore(path).initialize()

    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(initialize) for _ in range(3)]
        for job in jobs:
            job.result(timeout=15)
    with closing(sqlite3.connect(path)) as db:
        assert {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in names} == before


def test_same_source_scope_cannot_get_two_identities(tmp_path):
    workflow = event_workflow()
    from copy import deepcopy

    other = deepcopy(workflow["definitions"][0])
    other["name"], other["trigger"]["binding"] = "other-intake", "other"
    workflow["definitions"].append(other)
    bindings = {
        "inbox": source_binding(),
        "other": source_binding(source_id="22222222-2222-4222-8222-222222222222"),
    }
    with pytest.raises(EventBindingError):
        event_runtime(tmp_path, workflow=workflow, bindings=bindings)


def test_source_scope_identity_is_stable_across_packs(tmp_path):
    from test_automate_runtime import SUBJECT

    _, store, _ = event_runtime(tmp_path)
    with pytest.raises(EventBindingError):
        store.register_bindings(
            SUBJECT,
            "33333333-3333-4333-8333-333333333333",
            {
                "other": {
                    **source_binding(source_id="22222222-2222-4222-8222-222222222222"),
                    "policy": None,
                }
            },
        )


def test_duplicate_source_id_has_typed_error_and_no_bindings(tmp_path):
    from copy import deepcopy

    workflow = event_workflow()
    other = deepcopy(workflow["definitions"][0])
    other["name"], other["trigger"]["binding"] = "other-intake", "other"
    workflow["definitions"].append(other)
    store = WorkflowStore(tmp_path / "store.db")
    store.initialize()
    with pytest.raises(EventBindingError):
        event_runtime(
            tmp_path,
            store=store,
            workflow=workflow,
            bindings={"inbox": source_binding(), "other": source_binding(scope="different")},
        )
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM workflow_source_bindings").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM workflow_binding_sets").fetchone()[0] == 0


@pytest.mark.parametrize("idempotent", [False, True])
def test_event_replay_after_accept_then_crash_obeys_adapter_policy(tmp_path, idempotent):
    calls = []

    class AcceptThenCrash:
        def deliver(self, request):
            calls.append(dict(request))
            if len(calls) == 1:
                raise KeyboardInterrupt()
            return {"ok": True}

    adapter = AcceptThenCrash()
    adapter.idempotent = idempotent
    registry = AdapterRegistry.with_defaults()
    registry.register("notify.local", adapter)
    runtime, store, _ = event_runtime(tmp_path, registry=registry)
    raw = encoded(mail_event())
    with pytest.raises(KeyboardInterrupt):
        runtime.submit_event(binding="inbox", event=raw, now=NOW)
    replay = runtime.submit_event(binding="inbox", event=raw, now=NOW)
    assert replay.matched and not replay.applied
    assert len(calls) == (2 if idempotent else 1)
    assert [action.status for action in replay.actions] == (
        ["settled"] if idempotent else ["pending"]
    )
    assert counts(store) == (1, 1, 2, 1)


def test_on_grid_tick_before_anchor_is_durable_no_match(tmp_path):
    from datetime import timedelta

    trigger = {
        "source_kind": "schedule.tick",
        "binding": "timer",
        "anchor": "2026-01-02T00:00:00Z",
        "every_seconds": 60,
    }
    runtime, store, _ = event_runtime(
        tmp_path,
        workflow=event_workflow(trigger),
        bindings={"timer": source_binding("schedule.tick")},
    )
    raw = encoded({"source_kind": "schedule.tick", "scheduled_at": "2026-01-01T23:59:00Z"})
    for clock in [NOW, NOW + timedelta(seconds=60)]:
        result = runtime.submit_event(binding="timer", event=raw, now=clock)
        assert not result.matched and not result.applied and result.record is None
    assert counts(store) == (1, 0, 0, 0)


def test_safe_replay_rechecks_adapter_policy_under_lock(tmp_path, monkeypatch):
    calls = []

    class InitiallySafe:
        idempotent = True

        def deliver(self, request):
            calls.append(dict(request))
            return {"ok": True}

    adapter = InitiallySafe()
    runner, view, _ = pending_action(tmp_path, adapter)
    native = action_module.operation_lock

    @contextmanager
    def change_policy(*args, **kwargs):
        with native(*args, **kwargs):
            adapter.idempotent = False
            yield

    monkeypatch.setattr(action_module, "operation_lock", change_policy)
    result = runner.dispatch(view, now=NOW, safe_replay=True)
    assert result.status == "pending" and not result.delivered
    assert calls == []


@pytest.mark.parametrize("flag", [True, False, 0, 1, "", "true"])
def test_v1_recovery_requires_boolean_true(tmp_path, flag):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from test_automate_runtime import _licensed_host, _runtime, _store

    calls = []

    class Declared:
        idempotent = flag

        def deliver(self, request):
            calls.append(dict(request))
            return {"ok": True}

    store, host = _store(tmp_path), _licensed_host(tmp_path)
    registry = AdapterRegistry.with_defaults()
    registry.register("mail.send", Declared())
    runtime = _runtime(
        tmp_path,
        Ed25519PrivateKey.generate(),
        actions=[],
        registry=registry,
        store=store,
        host=host,
    )
    assert isinstance(runtime.workflow, Workflow)
    record = runtime.create_record(now=NOW)
    store.admit_action(
        record.record_id, kind="mail.send", dedupe_key="v1-review", request={}, now=NOW
    )
    outcomes = ActionRunner(store=store, registry=registry, host=host).recover_pending(now=NOW)
    assert [outcome.status for outcome in outcomes] == (
        ["settled"] if flag is True else ["pending"]
    )
    assert calls == ([{}] if flag is True else [])


@pytest.mark.parametrize(
    "raw",
    [
        b"\xffsynthetic-private-marker",
        b'{"sender":"synthetic-private-marker"',
        encoded({**mail_event(), "extra": "synthetic-private-marker"}),
    ],
)
def test_rejected_event_has_no_payload_in_exception_context(raw):
    from connect_automate.automate.events import EventInputError, parse_event

    with pytest.raises(EventInputError) as caught:
        parse_event(raw)
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    "edit",
    [
        {"source_id": "synthetic-private-marker"},
        {"scope": 123},
        {"extra": "synthetic-private-marker"},
    ],
)
def test_rejected_binding_has_no_payload_in_exception_context(tmp_path, edit):
    with pytest.raises(EventBindingError) as caught:
        event_runtime(tmp_path, bindings={"inbox": {**source_binding(), **edit}})
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
