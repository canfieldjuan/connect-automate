"""Synthetic source contract checks; no mail, services or persistence."""

import base64
import hashlib
import json
from copy import deepcopy

import pytest


def envelope(text="Synthetic inquiry"):
    ident = "00000000-0000-4000-8000-000000000001"
    return {
        "payload": {
            "schema": "lead.source.admission",
            "schema_version": "1.0",
            "organization_id": ident,
            "event_id": ident,
            "watcher_event_id": "a" * 64,
            "occurred_at": "2026-10-18T12:00:00Z",
            "source": {
                "namespace_id": ident,
                "provider": "synthetic",
                "account_id": "test-account",
                "mailbox_identity_key": "b" * 64,
                "message_id": "logical-message",
            },
            "trigger": {
                "rule_id": ident,
                "rule_version": 1,
                "admission_kind": "exact_sender",
                "selector_id": "configured-sender",
                "input_kind": "message_body",
                "part_id": "body",
            },
            "snapshot": {
                "snapshot_id": ident,
                "representation": "normalized-text",
                "normalization_version": "watcher-v1",
                "captured_at": "2026-10-18T12:00:00Z",
                "body": {
                    "state": "available",
                    "text": text,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "stored_chars": len(text),
                    "source_chars": len(text),
                    "completeness": "complete",
                },
                "attachments": {"count": None, "processing": "not_processed"},
            },
            "retention": {
                "policy_id": ident,
                "policy_version": 1,
                "recovery_deadline": "2026-10-18T13:00:00Z",
            },
        },
        "authorization": {
            "host_id": ident,
            "key_id": ident,
            "signature": base64.urlsafe_b64encode(bytes(64)).decode().rstrip("="),
        },
    }


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def parse(value):
    from connect_automate.lead_intake import parse_untrusted_source

    return parse_untrusted_source(encode(value))


def test_valid_source_round_trip():
    value = envelope()
    result = parse(value)
    assert result.model_dump(by_alias=True) == value
    assert result.payload.snapshot.body.text == "Synthetic inquiry"


@pytest.mark.parametrize(
    "text", ["", "x", "x" * 199999, "x" * 200000, "\x01" * 200000, "😀" * 200000]
)
def test_body_boundaries_preserve_exact_content(text):
    assert parse(envelope(text)).payload.snapshot.body.text == text


def test_body_above_limit_rejected():
    from connect_automate.lead_intake import SourceInputError

    with pytest.raises(SourceInputError):
        parse(envelope("x" * 200001))


@pytest.mark.parametrize(
    "path,value",
    [
        (("payload", "organization_id"), None),
        (("payload", "event_id"), "a" * 64),
        (("payload", "schema_version"), "2.0"),
        (("payload", "trigger", "rule_version"), True),
        (("payload", "trigger", "rule_version"), 0),
        (("payload", "trigger", "rule_version"), 2147483648),
        (("payload", "trigger", "rule_version"), "1"),
        (("payload", "trigger", "rule_version"), 1.0),
        (("payload", "trigger", "part_id"), "attachment"),
        (("payload", "trigger", "admission_kind"), "model_selected"),
        (("payload", "source", "account_id"), ""),
        (("payload", "source", "account_id"), False),
        (("payload", "source", "account_id"), "é" * 129),
        (("payload", "source", "message_id"), "x" * 257),
        (("payload", "snapshot", "body", "sha256"), "0" * 64),
        (("payload", "snapshot", "body", "stored_chars"), 0),
        (("payload", "snapshot", "body", "stored_chars"), False),
        (("payload", "snapshot", "body", "source_chars"), None),
        (("payload", "snapshot", "attachments", "count"), -1),
        (("payload", "snapshot", "attachments", "count"), False),
        (("payload", "snapshot", "attachments", "processing"), "complete"),
        (("payload", "occurred_at"), "2026-02-30T12:00:00Z"),
        (("payload", "occurred_at"), "2026-10-18T12:00:00+00:00"),
        (("payload", "occurred_at"), "2026-10-18T12:00:00.000Z"),
        (("payload", "snapshot", "captured_at"), "2026-10-18T12:00:01Z"),
        (("payload", "retention", "recovery_deadline"), "2026-10-18T12:00:00Z"),
        (("authorization", "signature"), "A" * 85 + "B"),
        (("authorization", "signature"), "A" * 86 + "=="),
    ],
)
def test_invalid_fields_fail_closed(path, value):
    from connect_automate.lead_intake import SourceInputError

    data = envelope()
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(SourceInputError, match="^invalid lead source input$"):
        parse(data)


@pytest.mark.parametrize("field", ["provider", "account_id", "message_id"])
@pytest.mark.parametrize("value", ["x", "x" * 255, "x" * 256, "é" * 128])
def test_opaque_identifiers_preserved(field, value):
    data = envelope()
    data["payload"]["source"][field] = value
    assert getattr(parse(data).payload.source, field) == value


@pytest.mark.parametrize("revision", [1, 2147483647])
def test_valid_revision_boundaries(revision):
    data = envelope()
    data["payload"]["trigger"]["rule_version"] = revision
    data["payload"]["retention"]["policy_version"] = revision
    assert parse(data).payload.trigger.rule_version == revision


@pytest.mark.parametrize(
    "state,total,valid",
    [
        ("truncated", 18, True),
        ("truncated", 17, False),
        ("truncated", None, False),
        ("unknown", None, True),
        ("unknown", 17, False),
        ("complete", 17, True),
        ("complete", 18, False),
    ],
)
def test_completeness_consistency(state, total, valid):
    from connect_automate.lead_intake import SourceInputError

    data = envelope()
    data["payload"]["snapshot"]["body"].update(completeness=state, source_chars=total)
    if valid:
        assert parse(data).payload.snapshot.body.completeness == state
    else:
        with pytest.raises(SourceInputError):
            parse(data)


@pytest.mark.parametrize(
    "reason", ["source_gone", "outside_scope", "retrieval_failed", "not_captured"]
)
def test_unavailable_has_no_invented_body(reason):
    from connect_automate.lead_intake import SourceInputError

    data = envelope()
    data["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": reason}
    assert parse(data).payload.snapshot.body.reason == reason
    data["payload"]["snapshot"]["body"]["text"] = "invented"
    with pytest.raises(SourceInputError):
        parse(data)


def objects(value):
    yield value
    for item in value.values():
        if isinstance(item, dict):
            yield from objects(item)


def test_all_objects_reject_missing_and_extra_members():
    from connect_automate.lead_intake import SourceInputError

    for index in range(len(list(objects(envelope())))):
        data = envelope()
        target = list(objects(data))[index]
        for key in list(target):
            saved = target.pop(key)
            with pytest.raises(SourceInputError):
                parse(data)
            target[key] = saved
        target["unexpected"] = "private narrative"
        with pytest.raises(SourceInputError):
            parse(data)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"null",
        b"[]",
        b"\xff",
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1.0}',
        b'{"x":"\\ud800"}',
        b"[" * 1100 + b"]" * 1100,
        b'{"x":' + b"9" * 5000 + b"}",
        "not bytes",
    ],
)
def test_malformed_json_is_safe(raw):
    from connect_automate.lead_intake import SourceInputError, parse_untrusted_source

    with pytest.raises(SourceInputError, match="^invalid lead source input$"):
        parse_untrusted_source(raw)


def test_duplicate_keys_at_nested_and_root_levels():
    from connect_automate.lead_intake import SourceInputError, parse_untrusted_source

    raw = encode(envelope())
    for malformed in [
        raw.replace(b'"payload":', b'"payload":null,"payload":', 1),
        raw.replace(b'"stored_chars":', b'"stored_chars":0,"stored_chars":'),
    ]:
        with pytest.raises(SourceInputError):
            parse_untrusted_source(malformed)


def test_raw_byte_cap():
    from connect_automate.lead_intake import SourceInputError, parse_untrusted_source

    raw = encode(envelope())
    for size in [2097151, 2097152]:
        assert parse_untrusted_source(raw + b" " * (size - len(raw)))
    with pytest.raises(SourceInputError):
        parse_untrusted_source(raw + b" " * (2097153 - len(raw)))


def test_canonicalization_uses_validated_payload_and_excludes_authorization():
    from connect_automate.lead_intake import canonical_payload, payload_digest

    data = envelope("é\x01😀")
    parsed = parse(data)
    expected = json.dumps(
        data["payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert canonical_payload(parsed) == expected
    assert payload_digest(parsed) == hashlib.sha256(expected).hexdigest()
    changed = deepcopy(data)
    changed["authorization"]["key_id"] = "00000000-0000-4000-8000-000000000002"
    assert payload_digest(parse(changed)) == payload_digest(parsed)
    changed["payload"]["event_id"] = "00000000-0000-4000-8000-000000000002"
    assert payload_digest(parse(changed)) != payload_digest(parsed)


def test_schema_validation_is_not_authentication_or_expiry_check():
    # All-zero signature is forged. Parsing succeeds without authorizing anything.
    parsed = parse(envelope())
    assert parsed.authorization.signature == "A" * 86
    assert not hasattr(parsed, "authenticated")


def test_nested_models_frozen():
    from pydantic import ValidationError

    parsed = parse(envelope())
    with pytest.raises(ValidationError):
        parsed.payload.snapshot.body.text = "changed"


def test_errors_never_echo_message_content():
    from connect_automate.lead_intake import SourceInputError

    data = envelope("CONFIDENTIAL-SYNTHETIC-NARRATIVE")
    data["payload"]["snapshot"]["body"]["sha256"] = "bad"
    with pytest.raises(SourceInputError) as caught:
        parse(data)
    assert str(caught.value) == "invalid lead source input"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


def test_canonical_vector_from_contract():
    from connect_automate.lead_intake.source import _canonical

    raw = _canonical({"b": "é", "a": 1})
    assert raw == b'{"a":1,"b":"\xc3\xa9"}'
    assert hashlib.sha256(raw).hexdigest() == (
        "09ad9fd2fb648cb2f62141215828ea00a62c299db05d20aa9ade2f527a301cc6"
    )


@pytest.mark.parametrize("field", ["selector_id", "normalization_version"])
def test_other_opaque_fields_enforce_utf8_byte_limit(field):
    from connect_automate.lead_intake import SourceInputError

    data = envelope()
    target = data["payload"]["trigger" if field == "selector_id" else "snapshot"]
    target[field] = "é" * 128
    parse(data)
    target[field] += "x"
    with pytest.raises(SourceInputError):
        parse(data)


@pytest.mark.parametrize("value", ["", False, 0, None, "A" * 85, "A" * 87])
def test_signature_falsy_and_length_boundaries(value):
    from connect_automate.lead_intake import SourceInputError

    data = envelope()
    data["authorization"]["signature"] = value
    with pytest.raises(SourceInputError):
        parse(data)


def test_surrogate_and_array_inside_otherwise_valid_source_rejected():
    from connect_automate.lead_intake import SourceInputError, parse_untrusted_source

    raw = encode(envelope())
    for value in [b'"\\ud800"', b'"\\udfff"', b"[]", b"[" + b"0," * 64 + b"0]"]:
        malformed = raw.replace(b'"test-account"', value)
        with pytest.raises(SourceInputError):
            parse_untrusted_source(malformed)


def test_unicode_normalization_is_not_silent():
    from connect_automate.lead_intake import payload_digest

    composed, decomposed = parse(envelope("é")), parse(envelope("e\u0301"))
    assert composed.payload.snapshot.body.stored_chars == 1
    assert decomposed.payload.snapshot.body.stored_chars == 2
    assert payload_digest(composed) != payload_digest(decomposed)


def test_uuid_and_digest_exact_matches_no_suffix():
    from connect_automate.lead_intake import SourceInputError

    for key in ["organization_id", "watcher_event_id"]:
        data = envelope()
        data["payload"][key] += "\n"
        with pytest.raises(SourceInputError):
            parse(data)
