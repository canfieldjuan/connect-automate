"""Reference-only native recovery, reusing the joined SQL and completion oracles."""

import multiprocessing
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
import test_lead_joined_concurrency as overlap
import test_lead_joined_recovery as joined
from test_lead_custody_composition import composition
from test_lead_custody_composition_recovery import (
    _managed_child,
    close_lifecycle,
    finish_lifecycle,
    lifecycle_start,
    wait_for,
)
from test_lead_custody_composition_recovery import (
    make_managed_case as make_managed_case,
)
from test_lead_custody_resume import resumed
from test_lead_custody_store import RESERVATION, reader
from test_lead_source_auth import NOW
from test_lead_source_store import database, store
from test_workflow_receipt_lookup import rows

from connect_automate.lead_intake.custody_protocol import canonical_request, parse_untrusted_request
from connect_automate.lead_intake.source_store import SourceStoreError

_JOINED_CHILD = joined._child
_OPEN_RUNTIME = joined.open_runtime


def references(case):
    """Only this packet crosses into a restarted resume process."""
    packet = {k: v for k, v in case.items() if k != "raw"}
    assert "raw" not in packet
    assert joined.BODY.encode() not in repr(packet).encode()
    return packet


def _resume_child(packet, target, fault, channel, control=None):
    assert "raw" not in packet
    current = dict(phase="observe", paused=False)
    real_connect = sqlite3.connect

    class Channel:
        def send(self, item):
            kind, name = item
            if kind == "checkpoint" and name.startswith("source-"):
                name = current["phase"] + name[len("source") :]
                item = kind, name
            channel.send(item)
            if kind != "checkpoint":
                return
            if control and not current["paused"] and name == control["pause"]:
                current["paused"] = True
                channel.send(("paused", name))
                assert control["release"].wait(30), "parent did not release resume"
            if name == target:
                if fault == "crash":
                    channel.send(("complete", None))
                    os._exit(joined.CRASH_EXIT)
                raise sqlite3.OperationalError("synthetic resume SQL failure")

        def close(self):
            channel.close()

    observed = Channel()

    def connect(*args, **kwargs):
        # The qualified harness marks write-bearing commits. Reads/revalidation
        # at an unchanged clock may write nothing; still mark their real commits.
        factory = kwargs.get("factory")
        if factory is not None:

            class CommitObserved(factory):
                def commit(self):
                    empty_source = self.role == "source" and not self.wrote
                    if empty_source:
                        observed.send(("checkpoint", "source-before"))
                    super().commit()
                    if empty_source:
                        observed.send(("checkpoint", "source-after"))

            kwargs["factory"] = CommitObserved
        return real_connect(*args, **kwargs)

    def clock():
        return (
            datetime.fromisoformat(packet["later_now"])
            if (packet.get("late") is not None and packet["late"].is_set())
            else NOW
        )

    def opened(case):
        runtime, owner, _, workflow = _OPEN_RUNTIME(case)
        access = reader(owner, expected_incarnation=case["incarnation"], clock=clock)
        intent = parse_untrusted_request(case["prepare"])
        request = parse_untrusted_request(case["resume"])
        handoff = composition(runtime, access, intent, clock=clock)
        actual_read = access.read_retained
        actual_revalidate = access.revalidate_existing
        bridge = SimpleNamespace(
            admit_source=lambda values: actual_revalidate(
                values[0], values[1], admission_id=values[2]
            )
        )

        def read(request):
            current["phase"] = "read"
            raw = actual_read(request)
            observed.send(("checkpoint", "read-return"))
            return raw

        def revalidate(request, raw, *, admission_id):
            current["phase"] = "revalidate"
            return bridge.admit_source((request, raw, admission_id))

        access.read_retained = read
        access.revalidate_existing = revalidate
        current.update(handoff=handoff, request=request)
        return runtime, owner, bridge, workflow

    def submit(runtime, unused):
        # The old harness requires an argument; it is created only in this child,
        # carries no source bytes and cannot reach the reference-only entry.
        assert unused == b"" and current["handoff"].runtime is runtime
        return current["handoff"].resume(request=current["request"])

    sqlite3.connect = connect
    joined.open_runtime = opened
    joined.submit = submit
    joined.SourceAdmissionConflict = SourceStoreError
    inner_control = {**control, "pause": None} if control else None
    _JOINED_CHILD({**packet, "raw": b""}, None, None, observed, inner_control)


@pytest.fixture
def make_resume_case(make_managed_case, monkeypatch):
    monkeypatch.setattr(joined, "_child", _resume_child)

    def make(state="available", *, admit=True):
        case = make_managed_case(state)
        _, owner, _, _ = _OPEN_RUNTIME(case)
        intent, upload = (parse_untrusted_request(case[k]) for k in ("prepare", "upload"))
        if admit:
            reader(owner, clock=lambda: NOW).admit_bound(upload, case["raw"])
        case["resume"] = canonical_request(resumed(intent, upload))
        return case

    return make


def run(case, target=None, fault=None):
    return joined.run_child(references(case), target, fault)


@contextmanager
def workers(monkeypatch, cases, pauses):
    monkeypatch.setattr(overlap, "_child", _resume_child)
    context = multiprocessing.get_context("spawn")
    children = [
        overlap.Submission(context, references(case), pause)
        for case, pause in zip(cases, pauses, strict=True)
    ]
    # Retain the original parent-only privacy oracle. Process args remain references.
    for child, case in zip(children, cases, strict=True):
        child.case = case
    try:
        for child in children:
            child.start()
            child.wait("ready")
        yield children
    finally:
        for child in children:
            child.close()


def recover(case, receipts, found):
    _, result = run(case)
    assert not result["source_applied"]
    assert result["workflow_applied"] is (found["workflow_outcome"] == "not_found")
    assert result["source_receipt"]["admission_id"] == receipts[0].admission_id
    count, after_receipts, after, persisted = joined.inspect(case)
    assert count == (1, 1, 1) and after_receipts == receipts
    for field in ("source_receipt", "workflow_event_id", "workflow_record_id"):
        assert after[field] == result[field]
        if found["workflow_outcome"] == "accepted":
            assert after[field] == found[field]
    assert len(persisted["workflow_records"]) == len(persisted["workflow_operations"]) == 1
    assert len(persisted["workflow_events"]) == 2 and persisted["workflow_actions"] == []
    _, replay = run(case)
    assert replay == {**result, "workflow_applied": False}
    assert joined.inspect(case) == (count, after_receipts, after, persisted)


@pytest.mark.parametrize("state", ["available", "unavailable"])
@pytest.mark.parametrize(
    "point,fault",
    [
        (point, fault)
        for point in (
            "read-before",
            "read-after",
            "read-return",
            "revalidate-before",
            "revalidate-after",
            "revalidate-return",
            "workflow-before",
            "workflow-after",
            "response-lost",
        )
        for fault in ("crash", "sql")
        if (point, fault) != ("response-lost", "sql")
    ],
)
def test_native_commit_faults_and_lost_response(make_resume_case, state, point, fault):
    case = make_resume_case(state)
    before = rows(_OPEN_RUNTIME(case)[3])
    run(case, point, fault)
    count, receipts, found, persisted = joined.inspect(case)
    committed = point in {"workflow-after", "response-lost"}
    assert count == (1, 1, 1) and len(receipts) == 1
    assert found["workflow_outcome"] == ("accepted" if committed else "not_found")
    if not committed:
        assert persisted == before
    recover(case, receipts, found)


@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_each_actual_workflow_write_rolls_back(make_resume_case, fault):
    trace, result = run(make_resume_case())
    assert not result["source_applied"] and result["workflow_applied"]
    writes = [v for k, v in trace if k == "write"]
    assert {s.split()[-1] for s in writes} == {
        "WORKFLOW_RECORDS",
        "WORKFLOW_EVENTS",
        "WORKFLOW_OPERATIONS",
        "WORKFLOW_EVENT_RECEIPTS",
    }
    for index in range(1, len(writes) + 1):
        case = make_resume_case()
        before = rows(_OPEN_RUNTIME(case)[3])
        observed, _ = run(case, f"write-{index}", fault)
        assert [v for k, v in observed if k == "write"] == writes[:index]
        count, receipts, found, persisted = joined.inspect(case)
        assert count == (1, 1, 1) and found["workflow_outcome"] == "not_found"
        assert persisted == before
        recover(case, receipts, found)


@pytest.mark.parametrize("reason", ["close", "reservation-expired"])
def test_source_only_upload_crash_then_reference_only_reopen(make_resume_case, monkeypatch, reason):
    case = make_resume_case(admit=False)
    with monkeypatch.context() as patch:
        patch.setattr(joined, "_child", _managed_child)
        joined.run_child(case, "source-after", "crash")
    _, owner, _, _ = _OPEN_RUNTIME(case)
    intent = parse_untrusted_request(case["prepare"])
    upload = parse_untrusted_request(case["upload"])
    if reason == "close":
        reader(owner, clock=lambda: NOW).close_admission(parse_untrusted_request(case["settle"]))
        case["resume"] = canonical_request(resumed(intent, upload, 2))
    else:
        case["late"] = multiprocessing.get_context("spawn").Event()
        case["late"].set()
        case["later_now"] = RESERVATION
    _, result = run(case)
    assert result["workflow_applied"] and not result["source_applied"]
    _, replay = run(case)
    assert replay == {**result, "workflow_applied": False}


def test_concurrent_resume_has_one_workflow_identity(make_resume_case, monkeypatch):
    case = make_resume_case()
    with workers(monkeypatch, [case, case], ["revalidate-locked", None]) as (one, two):
        one.control["start"].set()
        one.wait("paused", "revalidate-locked")
        two.control["start"].set()
        two.wait("blocked", "source")
        one.control["release"].set()
        one.finish()
        two.finish()
        results = [overlap.accepted(child) for child in (one, two)]
        assert sum(r["workflow_applied"] for r in results) == 1
        assert not any(r["source_applied"] for r in results)
        assert results[0]["workflow_event_id"] == results[1]["workflow_event_id"]
    overlap.audit(case, [case["raw"]], 1)


@pytest.mark.parametrize("kind", ["close", "revoke", "purge", "retire"])
@pytest.mark.parametrize("first", ["resume", "lifecycle"])
def test_native_lifecycle_writer_order(make_resume_case, monkeypatch, kind, first):
    case = make_resume_case()
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    process = receive = None
    messages = []
    try:
        with workers(
            monkeypatch, [case], ["revalidate-locked" if first == "resume" else "read-return"]
        ) as (resume,):
            resume.control["start"].set()
            resume.wait("paused", "revalidate-locked" if first == "resume" else "read-return")
            process, receive = lifecycle_start(
                case, kind, pause=None if first == "resume" else "locked", release=release
            )
            if first == "resume":
                wait_for(receive, messages, ("blocked", None))
                resume.control["release"].set()
                resume.finish()
                overlap.accepted(resume)
            else:
                wait_for(receive, messages, ("paused", "locked"))
                resume.control["release"].set()
                resume.wait("blocked", "source")
            release.set()
            # Shared completion protocol; original helper restricts result to close/revoke.
            if kind in {"close", "revoke"}:
                finish_lifecycle(process, receive, messages)
            else:
                while joined.read_trace(receive, messages) is not None:
                    pass
                process.join(10)
                assert process.exitcode == 0 and ("result", kind) in messages
                assert not [v for k, v in messages if k == "error"]
            if first == "lifecycle":
                resume.finish()
                assert [v[0] for k, v in resume.messages if k == "refusal"] == [
                    "SourceAuthenticationError"
                ]
            persisted = rows(_OPEN_RUNTIME(case)[3])
            assert len(persisted["workflow_records"]) == int(first == "resume")
    finally:
        release.set()
        if process is not None:
            close_lifecycle(process, receive)


def test_key_expires_while_revalidation_waits(make_resume_case, monkeypatch):
    from test_lead_source_store import next_snapshot

    case = make_resume_case()
    owner = store(case["source_root"])
    authority = owner.read_authority()
    grants = authority.model_dump()["key_grants"]
    grants[0]["valid_until"] = RESERVATION
    owner.publish_authority(next_snapshot(authority, key_grants=grants), expected_generation=1)
    case["late"] = multiprocessing.get_context("spawn").Event()
    case["later_now"] = RESERVATION
    with workers(monkeypatch, [case], ["read-return"]) as (resume,):
        resume.control["start"].set()
        resume.wait("paused", "read-return")
        with database(owner.path) as db:
            db.execute("BEGIN IMMEDIATE")
            resume.control["release"].set()
            resume.wait("blocked", "source")
            case["late"].set()
            db.rollback()
        resume.finish()
        assert [v[0] for k, v in resume.messages if k == "refusal"] == ["SourceAuthenticationError"]
    assert rows(_OPEN_RUNTIME(case)[3])["workflow_records"] == []


def test_concurrent_upload_and_reference_resume(make_resume_case, monkeypatch):
    case = make_resume_case()
    context = multiprocessing.get_context("spawn")
    with workers(monkeypatch, [case], ["revalidate-locked"]) as (resume,):
        resume.control["start"].set()
        resume.wait("paused", "revalidate-locked")
        monkeypatch.setattr(overlap, "_child", _managed_child)
        upload = overlap.Submission(context, case, None)
        try:
            upload.start()
            upload.wait("ready")
            upload.control["start"].set()
            upload.wait("blocked", "source")
            resume.control["release"].set()
            resume.finish()
            upload.finish()
            a, b = overlap.accepted(resume), overlap.accepted(upload)
            assert not a["source_applied"] and not b["source_applied"]
            assert sum(r["workflow_applied"] for r in (a, b)) == 1
            assert a["workflow_event_id"] == b["workflow_event_id"]
        finally:
            upload.close()
    overlap.audit(case, [case["raw"]], 1)
