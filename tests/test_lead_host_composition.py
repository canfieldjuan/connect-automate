"""Private trusted-host composition; no public workflow submission or adoption."""

import sqlite3
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_automate_runtime import (
    PACK_ID,
    SUBJECT,
    _envelope,
    _grant_bytes,
    _licensed_host,
    _pack_keys,
    _store,
)
from test_lead_receipt_vocabulary import workflow
from test_lead_source_admission import counts
from test_lead_source_auth import NOW, OTHER, encode, envelope, key, resign, trust, trust_data
from test_lead_source_store import private_root as private_root
from test_lead_source_store import store
from test_workflow_receipt_lookup import rows

from connect_automate.automate import AdapterRegistry, PackRuntime
from connect_automate.automate.engine import PackVersionError
from connect_automate.automate.events import EventBindingError, EventConflict, EventInputError
from connect_automate.automate.host import AutomateHost, AutomateLicenseError
from connect_automate.automate.pack import PackError
from connect_automate.lead_intake import (
    SourceAdmission,
    SourceAdmissionConflict,
    SourceAuthenticationError,
    SourceInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
    SourceTrustSnapshot,
    parse_untrusted_source,
    payload_digest,
)


def source_binding():
    value = envelope()
    namespace = value["payload"]["source"]["namespace_id"]
    return dict(
        source_kind="lead.source.received",
        source_id=namespace,
        scope=encode(
            dict(
                host_id=value["authorization"]["host_id"],
                organization_id=value["payload"]["organization_id"],
                namespace_id=namespace,
            )
        ).decode(),
    )


@pytest.fixture
def setup(tmp_path, private_root):
    owner = store(private_root)
    owner.initialize(trust())
    admission = SourceAdmission(owner, clock=lambda: NOW)
    signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    grant = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    workflow_store = _store(tmp_path)
    args = dict(
        pack_bytes=_envelope(
            signer,
            encode(dict(format_version=2, pack_id=PACK_ID, pack_version=1, workflow=workflow())),
        ),
        grant_bytes=_grant_bytes(grant),
        store=workflow_store,
        host=_licensed_host(tmp_path),
        registry=AdapterRegistry.with_defaults(),
        publisher_keys=_pack_keys(signer),
        grant_keys=_pack_keys(grant),
        subject=SUBJECT,
        now=NOW,
        event_bindings={"inbox": source_binding()},
        source_admission=admission,
        source_clock=lambda: NOW,
    )
    return args, owner, admission


def test_real_source_preparation_reauthenticates_and_only_commits_custody(setup, monkeypatch):
    args, owner, admission = setup
    runtime = PackRuntime.load(**args)

    def forbidden(*a, **kw):
        pytest.fail("preparation reached workflow admission/dispatch")

    monkeypatch.setattr(runtime._engine, "submit_event", forbidden)
    monkeypatch.setattr(runtime, "_dispatch_event_actions", forbidden)
    raw = encode(envelope())
    first = runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    second = runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    assert first.source_applied is True and second.source_applied is False
    assert first.event == second.event and first.now == NOW
    assert first.event.source_receipt.payload_digest == payload_digest(parse_untrusted_source(raw))
    assert counts(owner) == (1, 1, 1)
    with args["store"].read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 0
    # Public submission exists; private preparation still cannot admit workflows.


def test_admission_deployment_metadata_has_no_io(setup, monkeypatch):
    args, owner, admission = setup
    monkeypatch.setattr(owner, "_transaction", lambda: pytest.fail("opened source store"))
    assert admission.deployment == (trust().host_id, trust().organization_id)


def lookup(runtime, **updates):
    arguments = dict(
        binding="inbox",
        event_id=envelope()["payload"]["event_id"],
        expected_payload_digest=payload_digest(parse_untrusted_source(encode(envelope()))),
    )
    arguments.update(updates)
    return runtime._lookup_source_receipt(**arguments)


@pytest.mark.parametrize("state", ["available", "unavailable"])
def test_body_only_and_unavailable_metadata(setup, state):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    value = envelope()
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = dict(state="unavailable", reason="source_gone")
    before = rows(args["store"])
    result = runtime._prepare_source(binding="inbox", raw_source_bytes=resign(value))
    assert result.source_applied is True
    assert result.event.source_receipt.event_id == value["payload"]["event_id"]
    assert set(result.event.model_dump()) == {"source_kind", "schema_version", "source_receipt"}
    assert rows(args["store"]) == before
    assert counts(owner) == (1, 1, 1)


@pytest.mark.parametrize("option", ["source_admission", "source_clock"])
@pytest.mark.parametrize("bad", [None, False, 0, "", {}, object()])
def test_partial_and_wrong_trusted_configuration_before_registration(
    setup, monkeypatch, option, bad
):
    args, _, _ = setup
    args[option] = bad
    monkeypatch.setattr(args["store"], "register_bindings", lambda *a: pytest.fail("registered"))
    with pytest.raises(EventBindingError):
        PackRuntime.load(**args)


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_foreign_owner_rejected_before_registration(setup, monkeypatch, field):
    args, owner, _ = setup
    setattr(owner, field, OTHER)
    monkeypatch.setattr(args["store"], "register_bindings", lambda *a: pytest.fail("registered"))
    with pytest.raises(EventBindingError):
        PackRuntime.load(**args)


@pytest.mark.parametrize("fault", ["license", "pack", "grant"])
def test_load_authorization_precedes_composition(setup, monkeypatch, fault):
    args, _, _ = setup

    def reached(*a):
        pytest.fail("source metadata before pack/license gate")

    monkeypatch.setattr(SourceAdmission, "deployment", property(reached))
    monkeypatch.setattr(args["store"], "register_bindings", reached)
    expected = PackError
    if fault == "license":
        monkeypatch.setattr(AutomateHost, "licensed", lambda s: False)
        expected = AutomateLicenseError
    else:
        args[fault + "_bytes"] = b"invalid"
    with pytest.raises(expected):
        PackRuntime.load(**args)


def test_non_lead_pack_refuses_source_configuration(setup, monkeypatch):
    from test_automate_events import event_workflow
    from test_automate_events import source_binding as mail_binding

    args, _, _ = setup
    signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    args["pack_bytes"] = _envelope(
        signer,
        encode(dict(format_version=2, pack_id=PACK_ID, pack_version=1, workflow=event_workflow())),
    )
    args["event_bindings"] = {"inbox": mail_binding()}
    monkeypatch.setattr(args["store"], "register_bindings", lambda *a: pytest.fail("registered"))
    with pytest.raises(EventBindingError):
        PackRuntime.load(**args)


@pytest.mark.parametrize("entry", ["prepare", "lookup"])
@pytest.mark.parametrize("fault", ["license", "unknown", "falsy", "list"])
def test_operation_gates_before_any_owner_access(setup, monkeypatch, entry, fault):
    args, _, admission = setup
    runtime = PackRuntime.load(**args)

    def reached(*a, **kw):
        pytest.fail("owner access before route/license gate")

    monkeypatch.setattr(admission, "admit_source", reached)
    monkeypatch.setattr(args["store"], "lookup_source_event", reached)
    name = "inbox"
    expected = EventBindingError
    if fault == "license":
        monkeypatch.setattr(AutomateHost, "licensed", lambda s: False)
        expected = AutomateLicenseError
    else:
        name = {"unknown": "missing", "falsy": False, "list": []}[fault]
    with pytest.raises(expected):
        if entry == "prepare":
            runtime._prepare_source(binding=name, raw_source_bytes=encode(envelope()))
        else:
            lookup(runtime, binding=name)


@pytest.mark.parametrize("field", ["host_id", "organization_id", "namespace_id"])
def test_request_scope_denial_before_source_mutation(setup, monkeypatch, field):
    args, _, admission = setup
    runtime = PackRuntime.load(**args)
    value = envelope()
    target = (
        value["authorization"]
        if field == "host_id"
        else (value["payload"]["source"] if field == "namespace_id" else value["payload"])
    )
    target[field] = OTHER
    monkeypatch.setattr(
        admission, "admit_source", lambda raw: pytest.fail("scope reached admission")
    )
    with pytest.raises(EventBindingError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=resign(value))


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_owner_drift_refused_before_source_mutation(setup, monkeypatch, field):
    args, owner, admission = setup
    runtime = PackRuntime.load(**args)
    setattr(owner, field, OTHER)
    monkeypatch.setattr(
        admission, "admit_source", lambda raw: pytest.fail("drift reached admission")
    )
    with pytest.raises(EventBindingError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))


@pytest.mark.parametrize("kind", ["parsed", "receipt", "result", "dict", "bytearray", "empty"])
def test_copied_values_cannot_replace_raw_authentication(setup, monkeypatch, kind):
    args, _, admission = setup
    runtime = PackRuntime.load(**args)
    raw = encode(envelope())
    prior = admission.admit_source(raw)
    value = dict(
        parsed=parse_untrusted_source(raw),
        receipt=prior.receipt,
        result=prior,
        dict=envelope(),
        bytearray=bytearray(raw),
        empty=b"",
    )[kind]
    monkeypatch.setattr(
        admission, "admit_source", lambda raw: pytest.fail("nonbytes reached admission")
    )
    with pytest.raises(SourceInputError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=value)


@pytest.mark.parametrize(
    "field",
    [
        "host_id",
        "organization_id",
        "namespace_id",
        "event_id",
        "payload_digest",
        "recovery_deadline",
    ],
)
def test_fresh_receipt_must_match_request(setup, monkeypatch, field):
    args, _, admission = setup
    runtime = PackRuntime.load(**args)
    raw = encode(envelope())
    prior = admission.admit_source(raw)
    wrong = (
        "b" * 64
        if field == "payload_digest"
        else ("2026-10-18T13:00:01Z" if field == "recovery_deadline" else OTHER)
    )
    receipt = prior.receipt.model_copy(update={field: wrong})
    # All identifiers/intervals are valid: only the agreement check can refuse.
    changed = prior.model_copy(update={"receipt": receipt})
    monkeypatch.setattr(admission, "admit_source", lambda raw: changed)
    with pytest.raises(SourceStoreUnavailable) as caught:
        runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("fault", ["dict", "bool", "applied", "receipt"])
def test_malformed_owner_result_is_bounded(setup, monkeypatch, fault):
    args, _, admission = setup
    runtime = PackRuntime.load(**args)
    raw = encode(envelope())
    prior = admission.admit_source(raw)
    invalid = dict(
        dict=prior.model_dump(by_alias=True),
        bool=False,
        applied=prior.model_copy(update={"applied": 1}),
        receipt=prior.model_copy(
            update={
                "receipt": prior.receipt.model_copy(update={"admission_id": "private-sentinel"})
            }
        ),
    )[fault]
    monkeypatch.setattr(admission, "admit_source", lambda raw: invalid)
    with pytest.raises(SourceStoreUnavailable) as caught:
        runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    assert "private-sentinel" not in repr(caught.value)
    assert caught.value.__context__ is None


def test_configuration_and_prepared_values_are_frozen(setup):
    args, _, admission = setup
    runtime = PackRuntime.load(**args)
    args["event_bindings"]["inbox"]["scope"] = "changed"
    args["event_bindings"].clear()
    args["source_clock"] = lambda: pytest.fail("rebound clock")
    args["source_admission"] = None
    handoff = runtime._source_handoffs["inbox"]
    with pytest.raises(TypeError):
        runtime._source_handoffs["inbox"] = None
    with pytest.raises(TypeError):
        runtime._event_bindings["inbox"] = None
    for field in ("admission", "clock", "source"):
        with pytest.raises(FrozenInstanceError):
            setattr(handoff, field, None)
    with pytest.raises(AttributeError):
        admission.deployment = (OTHER, OTHER)
    result = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    with pytest.raises(FrozenInstanceError):
        result.source_applied = False
    with pytest.raises(ValueError, match="frozen"):
        result.event.source_receipt.event_id = OTHER
    assert result.now == NOW


def test_clock_runs_after_source_writer_is_released(setup):
    args, owner, _ = setup

    def clock():
        with owner._transaction():
            pass
        return NOW

    owner.busy_timeout_ms = 1
    args["source_clock"] = clock
    runtime = PackRuntime.load(**args)
    assert runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope())).now == NOW


@pytest.mark.parametrize(
    "value", [None, False, "", NOW.replace(tzinfo=None), NOW - timedelta(seconds=1)]
)
def test_workflow_clock_checked_by_event_owner(setup, value):
    args, owner, _ = setup
    args["source_clock"] = lambda: value
    runtime = PackRuntime.load(**args)
    with pytest.raises(EventInputError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    # No false workflow result: only source custody has committed.
    assert counts(owner) == (1, 1, 1)
    assert lookup(runtime) is None


def test_replay_requires_current_auth_and_rotation_keeps_projection(setup):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    raw = encode(envelope())
    first = runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    data = trust_data()
    data["key_grants"][0]["status"] = "revoked"
    rotated = deepcopy(data["key_grants"][0])
    signer = key(bytes(reversed(range(32))))
    rotated.update(key_id=OTHER, status="active", public_key=signer.public_key().public_bytes_raw())
    data["key_grants"].append(rotated)
    data["generation"] = 2
    owner.publish_authority(SourceTrustSnapshot.model_validate(data), expected_generation=1)
    with pytest.raises(SourceAuthenticationError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=raw)
    value = envelope()
    value["authorization"]["key_id"] = OTHER
    replay = runtime._prepare_source(binding="inbox", raw_source_bytes=resign(value, signer))
    assert replay.event == first.event and replay.source_applied is False


def test_conflict_and_distinct_events_use_source_owner(setup):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    first = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    value = envelope()
    value["payload"]["source"]["message_id"] = "other-message"
    with pytest.raises(SourceAdmissionConflict):
        runtime._prepare_source(binding="inbox", raw_source_bytes=resign(value))
    value = envelope()
    value["payload"]["event_id"] = OTHER
    second = runtime._prepare_source(binding="inbox", raw_source_bytes=resign(value))
    assert second.event.source_receipt.admission_id != first.event.source_receipt.admission_id
    assert counts(owner) == (2, 2, 2)


def test_source_uncertain_commit_stops_and_retry_reauthenticates(setup, monkeypatch):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    original = sqlite3.connect

    class LostAck(sqlite3.Connection):
        def commit(self):
            super().commit()
            raise sqlite3.OperationalError("private-lost-reply")

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=LostAck))
        with pytest.raises(SourceStoreUncertain):
            runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    result = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    assert result.source_applied is False and counts(owner) == (1, 1, 1)
    assert lookup(runtime) is None


def test_lookup_only_runtime_does_not_require_source_owner(setup, monkeypatch):
    args, _, _ = setup
    args.pop("source_admission")
    args.pop("source_clock")
    runtime = PackRuntime.load(**args)
    assert lookup(runtime) is None
    monkeypatch.setattr(args["store"], "connection", lambda: pytest.fail("lookup opened writer"))
    assert lookup(runtime) is None
    with pytest.raises(EventBindingError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))


def seed_workflow(args, prepared, matched):
    # Seed only through the real workflow owner: engine selection is the next slice.
    return args["store"].admit_event(
        subject=SUBJECT,
        pack_id=PACK_ID,
        pack_version=1,
        binding="inbox",
        source_id=source_binding()["source_id"],
        source_kind="lead.source.received",
        occurrence=prepared.event.source_receipt.event_id,
        payload=encode(prepared.event.model_dump()),
        workflow=workflow()["name"],
        initial_stage="waiting",
        allowed_stages=frozenset({"waiting", "ready"}),
        allowed_action_kinds=frozenset(),
        now=NOW,
        select=lambda: (
            ("capture", [{"kind": "record.transition", "to_stage": "ready"}], [])
            if matched
            else None
        ),
    )


@pytest.mark.parametrize("matched", [False, True])
def test_historical_lookup_uses_only_workflow_metadata(setup, monkeypatch, matched):
    args, owner, admission = setup
    runtime = PackRuntime.load(**args)
    prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    original = seed_workflow(args, prepared, matched)
    before = rows(args["store"])

    def reached(*a, **kw):
        pytest.fail("lookup used mutation/source/clock/dispatch")

    monkeypatch.setattr(owner, "_transaction", reached)
    monkeypatch.setattr(SourceAdmission, "deployment", property(reached))
    monkeypatch.setattr(admission, "admit_source", reached)
    monkeypatch.setattr(args["store"], "connection", reached)
    monkeypatch.setattr(runtime._runner, "dispatch", reached)
    result = lookup(runtime)
    assert result.source_receipt == prepared.event.source_receipt
    assert result.outcome.record == original.record and result.outcome.matched is matched
    assert rows(args["store"]) == before
    with pytest.raises(EventConflict):
        lookup(runtime, expected_payload_digest="b" * 64)


def test_lookup_preserves_version_refusal(setup):
    args, _, _ = setup
    runtime = PackRuntime.load(**args)
    prepared = runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
    seed_workflow(args, prepared, True)
    signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    args["pack_bytes"] = _envelope(
        signer, encode(dict(format_version=2, pack_id=PACK_ID, pack_version=2, workflow=workflow()))
    )
    upgraded = PackRuntime.load(**args)
    with pytest.raises(PackVersionError):
        lookup(upgraded)
    assert lookup(runtime).source_receipt == prepared.event.source_receipt


@pytest.mark.parametrize("kind", ["mail.received", "invalid-kind"])
def test_private_composition_requires_validated_lead_binding(setup, kind):
    from connect_automate.automate.events import SourceBinding
    from connect_automate.lead_intake.handoff import _SourceHandoff

    _, _, admission = setup
    value = SourceBinding.model_construct(**{**source_binding(), "source_kind": kind})
    with pytest.raises(EventBindingError) as caught:
        _SourceHandoff(value, admission, lambda: NOW)
    assert caught.value.__context__ is None


def test_bad_signature_is_not_authorized_by_matching_scope(setup):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    value = envelope()
    value["payload"]["source"]["message_id"] = "unsigned-edit"
    with pytest.raises(SourceAuthenticationError):
        runtime._prepare_source(binding="inbox", raw_source_bytes=encode(value))
    assert counts(owner) == (0, 0, 0)


def test_host_clock_is_not_read_during_lookup(setup):
    args, _, _ = setup

    def forbidden():
        pytest.fail("lookup sampled workflow clock")

    args["source_clock"] = forbidden
    runtime = PackRuntime.load(**args)
    assert lookup(runtime) is None


@pytest.mark.parametrize("entry", ["prepare", "lookup"])
def test_generic_binding_is_not_a_lead_route(setup, entry):
    from test_automate_events import event_workflow
    from test_automate_events import source_binding as mail_binding

    args, _, _ = setup
    signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    args["pack_bytes"] = _envelope(
        signer,
        encode(dict(format_version=2, pack_id=PACK_ID, pack_version=1, workflow=event_workflow())),
    )
    args["event_bindings"] = {"inbox": mail_binding()}
    args.pop("source_admission")
    args.pop("source_clock")
    runtime = PackRuntime.load(**args)
    with pytest.raises(EventBindingError):
        if entry == "prepare":
            runtime._prepare_source(binding="inbox", raw_source_bytes=encode(envelope()))
        else:
            lookup(runtime)


def test_duck_typed_source_owner_is_not_a_real_admission(setup, monkeypatch):
    from types import SimpleNamespace

    args, _, admission = setup
    args["source_admission"] = SimpleNamespace(
        deployment=admission.deployment, admit_source=admission.admit_source
    )
    monkeypatch.setattr(args["store"], "register_bindings", lambda *a: pytest.fail("registered"))
    with pytest.raises(EventBindingError):
        PackRuntime.load(**args)


@pytest.mark.parametrize("foreign", [False, True])
def test_every_configured_route_is_bound_before_registration(setup, monkeypatch, foreign):
    args, _, _ = setup
    value = workflow()
    second = deepcopy(value["definitions"][0])
    second["name"] = "second"
    second["trigger"]["binding"] = "second"
    value["definitions"].append(second)
    signer = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    args["pack_bytes"] = _envelope(
        signer, encode(dict(format_version=2, pack_id=PACK_ID, pack_version=1, workflow=value))
    )
    route = source_binding()
    import json

    scope = json.loads(route["scope"])
    scope["namespace_id"] = OTHER
    if foreign:
        scope["host_id"] = OTHER
    route.update(source_id=OTHER, scope=encode(scope).decode())
    args["event_bindings"]["second"] = route
    if foreign:
        monkeypatch.setattr(
            args["store"], "register_bindings", lambda *a: pytest.fail("registered")
        )
        with pytest.raises(EventBindingError):
            PackRuntime.load(**args)
    else:
        runtime = PackRuntime.load(**args)
        assert set(runtime._source_handoffs) == {"inbox", "second"}
        assert lookup(runtime, binding="second") is None
        # Being configured does not authorize a source's different namespace.
        with pytest.raises(EventBindingError):
            runtime._prepare_source(binding="second", raw_source_bytes=encode(envelope()))


def test_prepared_projection_cannot_authorize_generic_submission(setup):
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
