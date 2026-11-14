"""Closed synthetic evidence and command values, not a licensing API."""

from typing import Annotated, Literal

from pydantic import Field, StrictInt, TypeAdapter, model_validator

from qualification.owner_authority.protocol import (
    Closed,
    ConsumeBinding,
    Digest,
    FalseOnly,
    Instant,
    UuidV4,
)

Revision = Annotated[StrictInt, Field(ge=1, le=9223372036854775807)]


class CommandBase(Closed):
    version: Literal["offline-register/1"]
    operation_id: UuidV4
    epoch: UuidV4
    record_id: UuidV4


class CreateCommand(CommandBase):
    command: Literal["grant", "enroll", "issuance", "associate", "consume"]
    proof_id: UuidV4
    expected_revision: None = None


class WithdrawCommand(CommandBase):
    command: Literal["withdraw_grant", "withdraw_enrollment", "withdraw_association"]
    proof_id: None = None
    expected_revision: Revision


Command = TypeAdapter(Annotated[CreateCommand | WithdrawCommand, Field(discriminator="command")])


class Proof(Closed):
    version: Literal["offline-register-evidence/1"]
    evidence_class: Literal["OFFLINE_CONFORMANCE"]
    qualification_pass: FalseOnly
    proof_id: UuidV4
    record_id: UuidV4
    organization_id: UuidV4


class Grant(Proof):
    kind: Literal["GRANT"]
    provenance_ref: UuidV4
    policy_revision: Revision


class Enrollment(Proof):
    kind: Literal["ENROLLMENT"]
    registration_ref: UuidV4
    authority_expires_at: Instant
    required_source_expires_at: Instant | None


class Issuance(Proof):
    kind: Literal["ISSUANCE"]
    grant_id: UuidV4
    envelope_sha256: Digest


class Association(Proof):
    kind: Literal["ASSOCIATION"]
    grant_id: UuidV4
    enrollment_id: UuidV4
    entitlement_id: UuidV4
    verification_ref: UuidV4


class Consumption(Proof):
    kind: Literal["CONSUMPTION"]
    binding: ConsumeBinding
    receipt_sha256: Digest

    @model_validator(mode="after")
    def binding_scope(self):
        if self.binding.organization_id != self.organization_id:
            raise ValueError("consumption scope mismatch")
        return self


Evidence = Annotated[Grant | Enrollment | Issuance | Association | Consumption,
                     Field(discriminator="kind")]
EVIDENCE = TypeAdapter(Evidence)
