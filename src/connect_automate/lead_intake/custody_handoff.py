"""Private trusted-host composition, not a receiver or machine authentication.

The host supplies an already verified runtime and an enrolled concrete custody
facade. Metadata pins restrict routing; only the source writer authenticates raw
bytes and decides the fence. No receipt or request reference grants authority.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import TypeAdapter

from ..automate.engine import PackVersionError
from ..automate.events import (
    EventBindingError,
    EventConflict,
    EventInputError,
    SourceBinding,
    lead_deployment_scope,
)
from ..automate.host import AutomateLicenseError
from ..automate.runtime import PackRuntime
from ..entitlement import UuidV4
from .content import SourceContentUnavailable
from .custody_protocol import (
    ExpiredUnfencedStatusResultV12,
    ResolvedStatusResult,
    ResolvedStatusResultV12,
    ResumeRequest,
    RouteReference,
    StatusRequest,
    UnresolvedStatusResult,
    UnresolvedStatusResultV12,
    UploadRequest,
    _reservation_elapsed,
    canonical_request,
    canonical_status_result,
    canonical_status_result_v1_2,
    parse_untrusted_request,
)
from .custody_store import SourceCustodyStore
from .handoff import _prepared_source, _source_for_binding
from .receipts import ReceiptReference
from .results import SourceHandoffLookup, SourceHandoffResult, SourceHandoffUnknown
from .source import _canonical
from .source_store import (
    CustodyObservation,
    CustodyStatusObservation,
    SourceStoreConflict,
    SourceStoreError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
)


def _receipt_reference(receipt):
    return ReceiptReference.model_validate(
        {name: getattr(receipt, name) for name in ReceiptReference.model_fields}
    )


def _historical_lookup(facts, found):
    """Pure join shared with recovery; no new clock, lifecycle or I/O prerequisite."""
    if type(found) is not SourceHandoffLookup:
        raise ValueError("invalid lookup value")
    found = SourceHandoffLookup.model_validate(found, by_name=True)
    if found.workflow_outcome != "not_found":
        receipt = found.source_receipt
        if (
            facts.ever_custodied is not True
            or found.actions
            or (
                receipt.host_id,
                receipt.organization_id,
                receipt.namespace_id,
                receipt.event_id,
                receipt.payload_digest,
                receipt.recovery_deadline,
            )
            != (
                facts.scope.host_id,
                facts.scope.organization_id,
                facts.scope.namespace_id,
                facts.scope.event_id,
                facts.capture.payload_digest,
                facts.capture.recovery_deadline,
            )
        ):
            raise ValueError("inconsistent historical join")
        if facts.receipt is not None:
            reference = _receipt_reference(facts.receipt)
            if receipt != reference:
                raise ValueError("inconsistent historical receipt")
    return found


def _encoded_status(result):
    canonical_status_result(result)
    return result


def _encoded_status_v1_2(result):
    canonical_status_result_v1_2(result)
    return result


@dataclass(frozen=True, repr=False)
class _CustodyHandoff:
    runtime: PackRuntime
    custody: SourceCustodyStore
    route: RouteReference
    enrolled_machine_id: str
    clock: Callable[[], datetime]
    _source: SourceBinding = field(init=False)
    _route_digest: str = field(init=False)
    _owner: object = field(init=False)
    _incarnation: str = field(init=False)

    def __post_init__(self):
        valid = False
        try:
            if (
                type(self.runtime) is not PackRuntime
                or type(self.custody) is not SourceCustodyStore
                or not callable(self.clock)
                or not callable(self.custody._clock)
            ):
                raise ValueError("invalid trusted configuration")
            route = RouteReference.model_validate(self.route)
            machine = TypeAdapter(UuidV4).validate_python(self.enrolled_machine_id, strict=True)
            source = SourceBinding.model_validate(self.runtime._lead_source_binding(route.binding))
            object.__setattr__(self, "route", route)
            object.__setattr__(self, "enrolled_machine_id", machine)
            object.__setattr__(self, "_source", source)
            object.__setattr__(
                self, "_route_digest", hashlib.sha256(_canonical(route.model_dump())).hexdigest()
            )
            # Configuration only, never a database query or automatic enrollment.
            object.__setattr__(self, "_owner", self.custody._store)
            object.__setattr__(self, "_incarnation", self.custody._incarnation)
            valid = True
        except (ValueError, TypeError, AttributeError, RecursionError):
            pass
        if not valid:
            raise EventBindingError()
        self._check_runtime()

    def _check_runtime(self):
        source = self.runtime._lead_source_binding(self.route.binding)
        scope = lead_deployment_scope(self._source.scope, self._source.source_id)
        pack = self.runtime._pack
        if (
            (pack.pack_id, pack.pack_version) != (self.route.pack_id, self.route.pack_version)
            or source != self._source
            or any(definition.actions for definition in pack.workflow.definitions)
            or self.custody._store is not self._owner
            or self.custody._incarnation != self._incarnation
            or (self._owner.host_id, self._owner.organization_id)
            != (scope.host_id, scope.organization_id)
        ):
            raise EventBindingError()

    def _checked_request(self, request, expected_type):
        self._check_runtime()
        valid = False
        try:
            request = parse_untrusted_request(canonical_request(request))
            scope = lead_deployment_scope(self._source.scope, self._source.source_id)
            valid = type(request) is expected_type and (
                request.scope.host_id,
                request.scope.organization_id,
                request.scope.namespace_id,
                request.scope.route_digest,
                request.enrolled_machine_id,
            ) == (
                scope.host_id,
                scope.organization_id,
                scope.namespace_id,
                self._route_digest,
                self.enrolled_machine_id,
            )
        except (ValueError, TypeError, AttributeError, RecursionError):
            pass
        if not valid:
            raise EventBindingError()
        return request

    def _prepare(self, request: UploadRequest, raw: bytes):
        request = self._checked_request(request, UploadRequest)
        parsed = _source_for_binding(self._source, raw)
        admitted = self.custody.admit_bound(request, raw)
        return _prepared_source(self._source, parsed, admitted, self.clock)

    def _prepare_resume(self, request: ResumeRequest):
        request = self._checked_request(request, ResumeRequest)
        facts = self.custody.observe(
            handoff_id=request.handoff_id,
            scope=request.scope,
            enrolled_machine_id=request.enrolled_machine_id,
            capture=request.payload.capture,
        )
        if facts is None or facts.receipt is None:
            raise SourceContentUnavailable()
        raw = self.custody.read_retained(request)
        parsed = _source_for_binding(self._source, raw)
        admitted = self.custody.revalidate_existing(
            request, raw, admission_id=facts.receipt.admission_id
        )
        if (
            admitted.receipt != facts.receipt
            or admitted.applied is not False
            or admitted.content_state != "retained"
        ):
            raise SourceStoreUnavailable()
        return _prepared_source(self._source, parsed, admitted, self.clock)

    def submit(self, *, request: UploadRequest, raw_source_bytes: bytes):
        return self.runtime._submit_custody_source(
            custody=self, request=request, raw_source_bytes=raw_source_bytes
        )

    def resume(self, *, request: ResumeRequest):
        return self.runtime._resume_custody_source(custody=self, request=request)

    def recover(self, *, request: ResumeRequest) -> SourceHandoffLookup | SourceHandoffResult:
        """Observe committed history before attempting one freshly authorized resume.

        The two owners finish separate read snapshots. Neither observation is an
        authorization lease; only a valid not-found may enter the existing resume.
        """
        try:
            request = self._checked_request(request, ResumeRequest)
            facts = self.custody.observe(
                handoff_id=request.handoff_id,
                scope=request.scope,
                enrolled_machine_id=request.enrolled_machine_id,
                capture=request.payload.capture,
            )
            if facts is None:
                raise SourceContentUnavailable()
            if (
                type(facts) is not CustodyObservation
                or facts.handoff_id != request.handoff_id
                or facts.scope != request.scope
                or facts.capture != request.payload.capture
            ):
                raise ValueError("inconsistent custody observation")
            found = self.runtime.lookup_source_outcome(
                binding=self.route.binding,
                event_id=facts.scope.event_id,
                expected_payload_digest=facts.capture.payload_digest,
            )
            found = _historical_lookup(facts, found)
            if found.workflow_outcome != "not_found":
                return found
        except (SourceStoreUnavailable, SourceStoreUncertain):
            pass
        except (
            EventBindingError,
            EventInputError,
            EventConflict,
            PackVersionError,
            AutomateLicenseError,
            SourceContentUnavailable,
            SourceStoreError,
        ):
            raise
        except Exception:
            pass
        else:
            # No reused observation, refreshed fence, retry or post-failure lookup.
            return self.resume(request=request)
        raise SourceHandoffUnknown()

    def status(self, *, request: StatusRequest) -> ResolvedStatusResult | UnresolvedStatusResult:
        """Read source availability, then independent workflow history; never resume."""
        return self._status(request=request, version="1.1")

    def status_v1_2(
        self, *, request: StatusRequest
    ) -> ResolvedStatusResultV12 | ExpiredUnfencedStatusResultV12 | UnresolvedStatusResultV12:
        """Opt-in expired-unfenced projection; does not settle or authorize retries."""
        return self._status(request=request, version="1.2")

    def _status(self, *, request: StatusRequest, version: Literal["1.1", "1.2"]):
        request = self._checked_request(request, StatusRequest)
        resolved_type, unresolved_type, encode = {
            "1.1": (ResolvedStatusResult, UnresolvedStatusResult, _encoded_status),
            "1.2": (ResolvedStatusResultV12, UnresolvedStatusResultV12, _encoded_status_v1_2),
        }[version]
        code = "unknown"
        try:
            observation = self.custody.observe_status(request=request)
            if observation is None:
                return encode(
                    unresolved_type(
                        schema_version=version,
                        status="unresolved",
                        handoff_id=request.handoff_id,
                        code="not_found",
                    )
                )
            if type(observation) is not CustodyStatusObservation:
                raise ValueError("invalid status observation")
            facts = observation.custody
            if (
                type(facts) is not CustodyObservation
                or facts.handoff_id != request.handoff_id
                or facts.scope != request.scope
                or facts.capture != request.payload.capture
                or type(facts.ever_custodied) is not bool
                or type(facts.closed) is not bool
                or type(observation.namespace_retired) is not bool
                or (observation.admission_id is not None) != facts.ever_custodied
            ):
                raise ValueError("inconsistent status observation")
            found = receipt = deadline = None
            content, unavailable = observation.content_state, observation.unavailable_reason
            if facts.ever_custodied is True:
                found = _historical_lookup(
                    facts,
                    self.runtime.lookup_source_outcome(
                        binding=self.route.binding,
                        event_id=facts.scope.event_id,
                        expected_payload_digest=facts.capture.payload_digest,
                    ),
                )
                if content not in ("retained", "unavailable") or observation.namespace_retired != (
                    unavailable == "retired"
                ):
                    raise ValueError("inconsistent source availability")
                if facts.receipt is not None:
                    receipt = _receipt_reference(facts.receipt)
                elif observation.namespace_retired:
                    receipt = found.source_receipt
                if receipt is None or receipt.admission_id != observation.admission_id:
                    raise ValueError("missing historical receipt")
                phase = "custodied"
                reason = (
                    "workflow_known"
                    if found.workflow_outcome != "not_found"
                    else "custody_confirmed"
                    if content == "retained"
                    else "content_unavailable"
                )
            else:
                if facts.receipt is not None or (content, unavailable) != ("not_received", None):
                    raise ValueError("unexpected uncustodied receipt or content")
                if facts.closed:
                    phase, reason = "fenced_empty", "capture_cancelled"
                elif facts.capture is not None:
                    phase, content, reason = "upload_possible", "unknown", "pending"
                else:
                    phase, reason, deadline = (
                        "prepared",
                        "ready",
                        observation.reservation_expires_at,
                    )
                    if version == "1.2" and _reservation_elapsed(deadline, observation.observed_at):
                        phase, reason = "expired_unfenced", "settlement_required"
                        resolved_type = ExpiredUnfencedStatusResultV12
            return encode(
                resolved_type.model_validate(
                    dict(
                        schema_version=version,
                        status="resolved",
                        handoff_id=facts.handoff_id,
                        scope=facts.scope,
                        state_revision=facts.state_revision,
                        fence_generation=facts.fence_generation,
                        observed_at=observation.observed_at,
                        reservation_expires_at=deadline,
                        capture=facts.capture,
                        capture_phase=phase,
                        content_state=content,
                        unavailable_reason=unavailable,
                        workflow=found,
                        source_receipt=receipt,
                        reason=reason,
                    ),
                    by_name=True,
                )
            )
        except (SourceStoreConflict, EventConflict):
            code = "conflict"
        except (EventBindingError, EventInputError, PackVersionError, AutomateLicenseError):
            raise
        except Exception:
            pass
        # Encode outside the original handler: no input/cause/context crosses this boundary.
        # An unencodable conflict also falls back to the minimal unknown value.
        for outcome in dict.fromkeys((code, "unknown")):
            try:
                return encode(
                    unresolved_type(
                        schema_version=version,
                        status="unresolved",
                        handoff_id=request.handoff_id,
                        code=outcome,
                    )
                )
            except Exception:
                pass
        raise SourceHandoffUnknown()
