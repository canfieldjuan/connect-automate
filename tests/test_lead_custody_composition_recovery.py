"""Managed joined proof through the existing native-process crash/SQL harnesses."""

import multiprocessing
from datetime import datetime
from types import SimpleNamespace

import pytest
import test_lead_custody_races as custody_races
import test_lead_joined_concurrency as overlap
import test_lead_joined_recovery as joined
from test_lead_custody_composition import composition, prepare
from test_lead_custody_store import RESERVATION, managed_operation, reader
from test_lead_source_auth import NOW, envelope, resign

from connect_automate.lead_intake.custody_protocol import (
    canonical_request,
    parse_untrusted_request,
)
from connect_automate.lead_intake.source_store import SourceStoreError

_JOINED_CHILD = joined._child
_OPEN_RUNTIME = joined.open_runtime


def _managed_child(case, target, fault, channel, control=None):
    """Reuse actual SQL checkpoints and native completion, changing only entry.

    The bridge lets the existing harness observe source-return after the concrete
    facade returns. It never calls legacy admission or supplies a fake receipt.
    """
    current = {}

    def clock():
        if case.get("late") is not None and case["late"].is_set():
            return datetime.fromisoformat(case["later_now"])
        return NOW

    def open_managed(packet):
        runtime, owner, _, workflow = _OPEN_RUNTIME(packet)
        access = reader(owner, expected_incarnation=packet["incarnation"], clock=clock)
        intent = parse_untrusted_request(packet["prepare"])
        upload = parse_untrusted_request(packet["upload"])
        handoff = composition(runtime, access, intent, clock=clock)
        actual = access.admit_bound
        bridge = SimpleNamespace(admit_source=lambda raw: actual(upload, raw))

        def observed(request, raw):
            assert request == upload
            return bridge.admit_source(raw)

        access.admit_bound = observed
        current.update(handoff=handoff, upload=upload)
        return runtime, owner, bridge, workflow

    def submit_managed(runtime, raw):
        assert current["handoff"].runtime is runtime
        return current["handoff"].submit(request=current["upload"], raw_source_bytes=raw)

    joined.open_runtime = open_managed
    joined.submit = submit_managed
    # Managed owner conflicts share the existing fixed refusal trace format.
    joined.SourceAdmissionConflict = SourceStoreError
    _JOINED_CHILD(case, target, fault, channel, control)


@pytest.fixture
def make_managed_case(tmp_path, monkeypatch):
    make = joined.make_case.__wrapped__(tmp_path)
    monkeypatch.setattr(joined, "_child", _managed_child)
    monkeypatch.setattr(overlap, "_child", _managed_child)

    def managed(state="available"):
        case = make(state)
        runtime, owner, _, _ = _OPEN_RUNTIME(case)
        access = reader(owner, clock=lambda: NOW)
        import json

        intent, upload, raw = prepare(runtime, access, json.loads(case["raw"]))
        case.update(
            incarnation=owner.read_incarnation(),
            prepare=canonical_request(intent),
            upload=canonical_request(upload),
            settle=canonical_request(managed_operation(intent, "settle")),
            raw=raw,
        )
        return case

    return managed


@pytest.mark.parametrize("state", ["available", "unavailable"])
@pytest.mark.parametrize(
    "point",
    [
        "source-before",
        "source-after",
        "source-return",
        "workflow-before",
        "workflow-after",
        "response-lost",
    ],
)
def test_managed_crash_uses_joined_reopen_oracle(make_managed_case, state, point):
    joined.test_joined_crash_reopens_before_authenticated_replay(make_managed_case, state, point)


@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_managed_every_workflow_write_uses_joined_rollback_oracle(make_managed_case, fault):
    joined.test_each_observed_workflow_write_rolls_back(make_managed_case, fault)


@pytest.mark.parametrize("point", [None, "source-after"])
def test_managed_native_completion(make_managed_case, monkeypatch, point):
    joined.test_completion_does_not_poll_closed_peer(make_managed_case, monkeypatch, point)


def test_managed_missing_completion_is_not_success(make_managed_case, monkeypatch):
    joined.test_missing_completion_is_not_success(make_managed_case, monkeypatch)


@pytest.mark.parametrize("conflict", [False, True])
def test_managed_concurrent_upload_and_workflow_replay(make_managed_case, conflict):
    first = make_managed_case()
    second = dict(first)
    if conflict:
        value = envelope()
        value["payload"]["snapshot"]["snapshot_id"] = "00000000-0000-4000-8000-000000000002"
        second["raw"] = resign(value)
    with overlap.workers([first, second], ["source-locked", None]) as (one, two):
        overlap.contended(one, two)
        winner = overlap.accepted(one)
        if conflict:
            failures = [v for k, v in two.messages if k == "refusal"]
            assert failures == [
                ("SourceStoreConflict", ("lead source authority conflict",), True, True)
            ]
            assert not [v for k, v in two.messages if k == "result"]
        else:
            contender = overlap.accepted(two)
            for flag in ("source_applied", "workflow_applied"):
                assert sum(r[flag] for r in (winner, contender)) == 1
            assert contender["source_receipt"] == winner["source_receipt"]
            assert contender["workflow_record_id"] == winner["workflow_record_id"]
            assert contender["workflow_event_id"] == winner["workflow_event_id"]
    overlap.audit(first, [first["raw"]], 1)
    overlap.replay(first, winner)


def lifecycle_start(case, action, *, pause=None, release=None):
    context = multiprocessing.get_context("spawn")
    return custody_races.managed_start(
        context, case["source_root"], case, action, pause=pause, release=release
    )


def wait_for(receive, messages, expected):
    while True:
        observed = joined.read_trace(receive, messages)
        assert observed is not None, messages
        if observed == expected:
            return


def finish_lifecycle(process, receive, messages):
    while joined.read_trace(receive, messages) is not None:
        pass
    process.join(10)
    assert not process.is_alive() and process.exitcode == 0, messages
    assert ("result", "close") in messages or ("result", "revoke") in messages
    assert not [v for k, v in messages if k == "error"]


def close_lifecycle(process, receive):
    if process.is_alive():
        process.terminate()
    process.join(10)
    process.close()
    receive.close()


@pytest.mark.parametrize("first", ["admit", "close"])
def test_managed_close_admit_writer_order(make_managed_case, first):
    case = make_managed_case()
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    process = receive = None
    messages = []
    try:
        with overlap.workers([case], ["source-locked" if first == "admit" else None]) as (admit,):
            if first == "admit":
                admit.control["start"].set()
                admit.wait("paused", "source-locked")
                process, receive = lifecycle_start(case, "close")
                wait_for(receive, messages, ("blocked", None))
                admit.control["release"].set()
                admit.finish()
                overlap.accepted(admit)
                finish_lifecycle(process, receive, messages)
            else:
                process, receive = lifecycle_start(case, "close", pause="locked", release=release)
                wait_for(receive, messages, ("paused", "locked"))
                admit.control["start"].set()
                admit.wait("blocked", "source")
                release.set()
                finish_lifecycle(process, receive, messages)
                admit.finish()
                assert [v for k, v in admit.messages if k == "refusal"] == [
                    (
                        "SourceAuthenticationError",
                        ("lead source authentication rejected",),
                        True,
                        True,
                    )
                ]
                assert not [v for k, v in admit.messages if k == "result"]
    finally:
        release.set()
        if process is not None:
            close_lifecycle(process, receive)
    count, _, found, persisted = joined.inspect(case)
    expected = int(first == "admit")
    assert count == (expected, expected, expected)
    assert found["workflow_outcome"] == ("accepted" if expected else "not_found")
    assert len(persisted["workflow_records"]) == expected


@pytest.mark.parametrize("reason", ["revoke", "expiry"])
def test_managed_waiter_observes_changed_authority_or_time(make_managed_case, reason):
    case = make_managed_case()
    context = multiprocessing.get_context("spawn")
    late, release = context.Event(), context.Event()
    if reason == "expiry":
        case.update(late=late, later_now=RESERVATION)
    process = receive = None
    messages = []
    # A real close for expiry is unsuitable: it would mask the time guard.
    # Hold the writer without mutation with the established lifecycle holder.
    try:
        with overlap.workers([case], [None]) as (admit,):
            if reason == "revoke":
                process, receive = lifecycle_start(case, "revoke", pause="locked", release=release)
                wait_for(receive, messages, ("paused", "locked"))
                admit.control["start"].set()
                admit.wait("blocked", "source")
                release.set()
                finish_lifecycle(process, receive, messages)
                admit.finish()
            else:
                from test_lead_source_store import database, store

                owner = store(case["source_root"])
                with database(owner.path) as db:
                    db.execute("BEGIN IMMEDIATE")
                    admit.control["start"].set()
                    admit.wait("blocked", "source")
                    late.set()
                    db.rollback()
                admit.finish()
            assert [v for k, v in admit.messages if k == "refusal"] == [
                ("SourceAuthenticationError", ("lead source authentication rejected",), True, True)
            ]
            assert not [v for k, v in admit.messages if k == "result"]
    finally:
        release.set()
        if process is not None:
            close_lifecycle(process, receive)
    count, _, found, persisted = joined.inspect(case)
    assert count == (0, 0, 0) and found["workflow_outcome"] == "not_found"
    assert persisted["workflow_records"] == []


@pytest.mark.parametrize(
    "point", ["source-before", "source-after", "source-return", "workflow-before", "workflow-after"]
)
def test_managed_commit_errors_remain_unknown_and_replayable(make_managed_case, point):
    case = make_managed_case()
    joined.run_child(case, point, "sql")
    count, receipts, found, persisted = joined.inspect(case)
    source_committed = point != "source-before"
    workflow_committed = point == "workflow-after"
    assert count == ((1, 1, 1) if source_committed else (0, 0, 0))
    assert len(persisted["workflow_records"]) == int(workflow_committed)
    joined.assert_recovered(
        case,
        receipts,
        found,
        source_applied=not source_committed,
        workflow_applied=not workflow_committed,
    )


@pytest.mark.parametrize("reason", ["close", "expiry"])
def test_committed_custody_gap_does_not_invent_resume(make_managed_case, reason):
    case = make_managed_case()
    joined.run_child(case, "source-after", "crash")
    if reason == "close":
        process, receive = lifecycle_start(case, "close")
        try:
            finish_lifecycle(process, receive, [])
        finally:
            close_lifecycle(process, receive)
    else:
        late = multiprocessing.get_context("spawn").Event()
        late.set()
        case.update(late=late, later_now=RESERVATION)
    with overlap.workers([case], [None]) as (retry,):
        retry.control["start"].set()
        retry.finish()
        assert [v for k, v in retry.messages if k == "refusal"] == [
            ("SourceAuthenticationError", ("lead source authentication rejected",), True, True)
        ]
        assert not [v for k, v in retry.messages if k == "result"]
    count, receipts, found, persisted = joined.inspect(case)
    assert count == (1, 1, 1) and len(receipts) == 1
    assert found["workflow_outcome"] == "not_found"
    assert persisted["workflow_records"] == []


def test_managed_different_processes_win_source_and_workflow(make_managed_case):
    overlap.test_different_processes_win_source_and_workflow(make_managed_case)


def test_managed_workflow_contention_is_unknown_then_safe_replay(make_managed_case):
    from connect_automate.lead_intake.results import SourceHandoffUnknown

    case = make_managed_case()
    with overlap.workers([case, case], ["workflow-before", None]) as (first, second):
        first.control["start"].set()
        first.wait("paused", "workflow-before")
        second.control["start"].set()
        second.wait("blocked", "workflow")
        while not second.complete:
            second.receive()
        second.process.join(10)
        assert not second.process.is_alive() and second.process.exitcode == 0
        assert [v for k, v in second.messages if k == "unknown"] == [
            (SourceHandoffUnknown().args, None, None)
        ]
        assert not [v for k, v in second.messages if k in {"result", "refusal"}]
        first.control["release"].set()
        first.finish()
        winner = overlap.accepted(first)
    overlap.audit(case, [case["raw"]], 1)
    overlap.replay(case, winner)
