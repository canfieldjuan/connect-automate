"""Library-only authenticated workflow boundary; synthetic sources and real stores."""

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
    "fault", ["clock", "receipt", "source_ack", "workflow_before", "workflow_after", "dispatch"]
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
        elif fault == "dispatch":

            def dispatch(*a):
                raise RuntimeError("private-body-path-sql")

            patch.setattr(runtime, "_dispatch_event_actions", dispatch)
        with pytest.raises(
            SourceHandoffUnknown, match="^lead source handoff outcome unknown$"
        ) as caught:
            submit(runtime)
        assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert counts(owner) == (1, 1, 1)
    expected = "accepted" if fault in ("workflow_after", "dispatch") else "not_found"
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
        schema_version="1.0",
        source_receipt=receipt(),
        workflow_outcome="accepted",
        source_applied=True,
        workflow_applied=True,
        workflow_record_id=OTHER,
        workflow_event_id=OTHER,
        stage="ready",
        state_version=2,
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
    ],
)
@pytest.mark.parametrize("bad", [None, False, 0, "", "wrong", [], {}])
def test_result_fields_are_required_closed_and_strict(field, bad):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = model_payload()
    value[field] = bad
    valid = (field in ("source_applied", "workflow_applied") and bad is False) or (
        field == "stage" and bad == "wrong"
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
    schema="lead.source.handoff.lookup", schema_version="1.0", source_receipt=None,
    workflow_outcome="not_found", workflow_applied=False, workflow_record_id=None,
    workflow_event_id=None, stage=None, state_version=None,
))
assert "connect_automate.automate.runtime" not in sys.modules
assert "connect_automate.automate.store" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)
