"""Versioned, source-bound event admission (all inputs are synthetic)."""

import json
import multiprocessing
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Event as ThreadEvent

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_automate_runtime import (
    PACK_ID,
    SUBJECT,
    _envelope,
    _grant_bytes,
    _licensed_host,
    _pack_keys,
    _store,
)

from connect_automate.automate.definition import DefinitionError, canonical_workflow, parse_workflow

NOW = datetime(2026, 1, 2, tzinfo=UTC)
SOURCE = "11111111-1111-4111-8111-111111111111"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def mail_trigger():
    return {
        "source_kind": "mail.received",
        "binding": "inbox",
        "filters": [{"field": "sender", "op": "equals", "value": "sender@example.invalid"}],
        "match_all": False,
    }


def event_workflow(trigger=None):
    return {
        "vocabulary_version": 2,
        "name": "event-proof",
        "stages": ["waiting", "ready", "completed"],
        "initial_stage": "waiting",
        "definitions": [
            {
                "name": "intake",
                "trigger": mail_trigger() if trigger is None else trigger,
                "conditions": [{"field": "record.stage", "op": "equals", "value": "waiting"}],
                "effects": [{"kind": "record.transition", "to_stage": "ready"}],
                "actions": [
                    {
                        "action": "notify.local",
                        "request": {"title": "Review", "body": "Review the source."},
                    }
                ],
            },
            {
                "name": "approve",
                "trigger": {"source_kind": "operator.decision", "decision": "approve"},
                "conditions": [{"field": "record.stage", "op": "equals", "value": "ready"}],
                "effects": [{"kind": "record.transition", "to_stage": "completed"}],
                "actions": [],
            },
        ],
    }


def test_v2_event_workflow_is_admitted_without_changing_v1():
    data = event_workflow()
    workflow = parse_workflow(encoded(data))
    assert workflow.vocabulary_version == 2
    assert canonical_workflow(workflow) == encoded(data)


@pytest.mark.parametrize("version", [None, False, True, 1, 2.0, "2", 0, 3])
def test_unknown_or_coerced_workflow_version_is_rejected(version):
    data = event_workflow()
    data["vocabulary_version"] = version
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))


@pytest.mark.parametrize(
    "kind", ["notify", "notify.ntfy", "mail.send", "calendar.write", "connect.invoke"]
)
def test_event_cannot_emit_external_actions_but_operator_can(kind):
    data = event_workflow()
    request = (
        {
            "capability": {"id": "sample.process", "version": "1.0"},
            "input": {
                "artifact_id": SOURCE,
                "media_type": "text/plain",
                "filename": "request.txt",
                "content_base64": "",
            },
            "confirmed": True,
        }
        if kind == "connect.invoke"
        else {}
    )
    data["definitions"][0]["actions"] = [{"action": kind, "request": request}]
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))
    data["definitions"][0]["actions"] = []
    data["definitions"][1]["actions"] = [{"action": kind, "request": request}]
    parse_workflow(encoded(data))


@pytest.mark.parametrize(
    "edit",
    [
        lambda d: d["definitions"][0].update(conditions=[]),
        lambda d: d["definitions"][0]["effects"][0].update(to_stage="waiting"),
        lambda d: d["definitions"][0].update(
            effects=[{"kind": "overlay.set", "key": "k", "value": 1}]
        ),
        lambda d: d["definitions"][0]["trigger"].update(filters=[]),
        lambda d: d["definitions"][0]["trigger"].update(match_all=True),
        lambda d: d["definitions"][0]["trigger"]["filters"][0].update(op="contains"),
        lambda d: d["definitions"][0]["trigger"]["filters"][0].update(value=""),
    ],
)
def test_event_definition_guards_reject_invalid_shape(edit):
    data = event_workflow()
    edit(data)
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))


def mail_event(**updates):
    return {
        "source_kind": "mail.received",
        "message_id": "message-1",
        "received_at": "2026-01-01T00:00:00Z",
        "sender": "sender@example.invalid",
        "subject": "",
        **updates,
    }


def test_strict_event_input_and_utf8_byte_bounds():
    from connect_automate.automate.events import EventInputError, parse_event

    assert parse_event(encoded(mail_event())).subject == ""
    for field, limit in [("message_id", 512), ("sender", 256), ("subject", 1024)]:
        assert getattr(parse_event(encoded(mail_event(**{field: "é" * (limit // 2)}))), field)
        with pytest.raises(EventInputError, match="^invalid event input$"):
            parse_event(encoded(mail_event(**{field: "é" * (limit // 2) + "x"})))
    for update in [{"message_id": ""}, {"sender": False}, {"confirmed": True}, {"body": "x"}]:
        with pytest.raises(EventInputError):
            parse_event(encoded(mail_event(**update)))
    for raw in [
        b"",
        b"{}",
        b"null",
        b"\xff",
        b" " * 8193,
        b'{"source_kind":"mail.received","source_kind":"schedule.tick"}',
    ]:
        with pytest.raises(EventInputError):
            parse_event(raw)


@pytest.mark.parametrize("period", [0, False, True, "60", 59, 604801, None])
def test_period_rejects_falsy_and_out_of_bounds(period):
    data = event_workflow(
        {
            "source_kind": "schedule.tick",
            "binding": "timer",
            "anchor": "2026-01-01T00:00:00Z",
            "every_seconds": period,
        }
    )
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))


@pytest.mark.parametrize("period", [60, 604800])
def test_period_limits_and_explicit_match_all_are_valid(period):
    parse_workflow(
        encoded(
            event_workflow(
                {
                    "source_kind": "schedule.tick",
                    "binding": "timer",
                    "anchor": "2026-01-01T00:00:00Z",
                    "every_seconds": period,
                }
            )
        )
    )
    trigger = deepcopy(mail_trigger())
    trigger.update(filters=[], match_all=True)
    parse_workflow(encoded(event_workflow(trigger)))


def test_v2_pack_roundtrip_and_version_matrix():
    from connect_automate.automate.pack import PackError, PackManifest, load_pack

    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    payload = {
        "format_version": 2,
        "pack_id": PACK_ID,
        "pack_version": 1,
        "workflow": event_workflow(),
    }
    signed = _envelope(key, encoded(payload))
    assert load_pack(signed, keys=_pack_keys(key)).workflow.vocabulary_version == 2
    for version in [1, 3, False, True, 2.0, "2", None]:
        invalid = {**payload, "format_version": version}
        with pytest.raises(PackError):
            load_pack(_envelope(key, encoded(invalid)), keys=_pack_keys(key))
    with pytest.raises(ValueError):
        PackManifest.model_validate(
            {
                **payload,
                "format_version": 1,
                "workflow": parse_workflow(encoded(payload["workflow"])),
            }
        )


def source_binding(kind="mail.received", **updates):
    return {"source_id": SOURCE, "source_kind": kind, "scope": "synthetic-inbox", **updates}


def event_runtime(
    tmp_path, *, workflow=None, version=1, bindings=None, store=None, host=None, registry=None
):
    from connect_automate.automate import AdapterRegistry, PackRuntime

    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    grant = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    workflow = event_workflow() if workflow is None else workflow
    host = _licensed_host(tmp_path) if host is None else host
    store = _store(tmp_path) if store is None else store
    runtime = PackRuntime.load(
        _envelope(
            key,
            encoded(
                {
                    "format_version": 2,
                    "pack_id": PACK_ID,
                    "pack_version": version,
                    "workflow": workflow,
                }
            ),
        ),
        _grant_bytes(grant),
        store=store,
        host=host,
        registry=AdapterRegistry.with_defaults() if registry is None else registry,
        publisher_keys=_pack_keys(key),
        grant_keys=_pack_keys(grant),
        subject=SUBJECT,
        now=NOW,
        event_bindings={"inbox": source_binding()} if bindings is None else bindings,
    )
    return runtime, store, host


def counts(store):
    with store.connection() as db:
        return tuple(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "workflow_event_receipts",
                "workflow_records",
                "workflow_events",
                "workflow_actions",
            )
        )


def test_mail_event_creates_once_and_replays_original_outcome(tmp_path):
    runtime, store, host = event_runtime(tmp_path)
    event = encoded(mail_event())
    first = runtime.submit_event(binding="inbox", event=event, now=NOW)
    assert (first.matched, first.applied, first.record.stage, first.record.state_version) == (
        True,
        True,
        "ready",
        2,
    )
    assert counts(store) == (1, 1, 2, 1)
    assert [action.status for action in first.actions] == ["settled"]
    runtime.submit_decision(
        first.record.record_id,
        decision="approve",
        operation_key="approve-1",
        request={},
        expected_version=2,
        now=NOW,
    )
    reopened, _, _ = event_runtime(tmp_path, store=store, host=host)
    replay = reopened.submit_event(binding="inbox", event=event, now=NOW)
    assert (replay.applied, replay.record.stage, replay.record.state_version, replay.event_id) == (
        False,
        "ready",
        2,
        first.event_id,
    )
    assert counts(store) == (1, 1, 3, 1)
    assert store.get_record(first.record.record_id).stage == "completed"


def test_malformed_notification_is_a_visible_action_failure(tmp_path):
    data = event_workflow()
    del data["definitions"][0]["actions"][0]["request"]["body"]
    runtime, store, _ = event_runtime(tmp_path, workflow=data)
    result = runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    assert result.applied and [action.status for action in result.actions] == ["failed"]
    assert (
        store.list_actions(result.record.record_id)[0].last_error
        == "notify.local requires a string 'body'"
    )


def test_changed_payload_conflicts_and_upgrade_cannot_rerun(tmp_path):
    from connect_automate.automate import PackVersionError
    from connect_automate.automate.events import EventConflict

    runtime, store, host = event_runtime(tmp_path)
    runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    with pytest.raises(EventConflict, match="^event identity conflict$"):
        runtime.submit_event(binding="inbox", event=encoded(mail_event(subject="changed")), now=NOW)
    upgraded, _, _ = event_runtime(tmp_path, version=2, store=store, host=host)
    with pytest.raises(PackVersionError):
        upgraded.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    assert counts(store) == (1, 1, 2, 1)


def test_no_match_receipt_survives_new_filter_without_orphan_record(tmp_path):
    runtime, store, host = event_runtime(tmp_path)
    event = encoded(mail_event(sender="other@example.invalid"))
    outcome = runtime.submit_event(binding="inbox", event=event, now=NOW)
    assert not outcome.matched and outcome.record is None and not outcome.actions
    assert counts(store) == (1, 0, 0, 0)
    workflow = event_workflow()
    workflow["definitions"][0]["trigger"]["filters"][0]["value"] = "other@example.invalid"
    reopened, _, _ = event_runtime(tmp_path, workflow=workflow, store=store, host=host)
    assert not reopened.submit_event(binding="inbox", event=event, now=NOW).matched
    assert counts(store) == (1, 0, 0, 0)


@pytest.mark.parametrize(
    "bindings",
    [
        {},
        {"other": source_binding()},
        {"inbox": source_binding(scope="")},
        {"inbox": source_binding(source_kind="schedule.tick")},
    ],
)
def test_invalid_binding_fails_before_receipts_or_records(tmp_path, bindings):
    from connect_automate.automate.events import EventBindingError

    with pytest.raises(EventBindingError):
        event_runtime(tmp_path, bindings=bindings)


def test_bindings_are_defensive_and_persisted_across_reopen(tmp_path):
    from connect_automate.automate.events import EventBindingError

    bindings = {"inbox": source_binding()}
    runtime, store, host = event_runtime(tmp_path, bindings=bindings)
    bindings["inbox"]["source_id"] = "22222222-2222-4222-8222-222222222222"
    assert runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW).applied
    for changed in [
        source_binding(scope="new-account"),
        source_binding(source_id=bindings["inbox"]["source_id"]),
    ]:
        with pytest.raises(EventBindingError):
            event_runtime(tmp_path, bindings={"inbox": changed}, store=store, host=host)
    assert counts(store) == (1, 1, 2, 1)


def test_schedule_occurrence_grid_and_future_input(tmp_path):
    from connect_automate.automate.events import EventInputError

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

    def tick(instant):
        return encoded({"source_kind": "schedule.tick", "scheduled_at": instant})

    assert runtime.submit_event(
        binding="timer", event=tick("2026-01-01T00:00:00Z"), now=NOW
    ).applied
    assert not runtime.submit_event(
        binding="timer", event=tick("2026-01-01T00:00:01Z"), now=NOW
    ).matched
    assert not runtime.submit_event(
        binding="timer", event=tick("2026-01-01T00:00:00Z"), now=NOW
    ).applied
    assert runtime.submit_event(
        binding="timer", event=tick("2026-01-01T00:01:00Z"), now=NOW
    ).applied
    with pytest.raises(EventInputError):
        runtime.submit_event(binding="timer", event=tick("2026-01-02T00:00:01Z"), now=NOW)
    assert counts(store) == (3, 2, 4, 2)


def test_concurrent_dispatch_serializes_the_real_adapter(tmp_path):
    from connect_automate.automate import ActionRunner, AdapterRegistry

    entered, release = ThreadEvent(), ThreadEvent()
    calls = []

    class Blocking:
        idempotent = True

        def deliver(self, request):
            calls.append(dict(request))
            if len(calls) == 1:
                entered.set()
                assert release.wait(5)
            return {"ok": True}

    registry = AdapterRegistry.with_defaults()
    registry.register("notify.local", Blocking())
    runtime, store, host = event_runtime(tmp_path, registry=registry)
    record = runtime.create_record(now=NOW)
    admitted = store.admit_action(
        record.record_id,
        kind="notify.local",
        dedupe_key="probe",
        request={"title": "x", "body": "y"},
        now=NOW,
    )
    one = ActionRunner(store=store, registry=registry, host=host)
    two = ActionRunner(store=store, registry=registry, host=host)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(one.dispatch, admitted.view, now=NOW)
        assert entered.wait(2)
        try:
            second = two.dispatch(admitted.view, now=NOW)
        finally:
            release.set()
    assert len(calls) == 1
    assert first.result(timeout=2).status == "settled"
    assert second.status == "pending" and not second.delivered


@pytest.mark.parametrize("flag", [False, 0, 1, "", "false", None, True])
def test_v2_replay_never_retries_ambiguous_non_idempotent_delivery(tmp_path, flag):
    from connect_automate.automate import AdapterRegistry

    calls = []

    class AcceptThenInterrupt:
        idempotent = flag

        def deliver(self, request):
            calls.append(dict(request))
            if len(calls) == 1:
                raise KeyboardInterrupt()
            return {"ok": True}

    workflow = event_workflow()
    workflow["definitions"][1]["actions"] = [
        {"action": "mail.send", "request": {"to": "synthetic", "subject": "reviewed"}}
    ]
    registry = AdapterRegistry.with_defaults()
    registry.register("mail.send", AcceptThenInterrupt())
    runtime, store, _ = event_runtime(tmp_path, workflow=workflow, registry=registry)
    record = runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW).record
    kwargs = dict(
        decision="approve", operation_key="approval", request={}, expected_version=2, now=NOW
    )
    with pytest.raises(KeyboardInterrupt):
        runtime.submit_decision(record.record_id, **kwargs)
    replay = runtime.submit_decision(record.record_id, **kwargs)
    assert not replay.outcome.applied
    assert len(calls) == (2 if flag is True else 1)
    assert [action.status for action in replay.actions] == (
        ["settled"] if flag is True else ["pending"]
    )
    assert store.get_record(record.record_id).stage == "completed"


def test_replay_policy_is_bound_to_the_adapter_actually_called(tmp_path):
    from connect_automate.automate import ActionRunner, AdapterRegistry

    calls = []

    class Safe:
        idempotent = True

        def deliver(self, request):
            calls.append("safe")
            return {"ok": True}

    class Unsafe:
        idempotent = False

        def deliver(self, request):
            calls.append("unsafe")
            return {"ok": True}

    class Reconfigured(AdapterRegistry):
        resolutions = 0

        def resolve(self, kind):
            self.resolutions += 1
            return Safe() if self.resolutions == 1 else Unsafe()

    runtime, store, host = event_runtime(tmp_path)
    record = runtime.create_record(now=NOW)
    pending = store.admit_action(
        record.record_id, kind="mail.send", dedupe_key="frozen-adapter", request={}, now=NOW
    ).view
    runner = ActionRunner(store=store, registry=Reconfigured(), host=host)
    assert runner.dispatch(pending, now=NOW, safe_replay=True).delivered
    assert calls == ["safe"]


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:00.1Z",
        "2026-02-30T00:00:00Z",
        "0000-01-01T00:00:00Z",
        "2026-01-01",
        "",
        False,
        None,
    ],
)
def test_invalid_timestamps_fail_without_writes(tmp_path, stamp):
    from connect_automate.automate import EventInputError

    runtime, store, _ = event_runtime(tmp_path)
    with pytest.raises(EventInputError):
        runtime.submit_event(binding="inbox", event=encoded(mail_event(received_at=stamp)), now=NOW)
    assert counts(store) == (0, 0, 0, 0)


def test_event_size_boundary_ambiguity_and_identity_are_not_paths(tmp_path):
    from connect_automate.automate import AmbiguousEvent, EventInputError
    from connect_automate.automate.events import parse_event

    raw = encoded(mail_event())
    assert parse_event(raw + b" " * (8192 - len(raw))).message_id == "message-1"
    with pytest.raises(EventInputError):
        parse_event(raw + b" " * (8193 - len(raw)))
    workflow = event_workflow()
    duplicate = deepcopy(workflow["definitions"][0])
    duplicate["name"] = "second-intake"
    workflow["definitions"].append(duplicate)
    runtime, store, _ = event_runtime(tmp_path, workflow=workflow)
    with pytest.raises(AmbiguousEvent):
        runtime.submit_event(
            binding="inbox", event=encoded(mail_event(message_id="../../not-a-path")), now=NOW
        )
    assert counts(store) == (0, 0, 0, 0)


def test_receipt_sql_failure_rolls_back_record_effects_and_actions(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    with store.connection() as db:
        db.executescript(
            "CREATE TRIGGER injected_receipt_failure BEFORE INSERT ON "
            "workflow_event_receipts BEGIN SELECT RAISE(ABORT, 'injected receipt "
            "failure'); END;"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected receipt failure"):
        runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    assert counts(store) == (0, 0, 0, 0)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM workflow_operations").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM workflow_overlays").fetchone()[0] == 0


def _event_process(root, database, payload, start, queue, crash=None):
    """Real OS process; it never uses a service or touches an application store."""
    from connect_automate.automate import EventConflict, WorkflowStore

    store = WorkflowStore(Path(database))
    runtime, _, _ = event_runtime(Path(root), store=store)
    if crash in ("after-create", "after-effects"):
        name = "_create_record" if crash == "after-create" else "_apply_effects"
        original = getattr(store, name)

        def die(*args, **kwargs):
            original(*args, **kwargs)
            os._exit(17)

        setattr(store, name, die)
    elif crash == "before-commit":
        connection = store.connection

        @contextmanager
        def die_before_commit():
            with connection() as db:
                yield db
                os._exit(17)

        store.connection = die_before_commit
    elif crash == "after-commit":
        runtime._dispatch_event_actions = lambda *args: os._exit(17)
    start.wait(15)
    try:
        result = runtime.submit_event(binding="inbox", event=payload, now=NOW)
        queue.put(("ok", result.matched, result.applied))
    except EventConflict:
        queue.put(("conflict", False, False))


def _processes(tmp_path, payloads, *, crash=None):
    from connect_automate.automate import WorkflowStore

    store = WorkflowStore(tmp_path / "shared" / "workflow.db")
    store.initialize()
    context = multiprocessing.get_context("spawn")
    start, queue = context.Event(), context.Queue()
    processes = [
        context.Process(
            target=_event_process,
            args=(str(tmp_path / f"host-{index}"), str(store.path), payload, start, queue, crash),
        )
        for index, payload in enumerate(payloads)
    ]
    try:
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(20)
            assert not process.is_alive()
            assert process.exitcode == (17 if crash else 0)
        results = [] if crash else [queue.get(timeout=5) for _ in processes]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        queue.close()
        queue.join_thread()
    return store, results


@pytest.mark.parametrize("mode", ["identical", "conflicting", "distinct", "no-match"])
def test_native_process_receipt_races(tmp_path, mode):
    first = mail_event(sender="other@example.invalid") if mode == "no-match" else mail_event()
    second = {
        **first,
        **(
            {"subject": "changed"}
            if mode == "conflicting"
            else {"message_id": "message-2"}
            if mode == "distinct"
            else {}
        ),
    }
    store, results = _processes(tmp_path, [encoded(first), encoded(second)])
    if mode == "conflicting":
        assert sorted(item[0] for item in results) == ["conflict", "ok"]
    else:
        assert all(item[0] == "ok" for item in results)
    expected = (
        (1, 0, 0, 0) if mode == "no-match" else (2, 2, 4, 2) if mode == "distinct" else (1, 1, 2, 1)
    )
    assert counts(store) == expected
    if mode == "identical":
        assert sum(item[2] for item in results) == 1


@pytest.mark.parametrize(
    "point", ["after-create", "after-effects", "before-commit", "after-commit"]
)
def test_native_process_crash_transaction_boundaries(tmp_path, point):
    store, _ = _processes(tmp_path, [encoded(mail_event())], crash=point)
    assert counts(store) == ((1, 1, 2, 1) if point == "after-commit" else (0, 0, 0, 0))
    runtime, _, _ = event_runtime(tmp_path / "recovery", store=store)
    result = runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    assert result.matched and result.applied == (point != "after-commit")
    assert [action.status for action in result.actions] == ["settled"]
    assert counts(store) == (1, 1, 2, 1)


def _blocking_delivery_process(root, database, action_id, marker, entered, release, result):
    from connect_automate.automate import ActionRunner, AdapterRegistry, WorkflowStore

    class Blocking:
        idempotent = True

        def deliver(self, request):
            with open(marker, "a") as stream:
                stream.write("child\n")
            entered.set()
            if not release.wait(15):
                raise RuntimeError("test barrier timed out")
            return {"ok": True}

    store = WorkflowStore(Path(database))
    registry = AdapterRegistry.with_defaults()
    registry.register("notify.local", Blocking())
    _, _, host = event_runtime(Path(root), store=store, registry=registry)
    runner = ActionRunner(store=store, registry=registry, host=host)
    outcome = runner.dispatch(store.get_action(action_id), now=NOW)
    result.put((outcome.status, outcome.delivered))


def test_native_process_delivery_lock_is_shared_with_pending_recovery(tmp_path):
    from connect_automate.automate import ActionRunner, AdapterRegistry

    context = multiprocessing.get_context("spawn")
    entered, release, result = context.Event(), context.Event(), context.Queue()
    marker = tmp_path / "delivery.txt"

    class Parent:
        idempotent = True

        def deliver(self, request):
            with marker.open("a") as stream:
                stream.write("parent\n")
            return {"ok": True}

    registry = AdapterRegistry.with_defaults()
    registry.register("notify.local", Parent())
    runtime, store, host = event_runtime(tmp_path, registry=registry)
    record = runtime.create_record(now=NOW)
    pending = store.admit_action(
        record.record_id, kind="notify.local", dedupe_key="native-lock", request={}, now=NOW
    ).view
    process = context.Process(
        target=_blocking_delivery_process,
        args=(
            str(tmp_path / "child-host"),
            str(store.path),
            pending.action_id,
            str(marker),
            entered,
            release,
            result,
        ),
    )
    process.start()
    try:
        assert entered.wait(10)
        runner = ActionRunner(store=store, registry=registry, host=host)
        blocked = runner.recover_pending(now=NOW)
        assert [outcome.status for outcome in blocked] == ["pending"]
        assert not blocked[0].delivered
    finally:
        release.set()
        process.join(20)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0
    assert result.get(timeout=5) == ("settled", True)
    assert marker.read_text().splitlines() == ["child"]
    result.close()
    result.join_thread()


def test_direct_run_uses_the_same_lock_as_dispatch(tmp_path):
    from connect_automate.automate import ActionRunner, AdapterRegistry

    entered, release = ThreadEvent(), ThreadEvent()
    calls = []

    class Blocking:
        idempotent = True

        def deliver(self, request):
            calls.append(dict(request))
            entered.set()
            assert release.wait(10)
            return {"ok": True}

    registry = AdapterRegistry.with_defaults()
    registry.register("notify.local", Blocking())
    runtime, store, host = event_runtime(tmp_path, registry=registry)
    record = runtime.create_record(now=NOW)
    runner = ActionRunner(store=store, registry=registry, host=host)
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(
            runner.run,
            record.record_id,
            kind="notify.local",
            dedupe_key="direct-run",
            request={},
            now=NOW,
        )
        assert entered.wait(5)
        try:
            view = store.list_actions(record.record_id)[0]
            assert runner.dispatch(view, now=NOW).status == "pending"
        finally:
            release.set()
        assert running.result(timeout=5).delivered
    assert calls == [{}]


def test_unsupported_native_locking_never_delivers(tmp_path, monkeypatch):
    from connect_automate import locking

    runtime, store, _ = event_runtime(tmp_path)
    monkeypatch.setattr(locking, "FileLock", locking.SoftFileLock)
    with pytest.raises(RuntimeError, match="locking is not available"):
        runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    assert counts(store) == (1, 1, 2, 1)
    with store.connection() as db:
        assert [row[0] for row in db.execute("SELECT status FROM workflow_actions")] == ["pending"]


def test_receipts_and_bindings_are_immutable(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    before = runtime.create_record(now=NOW)
    store.initialize()
    assert store.get_record(before.record_id) == before
    runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW)
    for table in ["workflow_event_receipts", "workflow_source_bindings", "workflow_binding_sets"]:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"), store.connection() as db:
            db.execute(f"DELETE FROM {table}")


def test_real_v1_database_survives_additive_initialization(tmp_path):
    from connect_automate.automate import WorkflowStore

    path = tmp_path / "legacy.db"
    fixture = Path(__file__).parent / "fixtures" / "pack_events" / "v1-store.sql"
    tables = [
        "workflow_records",
        "workflow_events",
        "workflow_operations",
        "workflow_overlays",
        "workflow_actions",
    ]
    with closing(sqlite3.connect(path)) as db:
        db.executescript(fixture.read_text())
        before = {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in tables}
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name = 'workflow_event_receipts'"
        ).fetchall()
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        db.execute("SELECT 1")
    store = WorkflowStore(path)
    store.initialize()
    store.initialize()
    with store.connection() as db:
        after = {
            name: [tuple(row) for row in db.execute(f"SELECT * FROM {name}")] for name in tables
        }
        assert before == after
        assert db.execute("SELECT COUNT(*) FROM workflow_event_receipts").fetchone()[0] == 0
    runtime, _, _ = event_runtime(tmp_path / "new-runtime", store=store)
    assert runtime.submit_event(binding="inbox", event=encoded(mail_event()), now=NOW).applied


def test_operator_decision_cannot_impersonate_source_event(tmp_path):
    runtime, store, _ = event_runtime(tmp_path)
    record = runtime.create_record(now=NOW)
    result = runtime.submit_decision(
        record.record_id,
        decision="mail.received",
        operation_key="forged",
        request={"source_kind": "mail.received"},
        expected_version=1,
        now=NOW,
    )
    assert not result.outcome.matched
    assert store.get_record(record.record_id).stage == "waiting"
    assert counts(store) == (0, 1, 1, 0)
