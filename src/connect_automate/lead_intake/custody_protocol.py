"""Private R1 value vocabulary, NOT a receiver or an authentication boundary.

Every value remains untrusted. No IO, clock reads, signatures, admission, or
durability. Upload metadata is separate from the unchanged source artifact;
this private representation is not the future machine-proof wire contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from ..entitlement import UuidV4
from .receipts import ReceiptReference
from .results import SourceHandoffLookup
from .source import (
    MAX_SOURCE_BYTES,
    Digest,
    Instant,
    Opaque,
    Revision,
    SourceIdentity,
    UntrustedSource,
    _canonical,
    _Closed,
    _no_number,
    _shape,
    _unique,
    canonical_source,
    parse_untrusted_source,
    payload_digest,
)

MAX_RESULT_BYTES = 4096
CONTROL_MEDIA_TYPE = "application/vnd.local-connect.lead-custody-control+json"
RESULT_MEDIA_TYPE = "application/vnd.local-connect.lead-custody-result+json"


class CustodyInputError(ValueError):
    """Input-free error; internal validation errors must not cross this boundary."""

    def __init__(self):
        super().__init__("invalid custody protocol input")


class RouteReference(_Closed):
    provider_app_id: Opaque
    provider_instance_id: UuidV4
    provider_app_version: Opaque
    capability_id: Literal["lead.source.custody"]
    capability_version: Literal["1.0"]
    pack_id: UuidV4
    pack_version: Revision
    binding: Opaque


class ScopeReference(_Closed):
    host_id: UuidV4
    organization_id: UuidV4
    namespace_id: UuidV4
    event_id: UuidV4
    route_digest: Digest


class CaptureReference(_Closed):
    envelope_sha256: Digest
    payload_digest: Digest
    snapshot_id: UuidV4
    captured_at: Instant
    recovery_deadline: Instant
    artifact_size: Annotated[int, Field(ge=1, le=MAX_SOURCE_BYTES)]

    @model_validator(mode="after")
    def _window(self):
        if self.captured_at >= self.recovery_deadline:
            raise ValueError("invalid capture interval")
        return self


class PrepareIntent(_Closed):
    source: SourceIdentity
    watcher_event_id: Digest
    rule_id: UuidV4
    rule_version: Revision
    policy_id: UuidV4
    policy_version: Revision
    route: RouteReference


class OptionalCapture(_Closed):
    capture: CaptureReference | None


class RequiredCapture(_Closed):
    capture: CaptureReference


class _Request(_Closed):
    schema_version: Literal["1.0"]
    handoff_id: UuidV4
    control_id: UuidV4
    job_id: UuidV4
    scope: ScopeReference
    enrolled_machine_id: UuidV4
    # Opaque reference only; no credential/proof bytes or trusted actor claims.
    proof_reference: UuidV4 = Field(repr=False)


class PrepareRequest(_Request):
    operation: Literal["prepare"]
    expected_fence_generation: None
    payload: PrepareIntent

    @model_validator(mode="after")
    def _intent_binding(self):
        if self.scope.namespace_id != self.payload.source.namespace_id:
            raise ValueError("intent namespace mismatch")
        digest = hashlib.sha256(_canonical(self.payload.route.model_dump())).hexdigest()
        if self.scope.route_digest != digest:
            raise ValueError("intent route mismatch")
        return self


class UploadRequest(_Request):
    operation: Literal["upload"]
    expected_fence_generation: Revision
    payload: RequiredCapture


class StatusRequest(_Request):
    operation: Literal["status"]
    expected_fence_generation: Revision
    payload: OptionalCapture


class ResumeRequest(_Request):
    operation: Literal["resume"]
    expected_fence_generation: Revision
    payload: RequiredCapture


class SettleRequest(_Request):
    operation: Literal["settle"]
    expected_fence_generation: Revision
    payload: OptionalCapture


_REQUEST_TYPES = (PrepareRequest, UploadRequest, StatusRequest, ResumeRequest, SettleRequest)
_REQUEST = TypeAdapter(
    Annotated[
        PrepareRequest | UploadRequest | StatusRequest | ResumeRequest | SettleRequest,
        Field(discriminator="operation"),
    ]
)


class UnresolvedResult(_Closed):
    schema_version: Literal["1.0"]
    status: Literal["unresolved"]
    handoff_id: UuidV4
    code: Literal["unknown", "not_found", "refused", "conflict"]


class ResolvedResult(_Closed):
    schema_version: Literal["1.0"]
    status: Literal["resolved"]
    handoff_id: UuidV4
    scope: ScopeReference
    state_revision: Revision
    fence_generation: Revision
    observed_at: Instant
    reservation_expires_at: Instant | None
    capture: CaptureReference | None
    capture_phase: Literal["prepared", "upload_possible", "custodied", "fenced_empty"]
    content_state: Literal["not_received", "retained", "unavailable", "unknown"]
    unavailable_reason: Literal["expired", "purged", "retired", "lost"] | None
    workflow: SourceHandoffLookup | None
    source_receipt: ReceiptReference | None
    reason: Literal[
        "ready",
        "pending",
        "custody_confirmed",
        "workflow_known",
        "capture_lost",
        "capture_cancelled",
        "content_unavailable",
    ]

    @model_validator(mode="after")
    def _capture_metadata(self):
        phase = self.capture_phase
        if phase == "prepared" and self.capture is not None:
            raise ValueError("prepared capture present")
        if phase in ("upload_possible", "custodied") and self.capture is None:
            raise ValueError("required capture absent")
        if self.capture is not None and self.capture.captured_at > self.observed_at:
            raise ValueError("capture after observation")
        if phase == "prepared":
            if self.reservation_expires_at is None:
                raise ValueError("reservation absent")
            if self.reservation_expires_at <= self.observed_at:
                raise ValueError("reservation not ready")
        elif self.reservation_expires_at is not None:
            raise ValueError("unexpected reservation")
        return self

    @model_validator(mode="after")
    def _combination(self):
        if (self.content_state == "unavailable") != (self.unavailable_reason is not None):
            raise ValueError("unavailable reason mismatch")
        outcome = self.workflow.workflow_outcome if self.workflow is not None else None
        if self.capture_phase == "prepared":
            valid = (self.content_state, outcome, self.reason) == ("not_received", None, "ready")
        elif self.capture_phase == "upload_possible":
            valid = (self.content_state, outcome, self.reason) == ("unknown", None, "pending")
        elif self.capture_phase == "fenced_empty":
            valid = (
                self.content_state == "not_received"
                and outcome is None
                and self.reason in ("capture_lost", "capture_cancelled")
            )
        elif outcome in ("accepted", "no_match"):
            valid = (
                self.content_state in ("retained", "unavailable", "unknown")
                and self.reason == "workflow_known"
            )
        else:
            valid = (self.content_state, self.reason) in (
                ("retained", "custody_confirmed"),
                ("unavailable", "content_unavailable"),
            )
        if not valid:
            raise ValueError("illegal custody combination")
        return self

    @model_validator(mode="after")
    def _receipt_binding(self):
        if (self.capture_phase == "custodied") != (self.source_receipt is not None):
            raise ValueError("receipt presence mismatch")
        receipt = self.source_receipt
        if receipt is not None:
            for name in ("host_id", "organization_id", "namespace_id", "event_id"):
                if getattr(receipt, name) != getattr(self.scope, name):
                    raise ValueError("receipt scope mismatch")
            if receipt.payload_digest != self.capture.payload_digest:
                raise ValueError("receipt digest mismatch")
            if receipt.recovery_deadline != self.capture.recovery_deadline:
                raise ValueError("receipt deadline mismatch")
            if not (
                datetime.fromisoformat(self.capture.captured_at)
                <= datetime.fromisoformat(receipt.accepted_at)
                <= datetime.fromisoformat(self.observed_at)
            ):
                raise ValueError("receipt time mismatch")
        if (
            self.workflow is not None
            and self.workflow.source_receipt is not None
            and self.workflow.source_receipt != receipt
        ):
            raise ValueError("workflow receipt mismatch")
        return self

    @model_validator(mode="after")
    def _size(self):
        if len(_canonical(self.model_dump(by_alias=True))) > MAX_RESULT_BYTES:
            raise ValueError("result byte limit")
        return self


_RESULT_TYPES = (ResolvedResult, UnresolvedResult)
_RESULT = TypeAdapter(Annotated[ResolvedResult | UnresolvedResult, Field(discriminator="status")])


def _validate(adapter, value, limit):
    _shape(value)
    parsed = adapter.validate_python(value, by_name=isinstance(value, _Closed))
    data = parsed.model_dump(by_alias=True)
    _shape(data)
    wire = _canonical(data)
    if len(wire) > limit:
        raise ValueError("canonical byte limit")
    return parsed, wire


def _parse(raw, adapter, limit):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= limit:
            raise ValueError("input byte limit")
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_float=_no_number,
            parse_constant=_no_number,
        )
        return _validate(adapter, value, limit)[0]
    except (ValueError, TypeError, RecursionError):
        pass
    raise CustodyInputError()


def _encode(value, adapter, types, limit):
    try:
        if type(value) not in types:
            raise ValueError("expected untrusted custody model")
        return _validate(adapter, value, limit)[1]
    except (ValueError, TypeError, RecursionError):
        pass
    raise CustodyInputError()


def parse_untrusted_request(raw: bytes):
    """Private metadata syntax only; upload source bytes are a separate artifact."""
    return _parse(raw, _REQUEST, MAX_SOURCE_BYTES)


def canonical_request(value) -> bytes:
    return _encode(value, _REQUEST, _REQUEST_TYPES, MAX_SOURCE_BYTES)


def parse_untrusted_result(raw: bytes):
    """Validate a claim, not evidence that its claimed state ever existed."""
    return _parse(raw, _RESULT, MAX_RESULT_BYTES)


def canonical_result(value) -> bytes:
    return _encode(value, _RESULT, _RESULT_TYPES, MAX_RESULT_BYTES)


def _match_upload(upload, prepared, source, raw):
    if (
        upload.handoff_id != prepared.handoff_id
        or upload.scope != prepared.scope
        or upload.enrolled_machine_id != prepared.enrolled_machine_id
    ):
        raise ValueError("upload intent mismatch")
    if raw != canonical_source(source):
        raise ValueError("upload not canonical")
    payload = source.payload
    scope, intent, capture = upload.scope, prepared.payload, upload.payload.capture
    if (
        source.authorization.host_id != scope.host_id
        or payload.organization_id != scope.organization_id
        or payload.event_id != scope.event_id
    ):
        raise ValueError("upload scope mismatch")
    if (
        payload.source != intent.source
        or payload.watcher_event_id != intent.watcher_event_id
        or payload.trigger.rule_id != intent.rule_id
        or payload.trigger.rule_version != intent.rule_version
        or payload.retention.policy_id != intent.policy_id
        or payload.retention.policy_version != intent.policy_version
    ):
        raise ValueError("upload source mismatch")
    expected = dict(
        envelope_sha256=hashlib.sha256(raw).hexdigest(),
        payload_digest=payload_digest(source),
        snapshot_id=payload.snapshot.snapshot_id,
        captured_at=payload.snapshot.captured_at,
        recovery_deadline=payload.retention.recovery_deadline,
        artifact_size=len(raw),
    )
    if capture.model_dump() != expected:
        raise ValueError("upload capture mismatch")


def match_untrusted_upload(
    upload: UploadRequest, prepared: PrepareRequest, raw: bytes
) -> UntrustedSource:
    """Pure comparison only; a successful match grants no permission or custody."""
    try:
        upload = parse_untrusted_request(canonical_request(upload))
        prepared = parse_untrusted_request(canonical_request(prepared))
        if type(upload) is not UploadRequest or type(prepared) is not PrepareRequest:
            raise ValueError("invalid upload variants")
        source = parse_untrusted_source(raw)
        _match_upload(upload, prepared, source, raw)
        return source
    except (ValueError, TypeError, RecursionError):
        pass
    raise CustodyInputError()
