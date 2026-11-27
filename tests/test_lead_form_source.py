"""V1c synthetic form source and signing boundary."""

import base64
import hashlib
import json

import pytest
from test_lead_source import objects
from test_lead_source_auth import NOW, encode, envelope, resign, trust

from connect_automate.lead_intake import (
    SourceInputError,
    authenticate_source,
    canonical_source,
    parse_untrusted_source,
    source_signing_bytes,
)

FORM = "Name: Zoë\r\nEmail: synthetic@example.test\r\nMessage: Hello 😀\r\n  Name: data\r\n"
FORM_BYTES = FORM.encode()


def form_envelope(body=FORM_BYTES):
    value = envelope()
    payload = value["payload"]
    snapshot = payload["snapshot"]
    payload["schema_version"] = "2.0"
    payload["snapshot"] = {
        "snapshot_id": snapshot["snapshot_id"],
        "captured_at": snapshot["captured_at"],
        "representation": "exact-mime-part",
        "template_id": "synthetic-form-v1",
        "part": {
            "part_id": "1.2",
            "media_type": "text/plain",
            "charset": "utf-8",
            "content_base64": base64.b64encode(body).decode("ascii"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "source_owner_evidence": {
                "raw_message_sha256": hashlib.sha256(b"synthetic wire message").hexdigest(),
                "signing_domain": "form.example.test",
                "signing_selector": "synthetic",
            },
        },
        "attachments": snapshot["attachments"],
    }
    return value


def test_signed_v2_preserves_exact_form_and_source_evidence():
    value = form_envelope()
    raw = resign(value)
    source = parse_untrusted_source(raw)
    part = source.payload.snapshot.part
    assert part.content_bytes() == FORM_BYTES
    assert part.part_id == "1.2"
    assert part.source_owner_evidence.signing_domain == "form.example.test"
    assert part.source_owner_evidence.signing_selector == "synthetic"
    assert canonical_source(source) == json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    assert authenticate_source(raw, trust=trust(), now=NOW).source == source


def test_form_binding_fields_change_the_signing_preimage():
    value = form_envelope()
    before = source_signing_bytes(parse_untrusted_source(encode(value)))
    part = value["payload"]["snapshot"]["part"]
    evidence = part["source_owner_evidence"]
    for target, field, changed in [
        (part, "part_id", "1.3"),
        (evidence, "raw_message_sha256", "a" * 64),
        (evidence, "signing_domain", "other.example.test"),
        (evidence, "signing_selector", "other"),
    ]:
        original = target[field]
        target[field] = changed
        assert source_signing_bytes(parse_untrusted_source(encode(value))) != before
        target[field] = original


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "1.0"),
        (("schema_version",), "2.1"),
        (("snapshot", "representation"), "normalized-text"),
        (("snapshot", "template_id"), "unknown"),
        (("snapshot", "body"), {"state": "unavailable"}),
        (("snapshot", "part", "media_type"), "text/html"),
        (("snapshot", "part", "charset"), "iso-8859-1"),
        (("snapshot", "part", "part_id"), ""),
        (("snapshot", "part", "sha256"), "0" * 64),
        (("snapshot", "part", "content_base64"), "%%%="),
        (("snapshot", "part", "content_base64"), "TQ"),
        (("snapshot", "part", "content_base64"), "TR=="),
        (("snapshot", "part", "source_owner_evidence"), None),
        (("snapshot", "part", "source_owner_evidence", "raw_message_sha256"), "invalid"),
        (("snapshot", "part", "source_owner_evidence", "signing_domain"), ""),
        (("snapshot", "part", "source_owner_evidence", "signing_selector"), ""),
        (("snapshot", "part", "source_owner_evidence", "verified"), True),
    ],
)
def test_v2_refuses_invalid_members(path, value):
    # Use a matching decoded digest so noncanonical pad bits cannot hide
    # behind the digest guard.
    data = form_envelope(b"M" if value == "TR==" else FORM_BYTES)
    target = data["payload"]
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = value
    with pytest.raises(SourceInputError, match="^invalid lead source input$"):
        parse_untrusted_source(encode(data))


@pytest.mark.parametrize("content", [False, 0, None, []])
def test_v2_base64_requires_a_string(content):
    data = form_envelope(b"M")
    data["payload"]["snapshot"]["part"]["content_base64"] = content
    with pytest.raises(SourceInputError):
        parse_untrusted_source(encode(data))


def test_v2_requires_members_and_rejects_extra_members():
    data = form_envelope()
    for target in objects(data):
        for field in list(target):
            value = target.pop(field)
            with pytest.raises(SourceInputError):
                parse_untrusted_source(encode(data))
            target[field] = value
        target["unexpected"] = "synthetic"
        with pytest.raises(SourceInputError):
            parse_untrusted_source(encode(data))
        del target["unexpected"]


def test_v2_rejects_undecodable_bytes_with_matching_digest():
    with pytest.raises(SourceInputError):
        parse_untrusted_source(encode(form_envelope(b"\xff")))


def test_v2_encoded_budget_and_lexical_shape_precede_decode(monkeypatch):
    from connect_automate.lead_intake.source import MAX_BODY_CHARS, FormPart

    def unexpected_decode(self):
        pytest.fail("invalid base64 reached the body decoder")

    monkeypatch.setattr(FormPart, "content_bytes", unexpected_decode)
    for content in ("A" * (4 * ((4 * MAX_BODY_CHARS + 2) // 3) + 4), "TQ==\n"):
        data = form_envelope()
        data["payload"]["snapshot"]["part"]["content_base64"] = content
        with pytest.raises(SourceInputError):
            parse_untrusted_source(encode(data))


def test_v2_encoder_revalidates_copied_models():
    source = parse_untrusted_source(encode(form_envelope()))
    snapshot = source.payload.snapshot
    part = snapshot.part.model_copy(update={"sha256": "0" * 64})
    snapshot = snapshot.model_copy(update={"part": part})
    payload = source.payload.model_copy(update={"snapshot": snapshot})
    with pytest.raises(SourceInputError):
        canonical_source(source.model_copy(update={"payload": payload}))


@pytest.mark.parametrize("character", ["x", "😀"])
def test_v2_preserves_existing_character_budget(character):
    from connect_automate.lead_intake.source import MAX_BODY_CHARS

    for length in (MAX_BODY_CHARS - 1, MAX_BODY_CHARS):
        body = (character * length).encode()
        source = parse_untrusted_source(encode(form_envelope(body)))
        assert source.payload.snapshot.part.content_bytes() == body
    with pytest.raises(SourceInputError):
        parse_untrusted_source(encode(form_envelope((character * (MAX_BODY_CHARS + 1)).encode())))
