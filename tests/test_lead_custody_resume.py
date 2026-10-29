"""Reference-only runtime composition through real source and workflow owners."""

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from test_lead_custody_composition import composition, forbidden, prepare
from test_lead_custody_composition import managed as managed
from test_lead_custody_retained_read import BINDINGS, envelope_probe
from test_lead_custody_store import (
    RESERVATION,
    managed_operation,
    reader,
    rewrite_request,
    snapshot,
)
from test_lead_host_composition import setup as setup
from test_lead_source_admission import counts
from test_lead_source_auth import NOW, OTHER, envelope
from test_lead_source_store import next_snapshot, store
from test_lead_source_store import private_root as private_root
from test_workflow_receipt_lookup import rows

from connect_automate.automate import PackRuntime
from connect_automate.automate.events import EventBindingError
from connect_automate.automate.host import AutomateHost, AutomateLicenseError
from connect_automate.lead_intake import SourceAuthenticationError, SourceHandoffUnknown
from connect_automate.lead_intake.content import SourceContent, SourceContentUnavailable
from connect_automate.lead_intake.custody_protocol import ResumeRequest
from connect_automate.lead_intake.source_store import (
    SourceClockAdmin,
    SourceStoreBusy,
    SourceStoreConflict,
    SourceStoreUnavailable,
    SourceStoreUncertain,
)


def resumed(intent, upload, generation=1):
    return managed_operation(intent, "resume", upload.payload.capture.model_dump(), generation)


def test_closed_source_only_gap_resumes_after_reopen(managed):
    args, owner, _, access, intent, upload, raw = managed
    original = access.admit_bound(upload, raw)
    access.close_admission(managed_operation(intent, "settle"))
    assert rows(args["store"])["workflow_event_receipts"] == []
    reopened = reader(store(owner.root), clock=lambda: NOW)
    handoff = composition(PackRuntime.load(**args), reopened, intent)
    result = handoff.resume(request=resumed(intent, upload, 2))
    assert result.workflow_outcome == "accepted"
    assert result.source_applied is False and result.workflow_applied is True
    assert result.source_receipt.admission_id == original.receipt.admission_id


@pytest.fixture
def custodied(managed):
    args, owner, runtime, access, intent, upload, raw = managed
    admitted = access.admit_bound(upload, raw)
    return SimpleNamespace(
        args=args,
        owner=owner,
        runtime=runtime,
        access=access,
        intent=intent,
        upload=upload,
        raw=raw,
        admitted=admitted,
        request=resumed(intent, upload),
        handoff=composition(runtime, access, intent),
    )


@pytest.mark.parametrize("state", ["complete", "truncated", "unknown", "unavailable"])
@pytest.mark.parametrize("closed", [False, True])
def test_body_states_expired_reservation_and_replay(setup, state, closed):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    value = envelope()
    body = value["payload"]["snapshot"]["body"]
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = dict(state=state, reason="source_gone")
    else:
        body["completeness"] = state
        body["source_chars"] = (
            None if state == "unknown" else body["stored_chars"] + int(state == "truncated")
        )
    intent, upload, raw = prepare(runtime, access, value)
    original = access.admit_bound(upload, raw)
    if closed:
        access.close_admission(managed_operation(intent, "settle"))
    before = snapshot(owner)
    late = datetime.fromisoformat(RESERVATION)
    reopened = reader(store(owner.root), clock=lambda: late)
    handoff = composition(PackRuntime.load(**args), reopened, intent, clock=lambda: late)
    request = resumed(intent, upload, 2 if closed else 1)
    first = handoff.resume(request=request)
    replay = handoff.resume(request=request.model_copy(deep=True))
    assert first.workflow_outcome == "accepted" and first.workflow_applied
    assert not first.source_applied and first.actions == []
    assert first.source_receipt.admission_id == original.receipt.admission_id
    assert replay == first.model_copy(update={"workflow_applied": False})
    after = snapshot(owner)
    assert {k: v for k, v in after.items() if k != "authority_clock_history"} == {
        k: v for k, v in before.items() if k != "authority_clock_history"
    }
    assert counts(owner) == (1, 1, 1)
    assert raw.decode() not in repr(rows(args["store"])) + repr(first)


@pytest.mark.parametrize("phase", ["missing", "prepared", "bound", "closed-empty"])
def test_no_observed_receipt_is_unavailable_not_permanent_absence(setup, monkeypatch, phase):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    intent, upload, raw = prepare(
        runtime, access, phase="bound" if phase == "closed-empty" else phase
    )
    if phase == "closed-empty":
        access.close_admission(managed_operation(intent, "settle"))
    handoff = composition(runtime, access, intent)
    before = snapshot(owner)
    with monkeypatch.context() as patch:
        patch.setattr(access, "read_retained", forbidden)
        # A prepared-only handoff cannot match the supplied bound capture yet.
        with pytest.raises(
            SourceStoreConflict if phase == "prepared" else SourceContentUnavailable
        ):
            handoff.resume(request=resumed(intent, upload))
    assert snapshot(owner) == before and rows(args["store"])["workflow_records"] == []
    if phase == "bound":
        access.admit_bound(upload, raw)
        assert handoff.resume(request=resumed(intent, upload)).workflow_applied


@pytest.mark.parametrize("path,value", BINDINGS, ids=[p[-1] for p, _ in BINDINGS])
def test_full_binding_before_envelope(custodied, monkeypatch, path, value):
    c = custodied
    wrong = rewrite_request(c.request, path, value)
    expected = (
        EventBindingError
        if path
        in (
            ["scope", "host_id"],
            ["scope", "organization_id"],
            ["scope", "namespace_id"],
            ["scope", "route_digest"],
            ["enrolled_machine_id"],
        )
        else SourceStoreConflict
    )
    seen = envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(expected):
        c.handoff.resume(request=wrong)
    assert seen == [] and rows(c.args["store"])["workflow_records"] == []


@pytest.mark.parametrize("kind", ["prepare", "upload", "status", "settle"])
def test_exact_operation_is_required_at_both_entries(custodied, monkeypatch, kind):
    c = custodied
    wrong = (
        c.intent
        if kind == "prepare"
        else c.upload
        if kind == "upload"
        else managed_operation(c.intent, kind)
    )
    monkeypatch.setattr(c.access, "observe", forbidden)
    for call in (c.handoff.resume, c.handoff._prepare_resume):
        with pytest.raises(EventBindingError):
            call(request=wrong)
    # A copied ResumeRequest whose discriminator says upload cannot exploit its type.
    with pytest.raises(EventBindingError):
        c.handoff.resume(request=c.request.model_copy(update={"operation": "upload"}))


@pytest.mark.parametrize("value", [None, False, "", 0, -1, 2147483648])
def test_falsy_and_out_of_range_generation_before_source(custodied, monkeypatch, value):
    c = custodied
    monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.resume(request=c.request.model_copy(update={"expected_fence_generation": value}))


@pytest.mark.parametrize("value", [1, 2147483647])
def test_valid_generation_boundary_and_canonical_consumer(custodied, monkeypatch, value):
    c = custodied
    request = c.request.model_copy(update={"expected_fence_generation": value})
    seen = []

    def observed(**kwargs):
        seen.append(kwargs)
        return None

    monkeypatch.setattr(c.access, "observe", observed)
    checked = c.handoff._checked_request(request, ResumeRequest)
    assert checked == request and checked is not request
    with pytest.raises(SourceContentUnavailable):
        c.handoff.resume(request=request)
    assert seen[0]["scope"] == request.scope and seen[0]["scope"] is not request.scope
    assert seen[0]["capture"] == request.payload.capture
    assert seen[0]["capture"] is not request.payload.capture


@pytest.mark.parametrize(
    "field,value", [("payload", {}), ("job_id", False), ("control_id", ""), ("scope", {})]
)
def test_partial_or_mixed_copied_value_never_reaches_source(custodied, monkeypatch, field, value):
    c = custodied
    monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.resume(request=c.request.model_copy(update={field: value}))


def test_request_only_surface_and_no_legacy_or_admission_fallback(custodied, monkeypatch):
    c = custodied
    assert list(inspect.signature(c.handoff.resume).parameters) == ["request"]
    monkeypatch.setattr(c.access, "admit_bound", forbidden)
    monkeypatch.setattr(c.runtime, "_prepare_source", forbidden)
    monkeypatch.setattr(SourceContent, "read_content", forbidden)
    original = c.access.revalidate_existing
    calls = []

    def revalidate(request, raw, *, admission_id):
        calls.append((request, raw, admission_id))
        assert request is not c.request and raw == c.raw
        return original(request, raw, admission_id=admission_id)

    monkeypatch.setattr(c.access, "revalidate_existing", revalidate)
    assert c.handoff.resume(request=c.request).workflow_applied
    assert not c.handoff.resume(request=c.request).workflow_applied
    assert len(calls) == 2
    assert all(call[2] == c.admitted.receipt.admission_id for call in calls)
    c.owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    with pytest.raises(SourceAuthenticationError):
        c.handoff.resume(request=c.request)
    assert len(calls) == 3


@pytest.mark.parametrize(
    "field,value",
    [("applied", True), ("applied", 0), ("content_state", "purged"), ("receipt", None)],
)
def test_each_fresh_owner_result_guard(custodied, monkeypatch, field, value):
    c = custodied
    original = c.access.revalidate_existing
    # Only extra receipt metadata changes: the shared event projection would accept it.
    if field == "receipt":
        value = c.admitted.receipt.model_copy(update={"key_id": OTHER})

    def inconsistent(*args, **kwargs):
        return original(*args, **kwargs).model_copy(update={field: value})

    monkeypatch.setattr(c.access, "revalidate_existing", inconsistent)
    with pytest.raises(SourceHandoffUnknown) as failure:
        c.handoff.resume(request=c.request)
    assert failure.value.__cause__ is None and failure.value.__context__ is None
    assert rows(c.args["store"])["workflow_records"] == []


def mutate(c, kind):
    content = SourceContent(c.owner, clock=lambda: NOW)
    if kind == "close":
        c.access.close_admission(managed_operation(c.intent, "settle"))
    elif kind == "revoke":
        c.owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    elif kind == "purge":
        content.purge_message(c.intent.payload.source, cutoff=NOW)
    elif kind == "retire":
        content.retire_namespace(c.intent.scope.namespace_id)
    elif kind == "expiry":
        deadline = datetime.fromisoformat(c.request.payload.capture.recovery_deadline)
        assert SourceContent(c.owner, clock=lambda: deadline).cleanup_expired(limit=1) == 1
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["close", "revoke", "purge", "retire", "expiry"])
@pytest.mark.parametrize("after", ["observe", "read_retained", "revalidate_existing"])
def test_stale_metadata_and_authorization_linearization(custodied, monkeypatch, kind, after):
    c = custodied
    original = getattr(c.access, after)

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        mutate(c, kind)
        return result

    monkeypatch.setattr(c.access, after, changed)
    if after == "revalidate_existing":
        assert c.handoff.resume(request=c.request).workflow_applied
    else:
        # No exception normalization: earlier snapshot/read is not current authority.
        with pytest.raises(SourceAuthenticationError):
            c.handoff.resume(request=c.request)
        assert rows(c.args["store"])["workflow_records"] == []


def test_observed_receipt_cannot_replace_current_link(custodied, monkeypatch):
    from dataclasses import replace

    c = custodied
    original = c.access.observe

    def stale(**kwargs):
        facts = original(**kwargs)
        return replace(facts, receipt=facts.receipt.model_copy(update={"admission_id": OTHER}))

    monkeypatch.setattr(c.access, "observe", stale)
    with pytest.raises(SourceAuthenticationError):
        c.handoff.resume(request=c.request)
    assert rows(c.args["store"])["workflow_records"] == []


@pytest.mark.parametrize("after_read", [False, True])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_deadline_boundary_and_no_automatic_generation_refresh(
    custodied, monkeypatch, after_read, offset
):
    c = custodied
    at = datetime.fromisoformat(c.request.payload.capture.recovery_deadline) + timedelta(
        microseconds=offset
    )
    if after_read:
        original = c.access.read_retained

        def late(request):
            raw = original(request)
            monkeypatch.setattr(c.access, "_clock", lambda: at)
            return raw

        monkeypatch.setattr(c.access, "read_retained", late)
    else:
        monkeypatch.setattr(c.access, "_clock", lambda: at)
    if offset < 0:
        assert c.handoff.resume(request=c.request).workflow_applied
        return
    with pytest.raises(SourceAuthenticationError if after_read else SourceContentUnavailable):
        c.handoff.resume(request=c.request)
    assert rows(c.args["store"])["workflow_records"] == []
    assert bool(snapshot(c.owner)["source_content"]) is after_read
    if not after_read:
        from uuid import uuid4

        admin = SourceClockAdmin(c.owner)
        admin.reconcile(
            operation_id=str(uuid4()), expected_sequence=admin.read().sequence, corrected_at=NOW
        )
        monkeypatch.setattr(c.access, "_clock", lambda: NOW)
        with pytest.raises(SourceContentUnavailable):
            c.handoff.resume(request=resumed(c.intent, c.upload, 2))


@pytest.mark.parametrize("after_read", [False, True])
def test_backward_clock_refuses_without_workflow(custodied, monkeypatch, after_read):
    c = custodied
    original = c.access.read_retained

    def late():
        return NOW - timedelta(seconds=1)

    if after_read:

        def read(request):
            raw = original(request)
            monkeypatch.setattr(c.access, "_clock", late)
            return raw

        monkeypatch.setattr(c.access, "read_retained", read)
    else:
        monkeypatch.setattr(c.access, "_clock", late)
    with pytest.raises(SourceAuthenticationError):
        c.handoff.resume(request=c.request)
    assert counts(c.owner) == (1, 1, 1) and rows(c.args["store"])["workflow_records"] == []


@pytest.mark.parametrize("method", ["observe", "read_retained", "revalidate_existing"])
@pytest.mark.parametrize(
    "error", [SourceStoreBusy, SourceStoreUnavailable, SourceStoreUncertain, RuntimeError]
)
def test_source_error_classification_and_sanitization(custodied, monkeypatch, method, error):
    c = custodied

    def failing(*args, **kwargs):
        raise error("synthetic-private-marker") if error is RuntimeError else error()

    monkeypatch.setattr(c.access, method, failing)
    expected = SourceStoreBusy if error is SourceStoreBusy else SourceHandoffUnknown
    with pytest.raises(expected) as failure:
        c.handoff.resume(request=c.request)
    assert failure.value.__context__ is None and failure.value.__cause__ is None
    assert "synthetic-private-marker" not in str(failure.value)
    assert rows(c.args["store"])["workflow_records"] == []


@pytest.mark.parametrize("after", [False, True])
@pytest.mark.parametrize("drift", ["license", "binding", "store", "incarnation"])
def test_runtime_pins_rechecked_before_read_and_workflow(custodied, monkeypatch, after, drift):
    c = custodied

    def change():
        if drift == "license":
            monkeypatch.setattr(AutomateHost, "licensed", lambda self: False)
        elif drift == "binding":
            monkeypatch.setattr(c.runtime, "_event_bindings", {})
        elif drift == "store":
            monkeypatch.setattr(c.access, "_store", store(c.owner.root))
        else:
            monkeypatch.setattr(c.access, "_incarnation", OTHER)

    if after:
        original = c.access.revalidate_existing

        def revalidate(*args, **kwargs):
            result = original(*args, **kwargs)
            change()
            return result

        monkeypatch.setattr(c.access, "revalidate_existing", revalidate)
    else:
        change()
        monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(AutomateLicenseError if drift == "license" else EventBindingError):
        c.handoff.resume(request=c.request)
    assert rows(c.args["store"])["workflow_records"] == []


@pytest.mark.parametrize("entry", ["_resume_custody_source", "_submit_source"])
@pytest.mark.parametrize("kind", ["proxy", "other-runtime"])
def test_runtime_concrete_owner_and_runtime_identity(custodied, entry, kind):
    c = custodied

    class Proxy:
        def __getattr__(self, name):
            return getattr(c.handoff, name)

    runtime = c.runtime if kind == "proxy" else PackRuntime.load(**c.args)
    options = dict(custody=Proxy() if kind == "proxy" else c.handoff, request=c.request)
    if entry == "_submit_source":
        options["binding"] = "inbox"
    with pytest.raises(EventBindingError):
        getattr(runtime, entry)(**options)


def test_no_raw_or_wrong_binding_on_shared_resume_entry(custodied, monkeypatch):
    c = custodied
    monkeypatch.setattr(c.access, "observe", forbidden)
    for options in (dict(binding="elsewhere"), dict(binding="inbox", raw_source_bytes=c.raw)):
        with pytest.raises(EventBindingError):
            c.runtime._submit_source(custody=c.handoff, request=c.request, **options)
    with pytest.raises(EventBindingError):
        c.handoff.submit(request=c.request, raw_source_bytes=None)


@pytest.mark.parametrize("kind", ["proxy", "runtime", "operation"])
def test_resume_entry_guards_before_shared_dispatch(custodied, monkeypatch, kind):
    c = custodied

    class Proxy:
        def __getattr__(self, name):
            return getattr(c.handoff, name)

    runtime = PackRuntime.load(**c.args) if kind == "runtime" else c.runtime
    monkeypatch.setattr(runtime, "_submit_source", forbidden)
    with pytest.raises(EventBindingError):
        runtime._resume_custody_source(
            custody=Proxy() if kind == "proxy" else c.handoff,
            request=c.upload if kind == "operation" else c.request,
        )


def test_upload_entry_guard_before_shared_dispatch(custodied, monkeypatch):
    c = custodied
    monkeypatch.setattr(c.runtime, "_submit_source", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.submit(request=c.request, raw_source_bytes=None)


def test_parsed_retained_source_scope_before_revalidation(custodied, monkeypatch):
    from test_lead_source_auth import resign

    c = custodied
    value = envelope()
    value["authorization"]["host_id"] = OTHER
    monkeypatch.setattr(c.access, "read_retained", lambda request: resign(value))
    monkeypatch.setattr(c.access, "revalidate_existing", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.resume(request=c.request)


def test_no_source_lock_crosses_workflow_owner(custodied, monkeypatch):
    from test_lead_source_store import database

    c = custodied
    original = c.runtime._engine._admit_event

    def complete(*args, **kwargs):
        with database(c.owner.path) as db:
            db.execute("PRAGMA busy_timeout=0")
            db.execute("BEGIN IMMEDIATE")
            db.rollback()
        return original(*args, **kwargs)

    monkeypatch.setattr(c.runtime._engine, "_admit_event", complete)
    assert c.handoff.resume(request=c.request).workflow_applied


def test_durable_no_match_uses_same_completion(custodied):
    from test_lead_host_composition import seed_workflow

    c = custodied
    prepared = c.handoff._prepare_resume(c.request)
    seed_workflow(c.args, prepared, matched=False)
    for _ in range(2):
        result = c.handoff.resume(request=c.request)
        assert result.workflow_outcome == "no_match"
        assert not result.workflow_applied and not result.source_applied
        assert result.workflow_record_id is None and result.workflow_event_id is None
        assert result.actions == []


def test_replay_preserves_original_workflow_identity_after_advancement(setup):
    from test_automate_events import event_workflow
    from test_lead_receipt_vocabulary import workflow
    from test_lead_runtime_results import signed_workflow

    args, owner, _ = setup
    value = workflow()
    value["definitions"].append(event_workflow()["definitions"][1])
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    intent, upload, raw = prepare(runtime, access)
    access.admit_bound(upload, raw)
    handoff = composition(runtime, access, intent)
    request = resumed(intent, upload)
    first = handoff.resume(request=request)
    runtime.submit_decision(
        first.workflow_record_id,
        decision="approve",
        operation_key="later",
        request={},
        expected_version=first.state_version,
        now=NOW,
    )
    assert args["store"].get_record(first.workflow_record_id).stage == "completed"
    assert handoff.resume(request=request) == first.model_copy(update={"workflow_applied": False})


@pytest.mark.parametrize("kind", ["revoke", "purge", "retire", "expiry"])
def test_history_is_readable_without_resuming_source(custodied, monkeypatch, kind):
    c = custodied
    first = c.handoff.resume(request=c.request)
    mutate(c, kind)
    before = rows(c.args["store"])
    with pytest.raises((SourceAuthenticationError, SourceContentUnavailable)):
        c.handoff.resume(request=c.request)
    monkeypatch.setattr(c.owner, "_transaction", forbidden)
    monkeypatch.setattr(c.owner, "_read_snapshot", forbidden)
    monkeypatch.setattr(c.access, "read_retained", forbidden)
    monkeypatch.setattr(c.runtime, "_dispatch_event_actions", forbidden)
    found = c.runtime.lookup_source_outcome(
        binding="inbox",
        event_id=c.request.scope.event_id,
        expected_payload_digest=c.request.payload.capture.payload_digest,
    )
    assert found.workflow_outcome == "accepted" and not found.workflow_applied
    assert found.source_receipt == first.source_receipt
    assert found.workflow_event_id == first.workflow_event_id
    assert rows(c.args["store"]) == before


@pytest.mark.parametrize("phase", ["read", "revalidate"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_final_sample_expiry_preserves_owner_semantics(custodied, monkeypatch, phase, offset):
    from itertools import chain, repeat

    c = custodied
    at = datetime.fromisoformat(c.request.payload.capture.recovery_deadline) + timedelta(
        microseconds=offset
    )
    times = iter(chain([NOW] if phase == "read" else [NOW, NOW, NOW], repeat(at)))
    monkeypatch.setattr(c.access, "_clock", times.__next__)
    if offset < 0:
        assert c.handoff.resume(request=c.request).workflow_applied
    else:
        with pytest.raises(
            SourceContentUnavailable if phase == "read" else SourceAuthenticationError
        ):
            c.handoff.resume(request=c.request)
        assert bool(snapshot(c.owner)["source_content"]) is (phase == "revalidate")
        assert rows(c.args["store"])["workflow_records"] == []


def test_late_cutoff_preserves_newer_capture_and_other_message(custodied):
    from uuid import uuid4

    c = custodied
    requests = [c.request]
    for kind in ("same-message", "newer", "other-message"):
        value = envelope()
        value["payload"]["event_id"] = str(uuid4())
        if kind == "newer":
            value["payload"]["snapshot"]["captured_at"] = "2026-10-18T12:00:01Z"
            value["payload"]["occurred_at"] = "2026-10-18T12:00:01Z"
        if kind == "other-message":
            value["payload"]["source"]["message_id"] = "other-message"
        intent, upload, raw = prepare(c.runtime, c.access, value)
        c.access.admit_bound(upload, raw)
        requests.append(resumed(intent, upload))
    SourceContent(c.owner, clock=lambda: NOW).purge_message(
        c.intent.payload.source,
        cutoff=datetime.fromisoformat(c.request.payload.capture.captured_at),
    )
    for request in requests[:2]:
        with pytest.raises(SourceContentUnavailable):
            c.handoff.resume(request=request.model_copy(update={"expected_fence_generation": 2}))
    for request in requests[2:]:
        assert c.handoff.resume(request=request).workflow_applied
    assert len(rows(c.args["store"])["workflow_records"]) == 2
