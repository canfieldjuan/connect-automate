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


def test_valid_consume_and_signed_receipt(wire):
    p = protocol()
    request, claim = check(wire)
    receipt = {
        "version": "owner-bootstrap/1", "purpose": "owner-bootstrap-receipt", "state": "CONSUMED",
        "receipt_id": uid(8), "binding": request.binding.model_dump(),
        "consumed_at": "2026-01-01T01:00:00Z",
    }
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
    "https://[fe80::1%25eth0]",
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


@pytest.mark.parametrize("origin", ["https://fixture.example", "https://fixture.example:443",
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
