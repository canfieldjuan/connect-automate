"""Library-only authenticated workflow boundary; synthetic sources and real stores."""

from contextlib import suppress

import pytest
from test_lead_host_composition import setup as setup
from test_lead_source_auth import encode, envelope
from test_lead_source_store import private_root as private_root

from connect_automate.automate import PackRuntime
from connect_automate.lead_intake import parse_untrusted_source, payload_digest


def submit(runtime, raw=None, binding="inbox"):
    return runtime.submit_source(
        binding=binding, raw_source_bytes=encode(envelope()) if raw is None else raw
    )


def lookup(runtime, raw=None, **updates):
    parsed = parse_untrusted_source(encode(envelope()) if raw is None else raw)
    args = dict(
        binding="inbox",
        event_id=parsed.payload.event_id,
        expected_payload_digest=payload_digest(parsed),
    )
    args.update(updates)
    return runtime.lookup_source_outcome(**args)


def test_public_submission_creates_workflow_and_preserves_replay_flags(setup):
    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    assert first.workflow_outcome == "accepted"
    assert first.source_applied is True and first.workflow_applied is True
    assert first.stage == "ready" and first.state_version == 2
    second = submit(runtime)
    assert second.source_receipt == first.source_receipt
    assert second.source_applied is False and second.workflow_applied is False
    assert second.workflow_record_id == first.workflow_record_id
    assert second.workflow_event_id == first.workflow_event_id
    found = lookup(runtime)
    assert found.workflow_outcome == "accepted" and found.workflow_applied is False
    assert found.source_receipt == first.source_receipt
    assert found.workflow_record_id == first.workflow_record_id
    assert "source_applied" not in found.model_dump()


def test_public_lookup_absence_has_no_invented_receipt(setup):
    args, _, _ = setup
    found = lookup(PackRuntime.load(**args))
    assert found.workflow_outcome == "not_found"
    assert found.source_receipt is None
    assert found.workflow_record_id is None and found.workflow_event_id is None
    assert found.stage is None and found.state_version is None
    assert found.workflow_applied is False


def signed_workflow(args, value, version=1):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from test_automate_runtime import PACK_ID, _envelope

    args["pack_bytes"] = _envelope(
        Ed25519PrivateKey.from_private_bytes(bytes(range(32))),
        encode(dict(format_version=2, pack_id=PACK_ID, pack_version=version, workflow=value)),
    )


@pytest.mark.parametrize("state", ["available", "unavailable"])
def test_body_metadata_and_source_only_replay_still_enter_workflow(setup, state):
    from test_lead_source_admission import counts
    from test_lead_source_auth import resign

    args, owner, admission = setup
    value = envelope()
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = dict(state="unavailable", reason="source_gone")
    raw = resign(value)
    original = admission.admit_source(raw)
    result = submit(PackRuntime.load(**args), raw)
    assert result.source_applied is False and result.workflow_applied is True
    assert result.source_receipt.admission_id == original.receipt.admission_id
    assert result.workflow_outcome == "accepted" and counts(owner) == (1, 1, 1)
    with args["store"].read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM workflow_actions").fetchone()[0] == 0
        payload = db.execute("SELECT payload FROM workflow_event_receipts").fetchone()[0]
    assert "snapshot" not in payload and "message_id" not in payload


@pytest.mark.parametrize("condition", ["equals", "in"])
def test_invalid_initial_stage_is_refused_at_signed_pack_load(setup, condition):
    from test_lead_receipt_vocabulary import workflow

    from connect_automate.automate.pack import PackError

    args, _, _ = setup
    value = workflow()
    value["definitions"][0]["conditions"][0].update(
        op=condition, value="ready" if condition == "equals" else ["ready"]
    )
    signed_workflow(args, value)
    with pytest.raises(PackError):
        PackRuntime.load(**args)


def test_durable_no_match_is_distinct_from_absence(setup):
    from test_lead_host_composition import seed_workflow

    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    assert lookup(runtime).workflow_outcome == "not_found"
    prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    seed_workflow(args, prepared, matched=False)
    # Valid lead packs always match; preserve historical no-match receipts through
    # the same real admission owner used by the preceding projection increment.
    first = submit(runtime)
    replay = submit(runtime)
    found = lookup(runtime)
    assert first.source_applied is False and replay.source_applied is False
    for result in (first, replay, found):
        assert result.workflow_outcome == "no_match" and result.workflow_applied is False
        assert result.source_receipt == prepared.event.source_receipt
        assert result.workflow_record_id is None and result.workflow_event_id is None
        assert result.stage is None and result.state_version is None
    with args["store"].read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 1


def test_ambiguous_selection_rolls_back_workflow_but_keeps_source(setup):
    from copy import deepcopy

    from test_lead_receipt_vocabulary import workflow
    from test_lead_source_admission import counts

    from connect_automate.automate.events import AmbiguousEvent

    args, owner, _ = setup
    value = workflow()
    second = deepcopy(value["definitions"][0])
    second["name"] = "second"
    value["definitions"].append(second)
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    with pytest.raises(AmbiguousEvent):
        submit(runtime)
    assert counts(owner) == (1, 1, 1)
    assert lookup(runtime).workflow_outcome == "not_found"
    with args["store"].read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 0


def test_public_replay_and_lookup_return_original_stage_after_advancement(setup):
    from test_automate_events import event_workflow
    from test_lead_receipt_vocabulary import workflow
    from test_lead_source_auth import NOW

    args, _, _ = setup
    value = workflow()
    value["definitions"].append(event_workflow()["definitions"][1])
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    runtime.submit_decision(
        first.workflow_record_id,
        decision="approve",
        operation_key="later",
        request={},
        expected_version=first.state_version,
        now=NOW,
    )
    assert args["store"].get_record(first.workflow_record_id).stage == "completed"
    for result in (submit(runtime), lookup(runtime)):
        assert result.stage == first.stage == "ready"
        assert result.state_version == first.state_version == 2
        assert result.workflow_event_id == first.workflow_event_id


@pytest.mark.parametrize("entry", ["submit", "lookup"])
def test_revision_conflict_is_not_new_work_or_not_found(setup, entry):
    from test_lead_receipt_vocabulary import workflow

    from connect_automate.automate.engine import PackVersionError

    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    signed_workflow(args, workflow(), version=2)
    upgraded = PackRuntime.load(**args)
    with pytest.raises(PackVersionError):
        (submit if entry == "submit" else lookup)(upgraded)
    assert lookup(runtime).workflow_event_id == first.workflow_event_id


def test_key_rotation_reauthenticates_and_distinct_events_remain_distinct(setup):
    from copy import deepcopy

    from test_lead_source_auth import OTHER, key, resign, trust_data

    from connect_automate.lead_intake import SourceAuthenticationError, SourceTrustSnapshot

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    data = trust_data()
    data["key_grants"][0]["status"] = "revoked"
    rotated = deepcopy(data["key_grants"][0])
    signer = key(bytes(reversed(range(32))))
    rotated.update(key_id=OTHER, status="active", public_key=signer.public_key().public_bytes_raw())
    data["key_grants"].append(rotated)
    data["generation"] = 2
    owner.publish_authority(SourceTrustSnapshot.model_validate(data), expected_generation=1)
    with pytest.raises(SourceAuthenticationError):
        submit(runtime)
    value = envelope()
    value["authorization"]["key_id"] = OTHER
    replay = submit(runtime, resign(value, signer))
    assert replay.source_receipt == first.source_receipt
    assert replay.source_applied is False and replay.workflow_applied is False
    value["payload"]["event_id"] = OTHER
    another = submit(runtime, resign(value, signer))
    assert another.workflow_record_id != first.workflow_record_id
    assert another.workflow_event_id != first.workflow_event_id
    assert another.source_applied is True and another.workflow_applied is True


def test_signed_payload_conflict_and_digest_conflict_are_preserved(setup):
    from test_lead_source_auth import resign

    from connect_automate.automate.events import EventConflict
    from connect_automate.lead_intake import SourceAdmissionConflict

    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    value = envelope()
    value["payload"]["source"]["message_id"] = "other-message"
    with pytest.raises(SourceAdmissionConflict):
        submit(runtime, resign(value))
    with pytest.raises(EventConflict):
        lookup(runtime, expected_payload_digest="b" * 64)
    assert lookup(runtime).workflow_record_id == first.workflow_record_id


@pytest.mark.parametrize("bad", [False, 0, "", [], "missing"])
@pytest.mark.parametrize("entry", ["submit", "lookup"])
def test_public_binding_refusal_precedes_store_access(setup, monkeypatch, bad, entry):
    from connect_automate.automate.events import EventBindingError

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)

    def forbidden(*a, **kw):
        pytest.fail("denied input accessed store")

    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(args["store"], "connection", forbidden)
    monkeypatch.setattr(args["store"], "read_connection", forbidden)
    with pytest.raises(EventBindingError):
        (submit if entry == "submit" else lookup)(runtime, binding=bad)


@pytest.mark.parametrize("entry", ["submit", "lookup"])
def test_public_license_denial_precedes_stores(setup, monkeypatch, entry):
    from connect_automate.automate.host import AutomateHost, AutomateLicenseError

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)

    def forbidden(*a, **kw):
        pytest.fail("unlicensed store access")

    monkeypatch.setattr(AutomateHost, "licensed", lambda s: False)
    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(args["store"], "read_connection", forbidden)
    with pytest.raises(AutomateLicenseError):
        (submit if entry == "submit" else lookup)(runtime)


@pytest.mark.parametrize("field", ["host_id", "organization_id", "namespace_id"])
def test_public_foreign_scope_precedes_source_admission(setup, monkeypatch, field):
    from test_lead_source_auth import OTHER, resign

    from connect_automate.automate.events import EventBindingError

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    value = envelope()
    target = (
        value["authorization"]
        if field == "host_id"
        else (value["payload"]["source"] if field == "namespace_id" else value["payload"])
    )
    target[field] = OTHER
    monkeypatch.setattr(owner, "_transaction", lambda: pytest.fail("foreign store access"))
    with pytest.raises(EventBindingError):
        submit(runtime, resign(value))


@pytest.mark.parametrize("kind", ["receipt", "result", "prepared", "event", "dict", "bytearray"])
def test_public_submission_never_accepts_copied_authority(setup, kind):
    from test_workflow_receipt_lookup import rows

    from connect_automate.lead_intake import SourceInputError

    args, _, admission = setup
    runtime = PackRuntime.load(**args)
    raw = encode(envelope())
    prior = admission.admit_source(raw)
    prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    copied = dict(
        receipt=prior.receipt,
        result=prior,
        prepared=prepared,
        event=encode(prepared.event.model_dump()),
        dict=envelope(),
        bytearray=bytearray(raw),
    )
    before = rows(args["store"])
    with pytest.raises(SourceInputError):
        submit(runtime, copied[kind])
    assert rows(args["store"]) == before


def test_mixed_pack_has_only_lead_handoff_and_preserves_generic_submission(setup):
    from test_automate_events import event_workflow, mail_event, source_binding
    from test_lead_receipt_vocabulary import workflow
    from test_lead_source_auth import NOW

    from connect_automate.automate.events import EventBindingError

    args, _, _ = setup
    value = workflow()
    mail = event_workflow()["definitions"][0]
    mail["name"] = "mail"
    mail["trigger"]["binding"] = "mail"
    value["definitions"].append(mail)
    args["event_bindings"]["mail"] = source_binding()
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    assert set(runtime._source_handoffs) == {"inbox"}
    with pytest.raises(EventBindingError):
        submit(runtime, binding="mail")
    with pytest.raises(EventBindingError):
        lookup(runtime, binding="mail")
    first = submit(runtime)
    assert lookup(runtime).workflow_record_id == first.workflow_record_id
    result = runtime.submit_event(binding="mail", event=encode(mail_event()), now=NOW)
    assert result.matched and result.applied


def test_clock_is_sampled_after_admission_returns(setup, monkeypatch):
    from test_lead_source_auth import NOW

    args, _, admission = setup
    returned = False
    original = admission.admit_source

    def admit(raw):
        nonlocal returned
        result = original(raw)
        returned = True
        return result

    def clock():
        assert returned, "clock sampled before admission returned"
        return NOW

    monkeypatch.setattr(admission, "admit_source", admit)
    args["source_clock"] = clock
    assert submit(PackRuntime.load(**args)).workflow_outcome == "accepted"


@pytest.mark.parametrize("outcome", ["accepted", "no_match", "not_found"])
def test_public_lookup_never_reads_source_or_dispatches(setup, monkeypatch, outcome):
    from test_lead_source_auth import NOW
    from test_workflow_receipt_lookup import rows

    from connect_automate.lead_intake import SourceAdmission

    args, owner, admission = setup
    deny_clock = False

    def clock():
        if deny_clock:
            pytest.fail("lookup sampled host clock")
        return NOW

    args["source_clock"] = clock
    runtime = PackRuntime.load(**args)
    if outcome == "no_match":
        from test_lead_host_composition import seed_workflow

        prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
        seed_workflow(args, prepared, matched=False)
    elif outcome == "accepted":
        submit(runtime)
    before = rows(args["store"])
    deny_clock = True

    def forbidden(*a, **kw):
        pytest.fail("lookup used source/writer/clock/dispatch")

    args.pop("source_admission")
    args.pop("source_clock")
    historical = PackRuntime.load(**args)
    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(SourceAdmission, "deployment", property(forbidden))
    monkeypatch.setattr(admission, "admit_source", forbidden)
    monkeypatch.setattr(args["store"], "connection", forbidden)
    monkeypatch.setattr(historical, "_dispatch_event_actions", forbidden)
    monkeypatch.setattr(runtime, "_dispatch_event_actions", forbidden)
    assert lookup(runtime).workflow_outcome == outcome
    assert lookup(historical).workflow_outcome == outcome
    assert rows(args["store"]) == before


@pytest.mark.parametrize(
    "fault", ["clock", "receipt", "source_ack", "workflow_before", "workflow_after"]
)
def test_operational_uncertainty_never_means_not_created(setup, monkeypatch, fault):
    from datetime import timedelta

    from test_lead_source_admission import counts
    from test_lead_source_auth import NOW, OTHER

    from connect_automate.lead_intake import SourceHandoffUnknown, SourceStoreUncertain

    args, owner, admission = setup
    if fault == "clock":
        args["source_clock"] = lambda: NOW - timedelta(seconds=1)
    runtime = PackRuntime.load(**args)
    with monkeypatch.context() as patch:
        if fault in ("receipt", "source_ack"):
            original = admission.admit_source

            def admit(raw):
                result = original(raw)
                if fault == "source_ack":
                    raise SourceStoreUncertain()
                return result.model_copy(
                    update={"receipt": result.receipt.model_copy(update={"host_id": OTHER})}
                )

            patch.setattr(admission, "admit_source", admit)
        elif fault in ("workflow_before", "workflow_after"):
            original = args["store"].admit_event

            def admit(**kw):
                if fault == "workflow_after":
                    original(**kw)
                raise OSError("private-body-path-sql")

            patch.setattr(args["store"], "admit_event", admit)
        with pytest.raises(
            SourceHandoffUnknown, match="^lead source handoff outcome unknown$"
        ) as caught:
            submit(runtime)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert counts(owner) == (1, 1, 1)
    expected = "accepted" if fault == "workflow_after" else "not_found"
    assert lookup(runtime).workflow_outcome == expected
    args["source_clock"] = lambda: NOW
    retried = submit(PackRuntime.load(**args))
    assert retried.source_applied is False
    assert retried.workflow_applied is (expected == "not_found")


@pytest.mark.parametrize("fault", ["missing", "io"])
def test_lookup_store_failure_is_unknown_not_absence(setup, monkeypatch, fault):
    from connect_automate.lead_intake import SourceHandoffUnknown

    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    if fault == "missing":
        args["store"].path = args["store"].path.parent / "absent.db"
    else:

        def fail(**kw):
            raise OSError("private-path")

        monkeypatch.setattr(args["store"], "lookup_source_event", fail)
    with pytest.raises(SourceHandoffUnknown) as caught:
        lookup(runtime)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("field", ["matched", "matched_type", "applied", "record", "event_id"])
def test_invalid_store_result_cannot_escape_as_success(setup, monkeypatch, field):
    from dataclasses import replace

    from connect_automate.lead_intake import SourceHandoffUnknown

    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    original = args["store"].admit_event

    def admit(**kw):
        result = original(**kw)
        value = {
            "matched": False,
            "matched_type": 1,
            "applied": 1,
            "record": None,
            "event_id": None,
        }[field]
        return replace(result, **{"matched" if field == "matched_type" else field: value})

    with monkeypatch.context() as patch:
        patch.setattr(args["store"], "admit_event", admit)
        patch.setattr(
            runtime, "_dispatch_event_actions", lambda *a: pytest.fail("invalid result dispatched")
        )
        with pytest.raises(SourceHandoffUnknown) as caught:
            submit(runtime)
        assert caught.value.__context__ is None
    assert lookup(runtime).workflow_outcome == "accepted"


def model_payload():
    from test_lead_receipt_vocabulary import OTHER, receipt

    return dict(
        schema="lead.source.handoff.result",
        schema_version="2.0",
        source_receipt=receipt(),
        workflow_outcome="accepted",
        source_applied=True,
        workflow_applied=True,
        workflow_record_id=OTHER,
        workflow_event_id=OTHER,
        stage="ready",
        state_version=2,
        actions=[],
    )


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "schema_version",
        "source_receipt",
        "workflow_outcome",
        "source_applied",
        "workflow_applied",
        "workflow_record_id",
        "workflow_event_id",
        "stage",
        "state_version",
        "actions",
    ],
)
@pytest.mark.parametrize("bad", [None, False, 0, "", "wrong", [], {}])
def test_result_fields_are_required_closed_and_strict(field, bad):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = model_payload()
    value[field] = bad
    valid = (
        (field in ("source_applied", "workflow_applied") and bad is False)
        or (field == "stage" and bad == "wrong")
        or (field == "actions" and bad == [])
    )
    if valid:
        assert SourceHandoffResult.model_validate(value).model_dump(by_alias=True) == value
    else:
        with pytest.raises(ValidationError):
            SourceHandoffResult.model_validate(value)
    value = model_payload()
    value.pop(field)
    with pytest.raises(ValidationError):
        SourceHandoffResult.model_validate(value)


@pytest.mark.parametrize("model", ["submit", "lookup"])
@pytest.mark.parametrize("variant", ["accepted", "no_match", "not_found"])
def test_result_variants_reject_mixed_projection_and_extras(model, variant):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffLookup, SourceHandoffResult

    value = model_payload()
    cls = SourceHandoffResult
    if model == "lookup":
        cls = SourceHandoffLookup
        value.pop("source_applied")
        value["schema"] = "lead.source.handoff.lookup"
        value["workflow_applied"] = False
    value["workflow_outcome"] = variant
    if variant != "accepted":
        value.update(
            workflow_applied=False,
            workflow_record_id=None,
            workflow_event_id=None,
            stage=None,
            state_version=None,
        )
    if variant == "not_found":
        value["source_receipt"] = None
    if variant == "not_found" and model == "submit":
        with pytest.raises(ValidationError):
            cls.model_validate(value)
        return
    assert cls.model_validate(value).model_dump(by_alias=True) == value
    for field in ("workflow_record_id", "workflow_event_id", "stage", "state_version"):
        bad = dict(value)
        bad[field] = None if variant == "accepted" else model_payload()[field]
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
    bad = dict(value)
    bad["private_extra"] = "private-sentinel"
    with pytest.raises(ValidationError):
        cls.model_validate(bad)
    if model == "lookup":
        bad = dict(value)
        bad["source_applied"] = False
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
        bad = dict(value)
        bad["workflow_applied"] = True
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
    if variant != "accepted":
        bad = dict(value)
        bad["workflow_applied"] = True
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
    bad = dict(value)
    bad["source_receipt"] = model_payload()["source_receipt"] if variant == "not_found" else None
    with pytest.raises(ValidationError):
        cls.model_validate(bad)


@pytest.mark.parametrize(
    "field,good,bad",
    [
        ("stage", "界" * 80, "界" * 81),
        ("stage", "a", ""),
        ("state_version", 1, 0),
        ("state_version", 9223372036854775807, 9223372036854775808),
        ("state_version", 2, True),
        ("state_version", 2, 2.0),
        ("source_applied", False, 0),
        ("workflow_applied", False, 0),
    ],
)
def test_projection_field_boundaries(field, good, bad):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = model_payload()
    value[field] = good
    assert getattr(SourceHandoffResult.model_validate(value), field) == good
    value[field] = bad
    with pytest.raises(ValidationError):
        SourceHandoffResult.model_validate(value)


def test_result_byte_cap_and_immutability(monkeypatch):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult, results

    value = model_payload()
    value["stage"] = "界" * 80
    value["actions"] = [_action_item(index) for index in range(8)]
    result = SourceHandoffResult.model_validate(value)
    size = len(result.model_dump_json(by_alias=True).encode("utf-8"))
    assert size < results.MAX_EVENT_BYTES
    for limit in (size, size + 1):
        monkeypatch.setattr(results, "MAX_EVENT_BYTES", limit)
        assert SourceHandoffResult.model_validate(value) == result
    monkeypatch.setattr(results, "MAX_EVENT_BYTES", size - 1)
    with pytest.raises(ValidationError, match="byte limit"):
        SourceHandoffResult.model_validate(value)
    with pytest.raises(ValidationError, match="frozen"):
        result.workflow_applied = False
    with pytest.raises(ValidationError, match="frozen"):
        result.source_receipt.event_id = "changed"


def test_result_instance_revalidated_after_model_copy():
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = SourceHandoffResult.model_validate(model_payload())
    corrupt = value.model_copy(update={"source_applied": 1})
    with pytest.raises(ValidationError):
        SourceHandoffResult.model_validate(corrupt)


def test_generic_public_apis_still_refuse_lead_receipts(setup):
    from test_automate_runtime import PACK_ID, SUBJECT
    from test_lead_source_auth import NOW
    from test_workflow_receipt_lookup import rows

    from connect_automate.automate.events import EventInputError

    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    before = rows(args["store"])
    with pytest.raises(EventInputError):
        runtime.submit_event(binding="inbox", event=encode(prepared.event.model_dump()), now=NOW)
    with pytest.raises(EventInputError):
        runtime._engine.submit_event(
            runtime.workflow,
            subject=SUBJECT,
            pack_id=PACK_ID,
            pack_version=1,
            binding="inbox",
            source=runtime._event_bindings["inbox"],
            event=prepared.event,
            now=NOW,
        )
    assert rows(args["store"]) == before


def test_permitted_local_actions_use_existing_dispatch_and_safe_replay(setup, monkeypatch):
    from test_automate_events import event_workflow
    from test_lead_receipt_vocabulary import workflow

    args, _, _ = setup
    value = workflow()
    value["definitions"][0]["actions"] = event_workflow()["definitions"][0]["actions"]
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    seen = []
    original = runtime._runner.dispatch

    def dispatch(view, *, now, safe_replay=False):
        seen.append(safe_replay)
        return original(view, now=now, safe_replay=safe_replay)

    monkeypatch.setattr(runtime._runner, "dispatch", dispatch)
    first = submit(runtime)
    submit(runtime)
    assert seen == [False, True]
    assert [a.status for a in args["store"].list_actions(first.workflow_record_id)] == ["settled"]
    lookup(runtime)
    assert seen == [False, True]


def test_current_license_rechecked_after_source_commit(setup, monkeypatch):
    from test_lead_source_admission import counts

    from connect_automate.automate.host import AutomateHost, AutomateLicenseError

    args, owner, admission = setup
    runtime = PackRuntime.load(**args)
    original = admission.admit_source

    def admit(raw):
        result = original(raw)
        monkeypatch.setattr(AutomateHost, "licensed", lambda s: False)
        return result

    monkeypatch.setattr(admission, "admit_source", admit)
    with pytest.raises(AutomateLicenseError):
        submit(runtime)
    assert counts(owner) == (1, 1, 1)
    with args["store"].read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 0


def test_missing_source_owner_allows_lookup_but_refuses_submission(setup):
    from connect_automate.automate.events import EventBindingError

    args, _, _ = setup
    args.pop("source_admission")
    args.pop("source_clock")
    runtime = PackRuntime.load(**args)
    assert lookup(runtime).workflow_outcome == "not_found"
    with pytest.raises(EventBindingError):
        submit(runtime)


def test_result_contract_import_does_not_load_operational_owners():
    import subprocess
    import sys

    code = """
import sys
from connect_automate.lead_intake import (
    SourceHandoffResult, SourceHandoffLookup, SourceHandoffUnknown,
)
for suffix in ("admission", "auth", "source_store", "handoff"):
    assert "connect_automate.lead_intake." + suffix not in sys.modules
SourceHandoffLookup.model_validate(dict(
    schema="lead.source.handoff.lookup", schema_version="2.0", source_receipt=None,
    workflow_outcome="not_found", workflow_applied=False, workflow_record_id=None,
    workflow_event_id=None, stage=None, state_version=None, actions=[],
))
assert "connect_automate.automate.runtime" not in sys.modules
assert "connect_automate.automate.store" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("entry", ["submit", "lookup"])
@pytest.mark.parametrize("fault", ["failed", "pending"])
@pytest.mark.parametrize("bad_index", [0, 1])
def test_known_dispatch_states_are_visible_on_submit_lookup_and_replay(
    setup, monkeypatch, entry, fault, bad_index
):
    from test_lead_receipt_vocabulary import workflow

    from connect_automate.automate import AdapterRegistry
    from connect_automate.lead_intake import SourceHandoffUnknown

    args, _, _ = setup
    value = workflow()
    actions = [
        {"action": "notify.local", "request": {"title": "Review", "body": "synthetic"}}
        for _ in range(2)
    ]
    calls = []
    if fault == "failed":
        actions[bad_index]["request"].pop("title")
        adapter = args["registry"].resolve("notify.local")
        native = adapter.deliver

        def deliver(request):
            calls.append(request)
            return native(request)

        monkeypatch.setattr(adapter, "deliver", deliver)
    else:
        args["registry"] = AdapterRegistry()
    value["definitions"][0]["actions"] = actions
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    original_rows = None
    for _ in range(2):
        if entry == "lookup":
            # Isolate lookup even on the old base; submit has its own strict regression.
            with suppress(SourceHandoffUnknown):
                submit(runtime)
            result = lookup(runtime)
        else:
            result = submit(runtime)
        found = lookup(runtime)
        assert result.workflow_outcome == found.workflow_outcome == "accepted"
        rows = args["store"].list_actions(found.workflow_record_id)
        expected = ["settled", "settled"] if fault == "failed" else ["pending", "pending"]
        expected[bad_index] = fault
        projected = [
            dict(action_id=row.action_id, kind=row.kind, status=row.status) for row in rows
        ]
        assert [item.model_dump() for item in result.actions] == projected
        assert [item.model_dump() for item in found.actions] == projected
        assert result.schema_version == found.schema_version == "2.0"
        assert [row.status for row in rows] == expected
        assert len(calls) == (2 if fault == "failed" else 0)
        if original_rows is not None:
            assert rows == original_rows
        original_rows = rows


def _track_source_preparation(runtime, monkeypatch):
    prepared = []
    original = runtime._prepare_source

    def prepare(**kwargs):
        result = original(**kwargs)
        prepared.append(result)
        return result

    monkeypatch.setattr(runtime, "_prepare_source", prepare)
    return prepared


def test_phase_two_binding_refusal_is_not_unknown(setup, monkeypatch):
    from test_lead_source_admission import counts
    from test_lead_source_auth import OTHER
    from test_workflow_receipt_lookup import corrupt, rows

    from connect_automate.automate.events import EventBindingError

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    prepared = _track_source_preparation(runtime, monkeypatch)
    source_id = args["event_bindings"]["inbox"]["source_id"]
    corrupt(args["store"], "workflow_source_bindings", "source_id=?", (OTHER,))
    before = rows(args["store"])
    with pytest.raises(EventBindingError, match="^invalid event binding$") as caught:
        submit(runtime)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert len(prepared) == 1 and prepared[0].source_applied is True
    assert counts(owner) == (1, 1, 1)
    assert rows(args["store"]) == before
    corrupt(args["store"], "workflow_source_bindings", "source_id=?", (source_id,))
    recovered = submit(runtime)
    assert recovered.source_applied is False and recovered.workflow_applied is True
    assert recovered.source_receipt == prepared[0].event.source_receipt


def test_phase_two_receipt_conflict_is_not_unknown(setup, monkeypatch):
    from test_lead_source_admission import counts
    from test_workflow_receipt_lookup import corrupt, rows

    from connect_automate.automate.events import EventConflict

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    prepared = _track_source_preparation(runtime, monkeypatch)
    with args["store"].read_connection() as db:
        fingerprint = db.execute("SELECT fingerprint FROM workflow_event_receipts").fetchone()[0]
    corrupt(args["store"], "workflow_event_receipts", "fingerprint=?", ("b" * 64,))
    before = rows(args["store"])
    with pytest.raises(EventConflict, match="^event identity conflict$") as caught:
        submit(runtime)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert len(prepared) == 1 and prepared[0].source_applied is False
    assert prepared[0].event.source_receipt == first.source_receipt
    assert counts(owner) == (1, 1, 1)
    assert rows(args["store"]) == before
    corrupt(args["store"], "workflow_event_receipts", "fingerprint=?", (fingerprint,))
    replay = submit(runtime)
    assert replay.source_applied is False and replay.workflow_applied is False
    assert replay.workflow_record_id == first.workflow_record_id
    assert replay.workflow_event_id == first.workflow_event_id


@pytest.mark.parametrize(
    "field,bad",
    [
        pytest.param("event_id", None, id="id-null"),
        pytest.param("event_id", False, id="id-false"),
        pytest.param("event_id", 0, id="id-zero"),
        pytest.param("event_id", "", id="id-empty"),
        pytest.param("event_id", "not-a-uuid", id="id-malformed"),
        pytest.param("event_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa".upper(), id="id-case"),
        pytest.param("expected_payload_digest", None, id="digest-null"),
        pytest.param("expected_payload_digest", False, id="digest-false"),
        pytest.param("expected_payload_digest", 0, id="digest-zero"),
        pytest.param("expected_payload_digest", "", id="digest-empty"),
        pytest.param("expected_payload_digest", "a" * 63, id="digest-short"),
        pytest.param("expected_payload_digest", "a" * 65, id="digest-long"),
        pytest.param("expected_payload_digest", "A" * 64, id="digest-case"),
        pytest.param("expected_payload_digest", "g" * 64, id="digest-nonhex"),
    ],
)
def test_public_lookup_input_refusal_is_not_unknown(setup, monkeypatch, field, bad):
    from test_lead_source_admission import counts
    from test_workflow_receipt_lookup import rows

    from connect_automate.automate.events import EventInputError

    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    valid = lookup(runtime)
    assert valid.workflow_outcome == "not_found"
    before = rows(args["store"])

    def forbidden(*args, **kwargs):
        pytest.fail("invalid lookup accessed storage")

    with monkeypatch.context() as patch:
        patch.setattr(owner, "_transaction", forbidden)
        patch.setattr(args["store"], "connection", forbidden)
        patch.setattr(args["store"], "read_connection", forbidden)
        with pytest.raises(EventInputError, match="^invalid event input$") as caught:
            lookup(runtime, **{field: bad})
        assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert lookup(runtime) == valid
    assert rows(args["store"]) == before
    assert counts(owner) == (0, 0, 0)


def _action_item(index=0, status="settled"):
    return dict(
        action_id=f"{index + 1:08x}-0000-4000-8000-000000000001",
        kind="notify.local",
        status=status,
    )


def _result_payload(entry):
    from connect_automate.lead_intake import SourceHandoffLookup, SourceHandoffResult

    value = model_payload()
    if entry == "lookup":
        value.pop("source_applied")
        value.update(schema="lead.source.handoff.lookup", workflow_applied=False)
        return SourceHandoffLookup, value
    return SourceHandoffResult, value


def _runtime_with_actions(args, count=1, *, failed=()):
    from test_lead_receipt_vocabulary import workflow

    value = workflow()
    value["definitions"][0]["actions"] = [
        dict(action="notify.local", request=dict(title=f"Review {index}", body="private-body"))
        for index in range(count)
    ]
    for index in failed:
        value["definitions"][0]["actions"][index]["request"].pop("title")
    signed_workflow(args, value)
    return PackRuntime.load(**args)


@pytest.mark.parametrize("entry", ["submit", "lookup"])
@pytest.mark.parametrize("count", [0, 1, 8])
def test_action_projection_accepts_every_supported_count(entry, count):
    model, value = _result_payload(entry)
    value["actions"] = [_action_item(index) for index in range(count)]
    assert model.model_validate(value).model_dump(by_alias=True) == value


@pytest.mark.parametrize("entry", ["submit", "lookup"])
@pytest.mark.parametrize("field", ["action_id", "kind", "status"])
@pytest.mark.parametrize("bad", [None, False, 0, "", "wrong", [], {}])
def test_action_items_require_closed_strict_fields(entry, field, bad):
    from pydantic import ValidationError

    model, value = _result_payload(entry)
    value["actions"] = [_action_item()]
    value["actions"][0][field] = bad
    with pytest.raises(ValidationError):
        model.model_validate(value)
    value["actions"] = [_action_item()]
    value["actions"][0].pop(field)
    with pytest.raises(ValidationError):
        model.model_validate(value)


@pytest.mark.parametrize("entry", ["submit", "lookup"])
@pytest.mark.parametrize(
    "bad",
    [None, False, 0, "", {}, (), [None], [False], [_action_item(), None]],
)
def test_action_array_is_required_and_never_defaulted(entry, bad):
    from pydantic import ValidationError

    model, value = _result_payload(entry)
    value["actions"] = bad
    with pytest.raises(ValidationError):
        model.model_validate(value)
    value.pop("actions")
    with pytest.raises(ValidationError):
        model.model_validate(value)


@pytest.mark.parametrize("entry", ["submit", "lookup"])
@pytest.mark.parametrize("fault", ["duplicate", "nine", "extra", "kind", "case", "v1"])
def test_action_projection_rejects_mixed_overflow_and_old_contract(entry, fault):
    from pydantic import ValidationError

    model, value = _result_payload(entry)
    value["actions"] = [_action_item()]
    if fault == "duplicate":
        value["actions"].append(_action_item(status="failed"))
    elif fault == "nine":
        value["actions"] = [_action_item(index) for index in range(9)]
    elif fault == "extra":
        value["actions"][0]["private_error"] = "private-path-body-sql"
    elif fault == "kind":
        value["actions"][0]["kind"] = "mail.send"
    elif fault == "case":
        value["actions"][0]["action_id"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa".upper()
    else:
        value["schema_version"] = "1.0"
    with pytest.raises(ValidationError):
        model.model_validate(value)


@pytest.mark.parametrize("entry", ["submit", "lookup"])
def test_no_match_cannot_carry_actions(entry):
    from pydantic import ValidationError

    model, value = _result_payload(entry)
    value.update(
        workflow_outcome="no_match",
        workflow_applied=False,
        workflow_record_id=None,
        workflow_event_id=None,
        stage=None,
        state_version=None,
        actions=[_action_item()],
    )
    with pytest.raises(ValidationError):
        model.model_validate(value)
    if entry == "lookup":
        value.update(workflow_outcome="not_found", source_receipt=None)
        with pytest.raises(ValidationError):
            model.model_validate(value)


@pytest.mark.parametrize("count", [0, 1, 8])
def test_real_action_delivery_preserves_order_and_size_bounds(setup, count):
    args, _, _ = setup
    runtime = _runtime_with_actions(args, count)
    first = submit(runtime)
    rows = args["store"].list_actions(first.workflow_record_id)
    assert len(first.actions) == count
    assert [item.action_id for item in first.actions] == [row.action_id for row in rows]
    assert [item.status for item in first.actions] == ["settled"] * count
    assert lookup(runtime).actions == first.actions == submit(runtime).actions
    assert len(first.model_dump_json(by_alias=True).encode()) <= 8192
    assert "private-body" not in first.model_dump_json()


def test_overflow_snapshot_is_unknown_instead_of_truncated_success(setup, monkeypatch):
    from test_lead_source_auth import NOW

    from connect_automate.lead_intake import SourceHandoffUnknown

    args, _, _ = setup
    runtime = _runtime_with_actions(args, 8)
    first = submit(runtime)
    # A malformed durable state must not turn a ninth event-owned row into success.
    # Normal admission already enforces eight; this probes the reader's own boundary.
    with args["store"].connection() as db:
        db.execute(
            "INSERT INTO workflow_actions "
            "(action_id, record_id, dedupe_key, kind, request, status, result, "
            "last_error, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)",
            (
                _action_item(8)["action_id"],
                first.workflow_record_id,
                f"pack.action:{first.workflow_event_id}:8",
                "notify.local",
                "{}",
                "pending",
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    monkeypatch.setattr(
        runtime, "_dispatch_event_actions", lambda *args: pytest.fail("invalid snapshot dispatched")
    )
    for operation in (lookup, submit):
        with pytest.raises(SourceHandoffUnknown) as caught:
            operation(runtime)
        assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("fault", ["before", "after", "normal"])
@pytest.mark.parametrize("unreadable", [False, True])
def test_dispatch_reads_once_after_attempt_without_redispatch(
    setup, monkeypatch, fault, unreadable
):
    from connect_automate.lead_intake import SourceHandoffUnknown

    args, _, _ = setup
    runtime = _runtime_with_actions(args)
    original_dispatch = runtime._dispatch_event_actions
    original_read = args["store"].lookup_source_event
    dispatches, reads = [], []

    def dispatch(*args):
        dispatches.append(True)
        if fault != "before":
            original_dispatch(*args)
        if fault != "normal":
            raise RuntimeError("private-title-path-body-sql")

    def read(**kwargs):
        reads.append(bool(dispatches))
        if unreadable and dispatches:
            raise OSError("private-title-path-body-sql")
        return original_read(**kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(runtime, "_dispatch_event_actions", dispatch)
        patch.setattr(args["store"], "lookup_source_event", read)
        if unreadable:
            with pytest.raises(SourceHandoffUnknown) as caught:
                submit(runtime)
            assert caught.value.__context__ is None and caught.value.__cause__ is None
            assert str(caught.value) == "lead source handoff outcome unknown"
        else:
            result = submit(runtime)
            assert [item.status for item in result.actions] == [
                "pending" if fault == "before" else "settled"
            ]
    assert dispatches == [True] and reads == [False, True]
    assert [item.status for item in lookup(runtime).actions] == [
        "pending" if fault == "before" else "settled"
    ]


@pytest.mark.parametrize("name", ["license", "binding", "conflict", "ambiguity", "revision"])
def test_dispatch_known_refusal_never_becomes_recovery_result(setup, monkeypatch, name):
    from connect_automate.automate.engine import PackVersionError
    from connect_automate.automate.events import AmbiguousEvent, EventBindingError, EventConflict
    from connect_automate.automate.host import AutomateLicenseError

    refusal = {
        "license": AutomateLicenseError,
        "binding": EventBindingError,
        "conflict": EventConflict,
        "ambiguity": AmbiguousEvent,
        "revision": PackVersionError,
    }[name]
    args, _, _ = setup
    runtime = _runtime_with_actions(args)
    original_read = args["store"].lookup_source_event
    reads = []

    def read(**kwargs):
        reads.append(True)
        return original_read(**kwargs)

    def denied(*args):
        raise refusal()

    monkeypatch.setattr(args["store"], "lookup_source_event", read)
    monkeypatch.setattr(runtime, "_dispatch_event_actions", denied)
    with pytest.raises(refusal):
        submit(runtime)
    assert reads == [True]
    assert [item.status for item in lookup(runtime).actions] == ["pending"]


@pytest.mark.parametrize("failed", [False, True])
def test_pending_recovery_and_restart_never_retry_terminal_actions(setup, monkeypatch, failed):
    from test_lead_source_auth import NOW

    from connect_automate.automate import AdapterRegistry

    args, _, _ = setup
    args["registry"] = AdapterRegistry()
    runtime = _runtime_with_actions(args, failed=(0,) if failed else ())
    pending = submit(runtime)
    assert [item.status for item in pending.actions] == ["pending"]
    args["registry"] = AdapterRegistry.with_defaults()
    adapter = args["registry"].resolve("notify.local")
    native = adapter.deliver
    calls = []

    def deliver(request):
        calls.append(request)
        return native(request)

    monkeypatch.setattr(adapter, "deliver", deliver)
    restarted = PackRuntime.load(**args)
    recovered = restarted._runner.recover_pending(now=NOW)
    expected = "failed" if failed else "settled"
    assert [item.status for item in recovered] == [expected]
    assert restarted._runner.recover_pending(now=NOW) == []
    found = lookup(PackRuntime.load(**args))
    assert [item.status for item in found.actions] == [expected]
    assert found.actions[0].action_id == pending.actions[0].action_id
    replay = submit(restarted)
    assert replay.actions == found.actions
    assert not replay.workflow_applied and not replay.source_applied
    assert len(calls) == 1


@pytest.mark.parametrize(
    "statuses",
    [
        ("settled", "failed", "pending"),
        ("pending", "failed", "settled"),
        ("failed", "pending", "settled"),
    ],
)
def test_mixed_actions_keep_every_state_on_submit_and_lookup(setup, statuses):
    from test_lead_source_auth import NOW

    from connect_automate.automate import AdapterRegistry

    args, _, _ = setup
    args["registry"] = AdapterRegistry()
    runtime = _runtime_with_actions(args, 3)
    pending = submit(runtime)
    for item, status in zip(pending.actions, statuses, strict=True):
        if status == "settled":
            args["store"].settle_action(item.action_id, result={}, now=NOW)
        elif status == "failed":
            args["store"].fail_action(item.action_id, error="private-error", now=NOW)
    for result in (lookup(runtime), submit(runtime), lookup(PackRuntime.load(**args))):
        assert [item.status for item in result.actions] == list(statuses)
        assert [item.action_id for item in result.actions] == [a.action_id for a in pending.actions]
        assert "private-error" not in result.model_dump_json()


def test_event_projection_excludes_later_decision_and_other_record_actions(setup):
    from test_automate_events import event_workflow
    from test_lead_receipt_vocabulary import workflow
    from test_lead_source_auth import NOW, OTHER, resign

    args, _, _ = setup
    value = workflow()
    value["definitions"][0]["actions"] = event_workflow()["definitions"][0]["actions"]
    later = event_workflow()["definitions"][1]
    later["actions"] = [dict(action="notify.local", request=dict(body="later-private"))]
    value["definitions"].append(later)
    signed_workflow(args, value)
    runtime = PackRuntime.load(**args)
    first = submit(runtime)
    decision = runtime.submit_decision(
        first.workflow_record_id,
        decision="approve",
        operation_key="later",
        request={},
        expected_version=first.state_version,
        now=NOW,
    )
    assert [item.status for item in decision.actions] == ["failed"]
    raw = envelope()
    raw["payload"]["event_id"] = OTHER
    other = submit(runtime, resign(raw))
    assert other.actions[0].action_id != first.actions[0].action_id
    # Probe both selector clauses independently: a foreign record with a forged
    # reserved event prefix must not join this event's public projection.
    with args["store"].connection() as db:
        db.execute(
            "INSERT INTO workflow_actions "
            "(action_id, record_id, dedupe_key, kind, request, status, result, "
            "last_error, created_at, updated_at) "
            "SELECT ?, record_id, ?, kind, request, status, result, last_error, "
            "created_at, updated_at FROM workflow_actions WHERE action_id = ?",
            (
                _action_item(7)["action_id"],
                f"pack.action:{first.workflow_event_id}:7",
                other.actions[0].action_id,
            ),
        )
    for result in (lookup(runtime), submit(runtime)):
        assert result.actions == first.actions
        assert result.stage == "ready" and result.state_version == first.state_version
    assert len(args["store"].list_actions(first.workflow_record_id)) == 2


@pytest.mark.parametrize("status", ["settled", "failed", "pending"])
def test_action_lookup_uses_no_source_writer_clock_or_dispatch(setup, monkeypatch, status):
    from test_workflow_receipt_lookup import rows

    from connect_automate.automate import AdapterRegistry

    args, owner, admission = setup
    if status == "pending":
        args["registry"] = AdapterRegistry()
    runtime = _runtime_with_actions(args, failed=(0,) if status == "failed" else ())
    result = submit(runtime)
    before = rows(args["store"])
    args.pop("source_admission")
    args.pop("source_clock")
    historical = PackRuntime.load(**args)

    def forbidden(*args, **kwargs):
        pytest.fail("action lookup crossed a source/writer/clock/dispatch boundary")

    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(admission, "admit_source", forbidden)
    monkeypatch.setattr(args["store"], "connection", forbidden)
    monkeypatch.setattr(historical, "_dispatch_event_actions", forbidden)
    monkeypatch.setattr(runtime, "_dispatch_event_actions", forbidden)
    assert lookup(runtime).actions == lookup(historical).actions == result.actions
    assert rows(args["store"]) == before


def _settle_source_actions(path, action_ids, channel):
    from test_lead_source_auth import NOW

    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(path)
    for action_id in action_ids:
        store.settle_action(action_id, result={}, now=NOW)
    channel.put("settled")


def test_action_lookup_shares_receipt_snapshot_during_process_settlement(setup, monkeypatch):
    import multiprocessing
    from contextlib import contextmanager

    from connect_automate.automate import AdapterRegistry

    args, _, _ = setup
    args["registry"] = AdapterRegistry()
    runtime = _runtime_with_actions(args, 2)
    pending = submit(runtime)
    native = args["store"].read_connection
    ctx = multiprocessing.get_context("spawn")
    channel = ctx.Queue()
    writer = ctx.Process(
        target=_settle_source_actions,
        args=(args["store"].path, [a.action_id for a in pending.actions], channel),
    )
    started = []

    @contextmanager
    def paused_read():
        with native() as db:
            if not started:
                started.append(True)
                writer.start()
                assert channel.get(timeout=30) == "settled"
                writer.join(timeout=30)
                assert writer.exitcode == 0
            yield db

    try:
        with monkeypatch.context() as patch:
            patch.setattr(args["store"], "read_connection", paused_read)
            assert [a.status for a in lookup(runtime).actions] == ["pending", "pending"]
        assert [a.status for a in lookup(runtime).actions] == ["settled", "settled"]
    finally:
        if writer.is_alive():
            writer.terminate()
            writer.join(timeout=30)
        channel.close()
        channel.join_thread()


def _crash_source_before_dispatch(case):
    import os

    from test_lead_joined_recovery import CRASH_EXIT, open_runtime

    runtime, _, _, _ = open_runtime(case)

    def crash(*args):
        os._exit(CRASH_EXIT)

    runtime._dispatch_event_actions = crash
    submit(runtime, case["raw"])


def test_process_crash_retains_pending_actions_for_safe_recovery(tmp_path):
    import multiprocessing

    from test_lead_joined_recovery import CRASH_EXIT, make_case, open_runtime
    from test_lead_receipt_vocabulary import workflow
    from test_lead_source_auth import NOW

    case = make_case.__wrapped__(tmp_path)()
    value = workflow()
    value["definitions"][0]["actions"] = [
        dict(action="notify.local", request=dict(title="Review", body="synthetic"))
    ]
    signed_workflow(case["args"], value)
    worker = multiprocessing.get_context("spawn").Process(
        target=_crash_source_before_dispatch, args=(case,)
    )
    try:
        worker.start()
        worker.join(timeout=30)
        assert worker.exitcode == CRASH_EXIT
        runtime, _, _, _ = open_runtime(case)
        found = lookup(runtime, case["raw"])
        assert [a.status for a in found.actions] == ["pending"]
        assert [a.status for a in runtime._runner.recover_pending(now=NOW)] == ["settled"]
        replay = submit(runtime, case["raw"])
        assert replay.actions[0].action_id == found.actions[0].action_id
        assert [a.status for a in replay.actions] == ["settled"]
        assert not replay.workflow_applied and not replay.source_applied
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=30)
