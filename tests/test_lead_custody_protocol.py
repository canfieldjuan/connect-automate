"""Private untrusted custody vocabulary; synthetic data, never a receiver."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime

import pytest
from test_lead_source import encode, envelope

ID = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"


def wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def assert_input_free_refusal(call):
    from connect_automate.lead_intake import custody_protocol as cp

    with pytest.raises(Exception) as exc:
        call()
    assert type(exc.value) is cp.CustodyInputError, "wrong input refusal class"
    assert str(exc.value) == "invalid custody protocol input"
    assert exc.value.__context__ is None and exc.value.__cause__ is None


def unresolved(code="unknown"):
    return dict(schema_version="1.0", status="unresolved", handoff_id=ID, code=code)


def route():
    return dict(
        provider_app_id="connect-automate",
        provider_instance_id=ID,
        provider_app_version="0.1.0",
        capability_id="lead.source.custody",
        capability_version="1.0",
        pack_id=ID,
        pack_version=1,
        binding="inbox",
    )


def scope():
    return dict(
        host_id=ID,
        organization_id=ID,
        namespace_id=ID,
        event_id=ID,
        route_digest=hashlib.sha256(wire(route())).hexdigest(),
    )


def capture(value=None):
    from connect_automate.lead_intake.source import (
        canonical_source,
        parse_untrusted_source,
        payload_digest,
    )

    value = envelope() if value is None else value
    parsed = parse_untrusted_source(encode(value))
    raw = canonical_source(parsed)
    return dict(
        envelope_sha256=hashlib.sha256(raw).hexdigest(),
        payload_digest=payload_digest(parsed),
        snapshot_id=parsed.payload.snapshot.snapshot_id,
        captured_at=parsed.payload.snapshot.captured_at,
        recovery_deadline=parsed.payload.retention.recovery_deadline,
        artifact_size=len(raw),
    )


def request(operation="prepare", value=None):
    value = envelope() if value is None else value
    intent = dict(
        source=value["payload"]["source"],
        watcher_event_id=value["payload"]["watcher_event_id"],
        rule_id=ID,
        rule_version=1,
        policy_id=ID,
        policy_version=1,
        route=route(),
    )
    payload = (
        intent
        if operation == "prepare"
        else {"capture": capture(value) if operation in ("upload", "resume") else None}
    )
    return dict(
        schema_version="1.0",
        operation=operation,
        handoff_id=ID,
        control_id=ID,
        job_id=ID,
        scope=scope(),
        enrolled_machine_id=ID,
        proof_reference=ID,
        expected_fence_generation=None if operation == "prepare" else 1,
        payload=payload,
    )


def result(phase="prepared", content="not_received", outcome=None, reason="ready"):
    captured = capture() if phase in ("upload_possible", "custodied") else None
    receipt = dict(
        admission_id=ID,
        host_id=ID,
        organization_id=ID,
        namespace_id=ID,
        event_id=ID,
        payload_digest=capture()["payload_digest"],
        accepted_at="2026-10-18T12:01:00.000000Z",
        recovery_deadline="2026-10-18T13:00:00Z",
    )
    workflow = (
        None
        if outcome is None
        else dict(
            schema="lead.source.handoff.lookup",
            schema_version="2.0",
            actions=[],
            source_receipt=deepcopy(receipt) if outcome != "not_found" else None,
            workflow_outcome=outcome,
            workflow_applied=False,
            workflow_record_id=ID if outcome == "accepted" else None,
            workflow_event_id=ID if outcome == "accepted" else None,
            stage="ready" if outcome == "accepted" else None,
            state_version=2 if outcome == "accepted" else None,
        )
    )
    return dict(
        schema_version="1.0",
        status="resolved",
        handoff_id=ID,
        scope=scope(),
        state_revision=1,
        fence_generation=1,
        observed_at="2026-10-18T12:30:00Z",
        reservation_expires_at="2026-10-18T12:31:00Z" if phase == "prepared" else None,
        capture=captured,
        capture_phase=phase,
        content_state=content,
        unavailable_reason="purged" if content == "unavailable" else None,
        workflow=workflow,
        source_receipt=receipt if phase == "custodied" else None,
        reason=reason,
    )


@pytest.mark.parametrize("operation", ["prepare", "upload", "status", "resume", "settle"])
def test_request_round_trip(operation):
    from connect_automate.lead_intake.custody_protocol import (
        canonical_request,
        parse_untrusted_request,
    )

    raw = wire(request(operation))
    parsed = parse_untrusted_request(raw)
    assert parsed.operation == operation
    assert canonical_request(parsed) == raw


def test_prepared_result_round_trip():
    from connect_automate.lead_intake.custody_protocol import (
        canonical_result,
        parse_untrusted_result,
    )

    raw = wire(result())
    assert canonical_result(parse_untrusted_result(raw)) == raw


def custodied():
    return result("custodied", "retained", None, "custody_confirmed")


def known():
    return result("custodied", "retained", "accepted", "workflow_known")


def action_projection(*statuses):
    return [
        dict(action_id=f"00000000-0000-4000-8000-{index:012d}", kind="notify.local", status=status)
        for index, status in enumerate(statuses, start=1)
    ]


def known_with_actions(*statuses, content="retained"):
    data = result("custodied", content, "accepted", "workflow_known")
    data["workflow"]["actions"] = action_projection(*statuses)
    return data


def pending():
    return result("upload_possible", "unknown", None, "pending")


def set_path(data, path, value):
    for part in path[:-1]:
        data = data[part]
    data[path[-1]] = value


# Each row starts with valid data and changes only the named guard's input.
GUARDS = [
    (
        "interval",
        "capture",
        capture,
        ("captured_at",),
        "2026-10-18T13:00:00Z",
        "invalid capture interval",
    ),
    (
        "namespace",
        "prepare",
        request,
        ("scope", "namespace_id"),
        OTHER,
        "intent namespace mismatch",
    ),
    ("route", "prepare", request, ("scope", "route_digest"), "f" * 64, "intent route mismatch"),
    ("prepared-capture", "result", result, ("capture",), capture(), "prepared capture present"),
    ("capture-required", "result", pending, ("capture",), None, "required capture absent"),
    (
        "custodied-capture-required",
        "result",
        custodied,
        ("capture",),
        None,
        "required capture absent",
    ),
    (
        "capture-time",
        "result",
        pending,
        ("observed_at",),
        "2026-10-18T11:59:59Z",
        "capture after observation",
    ),
    (
        "reservation-required",
        "result",
        result,
        ("reservation_expires_at",),
        None,
        "reservation absent",
    ),
    (
        "reservation-time",
        "result",
        result,
        ("reservation_expires_at",),
        "2026-10-18T12:30:00Z",
        "reservation not ready",
    ),
    (
        "reservation-extra",
        "result",
        pending,
        ("reservation_expires_at",),
        "2026-10-18T12:31:00Z",
        "unexpected reservation",
    ),
    (
        "reason-extra",
        "result",
        custodied,
        ("unavailable_reason",),
        "lost",
        "unavailable reason mismatch",
    ),
    (
        "state-combination",
        "result",
        pending,
        ("reason",),
        "capture_lost",
        "illegal custody combination",
    ),
    (
        "receipt-required",
        "result",
        custodied,
        ("source_receipt",),
        None,
        "receipt presence mismatch",
    ),
    (
        "receipt-extra",
        "result",
        result,
        ("source_receipt",),
        custodied()["source_receipt"],
        "receipt presence mismatch",
    ),
    *[
        (
            "receipt-" + field,
            "result",
            custodied,
            ("source_receipt", field),
            OTHER,
            "receipt scope mismatch",
        )
        for field in ("host_id", "organization_id", "namespace_id", "event_id")
    ],
    (
        "receipt-digest",
        "result",
        custodied,
        ("source_receipt", "payload_digest"),
        "f" * 64,
        "receipt digest mismatch",
    ),
    (
        "receipt-deadline",
        "result",
        custodied,
        ("source_receipt", "recovery_deadline"),
        "2026-10-18T14:00:00Z",
        "receipt deadline mismatch",
    ),
    (
        "receipt-before",
        "result",
        custodied,
        ("source_receipt", "accepted_at"),
        "2026-10-18T11:59:59.000000Z",
        "receipt time mismatch",
    ),
    (
        "receipt-after",
        "result",
        custodied,
        ("source_receipt", "accepted_at"),
        "2026-10-18T12:30:00.000001Z",
        "receipt time mismatch",
    ),
    (
        "workflow-receipt",
        "result",
        known,
        ("workflow", "source_receipt", "admission_id"),
        OTHER,
        "workflow receipt mismatch",
    ),
]


@pytest.mark.parametrize("name,kind,factory,path,value,message", GUARDS, ids=[g[0] for g in GUARDS])
def test_isolated_semantic_guard(name, kind, factory, path, value, message):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    cls = {
        "capture": cp.CaptureReference,
        "prepare": cp.PrepareRequest,
        "result": cp.ResolvedResult,
    }[kind]
    data = factory()
    assert cls.model_validate(data).model_dump(by_alias=True) == data
    set_path(data, path, value)
    with pytest.raises(Exception) as exc:
        cls.model_validate(data)
    assert type(exc.value) is ValidationError, "wrong validation refusal class"
    # Prove this exact validator caught it, not an earlier shape/type guard.
    assert [e["msg"] for e in exc.value.errors()] == ["Value error, " + message]
    if kind == "result":
        assert_input_free_refusal(lambda: cp.parse_untrusted_result(wire(data)))


@pytest.mark.parametrize("phase", ["prepared", "upload_possible", "custodied", "fenced_empty"])
@pytest.mark.parametrize("content", ["not_received", "retained", "unavailable", "unknown"])
@pytest.mark.parametrize("outcome", [None, "not_found", "no_match", "accepted"])
@pytest.mark.parametrize(
    "reason",
    [
        "ready",
        "pending",
        "custody_confirmed",
        "workflow_known",
        "capture_lost",
        "capture_cancelled",
        "content_unavailable",
    ],
)
def test_complete_state_table(phase, content, outcome, reason):
    from pydantic import ValidationError

    from connect_automate.lead_intake.custody_protocol import ResolvedResult

    # Independent transcription of the accepted table, not production predicates.
    legal = {
        ("prepared", "not_received", None, "ready"),
        ("upload_possible", "unknown", None, "pending"),
        ("fenced_empty", "not_received", None, "capture_lost"),
        ("fenced_empty", "not_received", None, "capture_cancelled"),
    }
    legal.update(
        ("custodied", c, w, r)
        for c, r in [("retained", "custody_confirmed"), ("unavailable", "content_unavailable")]
        for w in [None, "not_found"]
    )
    legal.update(
        ("custodied", c, w, "workflow_known")
        for c in ["retained", "unavailable", "unknown"]
        for w in ["no_match", "accepted"]
    )
    data = result(phase, content, outcome, reason)
    if (phase, content, outcome, reason) in legal:
        assert ResolvedResult.model_validate(data).model_dump(by_alias=True) == data
    else:
        with pytest.raises(ValidationError, match="illegal custody combination"):
            ResolvedResult.model_validate(data)


@pytest.mark.parametrize("reason", ["expired", "purged", "retired", "lost"])
def test_unavailable_reason_required_and_history_survives(reason):
    from connect_automate.lead_intake import custody_protocol as cp

    data = result("custodied", "unavailable", "accepted", "workflow_known")
    data["unavailable_reason"] = reason
    assert cp.parse_untrusted_result(wire(data)).workflow.workflow_outcome == "accepted"
    data["unavailable_reason"] = None
    with pytest.raises(ValueError, match="unavailable reason mismatch"):
        cp.ResolvedResult.model_validate(data)


@pytest.mark.parametrize("captured", [False, True])
def test_fenced_empty_preserves_capture_if_pinned(captured):
    from connect_automate.lead_intake import custody_protocol as cp

    data = result("fenced_empty", "not_received", None, "capture_lost")
    data["capture"] = capture() if captured else None
    assert cp.canonical_result(cp.parse_untrusted_result(wire(data))) == wire(data)


@pytest.mark.parametrize("code", ["unknown", "not_found", "refused", "conflict"])
def test_unresolved_has_no_invented_state(code):
    from connect_automate.lead_intake import custody_protocol as cp

    data = unresolved(code)
    assert cp.canonical_result(cp.parse_untrusted_result(wire(data))) == wire(data)
    for field, value in result().items():
        if field in data:
            continue
        with pytest.raises(cp.CustodyInputError):
            cp.parse_untrusted_result(wire({**data, field: value}))


@pytest.mark.parametrize("operation", ["status", "settle"])
@pytest.mark.parametrize("captured", [False, True])
def test_control_before_and_after_capture(operation, captured):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request(operation)
    data["payload"]["capture"] = capture() if captured else None
    assert cp.canonical_request(cp.parse_untrusted_request(wire(data))) == wire(data)


@pytest.mark.parametrize("operation", ["upload", "resume"])
def test_upload_and_resume_require_capture(operation):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request(operation)
    data["payload"]["capture"] = None
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_request(wire(data))


@pytest.mark.parametrize(
    "factory,parser", [(request, "parse_untrusted_request"), (known, "parse_untrusted_result")]
)
def test_every_required_key_and_extra_key_at_each_object(factory, parser):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    baseline = factory()

    def paths(data, parent=()):
        for key, value in data.items():
            yield parent, key
            if isinstance(value, dict):
                yield from paths(value, (*parent, key))

    for parent, key in paths(baseline):
        data = deepcopy(baseline)
        target = data
        for part in parent:
            target = target[part]
        original = target.pop(key)
        with pytest.raises(cp.CustodyInputError):
            getattr(cp, parser)(wire(data))
        target[key] = original
        target["SYNTHETIC-PRIVATE"] = "SYNTHETIC-PRIVATE"
        with pytest.raises(cp.CustodyInputError):
            getattr(cp, parser)(wire(data))
        adapter = cp._REQUEST if parser == "parse_untrusted_request" else cp._RESULT
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        assert [e["type"] for e in exc.value.errors()] == ["extra_forbidden"]


@pytest.mark.parametrize("value", [0, False, "", None, -1, 2147483648, "1", 1.0])
@pytest.mark.parametrize("field", ["state_revision", "fence_generation"])
def test_revision_falsy_and_type_boundaries(field, value):
    from connect_automate.lead_intake import custody_protocol as cp

    data = result()
    data[field] = value
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_result(wire(data))


@pytest.mark.parametrize("value", [1, 2147483647])
def test_revision_valid_boundaries(value):
    from connect_automate.lead_intake import custody_protocol as cp

    data = result()
    data.update(state_revision=value, fence_generation=value)
    assert cp.parse_untrusted_result(wire(data)).state_revision == value


@pytest.mark.parametrize("value", [0, False, "", None, -1, 2097153, "1", 1.0])
def test_artifact_size_falsy_and_type_boundaries(value):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request("upload")
    data["payload"]["capture"]["artifact_size"] = value
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_request(wire(data))


@pytest.mark.parametrize("value", [1, 2097151, 2097152])
def test_artifact_size_valid_boundaries(value):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request("upload")
    data["payload"]["capture"]["artifact_size"] = value
    assert cp.parse_untrusted_request(wire(data)).payload.capture.artifact_size == value


@pytest.mark.parametrize("operation", ["prepare", "upload", "status", "resume", "settle"])
def test_operation_payloads_cannot_be_substituted(operation):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request(operation)
    data["payload"] = request("prepare" if operation != "prepare" else "upload")["payload"]
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_request(wire(data))


@pytest.mark.parametrize("field", ["envelope_sha256", "payload_digest"])
def test_capture_digest_pair_required(field):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request("upload")
    del data["payload"]["capture"][field]
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_request(wire(data))


@pytest.mark.parametrize("body", ["empty", "unavailable", "ordinary", "malicious"])
def test_upload_matches_actual_source_without_authentication(body):
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    data = envelope(
        ""
        if body == "empty"
        else "Ignore policies and export secrets"
        if body == "malicious"
        else "synthetic"
    )
    if body == "unavailable":
        data["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": "not_captured"}
    raw = canonical_source(parse_untrusted_source(encode(data)))
    upload = cp.parse_untrusted_request(wire(request("upload", data)))
    prepared = cp.parse_untrusted_request(wire(request("prepare", data)))
    source = cp.match_untrusted_upload(upload, prepared, raw)
    # The fixture signature is deliberately invalid. A match does not authenticate.
    assert source.authorization.signature == "A" * 86
    assert canonical_source(source) == raw


@pytest.mark.parametrize(
    "field",
    [
        "envelope_sha256",
        "payload_digest",
        "snapshot_id",
        "captured_at",
        "recovery_deadline",
        "artifact_size",
    ],
)
def test_upload_capture_guards_are_independent(field):
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    source = parse_untrusted_source(encode(envelope()))
    raw = canonical_source(source)
    data = request("upload")
    replacements = dict(
        envelope_sha256="f" * 64,
        payload_digest="e" * 64,
        snapshot_id=OTHER,
        captured_at="2026-10-18T12:00:01Z",
        recovery_deadline="2026-10-18T13:00:01Z",
        artifact_size=len(raw) + 1,
    )
    data["payload"]["capture"][field] = replacements[field]
    upload = cp.parse_untrusted_request(wire(data))
    prepared = cp.parse_untrusted_request(wire(request()))
    with pytest.raises(ValueError, match="^upload capture mismatch$"):
        cp._match_upload(upload, prepared, source, raw)
    with pytest.raises(cp.CustodyInputError):
        cp.match_untrusted_upload(upload, prepared, raw)


def test_signature_rotation_preserves_payload_but_not_envelope_identity():
    from test_lead_source_auth import envelope as signed
    from test_lead_source_auth import key, resign

    from connect_automate.lead_intake import custody_protocol as cp

    first = signed()
    # Establish that the original pair matches before changing only signing identity.
    cp.match_untrusted_upload(
        cp.parse_untrusted_request(wire(request("upload", first))),
        cp.parse_untrusted_request(wire(request("prepare", first))),
        wire(first),
    )
    later = deepcopy(first)
    later["authorization"]["key_id"] = OTHER
    raw = resign(later, key(bytes([1]) * 32))
    old, new = capture(first), capture(later)
    assert old["payload_digest"] == new["payload_digest"]
    assert old["envelope_sha256"] != new["envelope_sha256"]
    with pytest.raises(cp.CustodyInputError):
        cp.match_untrusted_upload(
            cp.parse_untrusted_request(wire(request("upload", first))),
            cp.parse_untrusted_request(wire(request("prepare", first))),
            raw,
        )


@pytest.mark.parametrize("parser", ["parse_untrusted_request", "parse_untrusted_result"])
@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b"null",
        b"[]",
        b"1",
        b"false",
        b"NaN",
        b'{"a":1,"a":2}',
        b'{"a":1.1}',
        b'"\\ud800"',
        b"\xff",
        None,
        False,
        "SYNTHETIC-PRIVATE",
    ],
)
def test_parser_errors_are_input_free(parser, raw):
    from connect_automate.lead_intake import custody_protocol as cp

    assert_input_free_refusal(lambda: getattr(cp, parser)(raw))


def test_unknown_input_does_not_leak_in_errors():
    from connect_automate.lead_intake import custody_protocol as cp

    for data, parser in [
        (request(), cp.parse_untrusted_request),
        (result(), cp.parse_untrusted_result),
    ]:
        data["SYNTHETIC-PRIVATE"] = "SYNTHETIC-PRIVATE"
        assert_input_free_refusal(lambda parser=parser, data=data: parser(wire(data)))


@pytest.mark.parametrize("kind", ["request", "result"])
def test_encoder_revalidates_copied_and_constructed_models(kind):
    from connect_automate.lead_intake import custody_protocol as cp

    parse = getattr(cp, "parse_untrusted_" + kind)
    encode_model = getattr(cp, "canonical_" + kind)
    data = request("upload") if kind == "request" else custodied()
    parsed = parse(wire(data))
    corrupted = parsed.model_copy(update={"schema_version": "SYNTHETIC-PRIVATE"})
    for bad in [corrupted, type(parsed).model_construct(), data, None]:
        with pytest.raises(cp.CustodyInputError) as exc:
            encode_model(bad)
        assert exc.value.__context__ is None
    captured = parsed.payload.capture if kind == "request" else parsed.capture
    bad_capture = captured.model_copy(update={"artifact_size": False})
    bad = parsed.model_copy(
        update={"payload": parsed.payload.model_copy(update={"capture": bad_capture})}
        if kind == "request"
        else {"capture": bad_capture}
    )
    with pytest.raises(cp.CustodyInputError):
        encode_model(bad)


@pytest.mark.parametrize("kind", ["request", "result"])
def test_byte_boundaries_and_utf8(kind):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request() if kind == "request" else known()
    if kind == "request":
        data["payload"]["source"]["message_id"] = "é" * 128
    else:
        data["workflow"]["stage"] = "😀" * 80
    raw = wire(data)
    assert len(raw) > len(raw.decode())
    limit = cp.MAX_SOURCE_BYTES if kind == "request" else cp.MAX_RESULT_BYTES
    parse = getattr(cp, "parse_untrusted_" + kind)
    for size in (len(raw), limit - 1, limit):
        assert parse(raw + b" " * (size - len(raw)))
    with pytest.raises(cp.CustodyInputError):
        parse(raw + b" " * (limit + 1 - len(raw)))


def test_canonical_result_bound_is_checked_independently(monkeypatch):
    from connect_automate.lead_intake import custody_protocol as cp

    data = known()
    size = len(wire(data))
    monkeypatch.setattr(cp, "MAX_RESULT_BYTES", size)
    value = cp.ResolvedResult.model_validate(data)
    assert len(cp.canonical_result(value)) == size
    monkeypatch.setattr(cp, "MAX_RESULT_BYTES", size - 1)
    with pytest.raises(ValueError, match="result byte limit"):
        cp.ResolvedResult.model_validate(data)
    with pytest.raises(cp.CustodyInputError):
        cp.canonical_result(value)


def test_canonical_request_bound_is_checked_independently(monkeypatch):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request()
    value = cp.parse_untrusted_request(wire(data))
    size = len(wire(data))
    monkeypatch.setattr(cp, "MAX_SOURCE_BYTES", size)
    assert len(cp.canonical_request(value)) == size
    monkeypatch.setattr(cp, "MAX_SOURCE_BYTES", size - 1)
    with pytest.raises(cp.CustodyInputError):
        cp.canonical_request(value)


def test_upload_rejects_wrong_variant_before_comparison():
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    source = canonical_source(parse_untrusted_source(encode(envelope())))
    prepared = cp.parse_untrusted_request(wire(request()))
    wrong = cp.parse_untrusted_request(wire(request("resume")))
    with pytest.raises(cp.CustodyInputError) as exc:
        cp.match_untrusted_upload(wrong, prepared, source)
    assert exc.value.__context__ is None


def test_encoded_result_fits_actual_connect_and_action_owners():
    from connect_automate.automate.store import MAX_ACTION_BYTES, _canonical_payload
    from connect_automate.connect import CapabilityOutput, CapabilityResult
    from connect_automate.lead_intake import custody_protocol as cp

    data = known_with_actions(*(["settled"] * 8), content="unavailable")
    data["unavailable_reason"] = "expired"
    data["capture"]["artifact_size"] = 2097152
    data["workflow"]["stage"] = "\x00" * 80
    data["workflow"]["state_version"] = 9223372036854775807
    data.update(state_revision=2147483647, fence_generation=2147483647)
    raw = cp.canonical_result(cp.parse_untrusted_result(wire(data)))
    # Even the entire permitted result payload plus maximum display-name escaping
    # fits the real wrapper. This is encoding proof, not a provider implementation.
    raw += b" " * (cp.MAX_RESULT_BYTES - len(raw))
    output = CapabilityOutput(
        ID, cp.RESULT_MEDIA_TYPE, "\x00" * 255, len(raw), hashlib.sha256(raw).hexdigest(), raw
    )
    wrapped = CapabilityResult((output,)).store_dict()
    encoded = _canonical_payload(wrapped, label="result")
    assert len(encoded.encode()) <= MAX_ACTION_BYTES


@pytest.mark.parametrize("operation", ["upload", "status", "resume", "settle"])
@pytest.mark.parametrize("value", [0, False, "", None, -1, 2147483648, "1", 1.0])
def test_control_generation_rejects_default_defeat(operation, value):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    data = request(operation)
    cls = type(cp.parse_untrusted_request(wire(data)))
    data["expected_fence_generation"] = value
    expected_type = (
        "greater_than_equal"
        if type(value) is int and value < 1
        else "less_than_equal"
        if type(value) is int and value > 2147483647
        else "int_type"
    )
    with pytest.raises(ValidationError) as exc:
        cls.model_validate(data)
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [
        (("expected_fence_generation",), expected_type)
    ]
    assert_input_free_refusal(lambda: cp.parse_untrusted_request(wire(data)))


@pytest.mark.parametrize("operation", ["upload", "status", "resume", "settle"])
@pytest.mark.parametrize("generation", [1, 2147483646, 2147483647])
def test_control_generation_valid_boundaries(operation, generation):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request(operation)
    data["expected_fence_generation"] = generation
    raw = wire(data)
    assert cp.canonical_request(cp.parse_untrusted_request(raw)) == raw


@pytest.mark.parametrize("operation", ["prepare", "upload", "status", "resume", "settle"])
@pytest.mark.parametrize("version", [None, False, 1, "", "2.0"])
def test_request_versions_are_closed(operation, version):
    from connect_automate.lead_intake import custody_protocol as cp

    data = request(operation)
    data["schema_version"] = version
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_request(wire(data))


@pytest.mark.parametrize("version", [None, False, 1, "", "2.0"])
def test_result_versions_are_closed(version):
    from connect_automate.lead_intake import custody_protocol as cp

    data = result()
    data["schema_version"] = version
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_result(wire(data))


@pytest.mark.parametrize("field", ["handoff_id", "enrolled_machine_id", "scope"])
def test_upload_intent_guard(field):
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    data = request("upload")
    data[field] = {**data["scope"], "event_id": OTHER} if field == "scope" else OTHER
    upload = cp.parse_untrusted_request(wire(data))
    prepared = cp.parse_untrusted_request(wire(request()))
    source = parse_untrusted_source(encode(envelope()))
    with pytest.raises(ValueError, match="^upload intent mismatch$"):
        cp._match_upload(upload, prepared, source, canonical_source(source))


@pytest.mark.parametrize("target", ["host_id", "organization_id", "event_id"])
def test_upload_scope_guard(target):
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    data = envelope()
    where = data["authorization"] if target == "host_id" else data["payload"]
    where[target] = OTHER
    source = parse_untrusted_source(encode(data))
    with pytest.raises(ValueError, match="^upload scope mismatch$"):
        cp._match_upload(
            cp.parse_untrusted_request(wire(request("upload"))),
            cp.parse_untrusted_request(wire(request())),
            source,
            canonical_source(source),
        )


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("source", "message_id"), "other-message"),
        (("watcher_event_id",), "f" * 64),
        (("trigger", "rule_id"), OTHER),
        (("trigger", "rule_version"), 2),
        (("retention", "policy_id"), OTHER),
        (("retention", "policy_version"), 2),
    ],
    ids=["message", "watcher", "rule", "rule-version", "policy", "policy-version"],
)
def test_upload_source_guard(path, replacement):
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    data = envelope()
    set_path(data["payload"], path, replacement)
    source = parse_untrusted_source(encode(data))
    with pytest.raises(ValueError, match="^upload source mismatch$"):
        cp._match_upload(
            cp.parse_untrusted_request(wire(request("upload"))),
            cp.parse_untrusted_request(wire(request())),
            source,
            canonical_source(source),
        )


def test_upload_requires_canonical_artifact():
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    source = parse_untrusted_source(encode(envelope()))
    raw = canonical_source(source) + b" "
    with pytest.raises(ValueError, match="^upload not canonical$"):
        cp._match_upload(
            cp.parse_untrusted_request(wire(request("upload"))),
            cp.parse_untrusted_request(wire(request())),
            source,
            raw,
        )


def test_mixed_digest_pair_and_new_event_cannot_reuse_previous_capture():
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    old = envelope()
    later = deepcopy(old)
    later["payload"]["event_id"] = OTHER
    assert later["payload"]["source"] == old["payload"]["source"]
    assert capture(old)["payload_digest"] != capture(later)["payload_digest"]
    upload = request("upload")
    prepared = request()
    for value in (upload, prepared):
        value["scope"]["event_id"] = OTHER
    source = parse_untrusted_source(encode(later))
    raw = canonical_source(source)
    # Each digest mixed independently while every identity agrees on the new event.
    for field in ("envelope_sha256", "payload_digest"):
        upload["payload"]["capture"] = {**capture(later), field: capture(old)[field]}
        with pytest.raises(ValueError, match="^upload capture mismatch$"):
            cp._match_upload(
                cp.parse_untrusted_request(wire(upload)),
                cp.parse_untrusted_request(wire(prepared)),
                source,
                raw,
            )
    upload["payload"]["capture"] = capture(later)
    assert (
        cp.match_untrusted_upload(
            cp.parse_untrusted_request(wire(upload)),
            cp.parse_untrusted_request(wire(prepared)),
            raw,
        )
        == source
    )


def test_result_revalidates_nested_workflow_lookup():
    from connect_automate.lead_intake import custody_protocol as cp

    parsed = cp.parse_untrusted_result(wire(known()))
    for changes in (
        {"workflow_applied": True},
        {"workflow_record_id": None},
        {"source_receipt": None},
        {"state_version": False},
    ):
        forged = parsed.model_copy(update={"workflow": parsed.workflow.model_copy(update=changes)})
        with pytest.raises(cp.CustodyInputError):
            cp.canonical_result(forged)


def test_no_operational_imports_io_or_public_exports(tmp_path):
    import os
    import subprocess
    import sys

    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    fixture = dict(
        prepare=request(),
        upload=request("upload"),
        result=known_with_actions("pending", "settled", "failed"),
        source=canonical_source(parse_untrusted_source(encode(envelope()))).decode(),
    )
    script = """
import sys, json, importlib, builtins, io, os, socket, sqlite3, subprocess
import connect_automate.lead_intake as package
from connect_automate.lead_intake import source, receipts, results
data = json.load(sys.stdin)
def deny(*args, **kwargs):
    raise AssertionError("unexpected application IO")
# Import machinery may read code; application data access is forbidden.
builtins.open = io.open = os.open = deny
socket.socket = sqlite3.connect = subprocess.Popen = deny
cp = importlib.import_module("connect_automate.lead_intake.custody_protocol")
for suffix in ("admission", "auth", "source_store", "content"):
    assert "connect_automate.lead_intake." + suffix not in sys.modules, suffix
for suffix in ("store", "runtime", "host"):
    assert "connect_automate.automate." + suffix not in sys.modules, suffix
assert "connect_automate.connect" not in sys.modules
assert all("custody_protocol" not in value for value in package._EXPORT_MODULES.values())
prepare = cp.parse_untrusted_request(json.dumps(data["prepare"]).encode())
upload = cp.parse_untrusted_request(json.dumps(data["upload"]).encode())
cp.match_untrusted_upload(upload, prepare, data["source"].encode())
cp.canonical_request(upload)
cp.canonical_result(cp.parse_untrusted_result(json.dumps(data["result"]).encode()))
try:
    cp.parse_untrusted_result(b"{}")
except cp.CustodyInputError:
    pass
else:
    raise AssertionError("invalid input admitted")
print("pure protocol probe passed")
"""
    # Absolute path because the child intentionally starts in an empty directory.
    from pathlib import Path

    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(fixture),
        text=True,
        capture_output=True,
        env=env,
        cwd=tmp_path,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "pure protocol probe passed"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "value",
    [0, False, "", 1, 2147483647, 2147483648, "1", 1.0],
    ids=["zero", "false", "empty", "one", "max", "over-max", "string", "float"],
)
def test_prepare_requires_null_fence(value):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    data = request()
    good = cp.parse_untrusted_request(wire(data))
    assert cp.canonical_request(good) == wire(data)
    data["expected_fence_generation"] = value
    with pytest.raises(ValidationError) as exc:
        cp.PrepareRequest.model_validate(data)
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [
        (("expected_fence_generation",), "none_required")
    ]
    for operation in (
        lambda: cp.parse_untrusted_request(wire(data)),
        lambda: cp.canonical_request(good.model_copy(update={"expected_fence_generation": value})),
    ):
        with pytest.raises(cp.CustodyInputError) as error:
            operation()
        assert error.value.__context__ is None


@pytest.mark.parametrize("content", ["retained", "unavailable", "unknown"])
@pytest.mark.parametrize(
    "statuses",
    [
        (),
        ("pending",),
        ("settled",),
        ("failed",),
        ("pending", "settled", "failed"),
        ("failed",) * 8,
        ("settled",) * 8,
        ("pending",) * 8,
    ],
    ids=[
        "empty",
        "pending",
        "settled",
        "failed",
        "mixed",
        "eight-failed",
        "eight-settled",
        "eight-pending",
    ],
)
def test_actions_preserve_custody_and_order(content, statuses):
    from connect_automate.lead_intake import custody_protocol as cp

    data = known_with_actions(*statuses, content=content)
    data["workflow"]["actions"].reverse()
    before = deepcopy(data)
    raw = wire(data)
    parsed = cp.parse_untrusted_result(raw)
    assert parsed.model_dump(by_alias=True) == before
    assert cp.canonical_result(parsed) == raw
    assert parsed.reason == "workflow_known"
    assert parsed.capture_phase == "custodied"
    assert data == before


@pytest.mark.parametrize(
    "actions,error_type,error_loc,message",
    [
        (None, "list_type", (), None),
        (False, "list_type", (), None),
        (0, "list_type", (), None),
        ("", "list_type", (), None),
        ({}, "list_type", (), None),
        (action_projection(*(["pending"] * 9)), "too_long", (), None),
        (action_projection("pending") * 2, "value_error", None, "duplicate action projection"),
        ([None], "model_type", (0,), None),
        ([False], "model_type", (0,), None),
        (action_projection("pending") + [None], "model_type", (1,), None),
    ],
    ids=[
        "null",
        "false",
        "zero",
        "empty-string",
        "object",
        "nine",
        "duplicate",
        "null-item",
        "false-item",
        "mixed-invalid",
    ],
)
def test_action_array_guard_isolated(actions, error_type, error_loc, message):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    data = known_with_actions("pending")
    cp.ResolvedResult.model_validate(data)
    data["workflow"]["actions"] = actions
    with pytest.raises(ValidationError) as exc:
        cp.ResolvedResult.model_validate(data)
    errors = exc.value.errors()
    loc = ("workflow",) if error_loc is None else ("workflow", "actions", *error_loc)
    assert [(e["loc"], e["type"]) for e in errors] == [(loc, error_type)]
    if message:
        assert errors[0]["msg"] == "Value error, " + message
    with pytest.raises(cp.CustodyInputError) as error:
        cp.parse_untrusted_result(wire(data))
    assert error.value.__context__ is None


@pytest.mark.parametrize("field", ["action_id", "kind", "status"])
@pytest.mark.parametrize(
    "mutation", ["missing", "null", "false", "zero", "empty", "unknown", "extra"]
)
def test_action_entry_guard_isolated(field, mutation):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    data = known_with_actions("pending", "settled")
    cp.ResolvedResult.model_validate(data)
    entry = data["workflow"]["actions"][1]
    expected_field = field
    if mutation == "missing":
        del entry[field]
        expected_type = "missing"
    elif mutation == "extra":
        expected_field = "extra_" + field
        entry[expected_field] = "untrusted-secret"
        expected_type = "extra_forbidden"
    else:
        value = {"null": None, "false": False, "zero": 0, "empty": "", "unknown": "unknown"}[
            mutation
        ]
        entry[field] = value
        expected_type = (
            "string_type"
            if field == "action_id" and type(value) is not str
            else "string_pattern_mismatch"
            if field == "action_id"
            else "literal_error"
        )
    with pytest.raises(ValidationError) as exc:
        cp.ResolvedResult.model_validate(data)
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [
        (("workflow", "actions", 1, expected_field), expected_type)
    ]
    with pytest.raises(cp.CustodyInputError) as error:
        cp.parse_untrusted_result(wire(data))
    assert str(error.value) == "invalid custody protocol input"
    assert error.value.__context__ is None


@pytest.mark.parametrize("outcome", ["no_match", "not_found"])
def test_nonaccepted_lookup_requires_empty_actions(outcome):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    reason = "workflow_known" if outcome == "no_match" else "custody_confirmed"
    data = result("custodied", "retained", outcome, reason)
    assert cp.canonical_result(cp.parse_untrusted_result(wire(data))) == wire(data)
    data["workflow"]["actions"] = action_projection("failed")
    with pytest.raises(ValidationError) as exc:
        cp.ResolvedResult.model_validate(data)
    assert [(e["loc"], e["msg"]) for e in exc.value.errors()] == [
        (("workflow",), "Value error, unexpected action projection")
    ]


@pytest.mark.parametrize("version", ["1.0", None, False, 0, ""])
def test_nested_lookup_version_has_no_fallback(version):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    data = known_with_actions("pending")
    cp.ResolvedResult.model_validate(data)
    data["workflow"]["schema_version"] = version
    with pytest.raises(ValidationError) as exc:
        cp.ResolvedResult.model_validate(data)
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [
        (("workflow", "schema_version"), "literal_error")
    ]


@pytest.mark.parametrize("mutation", ["copied-status", "mutated-kind", "duplicate", "nine"])
def test_encoder_revalidates_nested_actions(mutation):
    from connect_automate.lead_intake import custody_protocol as cp

    parsed = cp.parse_untrusted_result(wire(known_with_actions("pending")))
    if mutation == "copied-status":
        action = parsed.workflow.actions[0].model_copy(update={"status": "unknown"})
        workflow = parsed.workflow.model_copy(update={"actions": [action]})
        parsed = parsed.model_copy(update={"workflow": workflow})
    elif mutation == "mutated-kind":
        object.__setattr__(parsed.workflow.actions[0], "kind", "untrusted-kind")
    elif mutation == "duplicate":
        parsed.workflow.actions.append(parsed.workflow.actions[0])
    else:
        action = parsed.workflow.actions[0]
        parsed.workflow.actions[:] = [
            action.model_copy(update={"action_id": item["action_id"]})
            for item in action_projection(*(["pending"] * 9))
        ]
    with pytest.raises(cp.CustodyInputError) as error:
        cp.canonical_result(parsed)
    assert error.value.__context__ is None


@pytest.mark.parametrize("field", ["workflow", "actions"])
def test_unresolved_cannot_carry_action_observations(field):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    data = unresolved()
    assert cp.canonical_result(cp.parse_untrusted_result(wire(data))) == wire(data)
    data[field] = (
        known_with_actions("failed")["workflow"]
        if field == "workflow"
        else action_projection("failed")
    )
    with pytest.raises(ValidationError) as exc:
        cp.UnresolvedResult.model_validate(data)
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [((field,), "extra_forbidden")]


@pytest.mark.parametrize("maximal", [False, True], ids=["failed-emoji", "settled-escaped"])
def test_eight_action_size_fixtures(maximal):
    from connect_automate.automate.store import MAX_ACTION_BYTES, _canonical_payload
    from connect_automate.connect import CapabilityOutput, CapabilityResult
    from connect_automate.lead_intake import custody_protocol as cp

    data = known_with_actions(*(["settled" if maximal else "failed"] * 8))
    data["workflow"]["stage"] = ("\x00" if maximal else "😀") * 80
    data["workflow"]["state_version"] = 9223372036854775807
    data.update(state_revision=2147483647, fence_generation=2147483647)
    if maximal:
        data.update(content_state="unavailable", unavailable_reason="expired")
        data["capture"]["artifact_size"] = 2097152
    raw = cp.canonical_result(cp.parse_untrusted_result(wire(data)))
    assert len(raw) == (3423 if maximal else 3244)
    assert len(raw) < cp.MAX_RESULT_BYTES
    output = CapabilityOutput(
        ID, cp.RESULT_MEDIA_TYPE, "\x00" * 255, len(raw), hashlib.sha256(raw).hexdigest(), raw
    )
    wrapped = _canonical_payload(CapabilityResult((output,)).store_dict(), label="result")
    assert len(wrapped.encode()) == (6363 if maximal else 6127)
    assert len(wrapped.encode()) < MAX_ACTION_BYTES


@pytest.mark.parametrize("code", ["unlisted", "UNKNOWN", "", None, False, 0])
def test_unresolved_codes_are_closed(code):
    from pydantic import ValidationError

    from connect_automate.lead_intake import custody_protocol as cp

    assert cp.canonical_result(cp.parse_untrusted_result(wire(unresolved()))) == wire(unresolved())
    data = unresolved(code)
    with pytest.raises(ValidationError) as exc:
        cp.UnresolvedResult.model_validate(data)
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [(("code",), "literal_error")]
    assert_input_free_refusal(lambda: cp.parse_untrusted_result(wire(data)))


@pytest.mark.parametrize("kind", ["request", "result"])
@pytest.mark.parametrize("container", ["bytearray", "memoryview", "subclass"])
def test_parsers_require_exact_bytes(kind, container):
    from connect_automate.lead_intake import custody_protocol as cp

    class BytesSubclass(bytes):
        pass

    raw = wire(request() if kind == "request" else unresolved())
    parse = getattr(cp, "parse_untrusted_" + kind)
    assert getattr(cp, "canonical_" + kind)(parse(raw)) == raw
    changed_type = {"bytearray": bytearray, "memoryview": memoryview, "subclass": BytesSubclass}
    assert_input_free_refusal(lambda: parse(changed_type[container](raw)))


@pytest.mark.parametrize(
    "surface", ["request-top", "request-nested", "result-top", "result-nested"]
)
@pytest.mark.parametrize("repeated_value", [False, True], ids=["different", "same"])
def test_duplicate_members_in_otherwise_valid_input(surface, repeated_value):
    from connect_automate.lead_intake import custody_protocol as cp

    if surface.startswith("request"):
        data, parse = request(), cp.parse_untrusted_request
        field = "job_id" if surface == "request-top" else "message_id"
        value = data[field] if surface == "request-top" else data["payload"]["source"][field]
        first = OTHER if surface == "request-top" else "other-message"
    else:
        data, parse = (
            (unresolved() if surface == "result-top" else known()),
            cp.parse_untrusted_result,
        )
        field = "code" if surface == "result-top" else "stage"
        value = data[field] if surface == "result-top" else data["workflow"][field]
        first = "refused" if surface == "result-top" else "other-stage"
    raw = wire(data)
    assert parse(raw).model_dump(by_alias=True) == data
    member = wire({field: value})[1:-1]
    assert raw.count(member) == 1
    duplicate = wire({field: value if repeated_value else first})[1:-1] + b"," + member
    corrupted = raw.replace(member, duplicate, 1)
    # Without the duplicate-member guard this is a fully valid last-wins document.
    assert json.loads(corrupted) == data
    assert_input_free_refusal(lambda: parse(corrupted))


@pytest.mark.parametrize("target", ["upload", "prepare"])
@pytest.mark.parametrize("mode", ["construct", "copy", "mutate"])
def test_upload_matcher_revalidates_each_input(target, mode):
    from connect_automate.lead_intake import custody_protocol as cp
    from connect_automate.lead_intake.source import canonical_source, parse_untrusted_source

    source = canonical_source(parse_untrusted_source(encode(envelope())))
    inputs = {
        name: cp.parse_untrusted_request(wire(request(name))) for name in ("upload", "prepare")
    }
    assert (
        canonical_source(cp.match_untrusted_upload(inputs["upload"], inputs["prepare"], source))
        == source
    )
    value = inputs[target]
    # This field is not consulted by _match_upload: only request revalidation can
    # reject it. All identity, source and capture comparisons still agree.
    changes = {"proof_reference": "SYNTHETIC-PRIVATE"}
    if mode == "construct":
        inputs[target] = type(value).model_construct(**{**value.__dict__, **changes})
    elif mode == "copy":
        inputs[target] = value.model_copy(update=changes)
    else:
        object.__setattr__(value, "proof_reference", changes["proof_reference"])
    assert_input_free_refusal(
        lambda: cp.match_untrusted_upload(inputs["upload"], inputs["prepare"], source)
    )


@pytest.mark.parametrize("phase", ["upload_possible", "custodied"])
def test_capture_at_observation_is_valid(phase):
    from connect_automate.lead_intake import custody_protocol as cp

    data = pending() if phase == "upload_possible" else custodied()
    data["observed_at"] = data["capture"]["captured_at"]
    if data["source_receipt"] is not None:
        # Receipt decision times require microseconds; preserve the same instant.
        data["source_receipt"]["accepted_at"] = (
            datetime.fromisoformat(data["observed_at"])
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    raw = wire(data)
    try:
        parsed = cp.parse_untrusted_result(raw)
    except Exception as error:
        pytest.fail(f"valid equality boundary rejected: {type(error).__name__}")
    assert cp.canonical_result(parsed) == raw
