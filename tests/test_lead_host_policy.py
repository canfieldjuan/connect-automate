"""Synthetic policy facts only: no credential, revocation or native-identity proof."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from connect_automate.lead_intake._host_policy import (
    DeploymentScope,
    HumanPolicyFacts,
    MachinePolicyFacts,
    PolicyInputError,
    PolicyRequest,
    RecordAccessFacts,
    evaluate_policy,
)

HOST = "00000000-0000-4000-8000-000000000001"
ORG = "00000000-0000-4000-8000-000000000002"
EMPLOYEE = "00000000-0000-4000-8000-000000000003"
RECORD = "00000000-0000-4000-8000-000000000004"
OTHER = "00000000-0000-4000-8000-000000000005"
READS = ("source.content.read", "source.outcome.read")
EFFECTS = (
    "source.authority.publish",
    "source.clock.reconcile",
    "source.message.purge",
    "source.namespace.retire",
)
DENIED = {"status": "policy_denied", "reason": "policy_mismatch"}


def facts(operation=READS[0], role="user"):
    scope = {"host_id": HOST, "organization_id": ORG}
    return {
        "deployment": dict(scope),
        "request": {
            **scope,
            "version": "1.0",
            "operation": operation,
            "record_id": RECORD if operation in READS else None,
        },
        "actor": {
            **scope,
            "kind": "human",
            "employee_id": EMPLOYEE,
            "enrollment": "active",
            "role": role,
            "session": "active",
            "observed_authority_version": 1,
            "current_authority_version": 1,
        },
        "resource": {
            **scope,
            "record_id": RECORD,
            "employee_id": EMPLOYEE,
            "read_assigned": True,
            "observed_grant_version": 1,
            "current_grant_version": 1,
        }
        if operation in READS
        else None,
    }


def machine():
    return {"kind": "machine", "host_id": HOST, "organization_id": ORG, "machine_id": OTHER}


def eligible(enforcement):
    return {
        "status": "policy_eligible",
        "reason": "policy_match",
        "enforcement": enforcement,
    }


@pytest.mark.parametrize("operation", READS + EFFECTS)
@pytest.mark.parametrize("role", ("admin", "user", "machine"))
def test_operation_actor_matrix(operation, role):
    value = facts(operation, role if role != "machine" else "user")
    if role == "machine":
        value["actor"] = machine()
    expected = DENIED
    if role != "machine" and (operation in READS or role == "admin"):
        expected = eligible("session_record_read" if operation in READS else "fresh_admin_effect")
    assert evaluate_policy(**value).model_dump() == expected


@pytest.mark.parametrize("operation", READS + EFFECTS)
@pytest.mark.parametrize("owner", ("request", "deployment", "actor"))
@pytest.mark.parametrize("field", ("host_id", "organization_id"))
def test_scope_mismatch_alone_denies(operation, owner, field):
    value = facts(operation, "admin")
    assert evaluate_policy(**value).status == "policy_eligible"
    value[owner][field] = OTHER
    assert evaluate_policy(**value).model_dump() == DENIED


@pytest.mark.parametrize("operation", READS + EFFECTS)
@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("enrollment", "disabled"),
        ("session", "locked"),
        ("session", "expired"),
        ("session", "revoked"),
        ("observed_authority_version", 2),
        ("current_authority_version", 2),
    ],
)
def test_human_authority_guard_alone_denies(operation, field, replacement):
    value = facts(operation, "admin")
    assert evaluate_policy(**value).status == "policy_eligible"
    value["actor"][field] = replacement
    assert evaluate_policy(**value).model_dump() == DENIED


@pytest.mark.parametrize("operation", READS)
@pytest.mark.parametrize("role", ("admin", "user"))
@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("host_id", OTHER),
        ("organization_id", OTHER),
        ("record_id", OTHER),
        ("employee_id", OTHER),
        ("read_assigned", False),
        ("observed_grant_version", 2),
        ("current_grant_version", 2),
    ],
)
def test_record_guard_alone_denies(operation, role, field, replacement):
    value = facts(operation, role)
    assert evaluate_policy(**value).status == "policy_eligible"
    value["resource"][field] = replacement
    assert evaluate_policy(**value).model_dump() == DENIED


@pytest.mark.parametrize("operation", READS)
@pytest.mark.parametrize("role", ("admin", "user"))
@pytest.mark.parametrize("missing", ("record_id", "resource"))
def test_unassigned_read_has_no_admin_bypass(operation, role, missing):
    value = facts(operation, role)
    if missing == "resource":
        value.pop("resource")
    else:
        value["request"]["record_id"] = None
    assert evaluate_policy(**value).model_dump() == DENIED


@pytest.mark.parametrize("operation", EFFECTS)
@pytest.mark.parametrize("stray", ("record_id", "resource"))
def test_admin_effect_refuses_stray_record_context(operation, stray):
    value = facts(operation, "admin")
    if stray == "resource":
        value["resource"] = facts()["resource"]
    else:
        value["request"]["record_id"] = RECORD
    assert evaluate_policy(**value).model_dump() == DENIED


@pytest.mark.parametrize(
    "operation",
    (
        "lead.approve",
        "export",
        "employee.enroll",
        "policy.edit",
        "source.submit",
        "source.resume",
        "source.status",
        "SOURCE.CONTENT.READ",
        "source.content.read ",
    ),
)
@pytest.mark.parametrize("actor", ("admin", "user", "machine"))
def test_unsupported_operation_denies(operation, actor):
    value = facts(operation, actor if actor != "machine" else "user")
    if actor == "machine":
        value["actor"] = machine()
    assert evaluate_policy(**value).model_dump() == DENIED


MODELS = {
    "deployment": DeploymentScope,
    "request": PolicyRequest,
    "actor": HumanPolicyFacts,
    "resource": RecordAccessFacts,
}
FIELDS = [(owner, field) for owner, data in facts().items() for field in data]


@pytest.mark.parametrize(("owner", "field"), FIELDS)
def test_every_required_field_missing_is_invalid(owner, field):
    value = facts()
    del value[owner][field]
    with pytest.raises(PolicyInputError, match="^invalid host policy input$"):
        evaluate_policy(**value)


@pytest.mark.parametrize("owner", MODELS)
def test_extra_field_is_invalid_even_on_constructed_models(owner):
    value = facts()
    model = MODELS[owner].model_validate(value[owner])
    # model_copy bypasses validation; evaluation must not trust that instance.
    value[owner] = model.model_copy(update={"secret_extra": "private narrative"})
    with pytest.raises(PolicyInputError) as error:
        evaluate_policy(**value)
    assert str(error.value) == "invalid host policy input"
    assert error.value.__context__ is None


FALSY_CASES = [
    pytest.param(owner, field, replacement, id=f"{owner}-{field}-{label}")
    for owner, field in FIELDS
    for label, replacement in (
        ("null", None),
        ("empty", ""),
        ("zero", 0),
        ("false", False),
        ("list", []),
        ("dict", {}),
    )
    if not (owner == "request" and field == "record_id" and replacement is None)
    and not (owner == "resource" and field == "read_assigned" and replacement is False)
]


@pytest.mark.parametrize(("owner", "field", "replacement"), FALSY_CASES)
def test_wrong_types_and_falsy_values_fail_closed(owner, field, replacement):
    value = facts()
    value[owner][field] = replacement
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


VERSIONS = (
    ("actor", "observed_authority_version"),
    ("actor", "current_authority_version"),
    ("resource", "observed_grant_version"),
    ("resource", "current_grant_version"),
)


@pytest.mark.parametrize(("owner", "field"), VERSIONS)
@pytest.mark.parametrize("replacement", (-1, 2147483648, True, 1.0, "1"))
def test_version_bounds_and_coercion(owner, field, replacement):
    value = facts()
    value[owner][field] = replacement
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


@pytest.mark.parametrize("version", (1, 2147483647))
def test_matching_version_boundaries_are_eligible(version):
    value = facts()
    for owner, field in VERSIONS:
        value[owner][field] = version
    assert evaluate_policy(**value).model_dump() == eligible("session_record_read")


@pytest.mark.parametrize(("owner", "field"), FIELDS)
def test_constructed_model_missing_field_revalidated(owner, field):
    value = facts()
    del value[owner][field]
    value[owner] = MODELS[owner].model_construct(**value[owner])
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


@pytest.mark.parametrize("field", ("role", "session", "employee_id"))
def test_machine_cannot_carry_human_fields(field):
    value = facts()
    value["actor"] = {**machine(), field: facts()["actor"][field]}
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


def test_machine_instance_is_also_revalidated():
    value = facts()
    value["actor"] = MachinePolicyFacts.model_construct(**{**machine(), "host_id": "bad"})
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


@pytest.mark.parametrize("field", tuple(machine()))
def test_machine_required_fields_are_validated(field):
    value = facts()
    value["actor"] = machine()
    del value["actor"][field]
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


@pytest.mark.parametrize("operation", (READS[0], "unsupported"))
def test_all_context_is_validated_even_for_denied_machine(operation):
    value = facts(operation)
    value["actor"] = machine()
    value["resource"] = {**facts()["resource"], "read_assigned": "false"}
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


@pytest.mark.parametrize(
    ("owner", "field", "replacement"),
    [
        ("request", "version", "2.0"),
        ("actor", "kind", "service"),
        ("actor", "role", "owner"),
        ("actor", "enrollment", "unknown"),
        ("actor", "session", "unknown"),
        ("request", "host_id", "ABCDEF00-0000-4000-8000-000000000001"),
        ("request", "host_id", "00000000-0000-1000-8000-000000000001"),
    ],
)
def test_unsupported_vocabulary_and_noncanonical_identity(owner, field, replacement):
    value = facts()
    value[owner][field] = replacement
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)


def test_valid_models_and_results_are_immutable_and_not_credentials():
    value = {owner: MODELS[owner].model_validate(data) for owner, data in facts().items()}
    result = evaluate_policy(**value)
    assert result.model_dump() == eligible("session_record_read")
    for model in (*value.values(), result):
        field = next(iter(type(model).model_fields))
        with pytest.raises(ValidationError):
            setattr(model, field, "changed")
    for owner in value:
        copied = dict(value)
        copied[owner] = result.model_copy()
        with pytest.raises(PolicyInputError):
            evaluate_policy(**copied)


def test_deterministic_without_io_or_input_mutation(monkeypatch):
    import builtins
    import socket
    import sqlite3
    from pathlib import Path

    def forbidden(*args, **kwargs):
        pytest.fail("policy evaluation attempted I/O")

    value = facts()
    before = deepcopy(value)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        first = evaluate_policy(**value)
        second = evaluate_policy(**value)
    assert first == second
    assert value == before


def test_serialized_context_is_not_accepted():
    import json

    value = facts()
    value["actor"] = json.dumps(value["actor"])
    with pytest.raises(PolicyInputError):
        evaluate_policy(**value)
