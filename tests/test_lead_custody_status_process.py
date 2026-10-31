"""Native source snapshots/restarts; reuse custody writer actors and state oracles."""

import multiprocessing
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime

import pytest
import test_lead_custody_status_process as this_lane
import test_lead_joined_recovery as joined
from test_lead_custody_composition import composition, forbidden
from test_lead_custody_composition_recovery import _managed_child
from test_lead_custody_composition_recovery import make_managed_case as make_managed_case
from test_lead_custody_races import CRASH, finish, managed_packet, managed_start, ordered_managed
from test_lead_custody_resume_recovery import _resume_child
from test_lead_custody_status import status
from test_lead_custody_store import RESERVATION, managed_operation, reader, snapshot
from test_lead_joined_recovery import open_runtime, read_trace
from test_lead_source_auth import NOW
from test_lead_source_store import private_root as private_root
from test_lead_source_store import store
from test_workflow_receipt_lookup import rows

from connect_automate.lead_intake.custody_protocol import canonical_request, parse_untrusted_request
from connect_automate.lead_intake.custody_store import SourceCustodyStore
from connect_automate.lead_intake.source_store import SourceStoreError


def inspect(access, request):
    try:
        found = access.observe_status(request=request)
        return None if found is None else asdict(found)
    except SourceStoreError as error:
        assert error.__context__ is None and error.__cause__ is None
        return type(error).__name__


def child(root, packet, channel, pause, release, fault):
    assert set(packet) == {"request", "incarnation"}  # No raw body, authority or live objects.
    owner = store(root)
    original = sqlite3.connect

    def checkpoint(name):
        channel.send(("checkpoint", name))
        if name != pause:
            return
        if fault == "crash":
            channel.send(("complete", None))
            os._exit(CRASH)
        if fault == "sql":
            raise sqlite3.OperationalError("SYNTHETIC-PRIVATE")
        channel.send(("paused", name))
        assert release.wait(30), "source reader not released"

    class Observed(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            pin = sql == "SELECT sql FROM sqlite_master LIMIT 1"
            if pin:
                checkpoint("pin-before")
            result = super().execute(sql, *args, **kwargs)
            if pin:
                checkpoint("pin-after")
            return result

        def close(self):
            checkpoint("release-before")
            super().close()
            checkpoint("release-after")

    def connect(path, *args, **kwargs):
        assert str(path) == owner.path.as_uri() + "?mode=ro"
        return original(path, *args, factory=Observed, **kwargs)

    def clock():
        checkpoint("clock")
        return NOW

    sqlite3.connect = connect
    try:
        access = SourceCustodyStore(
            owner,
            expected_incarnation=packet["incarnation"],
            clock=clock,
            max_handoffs=10,
            max_mutation_records=30,
            max_reservation_seconds=3600,
        )
        result = inspect(access, parse_untrusted_request(packet["request"]))
        checkpoint("response")
        channel.send(("result", result))
        channel.send(("complete", None))
    finally:
        channel.close()


@contextmanager
def reading(root, packet, point=None, fault=None):
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    release = context.Event()
    process = context.Process(target=child, args=(root, packet, send, point, release, fault))
    process.start()
    send.close()
    messages = []
    try:
        yield receive, release, messages
        closing = process
        process = None
        finish(closing, receive, messages, crashed=fault == "crash")
    finally:
        release.set()
        if process is not None:
            if process.is_alive():
                process.terminate()
            process.join(10)
            process.close()
            receive.close()


def references(packet, captured=True):
    prepared = parse_untrusted_request(packet["prepare"])
    upload = parse_untrusted_request(packet["upload"]) if captured else None
    return dict(
        request=canonical_request(status(prepared, upload)), incarnation=packet["incarnation"]
    )


def write(root, packet, action):
    process, channel = managed_start(multiprocessing.get_context("spawn"), root, packet, action)
    messages = []
    finish(process, channel, messages)
    assert ("result", action) in messages and not any(k == "error" for k, _ in messages)


@pytest.mark.parametrize(
    "action,phase",
    [
        ("bind", "prepared"),
        ("admit", "bound"),
        ("close", "admitted"),
        ("purge", "admitted"),
        ("retire", "admitted"),
        ("cleanup", "retired"),
        ("resume", "admitted"),
    ],
)
@pytest.mark.parametrize("point", ["pin-before", "pin-after", "clock", "release-after"])
def test_snapshot_orders(private_root, action, phase, point):
    owner, packet = managed_packet(private_root, phase)
    refs = references(packet, phase != "prepared")
    request = parse_untrusted_request(refs["request"])
    old = inspect(reader(owner, clock=lambda: NOW), request)
    if action == "resume":
        prepared = parse_untrusted_request(packet["prepare"])
        upload = parse_untrusted_request(packet["upload"])
        from test_lead_custody_store import managed_operation

        packet.update(
            resume=canonical_request(
                managed_operation(prepared, "resume", upload.payload.capture.model_dump())
            ),
            admission_id=old["admission_id"],
        )
    with reading(private_root, refs, point) as (channel, release, messages):
        while read_trace(channel, messages) != ("paused", point):
            assert messages[-1][0] != "error"
        write(private_root, packet, action)
        after_write = snapshot(owner)
        current = inspect(reader(owner, clock=lambda: NOW), request)
        release.set()
    expected = current if point == "pin-before" else old
    assert [v for k, v in messages if k == "result"] == [expected]
    for checkpoint in ("pin-before", "pin-after", "release-before", "release-after"):
        assert messages.count(("checkpoint", checkpoint)) == 1
    assert messages.count(("checkpoint", "clock")) == (expected != "SourceStoreConflict")
    assert snapshot(owner) == after_write
    with reading(private_root, refs) as (_, _, replay):
        pass
    assert [v for k, v in replay if k == "result"] == [current]
    print(dict(action=action, point=point, snapshot="new" if point == "pin-before" else "old"))


@pytest.mark.parametrize(
    "point,fault",
    [
        *(
            (p, "crash")
            for p in (
                "pin-before",
                "pin-after",
                "clock",
                "release-before",
                "release-after",
                "response",
            )
        ),
        *((p, "sql") for p in ("pin-before", "pin-after", "clock")),
    ],
)
def test_crash_failure_and_lost_response(private_root, point, fault):
    owner, packet = managed_packet(private_root, "admitted")
    refs = references(packet)
    before = snapshot(owner)
    expected = inspect(reader(owner, clock=lambda: NOW), parse_untrusted_request(refs["request"]))
    with reading(private_root, refs, point, fault) as (_, _, messages):
        pass
    assert ("checkpoint", point) in messages
    if fault == "sql":
        assert ("result", "SourceStoreUnavailable") in messages
    assert snapshot(owner) == before
    with reading(private_root, refs) as (_, _, replay):
        pass
    assert [v for k, v in replay if k == "result"] == [expected]
    assert snapshot(owner) == before


def composed_child(root, packet, channel, pause, release, fault):
    """Reuse native completion/writer actors, observing both real read connections."""
    assert "raw" not in packet
    runtime, owner, _, workflow = open_runtime(packet)
    access = reader(owner, expected_incarnation=packet["incarnation"], clock=lambda: NOW)
    handoff = composition(runtime, access, parse_untrusted_request(packet["prepare"]))
    request = parse_untrusted_request(packet["request"])
    owner._transaction = owner._record_clock = forbidden
    access.admit_bound = access.read_retained = access.revalidate_existing = forbidden
    workflow.connection = runtime._dispatch_event_actions = forbidden
    original = sqlite3.connect
    active = []

    def checkpoint(name):
        channel.send(("checkpoint", name))
        if name != pause:
            return
        if fault == "crash":
            channel.send(("complete", None))
            os._exit(CRASH)
        if fault == "sql":
            raise sqlite3.OperationalError("SYNTHETIC-PRIVATE")
        channel.send(("paused", name))
        assert release.wait(30), "status reader not released"

    class Observed(sqlite3.Connection):
        pinned = False

        def execute(self, sql, *args, **kwargs):
            pin = not self.pinned and sql.startswith("SELECT")
            if pin:
                checkpoint(self.role + "-before")
            result = super().execute(sql, *args, **kwargs)
            if pin:
                self.pinned = True
                checkpoint(self.role + "-after")
            return result

        def close(self):
            super().close()
            active.remove(self.role)
            checkpoint(self.role + "-released")

    def connect(path, *args, **kwargs):
        if str(path) == ":memory:":
            return original(path, *args, **kwargs)
        role = "source" if str(path) == owner.path.as_uri() + "?mode=ro" else "workflow"
        assert (
            str(path)
            == (owner.path if role == "source" else workflow.path).absolute().as_uri() + "?mode=ro"
        )
        assert not active, "owner read snapshots overlapped"
        db = original(path, *args, factory=Observed, **kwargs)
        db.role = role
        active.append(role)
        return db

    sqlite3.connect = connect
    try:
        result = handoff.status(request=request)
        checkpoint("response")
        channel.send(("result", result.model_dump(by_alias=True)))
        channel.send(("complete", None))
    finally:
        channel.close()


@pytest.fixture
def composed_case(make_managed_case, monkeypatch):
    monkeypatch.setattr(this_lane, "child", composed_child)
    case = make_managed_case()
    runtime, owner, _, workflow = open_runtime(case)
    access = reader(owner, clock=lambda: NOW)
    intent, upload = (parse_untrusted_request(case[k]) for k in ("prepare", "upload"))
    access.admit_bound(upload, case["raw"])
    case["request"] = canonical_request(status(intent, upload))
    return case, owner, workflow


def composed_refs(case):
    return {key: value for key, value in case.items() if key != "raw"}


def commit_workflow(case, *, resume=False):
    from test_lead_custody_store import managed_operation

    if resume:
        intent, upload = (parse_untrusted_request(case[k]) for k in ("prepare", "upload"))
        case = {
            **composed_refs(case),
            "resume": canonical_request(
                managed_operation(intent, "resume", upload.payload.capture.model_dump())
            ),
        }
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(
        target=_resume_child if resume else _managed_child, args=(case, None, None, send)
    )
    process.start()
    send.close()
    messages = []
    finish(process, receive, messages)
    assert any(k == "result" and v["workflow_outcome"] == "accepted" for k, v in messages)
    assert not any(k in ("refusal", "unknown") for k, _ in messages)


@pytest.mark.parametrize("action", ["upload", "resume", "close", "purge", "retire", "cleanup"])
@pytest.mark.parametrize(
    "point",
    [
        "source-before",
        "source-after",
        "source-released",
        "workflow-before",
        "workflow-after",
        "workflow-released",
    ],
)
def test_composed_snapshot_orders(composed_case, action, point):
    case, owner, workflow = composed_case
    if action not in ("upload", "resume"):
        commit_workflow(case)
    if action == "cleanup":
        write(case["source_root"], case, "retire")
    request = parse_untrusted_request(case["request"])
    old = reader(owner, clock=lambda: NOW).observe_status(request=request).custody
    with reading(case["source_root"], composed_refs(case), point) as (channel, release, messages):
        while read_trace(channel, messages) != ("paused", point):
            assert messages[-1][0] not in ("error", "result")
        if action in ("upload", "resume"):
            commit_workflow(case, resume=action == "resume")
        else:
            write(case["source_root"], case, action)
        after = snapshot(owner), rows(workflow)
        current = reader(owner, clock=lambda: NOW).observe_status(request=request).custody
        release.set()
    (result,) = [v for k, v in messages if k == "result"]
    assert result["status"] == "resolved", messages
    known = action not in ("upload", "resume") or point not in (
        "workflow-after",
        "workflow-released",
    )
    assert result["workflow"]["workflow_outcome"] == ("accepted" if known else "not_found")
    new_source = point == "source-before"
    reason = (
        "retired"
        if action == "cleanup" or action == "retire" and new_source
        else "purged"
        if action == "purge" and new_source
        else None
    )
    assert result["unavailable_reason"] == reason
    expected = current if new_source else old
    assert result["fence_generation"] == expected.fence_generation
    assert result["state_revision"] == expected.state_revision
    assert (snapshot(owner), rows(workflow)) == after
    with reading(case["source_root"], composed_refs(case)) as (_, _, replay):
        pass
    (latest,) = [v for k, v in replay if k == "result"]
    assert latest["workflow"]["workflow_outcome"] == "accepted"
    if action in ("upload", "resume"):
        assert latest["state_revision"] == result["state_revision"]
    assert latest["unavailable_reason"] == (
        "purged" if action == "purge" else "retired" if action in ("retire", "cleanup") else None
    )
    assert (snapshot(owner), rows(workflow)) == after
    print(dict(action=action, point=point, result=result, replay=latest))


@pytest.mark.parametrize(
    "point",
    [
        "source-before",
        "source-after",
        "source-released",
        "workflow-before",
        "workflow-after",
        "workflow-released",
        "response",
    ],
)
def test_composed_crash_and_reopen(composed_case, point):
    case, owner, workflow = composed_case
    commit_workflow(case)
    write(case["source_root"], case, "revoke")
    before = snapshot(owner), rows(workflow)
    with reading(case["source_root"], composed_refs(case), point, "crash") as (_, _, messages):
        pass
    assert ("checkpoint", point) in messages
    assert (snapshot(owner), rows(workflow)) == before
    with reading(case["source_root"], composed_refs(case)) as (_, _, replay):
        pass
    (found,) = [v for k, v in replay if k == "result"]
    assert found["reason"] == "workflow_known" and not found["workflow"]["workflow_applied"]
    assert (snapshot(owner), rows(workflow)) == before


@pytest.mark.parametrize(
    "point", ["source-before", "source-after", "workflow-before", "workflow-after"]
)
def test_composed_sql_failure_is_not_absence(composed_case, point):
    case, owner, workflow = composed_case
    before = snapshot(owner), rows(workflow)
    with reading(case["source_root"], composed_refs(case), point, "sql") as (_, _, messages):
        pass
    (found,) = [v for k, v in messages if k == "result"]
    assert found["code"] == "unknown" and "SYNTHETIC-PRIVATE" not in repr(messages)
    assert (snapshot(owner), rows(workflow)) == before


def v12_child(root, packet, channel, pause, release, fault):
    """Reuse the real snapshot harness, selecting only the new method and clock."""
    from connect_automate.lead_intake.custody_handoff import _CustodyHandoff

    original_reader = reader

    def configured_reader(*args, **kwargs):
        kwargs["clock"] = lambda: datetime.fromisoformat(packet["v12_clock"])
        return original_reader(*args, **kwargs)

    # These bridges live only in this fresh child. No result/store is simulated.
    this_lane.reader = configured_reader
    _CustodyHandoff.status = _CustodyHandoff.status_v1_2
    composed_child(root, packet, channel, pause, release, fault)


@pytest.fixture
def v12_process_case(tmp_path, monkeypatch):
    import json

    from test_lead_custody_composition import prepare

    case = joined.make_case.__wrapped__(tmp_path)()
    runtime, owner, _, workflow = open_runtime(case)
    access = reader(owner, clock=lambda: NOW)
    intent, upload, raw = prepare(runtime, access, json.loads(case["raw"]), phase="prepared")
    case.update(
        incarnation=owner.read_incarnation(),
        prepare=canonical_request(intent),
        upload=canonical_request(upload),
        settle=canonical_request(managed_operation(intent, "settle")),
        request=canonical_request(status(intent)),
        raw=raw,
        v12_clock=RESERVATION,
    )
    monkeypatch.setattr(this_lane, "child", v12_child)
    return case, owner, workflow


@pytest.mark.parametrize("action", ["bind", "admit", "close"])
@pytest.mark.parametrize("point", ["source-before", "source-after", "source-released", "response"])
def test_v12_native_snapshot_writer_orders(v12_process_case, action, point):
    case, owner, workflow = v12_process_case
    intent, upload = (parse_untrusted_request(case[k]) for k in ("prepare", "upload"))
    access = reader(owner, clock=lambda: NOW)
    if action == "admit":
        access.bind_upload(upload)
        case["request"] = canonical_request(status(intent, upload))
    request = parse_untrusted_request(case["request"])
    old = access.observe_status(request=request).custody
    with reading(case["source_root"], composed_refs(case), point) as (channel, release, messages):
        while read_trace(channel, messages) != ("paused", point):
            assert messages[-1][0] not in ("error", "result")
        # The writer samples NOW, before expiry. The source reader samples the
        # deadline in its own pinned snapshot: no late-upload permission is added.
        write(case["source_root"], case, action)
        after = snapshot(owner), rows(workflow)
        current = access.observe(
            handoff_id=intent.handoff_id,
            scope=intent.scope,
            enrolled_machine_id=intent.enrolled_machine_id,
        )
        release.set()
    (found,) = [value for key, value in messages if key == "result"]
    assert found["schema_version"] == "1.2"
    fresh = point == "source-before"
    if fresh and action == "bind":
        assert found["code"] == "conflict"  # Absent capture cannot adopt the new binding.
    else:
        expected = current if fresh else old
        phase = (
            {"admit": "custodied", "close": "fenced_empty"}[action]
            if fresh else "upload_possible" if action == "admit" else "expired_unfenced"
        )
        assert found["capture_phase"] == phase
        assert found["fence_generation"] == expected.fence_generation
        assert found["state_revision"] == expected.state_revision
        assert found["capture"] == (
            expected.capture.model_dump() if expected.capture is not None else None
        )
    assert (snapshot(owner), rows(workflow)) == after
    with reading(case["source_root"], composed_refs(case)) as (_, _, replay):
        pass
    (latest,) = [value for key, value in replay if key == "result"]
    if action == "bind":
        assert latest["code"] == "conflict"
    else:
        assert latest["capture_phase"] == {"admit": "custodied", "close": "fenced_empty"}[action]
        assert latest["fence_generation"] == current.fence_generation
        assert latest["state_revision"] == current.state_revision
    assert (snapshot(owner), rows(workflow)) == after
    print(dict(action=action, point=point, result=found, replay=latest))


@pytest.mark.parametrize("point", ["source-before", "source-after", "source-released", "response"])
def test_v12_native_status_crash_and_lost_response(v12_process_case, point):
    case, owner, workflow = v12_process_case
    before = snapshot(owner), rows(workflow)
    with reading(case["source_root"], composed_refs(case), point, "crash") as (_, _, messages):
        pass
    assert ("checkpoint", point) in messages
    assert not any(key == "result" for key, _ in messages)
    assert (snapshot(owner), rows(workflow)) == before
    with reading(case["source_root"], composed_refs(case)) as (_, _, replay):
        pass
    (found,) = [value for key, value in replay if key == "result"]
    assert found["capture_phase"] == "expired_unfenced"
    assert found["source_receipt"] is found["workflow"] is None
    assert (snapshot(owner), rows(workflow)) == before


@pytest.mark.parametrize("point", ["source-before", "source-after", "source-released"])
def test_v12_native_sql_failure_is_unknown(v12_process_case, point):
    case, owner, workflow = v12_process_case
    before = snapshot(owner), rows(workflow)
    with reading(case["source_root"], composed_refs(case), point, "sql") as (_, _, messages):
        pass
    (found,) = [value for key, value in messages if key == "result"]
    assert found["schema_version"] == "1.2" and found["code"] == "unknown"
    assert "SYNTHETIC-PRIVATE" not in repr(messages)
    assert (snapshot(owner), rows(workflow)) == before


@pytest.mark.parametrize("point", ["before-commit", "after-commit"])
def test_v12_native_settlement_crash_replay(v12_process_case, point):
    case, owner, workflow = v12_process_case
    with reading(case["source_root"], composed_refs(case)) as (_, _, initial):
        pass
    (observed,) = [value for key, value in initial if key == "result"]
    assert observed["capture_phase"] == "expired_unfenced"
    before = snapshot(owner), rows(workflow)
    process, channel = managed_start(
        multiprocessing.get_context("spawn"), case["source_root"], case, "close",
        target=point, fault="crash", now=RESERVATION,
    )
    messages = []
    finish(process, channel, messages, crashed=True)
    assert ("checkpoint", point) in messages
    after = snapshot(owner), rows(workflow)
    if point == "before-commit":
        assert after == before
    else:
        assert after[0] != before[0] and after[1] == before[1]
    with reading(case["source_root"], composed_refs(case)) as (_, _, reopened):
        pass
    (found,) = [value for key, value in reopened if key == "result"]
    assert found["capture_phase"] == (
        "expired_unfenced" if point == "before-commit" else "fenced_empty"
    )
    assert (snapshot(owner), rows(workflow)) == after
    # Replay the same explicit settlement; no status result triggers the writer.
    process, channel = managed_start(
        multiprocessing.get_context("spawn"), case["source_root"], case, "close", now=RESERVATION
    )
    completed = []
    finish(process, channel, completed)
    assert ("result", "close") in completed
    with reading(case["source_root"], composed_refs(case)) as (_, _, replay):
        pass
    (latest,) = [value for key, value in replay if key == "result"]
    assert latest["capture_phase"] == "fenced_empty"
    assert latest["fence_generation"] > observed["fence_generation"]
    if point == "after-commit":
        assert (snapshot(owner), rows(workflow)) == after


@pytest.mark.parametrize("first,second", [("close", "admit"), ("admit", "close")])
def test_v12_native_admission_settlement_orders(v12_process_case, first, second):
    case, owner, workflow = v12_process_case
    intent, upload = (parse_untrusted_request(case[k]) for k in ("prepare", "upload"))
    reader(owner, clock=lambda: NOW).bind_upload(upload)
    case["request"] = canonical_request(status(intent, upload))
    case["settle"] = canonical_request(
        managed_operation(intent, "settle", upload.payload.capture.model_dump())
    )
    m1, m2 = ordered_managed(case["source_root"], case, first, second)
    assert ("result", first) in m1 and not any(k == "error" for k, _ in m1)
    errors = [value for key, value in m2 if key == "error"]
    assert bool(errors) == (first == "close"), (m1, m2)
    if errors:
        assert errors[0][0] == "SourceAuthenticationError" and errors[0][2:] == (True, True)
    before = snapshot(owner), rows(workflow)
    with reading(case["source_root"], composed_refs(case)) as (_, _, messages):
        pass
    (found,) = [value for key, value in messages if key == "result"]
    assert found["capture_phase"] == ("fenced_empty" if first == "close" else "custodied")
    assert (found["source_receipt"] is None) == (first == "close")
    assert found["fence_generation"] == 2
    assert (snapshot(owner), rows(workflow)) == before
