"""Lookup-first native recovery using the qualified resume SQL/process harness."""

import multiprocessing
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
import test_lead_custody_resume_recovery as resume_lane
import test_lead_joined_concurrency as overlap
import test_lead_joined_recovery as joined
from test_lead_custody_composition import composition, forbidden
from test_lead_custody_composition_recovery import _managed_child
from test_lead_custody_composition_recovery import make_managed_case as make_managed_case
from test_lead_custody_resume import resumed
from test_lead_custody_resume_recovery import make_resume_case as make_resume_case
from test_lead_custody_resume_recovery import references
from test_lead_custody_store import RESERVATION, reader, snapshot
from test_lead_joined_lifecycle import change
from test_lead_source_auth import NOW
from test_workflow_receipt_lookup import rows

from connect_automate.lead_intake.custody_protocol import canonical_request, parse_untrusted_request

_COMPOSITION = composition


def _recovery_child(packet, target, fault, channel, control=None):
    """Change the call site only; retain actual SQL commits and parent oracles."""
    assert "raw" not in packet
    paused = False

    def checkpoint(name):
        nonlocal paused
        channel.send(("checkpoint", name))
        if control and not paused and name == control["pause"]:
            paused = True
            channel.send(("paused", name))
            assert control["release"].wait(30), "parent did not release recovery"
        if name == target:
            if fault == "crash":
                channel.send(("complete", None))
                os._exit(joined.CRASH_EXIT)
            raise sqlite3.OperationalError("synthetic recovery observation failure")

    def recovery_composition(runtime, access, intent, **kwargs):
        handoff = _COMPOSITION(runtime, access, intent, **kwargs)
        observe = access.observe
        lookup = runtime.lookup_source_outcome

        def observed(**kwargs):
            facts = observe(**kwargs)
            checkpoint("observe-return")
            return facts

        def looked_up(**kwargs):
            result = lookup(**kwargs)
            checkpoint("lookup-" + result.workflow_outcome)
            return result

        access.observe = observed
        runtime.lookup_source_outcome = looked_up
        if packet.get("history_only"):
            access._store._transaction = forbidden
            access._clock = forbidden
            access.read_retained = forbidden
            access.revalidate_existing = forbidden
            runtime._store.connection = forbidden
            runtime._dispatch_event_actions = forbidden
        # This test-only call-site bridge never enters production as an owner.
        return SimpleNamespace(runtime=runtime, resume=handoff.recover)

    resume_lane.composition = recovery_composition
    resume_lane._resume_child(packet, target, fault, channel, control)


@pytest.fixture
def make_recovery_case(make_resume_case, monkeypatch):
    monkeypatch.setattr(joined, "_child", _recovery_child)
    monkeypatch.setattr(overlap, "_child", _recovery_child)
    return make_resume_case


def run(case, target=None, fault=None):
    return joined.run_child(references(case), target, fault)


@contextmanager
def workers(cases, pauses):
    context = multiprocessing.get_context("spawn")
    children = [
        overlap.Submission(context, references(case), pause)
        for case, pause in zip(cases, pauses, strict=True)
    ]
    for child, case in zip(children, cases, strict=True):
        child.case = case  # Existing parent-only privacy oracle; never a child argument.
    try:
        for child in children:
            child.start()
            child.wait("ready")
        yield children
    finally:
        for child in children:
            child.close()


def exact_history(result, prior):
    assert result["schema"] == "lead.source.handoff.lookup"
    assert result["workflow_applied"] is False and "source_applied" not in result
    for field in (
        "source_receipt",
        "workflow_record_id",
        "workflow_event_id",
        "stage",
        "state_version",
    ):
        assert result[field] == prior[field]


@pytest.mark.parametrize("state", ["available", "unavailable"])
@pytest.mark.parametrize(
    "point,fault",
    [
        (point, fault)
        for point in (
            "observe-return",
            "lookup-not_found",
            "workflow-before",
            "workflow-after",
            "response-lost",
        )
        for fault in ("crash", "sql")
        if (point, fault) != ("response-lost", "sql")
    ],
)
def test_native_failure_and_reference_only_replay(make_recovery_case, state, point, fault):
    case = make_recovery_case(state)
    before = rows(resume_lane._OPEN_RUNTIME(case)[3])
    run(case, point, fault)
    count, receipts, found, persisted = joined.inspect(case)
    committed = point in {"workflow-after", "response-lost"}
    assert count == (1, 1, 1) and len(receipts) == 1
    assert found["workflow_outcome"] == ("accepted" if committed else "not_found")
    if not committed:
        assert persisted == before
    _, result = run(case)
    if committed:
        exact_history(result, found)
    else:
        assert result["schema"] == "lead.source.handoff.result" and result["workflow_applied"]
        assert result["source_applied"] is False
    assert result["source_receipt"]["admission_id"] == receipts[0].admission_id
    overlap.audit(case, [case["raw"]], 1)
    _, replay = run(case)
    exact_history(replay, result)


@pytest.mark.parametrize("kind", ["revoke", "purge", "retire", "retired-cleanup"])
def test_lost_reply_then_lifecycle_has_read_only_history(make_recovery_case, kind):
    case = make_recovery_case()
    run(case, "workflow-after", "crash")
    _, _, found, persisted = joined.inspect(case)
    change(case, kind)
    owner = resume_lane._OPEN_RUNTIME(case)[1]
    before = snapshot(owner)
    trace, result = run({**case, "history_only": True})
    exact_history(result, found)
    assert not [item for item in trace if item[0] == "write"]
    assert snapshot(owner) == before and rows(resume_lane._OPEN_RUNTIME(case)[3]) == persisted


@pytest.mark.parametrize("point", ["lookup-accepted", "response-lost"])
def test_history_response_loss_is_recoverable_again(make_recovery_case, point):
    case = make_recovery_case()
    _, first = run(case)
    change(case, "revoke")
    run({**case, "history_only": True}, point, "crash")
    _, found = run({**case, "history_only": True})
    exact_history(found, first)


def test_recovery_competitor_commits_after_not_found(make_recovery_case):
    case = make_recovery_case()
    with workers([case, case], ["lookup-not_found", None]) as (one, two):
        one.control["start"].set()
        one.wait("paused", "lookup-not_found")
        two.control["start"].set()
        two.finish()
        winner = overlap.accepted(two)
        one.control["release"].set()
        one.finish()
        replay = overlap.accepted(one)
        assert winner["workflow_applied"] and not replay["workflow_applied"]
        assert winner["schema"] == replay["schema"] == "lead.source.handoff.result"
        assert winner["workflow_event_id"] == replay["workflow_event_id"]
    overlap.audit(case, [case["raw"]], 1)


def test_recovery_and_upload_share_one_workflow_identity(make_recovery_case, monkeypatch):
    case = make_recovery_case()
    context = multiprocessing.get_context("spawn")
    with workers([case], ["lookup-not_found"]) as (recovery,):
        recovery.control["start"].set()
        recovery.wait("paused", "lookup-not_found")
        monkeypatch.setattr(overlap, "_child", _managed_child)
        upload = overlap.Submission(context, case, None)
        try:
            upload.start()
            upload.wait("ready")
            upload.control["start"].set()
            upload.finish()
            committed = overlap.accepted(upload)
            recovery.control["release"].set()
            recovery.finish()
            replay = overlap.accepted(recovery)
            assert committed["workflow_applied"] and not replay["workflow_applied"]
            assert replay["workflow_event_id"] == committed["workflow_event_id"]
        finally:
            upload.close()
    overlap.audit(case, [case["raw"]], 1)


@pytest.mark.parametrize("kind", ["close", "revoke", "purge", "retire"])
@pytest.mark.parametrize("committed", [False, True])
def test_not_found_then_lifecycle_preserves_refusal_and_later_history(
    make_recovery_case,
    kind,
    committed,
):
    case = make_recovery_case()
    with workers([case], ["lookup-not_found"]) as (recovery,):
        recovery.control["start"].set()
        recovery.wait("paused", "lookup-not_found")
        first = None
        if committed:
            _, first = run(case)
        if kind == "close":
            owner = resume_lane._OPEN_RUNTIME(case)[1]
            reader(owner, clock=lambda: NOW).close_admission(
                parse_untrusted_request(case["settle"])
            )
        else:
            change(case, kind)
        # Lifecycle finishes while recovery is paused in the other owner.
        recovery.control["release"].set()
        recovery.finish()
        assert [v[0] for k, v in recovery.messages if k == "refusal"] == [
            "SourceAuthenticationError"
        ]
        assert (
            len([v for k, v in recovery.messages if k == "checkpoint" and v.startswith("lookup-")])
            == 1
        )
    assert len(rows(resume_lane._OPEN_RUNTIME(case)[3])["workflow_records"]) == int(committed)
    if committed:
        _, later = run({**case, "history_only": True})
        exact_history(later, first)


@pytest.mark.parametrize("reason", ["closed", "reservation"])
def test_upload_crash_source_only_gap_recovers_by_reference(
    make_recovery_case, monkeypatch, reason
):
    case = make_recovery_case(admit=False)
    with monkeypatch.context() as patch:
        patch.setattr(joined, "_child", _managed_child)
        joined.run_child(case, "source-after", "crash")
    runtime, owner, _, workflow = resume_lane._OPEN_RUNTIME(case)
    intent = parse_untrusted_request(case["prepare"])
    upload = parse_untrusted_request(case["upload"])
    assert rows(workflow)["workflow_records"] == []
    if reason == "closed":
        reader(owner, clock=lambda: NOW).close_admission(parse_untrusted_request(case["settle"]))
        case["resume"] = canonical_request(resumed(intent, upload, 2))
    else:
        case["late"] = multiprocessing.get_context("spawn").Event()
        case["late"].set()
        case["later_now"] = datetime.fromisoformat(RESERVATION).isoformat()
    _, result = run(case)
    assert result["workflow_applied"] and not result["source_applied"]
    _, replay = run(case)
    exact_history(replay, result)


@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_every_actual_workflow_write_rolls_back(make_recovery_case, fault):
    trace, _ = run(make_recovery_case())
    writes = [v for k, v in trace if k == "write"]
    assert {s.split()[-1] for s in writes} == {
        "WORKFLOW_RECORDS",
        "WORKFLOW_EVENTS",
        "WORKFLOW_OPERATIONS",
        "WORKFLOW_EVENT_RECEIPTS",
    }
    for index in range(1, len(writes) + 1):
        case = make_recovery_case()
        before = rows(resume_lane._OPEN_RUNTIME(case)[3])
        observed, _ = run(case, f"write-{index}", fault)
        assert [v for k, v in observed if k == "write"] == writes[:index]
        count, receipts, found, persisted = joined.inspect(case)
        assert count == (1, 1, 1) and found["workflow_outcome"] == "not_found"
        assert persisted == before
        _, result = run(case)
        assert result["workflow_applied"] and not result["source_applied"]
        assert result["source_receipt"]["admission_id"] == receipts[0].admission_id
        overlap.audit(case, [case["raw"]], 1)
