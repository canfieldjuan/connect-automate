"""Joined lifecycle proof through real owners; synthetic content, no effects."""

import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from test_automate_events import event_workflow
from test_automate_runtime import _licensed_host
from test_lead_joined_concurrency import accepted, workers
from test_lead_joined_recovery import BODY, open_runtime, run_child
from test_lead_joined_recovery import make_case as make_case
from test_lead_receipt_vocabulary import workflow as lead_workflow
from test_lead_runtime_results import lookup, signed_workflow, submit
from test_lead_source_admission import counts
from test_lead_source_auth import NOW, encode, envelope, resign
from test_lead_source_content import identity
from test_lead_source_store import database, next_snapshot, store
from test_workflow_receipt_lookup import rows

from connect_automate.automate import AdapterRegistry, PackRuntime
from connect_automate.automate.engine import PackVersionError
from connect_automate.automate.events import EventBindingError, EventConflict, EventInputError
from connect_automate.automate.host import AutomateHost, AutomateLicenseError
from connect_automate.automate.store import WorkflowStore
from connect_automate.lead_intake import (
    SourceAdmission,
    SourceAuthenticationError,
    SourceInputError,
)
from connect_automate.lead_intake.content import SourceContent, SourceContentUnavailable
from connect_automate.lead_intake.source_store import SourceStore


def at(case, now):
    """Reconstruct the real public boundary with an explicit qualified test clock."""
    owner = store(case["source_root"])
    return PackRuntime.load(
        **case["args"],
        host=_licensed_host(case["root"] / uuid4().hex),
        registry=AdapterRegistry.with_defaults(),
        store=WorkflowStore(case["workflow_path"]),
        source_admission=SourceAdmission(owner, clock=lambda: now),
        source_clock=lambda: now,
    )


def source_rows(case):
    # Test oracle only; never substitute it for the production historical reader.
    with database(store(case["source_root"]).path) as db:
        names = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {
            name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
            for (name,) in names
        }


def workflow_rows(case, expected):
    persisted = rows(WorkflowStore(case["workflow_path"]))
    assert len(persisted["workflow_records"]) == expected
    assert len(persisted["workflow_event_receipts"]) == expected
    assert persisted["workflow_actions"] == []
    assert BODY not in json.dumps(persisted, default=str)
    if not expected:
        assert persisted["workflow_operations"] == []
        assert persisted["workflow_events"] == []
    return persisted


def deadline(case):
    return datetime.fromisoformat(
        json.loads(case["raw"])["payload"]["retention"]["recovery_deadline"]
    )


def revoke(owner):
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)


def change(case, kind, receipt=None):
    """Apply lifecycle only through its existing owner; return the active clock."""
    owner = store(case["source_root"])
    now = deadline(case) if kind in {"expiry", "cleanup"} else NOW
    content = SourceContent(owner, clock=lambda: now)
    if kind == "revoke":
        revoke(owner)
    elif kind == "expiry":
        with pytest.raises(SourceContentUnavailable):
            content.read_content(receipt.admission_id)
    elif kind == "cleanup":
        assert content.cleanup_expired(limit=1) == 1
        assert content.cleanup_expired(limit=1) == 0
    elif kind == "purge":
        assert content.purge_message(identity(), cutoff=NOW)
    elif kind in {"retire", "retired-cleanup"}:
        assert content.retire_namespace(identity().namespace_id)
        if kind == "retired-cleanup":
            assert content.cleanup_retired(identity().namespace_id, limit=1) == 1
            assert content.cleanup_retired(identity().namespace_id, limit=1) == 0
    else:
        pytest.fail(f"unknown lifecycle: {kind}")
    return now


def original(found, result):
    actual = found.model_dump(mode="json", by_alias=True)
    assert actual["workflow_applied"] is False
    assert "source_applied" not in actual
    for field in (
        "source_receipt",
        "workflow_record_id",
        "workflow_event_id",
        "workflow_outcome",
        "stage",
        "state_version",
    ):
        assert actual[field] == result[field]
    assert BODY not in json.dumps(actual)


@contextmanager
def history(case, monkeypatch):
    """Load without source configuration, then forbid all admission/effect paths."""
    source_before = source_rows(case)
    owner = WorkflowStore(case["workflow_path"])
    before = rows(owner)

    def forbidden(*a, **kw):
        pytest.fail("historical lookup touched source, clock, writer or dispatch")

    with monkeypatch.context() as patch:
        patch.setattr(SourceStore, "_transaction", forbidden)
        patch.setattr(SourceStore, "_check_clock", forbidden)
        patch.setattr(SourceStore, "_record_clock", forbidden)
        patch.setattr(SourceAdmission, "admit_source", forbidden)
        patch.setattr(SourceAdmission, "deployment", property(forbidden))
        runtime = PackRuntime.load(
            **case["args"],
            store=owner,
            host=_licensed_host(case["root"] / uuid4().hex),
            registry=AdapterRegistry.with_defaults(),
        )
        # Pack load registers the existing binding. The read itself cannot write.
        assert rows(owner) == before
        patch.setattr(WorkflowStore, "connection", forbidden)
        patch.setattr(WorkflowStore, "admit_event", forbidden)
        patch.setattr(PackRuntime, "_prepare_source", forbidden)
        patch.setattr(PackRuntime, "_dispatch_event_actions", forbidden)
        yield runtime
        assert rows(owner) == before
    assert source_rows(case) == source_before


@pytest.fixture(autouse=True)
def private_outputs(caplog, capsys):
    yield
    captured = capsys.readouterr()
    assert BODY not in caplog.text + captured.out + captured.err


@pytest.mark.parametrize("state", ["available", "unavailable"])
@pytest.mark.parametrize("reason", ["revoke", "deadline"])
def test_source_only_crash_cannot_recover_without_current_authority(
    make_case, monkeypatch, state, reason
):
    case = make_case(state)
    run_child(case, "source-after", "crash")
    owner = store(case["source_root"])
    assert counts(owner) == (1, 1, 1)
    workflow_rows(case, 0)
    if reason == "revoke":
        revoke(owner)
    now = deadline(case) if reason == "deadline" else NOW
    before = source_rows(case)
    with pytest.raises(SourceAuthenticationError) as caught:
        submit(at(case, now), case["raw"])
    assert caught.value.args == ("lead source authentication rejected",)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert source_rows(case) == before
    workflow_rows(case, 0)
    with history(case, monkeypatch) as runtime:
        found = lookup(runtime, case["raw"])
        assert found.workflow_outcome == "not_found"
        assert found.source_receipt is None and found.workflow_record_id is None
        assert (
            found.workflow_event_id is None and found.stage is None and found.state_version is None
        )


@pytest.mark.parametrize("state", ["available", "unavailable"])
def test_source_only_crash_recovers_just_before_deadline(make_case, monkeypatch, state):
    case = make_case(state)
    run_child(case, "source-after", "crash")
    before = source_rows(case)["source_receipts"]
    now = deadline(case) - timedelta(microseconds=1)
    result = submit(at(case, now), case["raw"])
    assert not result.source_applied and result.workflow_applied
    assert result.workflow_outcome == "accepted"
    assert source_rows(case)["source_receipts"] == before
    workflow_rows(case, 1)
    with history(case, monkeypatch) as runtime:
        original(lookup(runtime, case["raw"]), result.model_dump(mode="json", by_alias=True))


def test_copied_authority_cannot_recover_revoked_source(make_case, monkeypatch):
    case = make_case()
    runtime, owner, admission, _ = open_runtime(case)
    result = admission.admit_source(case["raw"])
    prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=case["raw"])
    serialized_event = encode(prepared.event.model_dump())
    revoke(owner)
    before = source_rows(case)
    for copied in (result, result.receipt, prepared, serialized_event):
        with pytest.raises(SourceInputError) as caught:
            submit(runtime, copied)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
    with pytest.raises(EventInputError):
        runtime.submit_event(binding="inbox", event=serialized_event, now=NOW)
    with pytest.raises(SourceAuthenticationError):
        submit(runtime, case["raw"])
    assert source_rows(case) == before
    workflow_rows(case, 0)
    with history(case, monkeypatch) as historical:
        assert lookup(historical, case["raw"]).workflow_outcome == "not_found"


@pytest.mark.parametrize(
    "kind", ["revoke", "expiry", "cleanup", "purge", "retire", "retired-cleanup"]
)
def test_historical_outcome_survives_source_lifecycle(make_case, monkeypatch, kind):
    case = make_case()
    _, result = run_child(case)
    before = workflow_rows(case, 1)
    receipt = lookup(open_runtime(case)[0], case["raw"]).source_receipt
    now = change(case, kind, receipt)
    owner = store(case["source_root"])
    content = SourceContent(owner, clock=lambda: now)
    if kind == "revoke":
        assert content.read_content(receipt.admission_id) == case["raw"]
    else:
        with pytest.raises(SourceContentUnavailable):
            content.read_content(receipt.admission_id)
    with pytest.raises(SourceAuthenticationError):
        submit(at(case, now), case["raw"])
    expected = (0, 0, 0) if kind == "retired-cleanup" else (1, int(kind in {"revoke", "retire"}), 1)
    assert counts(owner) == expected
    with history(case, monkeypatch) as runtime:
        original(lookup(runtime, case["raw"]), result)
    assert workflow_rows(case, 1) == before


@pytest.mark.parametrize("kind", ["revoke", "purge", "retire"])
@pytest.mark.parametrize("order", ["lifecycle-first", "source-first"])
def test_lifecycle_order_at_final_source_boundary(make_case, monkeypatch, kind, order):
    case = make_case()
    pause = "source-return" if order == "source-first" else None
    with workers([case], [pause]) as (child,):
        if order == "source-first":
            child.control["start"].set()
            child.wait("paused", "source-return")
            assert counts(store(case["source_root"])) == (1, 1, 1)
        workflow_rows(case, 0)
        change(case, kind)  # Must finish while submitter is held, without its source lock.
        assert child.process.is_alive()
        after_lifecycle = source_rows(case)
        child.control["start"].set()
        child.control["release"].set()
        child.finish()
        if order == "source-first":
            result = accepted(child)
            assert result["source_applied"] and result["workflow_applied"]
        else:
            refusal = [value for label, value in child.messages if label == "refusal"]
            assert refusal == [
                ("SourceAuthenticationError", ("lead source authentication rejected",), True, True)
            ]
            assert not any(label == "result" for label, _ in child.messages)
    assert source_rows(case) == after_lifecycle
    workflow_rows(case, int(order == "source-first"))
    with history(case, monkeypatch) as runtime:
        found = lookup(runtime, case["raw"])
        if order == "source-first":
            original(found, result)
        else:
            assert found.workflow_outcome == "not_found" and found.source_receipt is None


def test_late_purge_preserves_later_capture_and_all_historical_outcomes(make_case, monkeypatch):
    base = make_case()
    cutoff = NOW - timedelta(minutes=1)
    cases, results = [], []
    # Both sides of the cutoff, equality, and a different message at the cutoff.
    for offset, message in ((-1, None), (0, None), (1, None), (0, "unrelated")):
        value = envelope()
        stamp = (
            (cutoff + timedelta(seconds=offset))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        value["payload"]["event_id"] = str(uuid4())
        value["payload"]["occurred_at"] = stamp
        value["payload"]["snapshot"]["captured_at"] = stamp
        if message:
            value["payload"]["source"]["message_id"] = message
        case = {**base, "raw": resign(value)}
        _, result = run_child(case)
        cases.append(case)
        results.append(result)
    before = workflow_rows(base, 4)
    owner = store(base["source_root"])
    receipts = source_rows(base)["source_receipts"]
    content = SourceContent(owner, clock=lambda: NOW)
    assert content.purge_message(identity(), cutoff=cutoff)
    assert not content.purge_message(identity(), cutoff=cutoff)
    assert counts(owner) == (4, 2, 4)
    assert source_rows(base)["source_receipts"] == receipts
    for index, (case, result) in enumerate(zip(cases, results, strict=True)):
        admission_id = result["source_receipt"]["admission_id"]
        if index < 2:
            with pytest.raises(SourceContentUnavailable):
                content.read_content(admission_id)
            with pytest.raises(SourceAuthenticationError):
                submit(open_runtime(case)[0], case["raw"])
        else:
            assert content.read_content(admission_id) == case["raw"]
            replay = submit(open_runtime(case)[0], case["raw"])
            assert not replay.source_applied and not replay.workflow_applied
        with history(case, monkeypatch) as runtime:
            original(lookup(runtime, case["raw"]), result)
    assert workflow_rows(base, 4) == before


def test_original_metadata_and_refusals_after_advancement_and_erasure(make_case, monkeypatch):
    case = make_case()
    value = lead_workflow()
    value["definitions"].append(event_workflow()["definitions"][1])
    signed_workflow(case["args"], value)
    _, result = run_child(case)
    runtime, _, _, workflow = open_runtime(case)
    runtime.submit_decision(
        result["workflow_record_id"],
        decision="approve",
        operation_key="later",
        request={},
        expected_version=result["state_version"],
        now=NOW,
    )
    assert workflow.get_record(result["workflow_record_id"]).stage == "completed"
    change(case, "retired-cleanup")
    assert counts(store(case["source_root"])) == (0, 0, 0)
    before = workflow_rows(case, 1)
    with history(case, monkeypatch) as historical:
        original(lookup(historical, case["raw"]), result)
        with pytest.raises(EventConflict):
            lookup(historical, case["raw"], expected_payload_digest="b" * 64)
        for bad in (False, 0, "", "missing"):
            with pytest.raises(EventBindingError):
                lookup(historical, case["raw"], binding=bad)
        with monkeypatch.context() as patch:
            patch.setattr(AutomateHost, "licensed", lambda self: False)
            with pytest.raises(AutomateLicenseError):
                lookup(historical, case["raw"])
    upgraded = {**case, "args": deepcopy(case["args"])}
    signed_workflow(upgraded["args"], value, version=2)
    with history(upgraded, monkeypatch) as historical, pytest.raises(PackVersionError):
        lookup(historical, case["raw"])
    assert workflow_rows(case, 1) == before
