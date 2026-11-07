"""Synthetic, in-memory test keys only; no issuer, transport or native proof."""

import base64
import hashlib
import importlib
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def protocol():
    return importlib.import_module("qualification.owner_authority.protocol")


def renewal_values(wire):
    original = wire["manifest"].copy()
    installed = original | {"issued_at": "2026-01-02T00:00:00Z",
                            "expires_at": "2026-01-04T00:00:00Z"}
    candidate = installed | {"expires_at": "2026-01-05T00:00:00Z"}
    return original, installed, candidate


def renew(wire, original, installed, candidate, now=None):
    raw = [wire["sign"]("manifest", value, "release")
           for value in (candidate, original, installed)]
    return protocol().check_manifest_renewal(
        *raw, wire["keys"], frozenset({"release"}),
        datetime(2026, 1, 2, 12, tzinfo=UTC) if now is None else now)


def test_manifest_renewal_signed_forward_control(wire):
    original, installed, candidate = renewal_values(wire)
    assert renew(wire, original, installed, candidate).model_dump() == candidate


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def uid(index):
    return f"{index:08x}-1111-4111-8111-111111111111"


@pytest.fixture
def wire():
    p = protocol()
    keys = {name: Ed25519PrivateKey.generate() for name in ("release", "claim", "receipt", "host")}

    def sign(kind, data, key_id):
        payload = p.canonical(data)
        return p.canonical({
            "version": "owner-bootstrap/1", "key_id": key_id,
            "payload_base64url": b64(payload),
            "signature_base64url": b64(keys[key_id].sign(p.prefix(kind) + payload)),
        })

    import json

    manifest = {
        "version": "owner-bootstrap/1", "purpose": "owner-bootstrap-activation",
        "origin": "https://fixture.example", "claim_key_ids": ["claim"],
        "receipt_key_ids": ["receipt"], "issued_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-01-02T00:00:00Z",
    }
    claim = {
        "version": "owner-bootstrap/1", "purpose": "owner-bootstrap",
        "claim_id": uid(1), "organization_id": uid(2), "entitlement_id": uid(3),
        "generation": 1, "issued_at": "2026-01-01T00:00:00Z",
        "not_before": "2026-01-01T00:00:00Z", "expires_at": "2026-01-01T12:00:00Z",
    }
    claim_raw = sign("claim", claim, "claim")
    binding = {
        "version": "owner-bootstrap/1", "operation_id": uid(4), "installation_id": uid(5),
        "host_id": uid(6), "organization_id": uid(2), "claim_id": uid(1),
        "entitlement_id": uid(3), "generation": 1,
        "claim_sha256": hashlib.sha256(claim_raw).hexdigest(),
        "principal_commitment": "b" * 64, "initialization_sha256": "c" * 64,
        "installation_public_key": b64(keys["host"].public_key().public_bytes_raw()),
    }
    request = {"version": "owner-bootstrap/1", "owner_claim": json.loads(claim_raw),
               "binding": binding, "attempt_id": uid(7), "requested_at": "2026-01-01T01:00:00Z"}

    def request_bytes(data=None):
        data = deepcopy(request if data is None else data)
        signed = {k: data[k] for k in ("version", "binding", "attempt_id", "requested_at")}
        data["installation_signature"] = b64(
            keys["host"].sign(p.prefix("consume") + p.canonical(signed)))
        return p.canonical(data)

    return {
        "keys": {k: v.public_key().public_bytes_raw() for k, v in keys.items()},
        "sign": sign, "manifest": manifest, "claim": claim, "request": request,
        "request_bytes": request_bytes,
    }


def check(wire, request=None, now=datetime(2026, 1, 1, 1, tzinfo=UTC)):
    p = protocol()
    return p.check_consume_request(
        wire["request_bytes"](request), wire["sign"]("manifest", wire["manifest"], "release"),
        wire["keys"], frozenset({"release"}), now,
    )


def receipt_payload(wire):
    return {
        "version": "owner-bootstrap/1", "purpose": "owner-bootstrap-receipt", "state": "CONSUMED",
        "receipt_id": uid(8), "binding": wire["request"]["binding"].copy(),
        "consumed_at": "2026-01-01T01:00:00Z",
    }


def test_valid_consume_and_signed_receipt(wire):
    p = protocol()
    request, claim = check(wire)
    receipt = receipt_payload(wire)
    raw = wire["sign"]("receipt", receipt, "receipt")
    def checked_receipt(data):
        return p.check_receipt(data, wire["request_bytes"](),
                               wire["sign"]("manifest", wire["manifest"], "release"),
                               wire["keys"], frozenset({"release"}),
                               datetime(2026, 1, 1, 1, tzinfo=UTC))

    assert checked_receipt(raw).receipt_id == uid(8)
    for field, value in [("consumed_at", "2026-01-01T12:00:00Z"),
                         ("binding", request.binding.model_dump() | {"operation_id": uid(9)})]:
        with pytest.raises(p.ProtocolInputError):
            checked_receipt(wire["sign"]("receipt", receipt | {field: value}, "receipt"))


@pytest.mark.parametrize("offset", [-61, -60, -59, 0, 59, 60, 61])
def test_signed_attempt_clock_window_and_expired_claim_replay_shape(wire, offset):
    p = protocol()
    now = datetime(2026, 1, 1, 1, tzinfo=UTC) + timedelta(seconds=offset)
    if abs(offset) > 60:
        with pytest.raises(p.ClockSkewError) as exc:
            check(wire, now=now)
        assert exc.value.code == "OWNER_CLOCK_SKEW"
        assert exc.value.completion == "NOT_COMMITTED"
    else:
        assert check(wire, now=now)[0].binding.operation_id == uid(4)
    # Shape/signature admission permits expiry recovery; only a later ledger
    # decides new consumption, and fresh local authority remains out of scope.
    claim = wire["claim"] | {"expires_at": "2026-01-01T00:30:00Z"}
    raw = wire["sign"]("claim", claim, "claim")
    import json
    request = deepcopy(wire["request"])
    request["owner_claim"] = json.loads(raw)
    request["binding"]["claim_sha256"] = hashlib.sha256(raw).hexdigest()
    assert check(wire, request)[1].expires_at == claim["expires_at"]


@pytest.mark.parametrize("field,value", [
    ("claim_id", uid(9)), ("organization_id", uid(9)), ("entitlement_id", uid(9)),
    ("generation", 2), ("claim_sha256", "d" * 64),
])
def test_otherwise_valid_binding_mismatch_is_refused(wire, field, value):
    p = protocol()
    request = deepcopy(wire["request"])
    request["binding"][field] = value
    with pytest.raises(p.ProtocolInputError):
        check(wire, request)


@pytest.mark.parametrize("change", ["signature", "host_key", "domain", "noncanonical"])
def test_authentication_precedes_clock_classification(wire, change):
    import json
    p = protocol()
    data = json.loads(wire["request_bytes"]())
    if change == "signature":
        data["installation_signature"] = b64(b"\0" * 64)
    elif change == "host_key":
        data["binding"]["installation_public_key"] = b64(wire["keys"]["claim"])
    elif change == "domain":
        data["owner_claim"] = json.loads(wire["sign"]("receipt", wire["claim"], "claim"))
    raw = p.canonical(data) if change != "noncanonical" else json.dumps(data).encode()
    with pytest.raises(p.ProtocolInputError):
        p.check_consume_request(raw, wire["sign"]("manifest", wire["manifest"], "release"),
                                wire["keys"], frozenset({"release"}),
                                datetime(2026, 1, 1, 2, tzinfo=UTC))


def test_installation_signature_is_verified(wire):
    import json
    p = protocol()
    data = json.loads(wire["request_bytes"]())
    data["installation_signature"] = b64(b"\0" * 64)
    with pytest.raises(p.ProtocolInputError):
        p.check_consume_request(p.canonical(data),
                                wire["sign"]("manifest", wire["manifest"], "release"),
                                wire["keys"], frozenset({"release"}),
                                datetime(2026, 1, 1, 1, tzinfo=UTC))


@pytest.mark.parametrize("origin", [
    "http://fixture.example", "https://fixture.example/", "https://user@fixture.example",
    "https://fixture.example?", "https://fixture.example#", "https://fixture.example:444",
    "https://%66ixture.example", "https://fíxture.example", "https://fixture_.example",
    "https://fixture.example\n", "https://fixture.example/x", "https://-a.example",
    "https://[fe80::1%25eth0]", "https://fi_xt.example", "https://" + "a" * 64 + ".example",
])
def test_manifest_origin_uses_real_uri_parser(wire, origin):
    p = protocol()
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(wire["sign"]("manifest", wire["manifest"] | {"origin": origin}, "release"),
                        "manifest", wire["keys"], frozenset({"release"}))


def test_maximal_manifest_and_purpose_selected_budget(wire):
    p = protocol()
    names = [f"k{i:063}" for i in range(16)]
    keys = wire["keys"] | {n: wire["keys"]["claim"] for n in names}
    origin = "https://" + ".".join(["a" * 63] * 3 + ["a" * 55])
    manifest = wire["manifest"] | {
        "origin": origin, "claim_key_ids": names, "receipt_key_ids": names,
    }
    raw = wire["sign"]("manifest", manifest, "release")
    assert len(origin) == 255 and len(raw) > p.SMALL.envelope
    assert p.verify_signed(raw, "manifest", keys, frozenset({"release"})).origin == origin
    for kind in ("claim", "receipt"):
        with pytest.raises(p.ProtocolInputError):
            p.verify_signed(raw, kind, keys, frozenset({"release"}))
    for patch in ({"origin": origin + "a"}, {"claim_key_ids": names + ["extra"]},
                  {"claim_key_ids": ["a" * 65]}, {"claim_key_ids": []},
                  {"claim_key_ids": ["claim", "claim"]}):
        with pytest.raises(p.ProtocolInputError):
            p.verify_signed(wire["sign"]("manifest", manifest | patch, "release"),
                            "manifest", keys, frozenset({"release"}))


@pytest.mark.parametrize("patch", [
    {"generation": 0}, {"generation": False}, {"generation": 2147483648},
    {"issued_at": "2026-01-01T00:00:00.0Z"}, {"not_before": "2026-02-30T00:00:00Z"},
    {"expires_at": "2026-01-01T00:00:00Z"}, {"expires_at": "2026-01-02T00:00:01Z"},
    {"purpose": "owner-bootstrap-receipt"}, {"native_identity": "forged"},
])
def test_claim_schema_and_cross_field_guards(wire, patch):
    p = protocol()
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(wire["sign"]("claim", wire["claim"] | patch, "claim"),
                        "claim", wire["keys"], frozenset({"claim"}))


def test_missing_claim_fields_and_wrong_key_purpose(wire):
    p = protocol()
    for field in wire["claim"]:
        claim = wire["claim"].copy()
        del claim[field]
        with pytest.raises(p.ProtocolInputError):
            p.verify_signed(wire["sign"]("claim", claim, "claim"),
                            "claim", wire["keys"], frozenset({"claim"}))
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(wire["sign"]("claim", wire["claim"], "receipt"),
                        "claim", wire["keys"], frozenset({"claim"}))


@pytest.mark.parametrize("origin", ["https://fixture.example",
                                    "https://[::1]", "https://xn--bcher-kva.example"])
def test_valid_origin_second_side(wire, origin):
    p = protocol()
    raw = wire["sign"]("manifest", wire["manifest"] | {"origin": origin}, "release")
    assert p.verify_signed(raw, "manifest", wire["keys"], frozenset({"release"})).origin == origin


@pytest.mark.parametrize("kind", ["manifest", "claim", "receipt"])
def test_enclosing_byte_cap_before_parse(wire, monkeypatch, kind):
    p = protocol()
    budget = p.MANIFEST if kind == "manifest" else p.SMALL

    def forbidden(*args, **kwargs):
        pytest.fail("over-limit input reached JSON parser")

    monkeypatch.setattr(p.json, "loads", forbidden)
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(b" " * (budget.envelope + 1), kind, wire["keys"], frozenset({"claim"}))


def test_encoding_limits_and_schema_owner():
    p = protocol()
    fields = p.ActivationManifest.model_json_schema()["properties"]
    assert fields["origin"]["format"] == "uri"
    assert fields["issued_at"]["format"] == "date-time"
    for budget, model in [(p.SMALL, p.SmallEnvelope), (p.MANIFEST, p.ManifestEnvelope)]:
        payload_schema = model.model_json_schema()["properties"]["payload_base64url"]
        assert payload_schema["maxLength"] == budget.encoded
        assert p._decoded(b64(b"x" * budget.payload), budget.payload) == b"x" * budget.payload
        with pytest.raises(ValueError):
            p._decoded(b64(b"x" * (budget.payload + 1)), budget.payload)
    for value in ("=", "A", "AA=", "AB", "AA+", "AA/", "AA\n"):
        with pytest.raises(ValueError):
            p._decoded(value, 32)


def test_refusal_is_closed_untrusted_syntax():
    p = protocol()
    refusal = {"version": "owner-bootstrap/1", "code": "OWNER_CLOCK_SKEW",
               "operation_id": uid(4), "completion": "NOT_COMMITTED"}
    assert p.parse_refusal(p.canonical(refusal)).code == "OWNER_CLOCK_SKEW"
    for patch in ({"completion": "UNKNOWN"}, {"operation_id": None},
                  {"message": "private narrative"}, {"code": "NATIVE_AUTH_DENIED"}):
        with pytest.raises(p.ProtocolInputError):
            p.parse_refusal(p.canonical(refusal | patch))


def test_wire_functions_do_not_access_installed_or_external_state(wire, monkeypatch):
    import builtins
    import socket
    import sqlite3
    p = protocol()

    def forbidden(*args, **kwargs):
        pytest.fail("wire conformance attempted I/O")

    for owner, name in [(builtins, "open"), (Path, "open"),
                        (socket, "socket"), (sqlite3, "connect")]:
        monkeypatch.setattr(owner, name, forbidden)
    assert check(wire)[0].binding.operation_id == uid(4)
    assert p.verify_signed(wire["sign"]("claim", wire["claim"], "claim"),
                           "claim", wire["keys"], frozenset({"claim"})).claim_id == uid(1)


@pytest.mark.parametrize("origin", ["https://1.2.3.4", "https://127.1", "https://0x7f000001",
                                    "https://a.example.", "https://a.example:443"])
def test_canonical_origin_rejects_ip4_and_alternate_spellings(wire, origin):
    p = protocol()
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(wire["sign"]("manifest", wire["manifest"] | {"origin": origin}, "release"),
                        "manifest", wire["keys"], frozenset({"release"}))


@pytest.mark.parametrize("kind,key", [("manifest", "release"), ("claim", "claim"),
                                      ("receipt", "receipt")])
def test_issuer_signature_and_invalid_signature_mapping(wire, kind, key):
    import json
    p = protocol()
    payload = receipt_payload(wire) if kind == "receipt" else wire[kind]
    raw = wire["sign"](kind, payload, key)
    # Valid shape/purpose/key allowlist; replace ONLY the issuer signature.
    data = json.loads(raw)
    other = "receipt" if key != "receipt" else "claim"
    data["signature_base64url"] = json.loads(wire["sign"]("claim", wire["claim"], other))[
        "signature_base64url"]
    assert p.verify_signed(raw, kind, wire["keys"], frozenset({key}))
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(p.canonical(data), kind, wire["keys"], frozenset({key}))


def test_request_claim_uses_only_manifest_claim_key_set(wire):
    import json
    p = protocol()
    request = deepcopy(wire["request"])
    raw = wire["sign"]("claim", wire["claim"], "receipt")
    request["owner_claim"] = json.loads(raw)
    request["binding"]["claim_sha256"] = hashlib.sha256(raw).hexdigest()
    # The alternative key and all signatures are valid, but not for this role.
    assert p.verify_signed(raw, "claim", wire["keys"], frozenset({"receipt"}))
    with pytest.raises(p.ProtocolInputError):
        check(wire, request)


def test_receipt_uses_only_manifest_receipt_key_set(wire):
    p = protocol()
    raw = wire["sign"]("receipt", receipt_payload(wire), "claim")
    assert p.verify_signed(raw, "receipt", wire["keys"], frozenset({"claim"}))
    with pytest.raises(p.ProtocolInputError):
        p.check_receipt(raw, wire["request_bytes"](),
                        wire["sign"]("manifest", wire["manifest"], "release"),
                        wire["keys"], frozenset({"release"}),
                        datetime(2026, 1, 1, 1, tzinfo=UTC))


@pytest.mark.parametrize("field", ["claim_key_ids", "receipt_key_ids"])
def test_manifest_cannot_name_an_uninstalled_key(wire, field):
    p = protocol()
    raw = wire["sign"]("manifest", wire["manifest"] | {field: ["absent-key"]}, "release")
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(raw, "manifest", wire["keys"], frozenset({"release"}))


@pytest.mark.parametrize("expiry", ["2026-01-01T00:00:00Z", "2025-12-31T00:00:00Z",
                                     "2026-01-31T00:00:01Z"])
def test_manifest_interval_is_ordered_and_bounded(wire, expiry):
    p = protocol()
    raw = wire["sign"]("manifest", wire["manifest"] | {"expires_at": expiry}, "release")
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(raw, "manifest", wire["keys"], frozenset({"release"}))


@pytest.mark.parametrize("patch", [{"issued_at": "2026-01-01T02:00:00Z"},
                                   {"expires_at": "2026-01-01T01:00:00Z"}])
def test_manifest_must_be_current_at_issuer_time(wire, patch):
    p = protocol()
    wire["manifest"].update(patch)
    with pytest.raises(p.ProtocolInputError):
        check(wire)


@pytest.mark.parametrize("kind,field,value", [
    ("manifest", "purpose", "owner-bootstrap"),
    ("receipt", "purpose", "owner-bootstrap"), ("receipt", "state", "PENDING"),
])
def test_independent_manifest_and_receipt_constants(wire, kind, field, value):
    p = protocol()
    payload = receipt_payload(wire) if kind == "receipt" else wire[kind]
    key = "release" if kind == "manifest" else "receipt"
    with pytest.raises(p.ProtocolInputError):
        p.verify_signed(wire["sign"](kind, payload | {field: value}, key),
                        kind, wire["keys"], frozenset({key}))


@pytest.mark.parametrize("mode", ["offset", "subclass"])
def test_issuer_clock_requires_exact_utc_datetime(wire, mode):
    from datetime import timezone
    p = protocol()

    class OtherDate(datetime):
        pass

    now = (datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=1))) if mode == "offset"
           else OtherDate(2026, 1, 1, 1, tzinfo=UTC))
    with pytest.raises(p.ProtocolInputError):
        check(wire, now=now)


def test_request_byte_limit_precedes_request_parse(wire, monkeypatch):
    p = protocol()
    original = p.json.loads

    def loads(value, **kwargs):
        if len(value) > 8192:
            pytest.fail("oversize request reached JSON parse")
        return original(value, **kwargs)

    monkeypatch.setattr(p.json, "loads", loads)
    with pytest.raises(p.ProtocolInputError):
        p.check_consume_request(b" " * 8193,
                                wire["sign"]("manifest", wire["manifest"], "release"),
                                wire["keys"], frozenset({"release"}),
                                datetime(2026, 1, 1, 1, tzinfo=UTC))


@pytest.mark.parametrize("model_name,budget_name", [("SmallEnvelope", "SMALL"),
                                                  ("ManifestEnvelope", "MANIFEST")])
def test_decoded_budget_is_implied_by_earlier_encoded_schema(wire, model_name, budget_name):
    from pydantic import ValidationError
    p = protocol()
    model, budget = getattr(p, model_name), getattr(p, budget_name)
    value = b64(b"x" * (budget.payload + 1))
    # A downstream decoded-size guard is unreachable after the stronger encoded
    # schema. Test each owner directly; do not pretend one sample isolates both.
    assert len(value) > budget.encoded
    with pytest.raises(ValidationError):
        model.model_validate({"version": "owner-bootstrap/1", "key_id": "claim",
                              "payload_base64url": value,
                              "signature_base64url": b64(b"\0" * 64)})
    with pytest.raises(ValueError):
        p._decoded(value, budget.payload)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("field,value", [
    ("origin", "https://other.example"), ("claim_key_ids", ["host"]),
    ("receipt_key_ids", ["host"]),
])
def test_renewal_each_historical_policy_is_independently_checked(wire, side, field, value):
    p = protocol()
    values = list(renewal_values(wire))
    values[side] = values[side] | {field: value}
    with pytest.raises(p.ProtocolInputError):
        renew(wire, *values)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("field", ["issued_at", "expires_at"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_renewal_each_interval_half_and_equality(wire, side, field, offset):
    p = protocol()
    original, installed, candidate = renewal_values(wire)
    # Only the selected prior imposes the tighter bound: removing either reader
    # cannot be masked by the other historical comparison.
    values = [original, installed] if side == 1 else [installed, original]
    stamp = p._date(installed[field]) + timedelta(seconds=offset)
    candidate[field] = stamp.isoformat(timespec="seconds").replace("+00:00", "Z")
    if offset < 0 or (field == "expires_at" and offset == 0):
        with pytest.raises(p.ProtocolInputError):
            renew(wire, *values, candidate)
    else:
        assert renew(wire, *values, candidate).model_dump() == candidate


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("boundary", ["issued_at", "expires_at"])
def test_renewal_candidate_current_window(wire, boundary, offset):
    p = protocol()
    values = renewal_values(wire)
    now = p._date(values[2][boundary]) + timedelta(seconds=offset)
    if (boundary == "issued_at" and offset < 0) or (boundary == "expires_at" and offset >= 0):
        with pytest.raises(p.ProtocolInputError) as caught:
            renew(wire, *values, now=now)
        assert type(caught.value) is p.ProtocolInputError
    else:
        assert renew(wire, *values, now=now).model_dump() == values[2]


@pytest.mark.parametrize("seconds", [2591999, 2592000, 2592001])
def test_renewal_uses_existing_maximum_interval(wire, seconds):
    p = protocol()
    original, installed, candidate = renewal_values(wire)
    end = p._date(candidate["issued_at"]) + timedelta(seconds=seconds)
    candidate["expires_at"] = end.isoformat(timespec="seconds").replace("+00:00", "Z")
    if seconds > 2592000:
        with pytest.raises(p.ProtocolInputError):
            renew(wire, original, installed, candidate)
    else:
        assert renew(wire, original, installed, candidate).model_dump() == candidate


def test_renewal_reordered_key_sets_and_expired_history(wire):
    original, installed, candidate = renewal_values(wire)
    for value in (original, installed, candidate):
        value.update(claim_key_ids=["host", "claim"], receipt_key_ids=["release", "receipt"])
    candidate["claim_key_ids"].reverse()
    candidate["receipt_key_ids"].reverse()
    assert renew(wire, original, installed, candidate,
                 now=datetime(2026, 1, 4, 12, tzinfo=UTC)).model_dump() == candidate
    later = candidate | {"issued_at": "2026-01-04T12:00:00Z",
                         "expires_at": "2026-01-06T00:00:00Z"}
    assert renew(wire, original, candidate, later,
                 now=datetime(2026, 1, 5, tzinfo=UTC)).model_dump() == later


@pytest.mark.parametrize("side", [0, 1, 2])
@pytest.mark.parametrize("defect", ["absent", "empty", "wrong-signer", "bad-signature",
                                    "missing", "extra", "falsy", "purpose", "version", "oversize"])
def test_renewal_verifies_all_signed_inputs(wire, side, defect):
    p = protocol()
    values = list(renewal_values(wire))
    if defect == "missing":
        del values[side]["origin"]
    elif defect == "extra":
        values[side]["approved"] = True
    elif defect == "falsy":
        values[side]["claim_key_ids"] = []
    elif defect == "purpose":
        values[side]["purpose"] = "owner-bootstrap"
    elif defect == "version":
        values[side]["version"] = "owner-bootstrap/2"
    raw = [wire["sign"]("manifest", value, "release") for value in values]
    if defect == "absent":
        raw[side] = None
    elif defect == "empty":
        raw[side] = b""
    elif defect == "wrong-signer":
        raw[side] = wire["sign"]("manifest", values[side], "claim")
    elif defect == "bad-signature":
        import json
        envelope = json.loads(raw[side])
        envelope["signature_base64url"] = b64(bytes(64))
        raw[side] = p.canonical(envelope)
    elif defect == "oversize":
        raw[side] = b" " * (p.MANIFEST.envelope + 1)
    with pytest.raises(p.ProtocolInputError) as caught:
        p.check_manifest_renewal(raw[2], raw[0], raw[1], wire["keys"],
                                 frozenset({"release"}), datetime(2026, 1, 2, 12, tzinfo=UTC))
    assert type(caught.value) is p.ProtocolInputError


@pytest.mark.parametrize("bad_now", [None, False, 0, "", datetime(2026, 1, 2)])
def test_active_manifest_rejects_invalid_clock_before_absence(wire, bad_now):
    p = protocol()
    with pytest.raises(p.ProtocolInputError) as caught:
        p.verify_active_manifest(None, wire["keys"], frozenset({"release"}), bad_now)
    assert type(caught.value) is p.ProtocolInputError


@pytest.mark.parametrize("missing", [False, True])
def test_active_manifest_availability_survives_consume_admission(wire, missing):
    p = protocol()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    wire["request"]["requested_at"] = "2026-01-02T00:00:00Z"
    manifest = None if missing else wire["sign"]("manifest", wire["manifest"], "release")
    with pytest.raises(p.ManifestUnavailable):
        p.check_consume_request(wire["request_bytes"](), manifest, wire["keys"],
                                frozenset({"release"}), now)
    with pytest.raises(p.MalformedConsumeRequest):
        p.check_consume_request(b"{}", manifest, wire["keys"], frozenset({"release"}), now)


def test_active_manifest_untrusted_expired_bytes_are_not_unavailability(wire):
    p = protocol()
    raw = wire["sign"]("manifest", wire["manifest"], "claim")
    with pytest.raises(p.ProtocolInputError) as caught:
        p.verify_active_manifest(raw, wire["keys"], frozenset({"release"}),
                                 datetime(2026, 1, 2, tzinfo=UTC))
    assert type(caught.value) is p.ProtocolInputError


def test_renewal_selection_closed_schema_and_boundaries():
    from pydantic import ValidationError

    p = protocol()
    values = {"operation_id": uid(4), "pending_binding_sha256": "a" * 64,
              "original_manifest_sha256": "b" * 64, "installed_manifest_sha256": "c" * 64}
    selection = p.RenewalSelection.model_validate(values)
    assert selection.model_dump() == values
    schema = p.RenewalSelection.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(values) == set(schema["properties"])
    with pytest.raises(ValidationError):
        selection.operation_id = uid(5)
    for field in values:
        missing = values.copy()
        del missing[field]
        with pytest.raises(ValidationError):
            p.RenewalSelection.model_validate(missing)
        for invalid in (None, False, 0, "", "a" * 63, "a" * 65, "g" * 64, "a" * 64 + "\n"):
            with pytest.raises(ValidationError):
                p.RenewalSelection.model_validate(values | {field: invalid})
        if field != "operation_id":
            assert schema["properties"][field]["pattern"] == r"^[0-9a-f]{64}$"
    with pytest.raises(ValidationError):
        p.RenewalSelection.model_validate(values | {"approved": True})


@pytest.mark.parametrize("entry", ["active", "consume"])
@pytest.mark.parametrize("boundary", ["issued_at", "expires_at"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_active_manifest_window_has_exact_category(wire, entry, boundary, offset):
    p = protocol()
    now = p._date(wire["manifest"][boundary]) + timedelta(seconds=offset)
    manifest = wire["sign"]("manifest", wire["manifest"], "release")
    wire["request"]["requested_at"] = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    def verify():
        if entry == "active":
            return p.verify_active_manifest(manifest, wire["keys"], frozenset({"release"}), now)
        return p.check_consume_request(wire["request_bytes"](), manifest, wire["keys"],
                                        frozenset({"release"}), now)
    future = boundary == "issued_at" and offset < 0
    expired = boundary == "expires_at" and offset >= 0
    if future or expired:
        with pytest.raises(p.ProtocolInputError) as caught:
            verify()
        assert type(caught.value) is (p.ProtocolInputError if future else p.ManifestUnavailable)
    elif entry == "active":
        assert verify().model_dump() == wire["manifest"]
    else:
        assert verify()[0].requested_at == wire["request"]["requested_at"]
