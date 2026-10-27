"""Private fenced runtime composition; synthetic sources, no receiver or effects."""

import hashlib

import pytest
from test_lead_custody_protocol import capture
from test_lead_custody_store import RESERVATION, managed_operation, managed_request, reader
from test_lead_host_composition import setup as setup
from test_lead_source_auth import NOW, encode, envelope, resign
from test_lead_source_store import private_root as private_root
from test_workflow_receipt_lookup import rows

from connect_automate.automate import PackRuntime
from connect_automate.lead_intake.custody_protocol import parse_untrusted_request


def composition(runtime, access, prepared, **changes):
    from connect_automate.lead_intake.custody_handoff import _CustodyHandoff

    values = dict(
        runtime=runtime,
        custody=access,
        route=prepared.payload.route,
        enrolled_machine_id=prepared.enrolled_machine_id,
        clock=lambda: NOW,
    )
    values.update(changes)
    return _CustodyHandoff(**values)


def prepare(runtime, access, value=None, *, phase="bound"):
    value = envelope() if value is None else value
    raw = resign(value)
    data = managed_request(value).model_dump()
    data["payload"]["route"].update(
        pack_id=runtime.pack.pack_id, pack_version=runtime.pack.pack_version
    )
    data["scope"]["route_digest"] = hashlib.sha256(encode(data["payload"]["route"])).hexdigest()
    prepared = parse_untrusted_request(encode(data))
    upload = managed_operation(prepared, "upload", capture(value))
    if phase != "missing":
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
    if phase == "bound":
        access.bind_upload(upload)
    return prepared, upload, raw


@pytest.fixture
def managed(setup):
    args, owner, admission = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    prepared, upload, raw = prepare(runtime, access)
    return args, owner, runtime, access, prepared, upload, raw


def test_managed_raw_submission_joins_real_owners(managed):
    args, owner, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    result = handoff.submit(request=upload, raw_source_bytes=raw)
    assert result.workflow_outcome == "accepted"
    assert result.source_applied is True and result.workflow_applied is True
    assert result.actions == []
    persisted = rows(args["store"])
    assert len(persisted["workflow_records"]) == 1
    assert len(persisted["workflow_event_receipts"]) == 1
    assert persisted["workflow_actions"] == []


def submit(handoff, upload, raw):
    return handoff.submit(request=upload, raw_source_bytes=raw)


def forbidden(*args, **kwargs):
    pytest.fail("crossed the guarded owner boundary")


@pytest.mark.parametrize("state", ["complete", "truncated", "unknown", "unavailable"])
def test_body_states_and_open_replay(setup, state):
    from test_lead_source_admission import counts

    from connect_automate.lead_intake.content import SourceContent

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    value = envelope()
    body = value["payload"]["snapshot"]["body"]
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = dict(state=state, reason="source_gone")
    else:
        body["completeness"] = state
        if state == "truncated":
            body["source_chars"] = body["stored_chars"] + 1
        elif state == "unknown":
            body["source_chars"] = None
    prepared, upload, raw = prepare(runtime, access, value)
    handoff = composition(runtime, access, prepared)
    first = submit(handoff, upload, raw)
    second = submit(handoff, upload.model_copy(deep=True), raw)
    assert second == first.model_copy(update=dict(source_applied=False, workflow_applied=False))
    assert counts(owner) == (1, 1, 1)
    assert (
        SourceContent(owner, clock=lambda: NOW).read_content(first.source_receipt.admission_id)
        == raw
    )
    assert raw.decode() not in repr(rows(args["store"])) + repr(first)


@pytest.mark.parametrize("field", ["host_id", "organization_id", "namespace_id", "route_digest"])
def test_request_scope_rejected_before_owner(managed, monkeypatch, field):
    from test_lead_source_auth import OTHER

    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    scope = upload.scope.model_copy(update={field: "0" * 64 if field == "route_digest" else OTHER})
    wrong = upload.model_copy(update={"scope": scope})
    monkeypatch.setattr(access, "admit_bound", forbidden)
    with pytest.raises(EventBindingError):
        submit(handoff, wrong, raw)


@pytest.mark.parametrize("field", ["host_id", "organization_id", "namespace_id"])
def test_signed_source_scope_rejected_before_owner(managed, monkeypatch, field):
    from test_lead_source_auth import OTHER

    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, prepared, upload, _ = managed
    handoff = composition(runtime, access, prepared)
    value = envelope()
    target = value["authorization"] if field == "host_id" else value["payload"]
    if field == "namespace_id":
        target = target["source"]
    target[field] = OTHER
    raw = resign(value)
    monkeypatch.setattr(access, "admit_bound", forbidden)
    with pytest.raises(EventBindingError):
        submit(handoff, upload, raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider_app_id", "another-app"),
        ("provider_instance_id", "00000000-0000-4000-8000-000000000002"),
        ("provider_app_version", "2.0.0"),
        ("capability_id", "another-capability"),
        ("capability_version", "2.0"),
        ("pack_id", "00000000-0000-4000-8000-000000000002"),
        ("pack_version", 2),
        ("binding", "elsewhere"),
    ],
)
def test_full_route_pin_before_owner(managed, monkeypatch, field, value):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, prepared, upload, raw = managed
    altered = prepared.payload.route.model_copy(update={field: value})
    monkeypatch.setattr(access, "admit_bound", forbidden)
    with pytest.raises(EventBindingError):
        handoff = composition(runtime, access, prepared, route=altered)
        submit(handoff, upload, raw)


@pytest.mark.parametrize("value", [None, 0, False, "", "invalid"])
@pytest.mark.parametrize("field", ["enrolled_machine_id", "route", "clock", "custody"])
def test_bad_host_configuration_is_fixed_refusal(managed, field, value):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, prepared, _, _ = managed
    with pytest.raises(EventBindingError) as caught:
        composition(runtime, access, prepared, **{field: value})
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("bad", [None, 0, False, "", object()])
def test_no_duck_typed_runtime(managed, bad):
    from connect_automate.automate.events import EventBindingError

    _, _, _, access, prepared, _, _ = managed
    with pytest.raises(EventBindingError):
        composition(bad, access, prepared)


@pytest.mark.parametrize("kind", ["prepare", "settle", "resume", "status"])
def test_wrong_request_kind_is_not_dispatched(managed, monkeypatch, kind):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    candidate = (
        prepared
        if kind == "prepare"
        else managed_operation(prepared, kind, capture(envelope()) if kind == "resume" else None)
    )
    monkeypatch.setattr(access, "admit_bound", forbidden)
    with pytest.raises(EventBindingError):
        submit(handoff, candidate, raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("enrolled_machine_id", "00000000-0000-4000-8000-000000000002"),
        ("expected_fence_generation", 0),
        ("job_id", False),
        ("payload", {}),
    ],
)
def test_copied_request_is_revalidated(managed, monkeypatch, field, value):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    candidate = upload.model_copy(update={field: value})
    monkeypatch.setattr(access, "admit_bound", forbidden)
    with pytest.raises(EventBindingError):
        submit(handoff, candidate, raw)


def test_binding_is_frozen_and_closed_values_are_copied(managed):
    from dataclasses import FrozenInstanceError

    _, _, runtime, access, prepared, upload, raw = managed
    route = prepared.payload.route.model_dump()
    handoff = composition(runtime, access, prepared, route=route)
    route["provider_app_id"] = "changed-after-construction"
    with pytest.raises(FrozenInstanceError):
        handoff.custody = object()
    assert submit(handoff, upload, raw).workflow_outcome == "accepted"


@pytest.mark.parametrize("kind", ["deployment", "incarnation", "owner", "binding"])
def test_configuration_drift_refused_before_source(managed, monkeypatch, kind):
    from test_lead_source_auth import OTHER
    from test_lead_source_store import store

    from connect_automate.automate.events import EventBindingError

    _, owner, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    monkeypatch.setattr(access, "admit_bound", forbidden)
    if kind == "deployment":
        monkeypatch.setattr(owner, "organization_id", OTHER)
    elif kind == "incarnation":
        monkeypatch.setattr(access, "_incarnation", OTHER)
    elif kind == "owner":
        monkeypatch.setattr(access, "_store", store(owner.root))
    else:
        import json

        from connect_automate.automate.events import SourceBinding

        source = runtime._event_bindings["inbox"]
        scope = json.loads(source.scope)
        scope["host_id"] = OTHER
        changed = SourceBinding.model_validate(
            {**source.model_dump(), "scope": encode(scope).decode()}
        )
        monkeypatch.setattr(runtime, "_event_bindings", {"inbox": changed})
    with pytest.raises(EventBindingError):
        submit(handoff, upload, raw)


@pytest.mark.parametrize("placement", ["source", "later"])
def test_managed_requires_no_actions_anywhere(setup, monkeypatch, placement):
    from test_automate_events import event_workflow
    from test_lead_receipt_vocabulary import workflow
    from test_lead_runtime_results import signed_workflow

    from connect_automate.automate.events import EventBindingError

    args, owner, _ = setup
    data = workflow()
    target = data["definitions"][0]
    if placement == "later":
        target = event_workflow()["definitions"][1]
        data["definitions"].append(target)
    target["actions"] = [dict(action="notify.local", request=dict(body="synthetic"))]
    signed_workflow(args, data)
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    prepared, _, _ = prepare(runtime, access)
    monkeypatch.setattr(access, "admit_bound", forbidden)
    with pytest.raises(EventBindingError):
        composition(runtime, access, prepared)


@pytest.mark.parametrize("point", ["before-source", "before-workflow"])
def test_license_rechecked_at_both_boundaries(managed, monkeypatch, point):
    from connect_automate.automate.host import AutomateHost, AutomateLicenseError

    args, _, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    before = rows(args["store"])
    if point == "before-source":
        monkeypatch.setattr(AutomateHost, "licensed", lambda self: False)
        monkeypatch.setattr(access, "admit_bound", forbidden)
    else:
        original = access.admit_bound

        def admit(request, raw):
            result = original(request, raw)
            monkeypatch.setattr(AutomateHost, "licensed", lambda self: False)
            return result

        monkeypatch.setattr(access, "admit_bound", admit)
    with pytest.raises(AutomateLicenseError):
        submit(handoff, upload, raw)
    assert rows(args["store"]) == before


@pytest.mark.parametrize("phase", ["missing", "prepared"])
def test_no_implicit_prepare_or_bind(setup, monkeypatch, phase):
    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    prepared, upload, raw = prepare(runtime, access, phase=phase)
    handoff = composition(runtime, access, prepared)
    monkeypatch.setattr(access, "register_intent", forbidden)
    monkeypatch.setattr(access, "bind_upload", forbidden)
    before = rows(args["store"])
    with pytest.raises(SourceAuthenticationError if phase == "missing" else SourceStoreConflict):
        submit(handoff, upload, raw)
    assert rows(args["store"]) == before


def test_wrong_retained_incarnation_is_source_owner_refusal(managed):
    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.source_store import SourceStoreConflict

    args, owner, runtime, _, prepared, upload, raw = managed
    access = reader(owner, clock=lambda: NOW, expected_incarnation=OTHER)
    handoff = composition(runtime, access, prepared)
    before = rows(args["store"])
    with pytest.raises(SourceStoreConflict):
        submit(handoff, upload, raw)
    assert rows(args["store"]) == before


def test_replay_authenticates_and_copied_result_cannot_bypass(managed, monkeypatch):
    from test_lead_source_store import next_snapshot

    from connect_automate.automate.events import EventBindingError
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    args, owner, runtime, access, prepared, upload, raw = managed
    handoff = composition(runtime, access, prepared)
    result = submit(handoff, upload, raw)
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    before = rows(args["store"])
    with pytest.raises(SourceAuthenticationError):
        submit(handoff, upload, raw)
    with pytest.raises(EventBindingError):
        submit(handoff, result, raw)
    assert rows(args["store"]) == before


@pytest.mark.parametrize(
    "reason",
    ["signature", "raw-conflict", "capture-conflict", "close", "expiry", "purge", "retire"],
)
def test_owner_refusal_never_writes_workflow_or_falls_back(managed, monkeypatch, reason):
    from datetime import datetime

    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.content import SourceContent
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    args, owner, runtime, access, prepared, upload, raw = managed
    value = envelope()
    expected = SourceAuthenticationError
    if reason == "signature":
        value["authorization"]["signature"] = "A" * 86
        raw = encode(value)
    elif reason == "raw-conflict":
        value["payload"]["snapshot"]["snapshot_id"] = "00000000-0000-4000-8000-000000000002"
        raw = resign(value)
        expected = SourceStoreConflict
    elif reason == "capture-conflict":
        changed = upload.payload.capture.model_copy(update={"artifact_size": 1})
        upload = upload.model_copy(
            update={"payload": upload.payload.model_copy(update={"capture": changed})}
        )
        expected = SourceStoreConflict
    elif reason == "close":
        access.close_admission(managed_operation(prepared, "settle"))
    elif reason == "expiry":
        access = reader(owner, clock=lambda: datetime.fromisoformat(RESERVATION))
    elif reason == "purge":
        SourceContent(owner, clock=lambda: NOW).purge_message(prepared.payload.source, cutoff=NOW)
    elif reason == "retire":
        SourceContent(owner, clock=lambda: NOW).retire_namespace(prepared.scope.namespace_id)
    handoff = composition(runtime, access, prepared)
    monkeypatch.setattr(runtime, "_prepare_source", forbidden)
    monkeypatch.setattr(access, "revalidate_existing", forbidden)
    before = rows(args["store"])
    with pytest.raises(expected):
        submit(handoff, upload, raw)
    assert rows(args["store"]) == before


def test_historical_no_match_reuses_same_completion(managed):
    from test_lead_host_composition import seed_workflow

    args, _, runtime, access, intent, upload, raw = managed
    handoff = composition(runtime, access, intent)
    # A valid lead trigger matches all. Reuse the historical no-match proof,
    # seeded by the real workflow owner, rather than weakening pack validation.
    prepared = handoff._prepare(upload, raw)
    seed_workflow(args, prepared, matched=False)
    before = rows(args["store"])
    result = submit(handoff, upload, raw)
    assert result.workflow_outcome == "no_match"
    assert result.source_applied is False and result.workflow_applied is False
    assert result.workflow_record_id is None and result.actions == []
    assert rows(args["store"]) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("host_id", "00000000-0000-4000-8000-000000000002"),
        ("organization_id", "00000000-0000-4000-8000-000000000002"),
        ("namespace_id", "00000000-0000-4000-8000-000000000002"),
        ("event_id", "00000000-0000-4000-8000-000000000002"),
        ("payload_digest", "0" * 64),
        ("recovery_deadline", "2026-10-18T13:00:01Z"),
    ],
)
def test_fresh_owner_receipt_must_match_each_source_field(managed, monkeypatch, field, value):
    from connect_automate.lead_intake.results import SourceHandoffUnknown

    args, _, runtime, access, intent, upload, raw = managed
    handoff = composition(runtime, access, intent)
    original = access.admit_bound

    def changed(request, raw):
        result = original(request, raw)
        receipt = result.receipt.model_copy(update={field: value})
        return result.model_copy(update={"receipt": receipt})

    monkeypatch.setattr(access, "admit_bound", changed)
    monkeypatch.setattr(runtime._engine, "_admit_event", forbidden)
    before = rows(args["store"])
    with pytest.raises(SourceHandoffUnknown) as caught:
        submit(handoff, upload, raw)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert rows(args["store"]) == before


@pytest.mark.parametrize("point", ["source", "workflow", "projection"])
def test_errors_are_unknown_without_raw_or_exception_chain(
    managed, monkeypatch, caplog, capsys, point
):
    import sqlite3

    from connect_automate.lead_intake.results import SourceHandoffUnknown

    args, _, runtime, access, intent, upload, raw = managed
    handoff = composition(runtime, access, intent)
    marker = envelope()["payload"]["snapshot"]["body"]["text"]

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError(marker)

    target, method = {
        "source": (access, "admit_bound"),
        "workflow": (runtime._engine, "_admit_event"),
        "projection": (runtime, "_lookup_source_receipt"),
    }[point]
    monkeypatch.setattr(target, method, broken)
    with pytest.raises(SourceHandoffUnknown) as caught:
        submit(handoff, upload, raw)
    assert caught.value.args == ("lead source handoff outcome unknown",)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    captured = capsys.readouterr()
    assert (
        marker
        not in str(caught.value)
        + repr(rows(args["store"]))
        + caplog.text
        + captured.out
        + captured.err
    )


@pytest.mark.parametrize("last", ["deadline", "backward"])
def test_final_source_clock_refuses_before_workflow(managed, last):
    from datetime import datetime, timedelta

    from test_lead_custody_store import snapshot

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    args, owner, runtime, _, intent, upload, raw = managed
    samples = iter(
        [
            NOW,
            datetime.fromisoformat(RESERVATION)
            if last == "deadline"
            else NOW - timedelta(microseconds=1),
        ]
    )
    access = reader(owner, clock=lambda: next(samples))
    handoff = composition(runtime, access, intent)
    before = snapshot(owner), rows(args["store"])
    with pytest.raises(SourceAuthenticationError):
        submit(handoff, upload, raw)
    assert (snapshot(owner), rows(args["store"])) == before


def test_source_writer_released_and_post_commit_close_does_not_erase_receipt(managed, monkeypatch):
    from test_lead_source_store import database

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    args, owner, runtime, access, intent, upload, raw = managed
    handoff = composition(runtime, access, intent)
    original = runtime._engine._admit_event

    def complete(*a, **kw):
        with database(owner.path) as db:
            db.execute("PRAGMA busy_timeout=0")
            db.execute("BEGIN IMMEDIATE")  # Would fail if source writer remained held.
            db.rollback()
        access.close_admission(managed_operation(intent, "settle"))
        return original(*a, **kw)

    monkeypatch.setattr(runtime._engine, "_admit_event", complete)
    result = submit(handoff, upload, raw)
    assert result.workflow_outcome == "accepted"
    before = rows(args["store"])
    with pytest.raises(SourceAuthenticationError):
        submit(handoff, upload, raw)
    assert rows(args["store"]) == before


def test_managed_entry_does_not_require_legacy_admission_configuration(setup):
    args, owner, _ = setup
    args.pop("source_admission")
    args.pop("source_clock")
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    prepared, upload, raw = prepare(runtime, access)
    assert (
        submit(composition(runtime, access, prepared), upload, raw).workflow_outcome == "accepted"
    )


@pytest.mark.parametrize("entry", ["_submit_custody_source", "_submit_source"])
def test_runtime_refuses_arbitrary_admission_callback(managed, entry):
    from types import SimpleNamespace

    from connect_automate.automate.events import EventBindingError

    _, _, runtime, _, intent, upload, raw = managed
    counterfeit = SimpleNamespace(runtime=runtime, route=intent.payload.route, _prepare=forbidden)
    options = dict(custody=counterfeit, request=upload, raw_source_bytes=raw)
    if entry == "_submit_source":
        options["binding"] = "inbox"
    with pytest.raises(EventBindingError):
        getattr(runtime, entry)(**options)


def test_second_boundary_rechecks_binding_after_source_commit(managed, monkeypatch):
    from test_lead_source_admission import counts

    from connect_automate.automate.events import EventBindingError

    args, owner, runtime, access, intent, upload, raw = managed
    handoff = composition(runtime, access, intent)
    original = access.admit_bound

    def admit(request, raw):
        result = original(request, raw)
        monkeypatch.setattr(runtime, "_event_bindings", {})
        return result

    monkeypatch.setattr(access, "admit_bound", admit)
    before = rows(args["store"])
    with pytest.raises(EventBindingError):
        submit(handoff, upload, raw)
    assert counts(owner) == (1, 1, 1)
    assert rows(args["store"]) == before


def test_managed_binding_cannot_be_used_on_another_runtime(managed):
    from connect_automate.automate.events import EventBindingError

    args, _, runtime, access, intent, upload, raw = managed
    handoff = composition(runtime, access, intent)
    other = PackRuntime.load(**args)
    with pytest.raises(EventBindingError):
        other._submit_custody_source(custody=handoff, request=upload, raw_source_bytes=raw)


def test_old_legacy_entry_still_refuses_reserved_source(managed):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    args, _, runtime, _, _, _, raw = managed
    before = rows(args["store"])
    with pytest.raises(SourceAuthenticationError):
        runtime.submit_source(binding="inbox", raw_source_bytes=raw)
    assert rows(args["store"]) == before


@pytest.mark.parametrize("owner", ["runtime", "custody"])
def test_concrete_owner_guard_not_a_missing_attribute_backstop(managed, owner):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, intent, _, _ = managed

    class Proxy:
        def __init__(self, actual):
            self.actual = actual

        def __getattr__(self, name):
            return getattr(self.actual, name)

    # All expected attributes are present; only the concrete-owner gate refuses.
    with pytest.raises(EventBindingError):
        composition(
            Proxy(runtime) if owner == "runtime" else runtime,
            Proxy(access) if owner == "custody" else access,
            intent,
        )


@pytest.mark.parametrize(
    "field,value", [("pack_id", "00000000-0000-4000-8000-000000000002"), ("pack_version", 2)]
)
def test_signed_pack_pin_is_checked_at_construction(managed, field, value):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, intent, _, _ = managed
    route = intent.payload.route.model_copy(update={field: value})
    # No request follows: a later route-digest check cannot mask this guard.
    with pytest.raises(EventBindingError):
        composition(runtime, access, intent, route=route)


@pytest.mark.parametrize("field,value", [("capability_id", "other"), ("capability_version", "2.0")])
def test_copied_route_is_revalidated_at_construction(managed, field, value):
    from connect_automate.automate.events import EventBindingError

    _, _, runtime, access, intent, _, _ = managed
    with pytest.raises(EventBindingError):
        composition(
            runtime, access, intent, route=intent.payload.route.model_copy(update={field: value})
        )


def test_readonly_facade_is_not_a_submission_owner(managed):
    from connect_automate.automate.events import EventBindingError

    _, owner, runtime, _, intent, _, _ = managed
    with pytest.raises(EventBindingError):
        composition(runtime, reader(owner), intent)
