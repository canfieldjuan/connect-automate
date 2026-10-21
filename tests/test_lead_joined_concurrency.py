"""Controlled overlapping public submissions; no-action signed pack, real owners."""

import hashlib
import json
import multiprocessing
from contextlib import contextmanager
from copy import deepcopy

import pytest
from test_lead_joined_recovery import (
    BODY,
    _child,
    inspect,
    open_runtime,
    read_trace,
    run_child,
)
from test_lead_joined_recovery import make_case as make_case
from test_lead_runtime_results import lookup, submit
from test_lead_source_auth import OTHER, envelope, key, resign, trust_data
from test_workflow_receipt_lookup import rows

from connect_automate.lead_intake import (
    SourceAuthenticationError,
    SourceTrustSnapshot,
    parse_untrusted_source,
)


class Submission:
    def __init__(self, context, case, pause):
        self.case = case
        self.reader, self.writer = context.Pipe(duplex=False)
        self.control = dict(start=context.Event(), release=context.Event(), pause=pause)
        self.process = context.Process(
            target=_child, args=(case, None, None, self.writer, self.control)
        )
        self.messages, self.complete = [], False

    def start(self):
        self.process.start()
        self.writer.close()

    def receive(self):
        message = read_trace(self.reader, self.messages)
        self.complete = message is None
        return message

    def wait(self, kind, value=None):
        while not self.complete:
            message = self.receive()
            if message == (kind, value):
                return
        pytest.fail(f"worker completed before {kind}: {self.messages}")

    def finish(self):
        while not self.complete:
            self.receive()
        self.process.join(10)
        assert not self.process.is_alive(), "worker did not exit after completion"
        assert self.process.exitcode == 0
        body = json.loads(self.case["raw"])["payload"]["snapshot"]["body"].get("text")
        serialized = json.dumps(self.messages)
        for sentinel in (BODY, body):
            if sentinel:
                assert sentinel not in serialized
        assert any(kind == "logs" for kind, _ in self.messages)
        assert not any(kind == "unknown" for kind, _ in self.messages), self.messages
        print(serialized)

    def close(self):
        self.control["start"].set()
        self.control["release"].set()
        if self.process.pid is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(10)
        self.reader.close()
        self.writer.close()
        self.process.close()


@contextmanager
def workers(cases, pauses):
    context = multiprocessing.get_context("spawn")
    children = [Submission(context, case, pause) for case, pause in zip(cases, pauses, strict=True)]
    try:
        for child in children:
            child.start()
        for child in children:
            child.wait("ready")  # Both runtimes loaded before any admission starts.
        yield children
    finally:
        for child in children:
            child.close()


def contended(first, second):
    first.control["start"].set()
    first.wait("paused", "source-locked")
    second.control["start"].set()
    second.wait("blocked", "source")  # Actual SQLITE_BUSY, not a scheduling guess.
    first.control["release"].set()
    first.finish()
    second.finish()


def accepted(child):
    results = [value for kind, value in child.messages if kind == "result"]
    assert len(results) == 1, child.messages
    assert not any(kind == "refusal" for kind, _ in child.messages)
    assert results[0]["workflow_outcome"] == "accepted"
    assert (results[0]["stage"], results[0]["state_version"]) == ("ready", 2)
    return results[0]


def audit(case, originals, expected):
    count, receipts, found, persisted = inspect(case, expected_sources=originals)
    assert count == (expected, expected, expected)
    assert len(receipts) == expected
    assert found["workflow_outcome"] == "accepted"
    for table, size in (
        ("workflow_records", expected),
        ("workflow_event_receipts", expected),
        ("workflow_operations", expected),
        ("workflow_events", expected * 2),
        ("workflow_actions", 0),
    ):
        assert len(persisted[table]) == size
    return receipts, persisted


def replay(case, original):
    before = rows(open_runtime(case)[3])
    _, result = run_child(case)
    assert result == {**original, "source_applied": False, "workflow_applied": False}
    found = lookup(open_runtime(case)[0], case["raw"]).model_dump(mode="json", by_alias=True)
    for field in ("source_receipt", "workflow_record_id", "workflow_event_id", "stage"):
        assert found[field] == original[field]
    assert rows(open_runtime(case)[3]) == before


@pytest.mark.parametrize("kind", ["same", "different", "conflict"])
def test_overlapping_source_identity(make_case, kind):
    first = make_case()
    value = envelope()
    if kind == "different":
        value["payload"]["event_id"] = OTHER
    elif kind == "conflict":
        text = "Conflicting synthetic inquiry"
        value["payload"]["snapshot"]["body"].update(
            text=text,
            stored_chars=len(text),
            source_chars=len(text),
            sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
    second = {**first, "raw": resign(value)}
    parse_untrusted_source(second["raw"])  # A signed conflict, not a malformed body.
    with workers([first, second], ["source-locked", None]) as (a, b):
        contended(a, b)
        winner = accepted(a)
        if kind == "conflict":
            refusals = [value for label, value in b.messages if label == "refusal"]
            assert len(refusals) == 1
            assert refusals[0][0] == "SourceAdmissionConflict"
            assert refusals[0][2:] == (True, True)
            assert not any(label == "result" for label, _ in b.messages)
        else:
            contender = accepted(b)
            expected = 2 if kind == "different" else 1
            for flag in ("source_applied", "workflow_applied"):
                assert sum(result[flag] for result in (winner, contender)) == expected
            for field in ("source_receipt", "workflow_record_id", "workflow_event_id"):
                assert (winner[field] == contender[field]) is (kind == "same")
    originals = [first["raw"], second["raw"]] if kind == "different" else [first["raw"]]
    audit(first, originals, 2 if kind == "different" else 1)
    replay(first, winner)
    if kind != "conflict":
        replay(second, contender)
    else:
        assert winner["source_applied"] and winner["workflow_applied"]


def test_rotated_key_concurrent_replays_keep_original_custody(make_case):
    case = make_case()
    runtime, owner, admission, workflow = open_runtime(case)
    original = admission.admit_source(case["raw"]).receipt
    data = trust_data()
    old = data["key_grants"][0]
    old["status"] = "revoked"
    replacement = deepcopy(old)
    signer = key(bytes(reversed(range(32))))
    replacement.update(
        key_id=OTHER, status="active", public_key=signer.public_key().public_bytes_raw()
    )
    data["key_grants"].append(replacement)
    data["generation"] = 2
    owner.publish_authority(SourceTrustSnapshot.model_validate(data), expected_generation=1)
    value = envelope()
    value["authorization"]["key_id"] = OTHER
    rotated = {**case, "raw": resign(value, signer)}
    with workers([rotated, rotated], ["source-locked", None]) as (a, b):
        contended(a, b)
        results = [accepted(a), accepted(b)]
        assert [r["source_applied"] for r in results] == [False, False]
        assert sorted(r["workflow_applied"] for r in results) == [False, True]
        assert results[0]["source_receipt"] == results[1]["source_receipt"]
        assert results[0]["workflow_record_id"] == results[1]["workflow_record_id"]
        assert results[0]["workflow_event_id"] == results[1]["workflow_event_id"]
    receipts, before = audit(rotated, [case["raw"]], 1)
    assert receipts == [original]
    replay(rotated, results[0])
    with pytest.raises(SourceAuthenticationError):
        submit(runtime, case["raw"])
    assert rows(workflow) == before


def test_different_processes_win_source_and_workflow(make_case):
    case = make_case()
    with workers([case, case], ["source-return", None]) as (a, b):
        a.control["start"].set()
        a.wait("paused", "source-return")
        b.control["start"].set()
        b.finish()  # Must finish while the original submit is still held.
        second = accepted(b)
        assert (second["source_applied"], second["workflow_applied"]) == (False, True)
        assert a.process.is_alive()
        a.control["release"].set()
        a.finish()
        first = accepted(a)
        assert (first["source_applied"], first["workflow_applied"]) == (True, False)
        assert second == {**first, "source_applied": False, "workflow_applied": True}
    audit(case, [case["raw"]], 1)
    replay(case, first)


def test_public_lookup_keeps_snapshot_across_joined_commit(make_case, monkeypatch):
    case = make_case()
    runtime, owner, _, workflow = open_runtime(case)
    native = workflow.read_connection

    def forbidden(*args, **kwargs):
        pytest.fail("historical lookup attempted a source access, write or effect")

    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(workflow, "connection", forbidden)
    monkeypatch.setattr(runtime, "_prepare_source", forbidden)
    monkeypatch.setattr(runtime, "_dispatch_event_actions", forbidden)
    with workers([case], ["workflow-before"]) as (writer,):

        @contextmanager
        def pinned_read():
            with native() as db:  # Existing owner pins its snapshot before yielding.
                writer.control["start"].set()
                writer.wait("paused", "workflow-before")
                assert db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 0
                writer.control["release"].set()
                writer.finish()
                yield db

        with monkeypatch.context() as patch:
            patch.setattr(workflow, "read_connection", pinned_read)
            absent = lookup(runtime, case["raw"])
        result = accepted(writer)
    assert absent.workflow_outcome == "not_found" and absent.source_receipt is None
    before = rows(workflow)
    found = lookup(runtime, case["raw"])
    assert found.workflow_outcome == "accepted" and found.workflow_applied is False
    assert found.workflow_record_id == result["workflow_record_id"]
    assert found.workflow_event_id == result["workflow_event_id"]
    assert found.source_receipt.model_dump(mode="json") == result["source_receipt"]
    assert rows(workflow) == before
    audit(case, [case["raw"]], 1)
