"""Private policy calculation over host-supplied facts, never authentication.

Eligibility is not a credential. No public API consumes these results: a future
protected host must acquire authoritative facts and enforce each operation at its
owner, including revocation and fresh one-use proofs. Supplied snapshots cannot
prove identity, freshness, possession or permission to execute an effect.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, TypeAdapter

from ..entitlement import UuidV4

_Version = Annotated[StrictInt, Field(ge=1, le=2147483647)]


class PolicyInputError(ValueError):
    """Fixed, input-free failure at the evaluator boundary."""

    def __init__(self):
        super().__init__("invalid host policy input")


class _Closed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


class DeploymentScope(_Closed):
    host_id: UuidV4
    organization_id: UuidV4


class PolicyRequest(DeploymentScope):
    version: Literal["1.0"]
    operation: Annotated[StrictStr, Field(min_length=1)]
    record_id: UuidV4 | None


class HumanPolicyFacts(DeploymentScope):
    kind: Literal["human"]
    employee_id: UuidV4
    enrollment: Literal["active", "disabled"]
    role: Literal["admin", "user"]
    session: Literal["active", "locked", "expired", "revoked"]
    observed_authority_version: _Version
    current_authority_version: _Version


class MachinePolicyFacts(DeploymentScope):
    kind: Literal["machine"]
    machine_id: UuidV4


class RecordAccessFacts(DeploymentScope):
    record_id: UuidV4
    employee_id: UuidV4
    read_assigned: bool
    observed_grant_version: _Version
    current_grant_version: _Version


class _Denied(_Closed):
    status: Literal["policy_denied"]
    reason: Literal["policy_mismatch"]


class _Eligible(_Closed):
    status: Literal["policy_eligible"]
    reason: Literal["policy_match"]
    enforcement: Literal["session_record_read", "fresh_admin_effect"]


_Actor = Annotated[HumanPolicyFacts | MachinePolicyFacts, Field(discriminator="kind")]
_ACTOR = TypeAdapter(_Actor)
_READS = frozenset(("source.content.read", "source.outcome.read"))
_ADMIN_EFFECTS = frozenset(
    (
        "source.authority.publish",
        "source.clock.reconcile",
        "source.message.purge",
        "source.namespace.retire",
    )
)


def _same_scope(left: DeploymentScope, right: DeploymentScope) -> bool:
    return left.host_id == right.host_id and left.organization_id == right.organization_id


def evaluate_policy(
    *, request: object, deployment: object, actor: object, resource: object = None
) -> _Denied | _Eligible:
    """Evaluate validated facts; do not authenticate them or execute their request.

    Dicts and model instances are accepted for internal host composition only.
    Every call revalidates them, even for an unsupported operation or machine.
    No clock/state reader exists here, so version comparisons are snapshot logic.
    """
    try:
        req = PolicyRequest.model_validate(request)
        scope = DeploymentScope.model_validate(deployment)
        principal = _ACTOR.validate_python(actor)
        access = None if resource is None else RecordAccessFacts.model_validate(resource)
    except (ValueError, TypeError):
        # Raise outside the handler so neither cause nor context retains input.
        pass
    else:
        return _evaluate(req, scope, principal, access)
    raise PolicyInputError()


def _evaluate(
    request: PolicyRequest,
    deployment: DeploymentScope,
    actor: HumanPolicyFacts | MachinePolicyFacts,
    resource: RecordAccessFacts | None,
) -> _Denied | _Eligible:
    denied = _Denied(status="policy_denied", reason="policy_mismatch")
    if not _same_scope(request, deployment) or not _same_scope(actor, deployment):
        return denied
    if not isinstance(actor, HumanPolicyFacts):
        return denied
    if (
        actor.enrollment != "active"
        or actor.session != "active"
        or actor.observed_authority_version != actor.current_authority_version
    ):
        return denied
    if request.operation in _READS:
        if (
            resource is None
            or not _same_scope(resource, deployment)
            or resource.record_id != request.record_id
            or resource.employee_id != actor.employee_id
            or not resource.read_assigned
            or resource.observed_grant_version != resource.current_grant_version
        ):
            return denied
        return _Eligible(
            status="policy_eligible", reason="policy_match", enforcement="session_record_read"
        )
    if (
        request.operation in _ADMIN_EFFECTS
        and actor.role == "admin"
        and request.record_id is None
        and resource is None
    ):
        return _Eligible(
            status="policy_eligible", reason="policy_match", enforcement="fresh_admin_effect"
        )
    return denied
