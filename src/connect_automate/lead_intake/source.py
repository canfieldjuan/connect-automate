"""Closed source envelope; parsing never authenticates or admits a source.

No mail access, IO, clocks, persistence or inference. Host authentication and
durable admission must precede any effect from these untrusted values.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ..entitlement import UuidV4

MAX_SOURCE_BYTES = 2097152
MAX_BODY_CHARS = 200000
MAX_OPAQUE_BYTES = 256
MAX_DEPTH = 16
MAX_METADATA_COUNT = 9007199254740991


class SourceInputError(ValueError):
    """Input-free error suitable for boundary logs."""

    def __init__(self):
        super().__init__("invalid lead source input")


def _opaque(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value.encode("utf-8")) <= MAX_OPAQUE_BYTES:
        raise ValueError("invalid opaque identifier")
    return value


def _time(value: object) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is None
    ):
        raise ValueError("invalid UTC timestamp")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _signature(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{86}", value) is None:
        raise ValueError("invalid signature encoding")
    decoded = base64.urlsafe_b64decode(value + "==")
    if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != value:
        raise ValueError("noncanonical signature encoding")
    return value


Opaque = Annotated[str, BeforeValidator(_opaque)]
Instant = Annotated[str, BeforeValidator(_time)]
Signature = Annotated[str, BeforeValidator(_signature)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[int, Field(ge=1, le=2147483647)]
Count = Annotated[int, Field(ge=0, le=MAX_METADATA_COUNT)]


class _Closed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


class SourceIdentity(_Closed):
    namespace_id: UuidV4
    provider: Opaque
    account_id: Opaque
    mailbox_identity_key: Digest
    message_id: Opaque


class Trigger(_Closed):
    rule_id: UuidV4
    rule_version: Revision
    admission_kind: Literal["exact_sender"]
    selector_id: Opaque
    input_kind: Literal["message_body"]
    part_id: Literal["body"]


class AvailableBody(_Closed):
    state: Literal["available"]
    text: Annotated[str, Field(max_length=MAX_BODY_CHARS, repr=False)]
    sha256: Digest
    stored_chars: Annotated[int, Field(ge=0, le=MAX_BODY_CHARS)]
    source_chars: Count | None
    completeness: Literal["complete", "truncated", "unknown"]

    @model_validator(mode="after")
    def _integrity(self):
        if self.stored_chars != len(self.text):
            raise ValueError("body length mismatch")
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("body digest mismatch")
        if self.completeness == "complete" and self.source_chars != self.stored_chars:
            raise ValueError("invalid complete body")
        if self.completeness == "truncated" and (
            self.source_chars is None or self.source_chars <= self.stored_chars
        ):
            raise ValueError("invalid truncated body")
        if self.completeness == "unknown" and self.source_chars is not None:
            raise ValueError("invalid unknown body")
        return self


class UnavailableBody(_Closed):
    state: Literal["unavailable"]
    reason: Literal["source_gone", "outside_scope", "retrieval_failed", "not_captured"]


class Attachments(_Closed):
    count: Count | None
    processing: Literal["not_processed"]


class Snapshot(_Closed):
    snapshot_id: UuidV4
    representation: Literal["normalized-text"]
    normalization_version: Opaque
    captured_at: Instant
    body: Annotated[AvailableBody | UnavailableBody, Field(discriminator="state")]
    attachments: Attachments


class Retention(_Closed):
    policy_id: UuidV4
    policy_version: Revision
    recovery_deadline: Instant


class Payload(_Closed):
    schema_name: Literal["lead.source.admission"] = Field(alias="schema")
    schema_version: Literal["1.0"]
    organization_id: UuidV4
    event_id: UuidV4
    watcher_event_id: Digest
    occurred_at: Instant
    source: SourceIdentity
    trigger: Trigger
    snapshot: Snapshot
    retention: Retention

    @model_validator(mode="after")
    def _ordering(self):
        # Fixed-width validated UTC instants have chronological lexical ordering.
        if not self.snapshot.captured_at <= self.occurred_at < self.retention.recovery_deadline:
            raise ValueError("invalid source time ordering")
        return self


class Authorization(_Closed):
    host_id: UuidV4
    key_id: UuidV4
    signature: Signature


class UntrustedSource(_Closed):
    """Syntax-valid only: signature, authority, scope and freshness are unverified."""

    payload: Payload
    authorization: Authorization


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate member")
        result[key] = value
    return result


def _no_number(value):
    raise ValueError("noninteger number")


def _shape(value, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("excess depth")
    if isinstance(value, str):
        value.encode("utf-8")  # Reject lone surrogates, including in opaque identifiers.
    elif isinstance(value, dict):
        for key, item in value.items():
            _shape(key, depth + 1)
            _shape(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 64:
            raise ValueError("excess list length")
        for item in value:
            _shape(item, depth + 1)


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _validate_source(value) -> tuple[UntrustedSource, bytes]:
    """One validation and envelope serialization owner for both public boundaries."""
    _shape(value)
    # Revalidated models expose Python field names (schema_name); raw envelopes
    # must still use wire aliases (schema). Never relax the raw-input contract.
    source = UntrustedSource.model_validate(value, by_name=isinstance(value, UntrustedSource))
    data = source.model_dump(by_alias=True)
    _shape(data)
    wire = _canonical(data)
    if len(wire) > MAX_SOURCE_BYTES:
        raise ValueError("excess canonical size")
    return source, wire


def parse_untrusted_source(raw: bytes) -> UntrustedSource:
    """Validate only. Never log input or mistake success for authenticated admission."""
    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SOURCE_BYTES:
            raise ValueError("invalid envelope size")
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_float=_no_number,
            parse_constant=_no_number,
        )
        source, _ = _validate_source(value)
        return source
    except (ValueError, TypeError, RecursionError):
        pass
    # Leaving the handler releases the internal exception instead of merely
    # suppressing its printed traceback. Caller-owned frames are not erased.
    raise SourceInputError()


def _encode_source(source: UntrustedSource, *, payload_only: bool) -> bytes:
    try:
        if not isinstance(source, UntrustedSource):
            raise ValueError("expected parsed source model")
        validated, wire = _validate_source(source)
        return _canonical(validated.payload.model_dump(by_alias=True)) if payload_only else wire
    except (ValueError, TypeError, RecursionError):
        pass
    raise SourceInputError()


def canonical_source(source: UntrustedSource) -> bytes:
    """Validated compact UTF-8 envelope for senders; not a signature or admission."""
    return _encode_source(source, payload_only=False)


def canonical_payload(source: UntrustedSource) -> bytes:
    """Canonical payload only. Not a signing preimage or authorization proof."""
    return _encode_source(source, payload_only=True)


def payload_digest(source: UntrustedSource) -> str:
    """Business payload digest is independent of signature/key rotation."""
    return hashlib.sha256(canonical_payload(source)).hexdigest()
