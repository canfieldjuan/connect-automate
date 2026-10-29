"""Lookup-first recovery through concrete source and workflow owners."""

import inspect
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime

import pytest
from test_lead_custody_composition import composition, forbidden, prepare
from test_lead_custody_composition import managed as managed
from test_lead_custody_resume import custodied as custodied
from test_lead_custody_resume import mutate, resumed
from test_lead_custody_retained_read import BINDINGS, envelope_probe
from test_lead_custody_store import (
    RESERVATION,
    managed_operation,
    reader,
    rewrite_request,
    snapshot,
)
from test_lead_host_composition import seed_workflow
from test_lead_host_composition import setup as setup
from test_lead_source_auth import NOW, OTHER, envelope
from test_lead_source_store import next_snapshot, store
from test_lead_source_store import private_root as private_root
from test_workflow_receipt_lookup import rows

from connect_automate.automate import PackRuntime
from connect_automate.automate.engine import PackVersionError
from connect_automate.automate.events import EventBindingError, EventConflict, EventInputError
from connect_automate.automate.host import AutomateLicenseError
from connect_automate.lead_intake import SourceAuthenticationError, SourceHandoffUnknown
from connect_automate.lead_intake.content import SourceContent, SourceContentUnavailable
from connect_automate.lead_intake.custody_handoff import _CustodyHandoff
from connect_automate.lead_intake.results import SourceHandoffLookup, SourceHandoffResult
from connect_automate.lead_intake.source_store import (
    SourceStoreBusy,
    SourceStoreConflict,
    SourceStoreInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
)


def test_lost_response_reopens_revoked_history_without_authority(custodied, monkeypatch):
    c = custodied

    def lost(**kwargs):
        raise RuntimeError("synthetic response loss after workflow commit")

    with monkeypatch.context() as patch:
        patch.setattr(c.runtime, "_lookup_source_receipt", lost)
        with pytest.raises(SourceHandoffUnknown):
            c.handoff.resume(request=c.request)
    assert len(rows(c.args["store"])["workflow_event_receipts"]) == 1
    c.owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    owner = store(c.owner.root)
    access = reader(owner, clock=lambda: NOW)
    runtime = PackRuntime.load(**c.args)
    handoff = composition(runtime, access, c.intent)
    # The earlier entry still requires current authentication, even on replay.
    with pytest.raises(SourceAuthenticationError):
        handoff.resume(request=c.request)
    expected = runtime.lookup_source_outcome(
        binding="inbox",
        event_id=c.request.scope.event_id,
        expected_payload_digest=c.request.payload.capture.payload_digest,
    )
    before = snapshot(owner), rows(c.args["store"])
    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(access, "read_retained", forbidden)
    monkeypatch.setattr(access, "revalidate_existing", forbidden)
    monkeypatch.setattr(access, "_clock", forbidden)
    monkeypatch.setattr(runtime, "_dispatch_event_actions", forbidden)
    monkeypatch.setattr(c.args["store"], "connection", forbidden)
    monkeypatch.setattr(_CustodyHandoff, "resume", forbidden)
    result = handoff.recover(request=c.request)
    assert type(result) is SourceHandoffLookup and result == expected
    assert result.workflow_applied is False and "source_applied" not in result.model_dump()
    assert (snapshot(owner), rows(c.args["store"])) == before


@contextmanager
def history_only(c, monkeypatch):
    from connect_automate.lead_intake import admission

    before = snapshot(c.owner), rows(c.args["store"])
    with monkeypatch.context() as patch:
        patch.setattr(c.owner, "_transaction", forbidden)
        patch.setattr(c.owner, "_check_clock", forbidden)
        patch.setattr(c.access, "read_retained", forbidden)
        patch.setattr(c.access, "revalidate_existing", forbidden)
        patch.setattr(c.access, "_clock", forbidden)
        patch.setattr(admission, "authenticate_source", forbidden)
        patch.setattr(_CustodyHandoff, "resume", forbidden)
        patch.setattr(c.runtime, "_dispatch_event_actions", forbidden)
        patch.setattr(c.args["store"], "connection", forbidden)
        seen = envelope_probe(patch, forbidden=True)
        yield
        assert seen == []
    assert (snapshot(c.owner), rows(c.args["store"])) == before


def historical(c, outcome="accepted"):
    if outcome == "no_match":
        seed_workflow(c.args, c.handoff._prepare_resume(c.request), matched=False)
    first = c.handoff.resume(request=c.request)
    expected = c.runtime.lookup_source_outcome(
        binding="inbox",
        event_id=c.request.scope.event_id,
        expected_payload_digest=c.request.payload.capture.payload_digest,
    )
    assert expected.source_receipt == first.source_receipt
    return expected


@pytest.mark.parametrize("outcome", ["accepted", "no_match"])
@pytest.mark.parametrize(
    "kind",
    [
        "none",
        "close",
        "stale",
        "reservation",
        "revoke",
        "key-expiry",
        "expiry",
        "purge",
        "retire",
        "retired-cleanup",
    ],
)
def test_history_ignores_source_eligibility(custodied, monkeypatch, outcome, kind):
    c = custodied
    expected = historical(c, outcome)
    if kind in {"close", "revoke", "expiry", "purge", "retire"}:
        mutate(c, kind)
    elif kind == "retired-cleanup":
        content = SourceContent(c.owner, clock=lambda: NOW)
        content.retire_namespace(c.intent.scope.namespace_id)
        assert content.cleanup_retired(c.intent.scope.namespace_id, limit=1) == 1
        facts = c.access.observe(
            handoff_id=c.request.handoff_id,
            scope=c.request.scope,
            enrolled_machine_id=c.request.enrolled_machine_id,
            capture=c.request.payload.capture,
        )
        assert facts.receipt is None and facts.ever_custodied
    elif kind == "key-expiry":
        authority = c.owner.read_authority()
        grants = authority.model_dump()["key_grants"]
        grants[0]["valid_until"] = RESERVATION
        c.owner.publish_authority(
            next_snapshot(authority, key_grants=grants), expected_generation=1
        )
    if kind in {"reservation", "key-expiry"}:
        c.access._clock = lambda: datetime.fromisoformat(RESERVATION)
    request = c.request.model_copy(update={"expected_fence_generation": 2147483647})
    with history_only(c, monkeypatch):
        result = c.handoff.recover(request=request)
    assert result == expected and type(result) is SourceHandoffLookup
    assert result.schema_name == "lead.source.handoff.lookup"
    with pytest.raises(AttributeError):
        _ = result.source_applied


@pytest.mark.parametrize("state", ["complete", "truncated", "unknown", "unavailable"])
@pytest.mark.parametrize("closed", [False, True])
def test_not_found_reenters_fresh_resume_once(setup, monkeypatch, state, closed):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    value = envelope()
    body = value["payload"]["snapshot"]["body"]
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = dict(state=state, reason="source_gone")
    else:
        body.update(
            completeness=state,
            source_chars=(
                None if state == "unknown" else body["stored_chars"] + int(state == "truncated")
            ),
        )
    intent, upload, raw = prepare(runtime, access, value)
    receipt = access.admit_bound(upload, raw).receipt
    if closed:
        access.close_admission(managed_operation(intent, "settle"))
    access._clock = lambda: datetime.fromisoformat(RESERVATION)
    handoff = composition(runtime, access, intent, clock=access._clock)
    request = resumed(intent, upload, 2 if closed else 1)
    calls = []
    original = _CustodyHandoff.resume

    def resume(self, *, request):
        calls.append(request)
        return original(self, request=request)

    monkeypatch.setattr(_CustodyHandoff, "resume", resume)
    first = handoff.recover(request=request)
    assert (
        type(first) is SourceHandoffResult and first.workflow_applied and not first.source_applied
    )
    assert first.source_receipt.admission_id == receipt.admission_id
    assert len(calls) == 1 and calls[0] == request and calls[0] is not request
    replay = handoff.recover(request=request)
    assert type(replay) is SourceHandoffLookup and not replay.workflow_applied
    assert replay.workflow_event_id == first.workflow_event_id and len(calls) == 1
    assert len(rows(args["store"])["workflow_records"]) == 1


def test_history_returns_original_stage_after_advancement(setup):
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
    first = handoff.recover(request=request)
    runtime.submit_decision(
        first.workflow_record_id,
        decision="approve",
        operation_key="later",
        request={},
        expected_version=first.state_version,
        now=NOW,
    )
    assert args["store"].get_record(first.workflow_record_id).stage == "completed"
    found = handoff.recover(request=request)
    for field in ("workflow_event_id", "workflow_record_id", "stage", "state_version"):
        assert getattr(found, field) == getattr(first, field)


@pytest.mark.parametrize("path,value", BINDINGS, ids=[p[-1] for p, _ in BINDINGS])
def test_request_binding_precedes_lookup(custodied, monkeypatch, path, value):
    c = custodied
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
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
    with pytest.raises(expected):
        c.handoff.recover(request=rewrite_request(c.request, path, value))


@pytest.mark.parametrize("value", [None, False, "", 0, -1, 2147483648])
def test_invalid_generation_precedes_observation(custodied, monkeypatch, value):
    c = custodied
    monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.recover(request=c.request.model_copy(update={"expected_fence_generation": value}))


@pytest.mark.parametrize("generation", [1, 2147483647])
def test_canonical_copy_is_consumed_without_fence_refresh(custodied, monkeypatch, generation):
    c = custodied
    request = c.request.model_copy(update={"expected_fence_generation": generation})
    observations, resumes = [], []
    observe = c.access.observe

    def observed(**kwargs):
        observations.append(kwargs)
        return observe(**kwargs)

    def resume(self, *, request):
        resumes.append(request)
        raise SourceAuthenticationError()

    monkeypatch.setattr(c.access, "observe", observed)
    monkeypatch.setattr(_CustodyHandoff, "resume", resume)
    with pytest.raises(SourceAuthenticationError):
        c.handoff.recover(request=request)
    assert len(resumes) == len(observations) == 1
    assert resumes[0] == request and resumes[0] is not request
    assert observations[0]["scope"] == request.scope
    assert observations[0]["scope"] is not request.scope


@pytest.mark.parametrize("kind", ["prepare", "upload", "status", "settle", "copied"])
def test_other_operations_are_not_recovery(custodied, monkeypatch, kind):
    c = custodied
    request = (
        c.intent
        if kind == "prepare"
        else c.upload
        if kind == "upload"
        else c.request.model_copy(update={"operation": "upload"})
        if kind == "copied"
        else managed_operation(c.intent, kind)
    )
    monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.recover(request=request)


@pytest.mark.parametrize(
    "field,value",
    [
        ("job_id", False),
        ("scope", {}),
        ("payload", {}),
        ("operation", ""),
        ("enrolled_machine_id", None),
        ("unexpected", "value"),
    ],
)
def test_mixed_copied_requests_fail_closed(custodied, monkeypatch, field, value):
    c = custodied
    monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.recover(request=c.request.model_copy(update={field: value}))


@pytest.mark.parametrize("phase", ["missing", "prepared", "bound", "closed-empty"])
def test_absent_source_metadata_does_not_invent_history(setup, monkeypatch, phase):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    intent, upload, _ = prepare(
        runtime, access, phase="bound" if phase == "closed-empty" else phase
    )
    if phase == "closed-empty":
        access.close_admission(managed_operation(intent, "settle"))
    handoff = composition(runtime, access, intent)
    monkeypatch.setattr(access, "read_retained", forbidden)
    with pytest.raises(SourceStoreConflict if phase == "prepared" else SourceContentUnavailable):
        handoff.recover(request=resumed(intent, upload))
    assert rows(args["store"])["workflow_records"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("host_id", OTHER),
        ("organization_id", OTHER),
        ("namespace_id", OTHER),
        ("event_id", OTHER),
        ("payload_digest", "0" * 64),
        ("recovery_deadline", "2026-10-18T13:00:01Z"),
    ],
)
def test_each_historical_receipt_join_without_source_receipt(
    custodied,
    monkeypatch,
    field,
    value,
):
    c = custodied
    found = historical(c)
    content = SourceContent(c.owner, clock=lambda: NOW)
    content.retire_namespace(c.intent.scope.namespace_id)
    content.cleanup_retired(c.intent.scope.namespace_id, limit=1)
    wrong = found.model_copy(
        update={"source_receipt": found.source_receipt.model_copy(update={field: value})}
    )
    # Prove the projection accepts this fixture; only the joined identity rejects it.
    SourceHandoffLookup.model_validate(wrong, by_name=True)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: wrong)
    with history_only(c, monkeypatch), pytest.raises(SourceHandoffUnknown) as failure:
        c.handoff.recover(request=c.request)
    assert failure.value.__cause__ is None and failure.value.__context__ is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("admission_id", OTHER),
        ("accepted_at", "2026-10-18T12:00:01.000000Z"),
    ],
)
def test_full_remaining_receipt_reference_equality(custodied, monkeypatch, field, value):
    c = custodied
    found = historical(c)
    wrong = found.model_copy(
        update={"source_receipt": found.source_receipt.model_copy(update={field: value})}
    )
    SourceHandoffLookup.model_validate(wrong, by_name=True)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: wrong)
    with history_only(c, monkeypatch), pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


@pytest.mark.parametrize("ever", [False, None, 0, 1, "true"])
def test_known_history_requires_exact_custody_fact(custodied, monkeypatch, ever):
    c = custodied
    historical(c)
    observe = c.access.observe
    monkeypatch.setattr(
        c.access, "observe", lambda **kw: replace(observe(**kw), ever_custodied=ever)
    )
    with history_only(c, monkeypatch), pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


@pytest.mark.parametrize(
    "change",
    [
        {"workflow_applied": True},
        {"source_applied": False},
        {"schema_version": "1.0"},
        {"schema_name": "lead.source.handoff.result"},
        {"workflow_outcome": "absent"},
        {"source_receipt": None},
        {"workflow_record_id": None},
        {"state_version": 0},
        {"actions": [{"action_id": OTHER, "kind": "notify.local", "status": "pending"}]},
    ],
    ids=[
        "applied",
        "source-flag",
        "version",
        "schema",
        "outcome",
        "receipt",
        "record",
        "state",
        "action",
    ],
)
def test_bad_lookup_projection_never_resumes(custodied, monkeypatch, change):
    c = custodied
    found = historical(c).model_copy(update=change)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: found)
    with history_only(c, monkeypatch), pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


@pytest.mark.parametrize("bad", [None, False, {}, "not_found"])
def test_bad_lookup_type_is_not_absence(custodied, monkeypatch, bad):
    c = custodied
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: bad)
    monkeypatch.setattr(_CustodyHandoff, "resume", forbidden)
    with pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


@pytest.mark.parametrize("where", ["observe", "lookup"])
@pytest.mark.parametrize(
    "error",
    [
        SourceStoreUnavailable,
        SourceStoreUncertain,
        RuntimeError,
        ValueError,
        OSError,
    ],
)
def test_uncertainty_has_no_fallback_or_private_chain(custodied, monkeypatch, where, error):
    c = custodied

    def broken(**kwargs):
        if error in (SourceStoreUnavailable, SourceStoreUncertain):
            raise error()
        raise error("private body /private/path SQL secret")

    target, name = (
        (c.access, "observe") if where == "observe" else (c.runtime, "lookup_source_outcome")
    )
    monkeypatch.setattr(target, name, broken)
    monkeypatch.setattr(_CustodyHandoff, "resume", forbidden)
    with pytest.raises(SourceHandoffUnknown) as caught:
        c.handoff.recover(request=c.request)
    assert caught.value.args == ("lead source handoff outcome unknown",)
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize(
    "where,error",
    [
        ("observe", SourceStoreBusy),
        ("observe", SourceStoreConflict),
        ("observe", SourceStoreInputError),
        ("lookup", EventBindingError),
        ("lookup", EventInputError),
        ("lookup", EventConflict),
        ("lookup", PackVersionError),
        ("lookup", AutomateLicenseError),
    ],
)
def test_owner_refusals_stay_refusals(custodied, monkeypatch, where, error):
    c = custodied
    problem = (
        error("fixed refusal") if error in (PackVersionError, AutomateLicenseError) else error()
    )

    def broken(**kwargs):
        raise problem

    target, name = (
        (c.access, "observe") if where == "observe" else (c.runtime, "lookup_source_outcome")
    )
    monkeypatch.setattr(target, name, broken)
    monkeypatch.setattr(_CustodyHandoff, "resume", forbidden)
    with pytest.raises(error) as caught:
        c.handoff.recover(request=c.request)
    assert caught.value is problem


@pytest.mark.parametrize("kind", ["close", "revoke", "purge", "retire", "expiry"])
def test_not_found_then_lifecycle_is_refused_without_second_lookup(custodied, monkeypatch, kind):
    c = custodied
    lookup = c.runtime.lookup_source_outcome
    calls = []

    def change_after(**kw):
        result = lookup(**kw)
        calls.append(result.workflow_outcome)
        mutate(c, kind)
        return result

    monkeypatch.setattr(c.runtime, "lookup_source_outcome", change_after)
    with pytest.raises((SourceAuthenticationError, SourceContentUnavailable)):
        c.handoff.recover(request=c.request)
    assert calls == ["not_found"] and rows(c.args["store"])["workflow_records"] == []


def test_source_snapshot_ends_before_workflow_lookup(custodied, monkeypatch):
    c = custodied
    original = c.owner._read_snapshot
    lookup = c.runtime.lookup_source_outcome
    active = []

    @contextmanager
    def source_snapshot(**kw):
        with original(**kw) as db:
            active.append(db)
            try:
                yield db
            finally:
                active.pop()

    def checked(**kw):
        assert not active
        assert kw == dict(
            binding="inbox",
            event_id=c.request.scope.event_id,
            expected_payload_digest=c.request.payload.capture.payload_digest,
        )
        assert kw["expected_payload_digest"] != c.request.payload.capture.envelope_sha256
        return lookup(**kw)

    monkeypatch.setattr(c.owner, "_read_snapshot", source_snapshot)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", checked)
    assert c.handoff.recover(request=c.request).workflow_applied


def test_private_signature_accepts_only_request():
    signature = inspect.signature(_CustodyHandoff.recover)
    assert list(signature.parameters) == ["self", "request"]
    assert signature.parameters["request"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize(
    "kind", ["host", "deployment", "incarnation", "owner", "binding", "license", "actions", "pack"]
)
def test_historical_recovery_keeps_runtime_pins(custodied, monkeypatch, kind):
    from connect_automate.automate.host import AutomateHost

    c = custodied
    historical(c)
    if kind == "host":
        monkeypatch.setattr(c.owner, "host_id", OTHER)
    elif kind == "deployment":
        monkeypatch.setattr(c.owner, "organization_id", OTHER)
    elif kind == "incarnation":
        monkeypatch.setattr(c.access, "_incarnation", OTHER)
    elif kind == "owner":
        monkeypatch.setattr(c.access, "_store", store(c.owner.root))
    elif kind == "binding":
        monkeypatch.setattr(c.runtime, "_event_bindings", {})
    elif kind == "license":
        monkeypatch.setattr(AutomateHost, "licensed", lambda self: False)
    else:
        from test_lead_receipt_vocabulary import workflow
        from test_lead_runtime_results import signed_workflow

        args = dict(c.args)
        value = workflow()
        if kind == "actions":
            value["definitions"][0]["actions"] = [
                dict(action="notify.local", request=dict(body="synthetic"))
            ]
        signed_workflow(args, value, version=2 if kind == "pack" else 1)
        monkeypatch.setattr(c.runtime, "_pack", PackRuntime.load(**args)._pack)
    monkeypatch.setattr(c.access, "observe", forbidden)
    with pytest.raises(AutomateLicenseError if kind == "license" else EventBindingError):
        c.handoff.recover(request=c.request)


@pytest.mark.parametrize("field", ["handoff_id", "scope", "capture"])
def test_misdirected_observation_is_unknown_before_lookup(custodied, monkeypatch, field):
    c = custodied
    observed = c.access.observe
    value = (
        OTHER
        if field == "handoff_id"
        else c.request.scope.model_copy(update={"event_id": OTHER})
        if field == "scope"
        else c.request.payload.capture.model_copy(update={"snapshot_id": OTHER})
    )
    monkeypatch.setattr(c.access, "observe", lambda **kw: replace(observed(**kw), **{field: value}))
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
    with pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


def test_dict_lookup_is_not_the_closed_owner_value(custodied, monkeypatch):
    c = custodied
    valid_dict = historical(c).model_dump(by_alias=True)
    SourceHandoffLookup.model_validate(valid_dict)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: valid_dict)
    with history_only(c, monkeypatch), pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


def test_observation_requires_concrete_owner_value(custodied, monkeypatch):
    from types import SimpleNamespace

    c = custodied
    observe = c.access.observe
    monkeypatch.setattr(c.access, "observe", lambda **kw: SimpleNamespace(**vars(observe(**kw))))
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
    with pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)


def test_corrupt_not_found_cannot_resume(custodied, monkeypatch):
    c = custodied
    found = c.runtime.lookup_source_outcome(
        binding="inbox",
        event_id=c.request.scope.event_id,
        expected_payload_digest=c.request.payload.capture.payload_digest,
    )
    assert found.workflow_outcome == "not_found"
    wrong = found.model_copy(update={"workflow_record_id": OTHER})
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: wrong)
    monkeypatch.setattr(_CustodyHandoff, "resume", forbidden)
    with pytest.raises(SourceHandoffUnknown):
        c.handoff.recover(request=c.request)
