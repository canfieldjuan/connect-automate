"""Offline register input boundary; no production authority."""

import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1]))
r = importlib.import_module("qualification.licensing_register.protocol")


def uid(n):
    return f"{n:08x}-1111-4111-8111-111111111111"


def command(**changes):
    return dict(version="offline-register/1", command="grant", operation_id=uid(1),
                epoch=uid(2), record_id=uid(3), proof_id=uid(4)) | changes


def test_register_command_is_closed():
    assert r.Command.validate_python(command()).command == "grant"
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(verified=True))


@pytest.mark.parametrize("value", [0, -1, True, False, "", "1"])
def test_invalid_revisions_do_not_default(value):
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(command="withdraw_grant", proof_id=None,
                                         expected_revision=value))


def test_create_and_withdraw_branches():
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(expected_revision=1))
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(command="withdraw_grant", proof_id=None))
    assert r.Command.validate_python(command(command="withdraw_grant", proof_id=None,
                                            expected_revision=1)).expected_revision == 1


@pytest.mark.parametrize("value", [None, 0, -1, True, False, "", "1", 2**63])
def test_change_revision_fields_are_strict(value):
    for kind in ("begin_change", "finish_change"):
        c = command(command=kind, expected_revision=value, change_id=uid(5))
        c.update(proof_id=None, reason="SOURCE_UPDATED") if kind == "begin_change" else c.update(
            decision_id=uid(6))
        with pytest.raises(ValidationError):
            r.Command.validate_python(c)


def test_change_branches_are_closed_and_positive_boundaries_pass():
    b = command(command="begin_change", proof_id=None, expected_revision=1,
                change_id=uid(5), reason="SOURCE_UPDATED")
    f = command(command="finish_change", expected_revision=2**63-1,
                change_id=uid(5), decision_id=uid(6))
    assert r.Command.validate_python(b).expected_revision == 1
    assert r.Command.validate_python(f).expected_revision == 2**63-1
    for c in (b | {"decision_id": uid(6)}, b | {"reason": "INITIAL"}, b | {"verified": True},
              f | {"reason": "SOURCE_UPDATED"}, f | {"actor": uid(7)},
              {k: v for k, v in f.items() if k != "decision_id"}):
        with pytest.raises(ValidationError):
            r.Command.validate_python(c)


@pytest.mark.parametrize("value", [None, 0, -1, True, False, "", "1", 2**63])
def test_completion_revision_fields_are_strict(value):
    p = dict(version="offline-register-evidence/1", evidence_class="OFFLINE_CONFORMANCE",
        qualification_pass=False, proof_id=uid(1), record_id=uid(2), organization_id=uid(3),
        kind="ENROLLMENT_COMPLETION", change_id=uid(4), pending_revision=1,
        decision_proof_id=uid(5), decision_sha256="a" * 64, registration_ref=uid(6),
        private_revision=1, private_sha256="b" * 64)
    assert r.EVIDENCE.validate_python(p).pending_revision == 1
    for field in ("pending_revision", "private_revision"):
        with pytest.raises(ValidationError):
            r.EVIDENCE.validate_python(p | {field: value})


@pytest.mark.parametrize("value", [None, 0, -1, True, False, "", "1", 2**63])
def test_correction_revision_branches_are_strict(value):
    c = command(command="correct_association", expected_revision=value)
    with pytest.raises(ValidationError):
        r.Command.validate_python(c)
    proof = dict(version="offline-register-evidence/1", evidence_class="OFFLINE_CONFORMANCE",
        qualification_pass=False, proof_id=uid(1), record_id=uid(2), organization_id=uid(3),
        kind="ASSOCIATION_CORRECTION", expected_revision=1, entitlement_id=uid(4),
        grant_id=uid(5), grant_revision=1, enrollment_id=uid(6), enrollment_revision=1,
        verification_ref=uid(7))
    for field in ("expected_revision", "grant_revision", "enrollment_revision"):
        with pytest.raises(ValidationError):
            r.EVIDENCE.validate_python(proof | {field: value})
    for field in ("proof_id", "record_id", "entitlement_id", "verification_ref"):
        with pytest.raises(ValidationError):
            r.EVIDENCE.validate_python(proof | {field: "not-a-uuid"})
    assert r.EVIDENCE.validate_python(proof).expected_revision == 1


def test_correction_closed_fields_and_positive_boundaries():
    c = command(command="correct_association", expected_revision=1)
    assert r.Command.validate_python(c).expected_revision == 1
    largest = r.Command.validate_python(c | {"expected_revision": 2**63-1})
    assert largest.expected_revision == 2**63-1
    for extra in ({"expected_revision": None}, {"proof_id": None}, {"reason": "RECORD_CORRECTION"},
                  {"actor": uid(8)}, {"verified": True}, {"organization_id": uid(9)}):
        with pytest.raises(ValidationError):
            r.Command.validate_python(c | extra)
