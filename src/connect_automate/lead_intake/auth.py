"""Pure source authentication, not enrollment, replay prevention or admission.

Trust and the UTC clock must come from the local host, never the source request.
A result is a point-in-time assertion; later writes must coordinate current trust
and time with their commit. No filesystem, network, logging or key custody here.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from pydantic import BeforeValidator, Field, model_validator

from ..entitlement import UuidV4, verify_signature
from .source import (
    Digest,
    Instant,
    Opaque,
    Revision,
    SourceInputError,
    UntrustedSource,
    _Closed,
    _validate_source,
    parse_untrusted_source,
    payload_digest,
)

SIGNING_CONTEXT = "connect-lead-source-auth-v1"


class SourceAuthenticationError(ValueError):
    """Fixed, input-free rejection; does not reveal whether any grant exists."""

    def __init__(self):
        super().__init__("lead source authentication rejected")


def _sequence(value: object) -> tuple:
    # Copy mutable input before validation; sets would hide duplicate records.
    if type(value) not in (list, tuple):
        raise ValueError("expected sequence")
    return tuple(value)


Mailbox = Annotated[tuple[Opaque, Opaque, Digest], BeforeValidator(_sequence)]
PolicyRef = Annotated[tuple[UuidV4, Revision], BeforeValidator(_sequence)]


class SourceKeyGrant(_Closed):
    key_id: UuidV4
    namespace_id: UuidV4
    public_key: Annotated[bytes, Field(min_length=32, max_length=32, repr=False)]
    status: Literal["active", "revoked"]
    valid_from: Instant
    valid_until: Instant
    mailboxes: Annotated[tuple[Mailbox, ...], BeforeValidator(_sequence), Field(min_length=1)]
    retention_policies: Annotated[
        tuple[PolicyRef, ...], BeforeValidator(_sequence), Field(min_length=1)
    ]

    @model_validator(mode="after")
    def _grant_integrity(self):
        if self.valid_from >= self.valid_until:
            raise ValueError("empty key validity interval")
        if len(set(self.mailboxes)) != len(self.mailboxes):
            raise ValueError("duplicate mailbox scope")
        if len(set(self.retention_policies)) != len(self.retention_policies):
            raise ValueError("duplicate policy scope")
        return self


class SourceRetentionPolicy(_Closed):
    policy_id: UuidV4
    policy_version: Revision
    max_recovery_seconds: Revision


class SourceTrustSnapshot(_Closed):
    """Locally supplied authority, copied and revalidated on every authentication.

    This model cannot enforce cross-snapshot monotonic publication or enrollment.
    The later administrative owner must enforce those durable invariants.
    """

    version: Literal["1.0"]
    host_id: UuidV4
    organization_id: UuidV4
    generation: Revision
    key_grants: Annotated[tuple[SourceKeyGrant, ...], BeforeValidator(_sequence)]
    retention_policies: Annotated[tuple[SourceRetentionPolicy, ...], BeforeValidator(_sequence)]

    @model_validator(mode="after")
    def _snapshot_integrity(self):
        if len({grant.key_id for grant in self.key_grants}) != len(self.key_grants):
            raise ValueError("duplicate key identifier")
        if len({grant.public_key for grant in self.key_grants}) != len(self.key_grants):
            raise ValueError("duplicate public key")
        policies = {(policy.policy_id, policy.policy_version) for policy in self.retention_policies}
        if len(policies) != len(self.retention_policies):
            raise ValueError("duplicate retention policy")
        if any(
            ref not in policies for grant in self.key_grants for ref in grant.retention_policies
        ):
            raise ValueError("dangling policy scope")
        return self


@dataclass(frozen=True, slots=True)
class AuthenticatedSource:
    """In-process result, not an unforgeable object or permission for a later write."""

    source: UntrustedSource = field(repr=False)
    payload_digest: str
    host_id: str
    organization_id: str
    namespace_id: str
    key_id: str
    trust_generation: int
    policy_id: str
    policy_version: int
    verified_at: datetime
    valid_until: datetime


def source_signing_bytes(source: UntrustedSource) -> bytes:
    """Validated signing preimage; malformed models raise SourceInputError.

    Consume a fresh snapshot from the existing source validation owner,
    not attributes of a caller-constructed or copied model. Only the payload is
    hashed; host and key are bound here from that same snapshot.
    """
    try:
        if not isinstance(source, UntrustedSource):
            raise ValueError("expected parsed source model")
        source, _ = _validate_source(source)
        digest = payload_digest(source)
        return "\n".join(
            [SIGNING_CONTEXT, source.authorization.host_id, source.authorization.key_id, digest]
        ).encode("ascii")
    except (ValueError, TypeError, RecursionError):
        pass
    raise SourceInputError()


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def authenticate_source(
    raw: bytes, *, trust: SourceTrustSnapshot, now: datetime
) -> AuthenticatedSource:
    """Authenticate against current local authority; never lookup or persist a receipt."""
    try:
        if not isinstance(trust, SourceTrustSnapshot):
            raise ValueError("expected local trust snapshot")
        authority = SourceTrustSnapshot.model_validate(trust)
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("expected host UTC clock")
        source = parse_untrusted_source(raw)
        payload, authorization = source.payload, source.authorization
        if authorization.host_id != authority.host_id:
            raise ValueError("receiver mismatch")
        if payload.organization_id != authority.organization_id:
            raise ValueError("organization mismatch")
        grant = next((g for g in authority.key_grants if g.key_id == authorization.key_id), None)
        if grant is None:
            raise ValueError("unknown key")
        if grant.status != "active":
            raise ValueError("revoked key")
        identity = payload.source
        if identity.namespace_id != grant.namespace_id:
            raise ValueError("namespace mismatch")
        # Whole-tuple, code-point comparison. No case folding or normalization.
        mailbox = (identity.provider, identity.account_id, identity.mailbox_identity_key)
        if mailbox not in grant.mailboxes:
            raise ValueError("mailbox scope mismatch")
        retention = payload.retention
        policy_ref = (retention.policy_id, retention.policy_version)
        if policy_ref not in grant.retention_policies:
            raise ValueError("policy scope mismatch")
        policy = next(
            p for p in authority.retention_policies if (p.policy_id, p.policy_version) == policy_ref
        )
        key_start, key_end = _instant(grant.valid_from), _instant(grant.valid_until)
        if now < key_start:
            raise ValueError("key not yet valid")
        if now >= key_end:
            raise ValueError("key expired")
        verify_signature(
            {grant.key_id: grant.public_key},
            authorization.key_id,
            source_signing_bytes(source),
            base64.urlsafe_b64decode(authorization.signature + "=="),
        )
        # Capture <= occurrence < deadline is already enforced by the parser.
        occurred, deadline = _instant(payload.occurred_at), _instant(retention.recovery_deadline)
        if now < occurred:
            raise ValueError("future source")
        if now >= deadline:
            raise ValueError("source expired")
        if deadline - occurred > timedelta(seconds=policy.max_recovery_seconds):
            raise ValueError("recovery window exceeds policy")
        return AuthenticatedSource(
            source=source,
            payload_digest=payload_digest(source),
            host_id=authority.host_id,
            organization_id=authority.organization_id,
            namespace_id=identity.namespace_id,
            key_id=grant.key_id,
            trust_generation=authority.generation,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            verified_at=now,
            valid_until=min(key_end, deadline),
        )
    except (ValueError, TypeError, RecursionError, InvalidSignature):
        pass
    # Release internal exceptions, including decoder/validation input and keys.
    raise SourceAuthenticationError()
