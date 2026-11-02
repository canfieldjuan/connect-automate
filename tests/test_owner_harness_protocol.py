"""Offline contracts only; no controller, issuer or native proof is exercised."""

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def protocol():
    return importlib.import_module("qualification.owner_authority.protocol")


def fixture(kind="result"):
    artifact = {"alias": "fixture-one", "sha256": "a" * 64}
    packet = {
        "version": "owner-harness/1",
        "evidence_class": "OFFLINE_CONFORMANCE",
        "qualification_pass": False,
        "contract_commit": "a" * 40,
        "harness_commit": "b" * 40,
        "run_id": "11111111-1111-4111-8111-111111111111",
        "dependency_lock_sha256": "c" * 64,
    }
    if kind == "run":
        return packet | {"case_ids": ["wire-good"], "fixtures": [artifact]}
    case = {
        "case_id": "wire-good", "platform": "linux", "outcome": "PASS",
        "expected_code": "VALID", "actual_code": "VALID", "assertion_ids": ["a-one"],
        "fixture_sha256": "d" * 64, "duration_ns": 1, "artifacts": [artifact],
    }
    return packet | {"cases": [case]}


@pytest.mark.parametrize("kind", ["run", "result"])
def test_offline_packet_round_trip_and_schema_drift(kind):
    p = protocol()
    data = fixture(kind)
    model = p.parse_packet(p.canonical(data), kind)
    assert model.model_dump() == data
    assert p.packet_bytes(model) == p.canonical(data)
    schema = p.schemas()[kind + ".schema.json"]
    assert (ROOT / "qualification/owner_authority" / (kind + ".schema.json")).read_bytes() == schema
    decoded = json.loads(schema)
    assert decoded["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert decoded["properties"]["evidence_class"]["const"] == "OFFLINE_CONFORMANCE"
    assert decoded["properties"]["qualification_pass"] == {
        "const": False, "title": "Qualification Pass", "type": "boolean",
    }
    for item in [decoded, *decoded.get("$defs", {}).values()]:
        if item.get("type") == "object":
            assert item["additionalProperties"] is False
            assert set(item["required"]) == set(item["properties"])


@pytest.mark.parametrize("kind", ["run", "result"])
@pytest.mark.parametrize("field,value", [
    ("evidence_class", "NATIVE_QUALIFICATION"), ("qualification_pass", True),
    ("qualification_pass", 0), ("qualification_pass", ""), ("qualification_pass", None),
    ("overall", "PASS"), ("outcome", "PASS"), ("version", "other"),
])
def test_native_and_falsy_overrides_rejected_without_controller(kind, field, value):
    p = protocol()
    data = fixture(kind) | {field: value}
    with pytest.raises(p.ProtocolInputError, match="invalid offline protocol input"):
        p.parse_packet(p.canonical(data), kind)


@pytest.mark.parametrize("kind", ["run", "result"])
def test_every_missing_field_is_independently_refused(kind):
    p = protocol()
    for field in fixture(kind):
        data = fixture(kind)
        del data[field]
        with pytest.raises(p.ProtocolInputError):
            p.parse_packet(p.canonical(data), kind)


def test_numeric_zero_does_not_satisfy_false_literal():
    p = protocol()
    with pytest.raises(p.ProtocolInputError):
        p.parse_packet(p.canonical(fixture() | {"qualification_pass": 0}), "result")


def test_nested_required_fields_and_run_uniqueness():
    p = protocol()
    for field in fixture()["cases"][0]:
        data = fixture()
        del data["cases"][0][field]
        with pytest.raises(p.ProtocolInputError):
            p.parse_packet(p.canonical(data), "result")
    for field in ("case_ids", "fixtures"):
        data = fixture("run")
        data[field] *= 2
        with pytest.raises(p.ProtocolInputError):
            p.parse_packet(p.canonical(data), "run")


def test_packet_byte_cap_applies_before_json_parse(monkeypatch):
    p = protocol()
    raw = p.canonical(fixture())
    padded = raw + b" " * (p.PACKET_BYTES - len(raw))
    assert p.parse_packet(padded, "result").qualification_pass is False

    def forbidden(*args, **kwargs):
        pytest.fail("oversize packet reached JSON parser")

    monkeypatch.setattr(p.json, "loads", forbidden)
    with pytest.raises(p.ProtocolInputError):
        p.parse_packet(padded + b" ", "result")


@pytest.mark.parametrize("duration", [0, 1, 179999999999, 180000000000])
def test_valid_duration_boundaries_and_empty_artifacts(duration):
    p = protocol()
    data = fixture()
    data["cases"][0].update(duration_ns=duration, artifacts=[])
    assert p.parse_packet(p.canonical(data), "result").cases[0].duration_ns == duration


@pytest.mark.parametrize("outcome", ["PASS", "FAIL", "STOP"])
def test_case_outcome_is_only_an_offline_assertion(outcome):
    p = protocol()
    data = fixture()
    data["cases"][0]["outcome"] = outcome
    assert p.parse_packet(p.canonical(data), "result").qualification_pass is False


@pytest.mark.parametrize("field,value", [
    ("outcome", "NOT_RUN"), ("platform", "native"), ("case_id", ""),
    ("case_id", "x" * 65), ("case_id", "../personal"), ("case_id", "a\n"),
    ("duration_ns", -1), ("duration_ns", False), ("duration_ns", 180000000001),
    ("assertion_ids", []), ("assertion_ids", ["a"] * 2),
    ("actual_code", "raw confidential text"), ("fixture_sha256", "z" * 64),
    ("evidence_class", "NATIVE_QUALIFICATION"),
])
def test_isolated_case_guards(field, value):
    p = protocol()
    data = fixture()
    data["cases"][0][field] = value
    with pytest.raises(p.ProtocolInputError):
        p.parse_packet(p.canonical(data), "result")


def test_mixed_cases_duplicates_and_artifacts():
    p = protocol()
    for field in ("case_id", "artifacts"):
        data = fixture()
        if field == "case_id":
            data["cases"] *= 2
        else:
            data["cases"][0]["artifacts"] *= 2
        with pytest.raises(p.ProtocolInputError):
            p.parse_packet(p.canonical(data), "result")
    data = fixture()
    data["cases"].append(deepcopy(data["cases"][0]) | {"case_id": "other", "outcome": "NATIVE"})
    with pytest.raises(p.ProtocolInputError):
        p.parse_packet(p.canonical(data), "result")


def test_valid_maximum_packet_and_empty_boundary():
    p = protocol()
    data = fixture()
    case = data["cases"][0]
    case["duration_ns"] = 180000000000
    case["assertion_ids"] = [f"a{i:063}" for i in range(64)]
    case["artifacts"] = [{"alias": f"a{i:063}", "sha256": "a" * 64} for i in range(64)]
    data["cases"] = [deepcopy(case) | {"case_id": f"c{i:063}"} for i in range(64)]
    assert len(p.packet_bytes(p.parse_packet(p.canonical(data), "result"))) <= p.PACKET_BYTES
    for cases in ([], data["cases"] + [case]):
        with pytest.raises(p.ProtocolInputError):
            p.parse_packet(p.canonical(data | {"cases": cases}), "result")


@pytest.mark.parametrize("kind", ["run", "result"])
def test_duplicate_member_cannot_be_hidden_by_later_valid_value(kind):
    p = protocol()
    raw = p.canonical(fixture(kind)).replace(
        b'"qualification_pass":false', b'"qualification_pass":true,"qualification_pass":false',
    )
    # Without the duplicate-member guard, JSON's last-value rule makes this
    # otherwise-valid packet pass every model/schema check.
    assert json.loads(raw) == fixture(kind)
    with pytest.raises(p.ProtocolInputError):
        p.parse_packet(raw, kind)


@pytest.mark.parametrize("raw", [b'{"x":NaN}',
                                     b'{"x":Infinity}', b'"text"', b'\xff', b'[' * 2000])
def test_malformed_json_refuses_with_input_free_error(raw):
    p = protocol()
    with pytest.raises(p.ProtocolInputError) as exc:
        p.parse_packet(raw, "result")
    assert str(exc.value) == "invalid offline protocol input"


def test_models_are_revalidated_on_serialization_and_no_io(monkeypatch):
    p = protocol()
    model = p.parse_packet(p.canonical(fixture()), "result")
    for changed in ({"qualification_pass": True}, {"qualification_pass": 0}):
        with pytest.raises(p.ProtocolInputError):
            p.packet_bytes(model.model_copy(update=changed))
    model.cases[0].artifacts.append(model.cases[0].artifacts[0])
    with pytest.raises(p.ProtocolInputError):
        p.packet_bytes(model)
    with pytest.raises(ValidationError):
        model.qualification_pass = True
    import builtins
    import socket
    import sqlite3

    def forbidden(*args, **kwargs):
        pytest.fail("offline protocol attempted I/O")

    for owner, name in [(builtins, "open"), (Path, "open"),
                        (socket, "socket"), (sqlite3, "connect")]:
        monkeypatch.setattr(owner, name, forbidden)
    assert p.parse_packet(p.canonical(fixture()), "result").qualification_pass is False
