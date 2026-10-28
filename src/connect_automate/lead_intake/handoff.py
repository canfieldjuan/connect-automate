"""Private host composition; not workflow acceptance or a submission credential.

Only the verified runtime calls this seam. Public submission reauthenticates raw
bytes every time; no consumer may submit prepared metadata as authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..automate.events import (
    EventBindingError,
    LeadSourceEvent,
    SourceBinding,
    check_event_time,
    lead_deployment_scope,
)
from .admission import SourceAdmission, SourceAdmissionResult
from .receipts import ReceiptReference
from .source import UntrustedSource, parse_untrusted_source, payload_digest
from .source_store import SourceStoreUnavailable


@dataclass(frozen=True)
class _PreparedSource:
    event: LeadSourceEvent
    source_applied: bool
    now: datetime


@dataclass(frozen=True)
class _SourceHandoff:
    source: SourceBinding
    admission: SourceAdmission = field(repr=False)
    clock: Callable[[], datetime] = field(repr=False)

    def __post_init__(self):
        valid = False
        try:
            if not isinstance(self.admission, SourceAdmission) or not callable(self.clock):
                raise ValueError("invalid trusted configuration")
            # PackRuntime._validate_bindings owns source model validation/copying.
            source = self.source
            if source.source_kind != "lead.source.received":
                raise ValueError("wrong source kind")
            scope = lead_deployment_scope(source.scope, source.source_id)
            valid = self.admission.deployment == (scope.host_id, scope.organization_id)
        except (ValueError, TypeError, RecursionError):
            pass
        if not valid:
            raise EventBindingError()

    def prepare(self, raw: bytes) -> _PreparedSource:
        scope = lead_deployment_scope(self.source.scope, self.source.source_id)
        # Refuse configuration drift before admitting any source. Actual durable
        # authority is still checked by SourceAdmission inside its own transaction.
        if self.admission.deployment != (scope.host_id, scope.organization_id):
            raise EventBindingError()
        parsed = _source_for_binding(self.source, raw)
        # Every replay reauthenticates. No callback runs under the source writer.
        admitted = self.admission.admit_source(raw)
        return _prepared_source(self.source, parsed, admitted, self.clock)


def _source_for_binding(source: SourceBinding, raw: bytes) -> UntrustedSource:
    scope = lead_deployment_scope(source.scope, source.source_id)
    parsed = parse_untrusted_source(raw)
    payload = parsed.payload
    if (
        parsed.authorization.host_id,
        payload.organization_id,
        payload.source.namespace_id,
    ) != (scope.host_id, scope.organization_id, scope.namespace_id):
        raise EventBindingError()
    return parsed


def _prepared_source(
    source: SourceBinding,
    parsed: UntrustedSource,
    admitted: SourceAdmissionResult,
    clock: Callable[[], datetime],
) -> _PreparedSource:
    """Validate a fresh owner result; never a submission authority by itself."""
    scope = lead_deployment_scope(source.scope, source.source_id)
    payload = parsed.payload
    valid = False
    try:
        if not isinstance(admitted, SourceAdmissionResult):
            raise ValueError("invalid source result")
        admitted = SourceAdmissionResult.model_validate(admitted)
        receipt = admitted.receipt
        reference = ReceiptReference.model_validate(
            {name: getattr(receipt, name) for name in ReceiptReference.model_fields}
        )
        valid = (
            reference.host_id,
            reference.organization_id,
            reference.namespace_id,
            reference.event_id,
            reference.payload_digest,
            reference.recovery_deadline,
        ) == (
            scope.host_id,
            scope.organization_id,
            scope.namespace_id,
            payload.event_id,
            payload_digest(parsed),
            payload.retention.recovery_deadline,
        )
    except (ValueError, TypeError, RecursionError):
        pass
    if not valid:
        raise SourceStoreUnavailable()
    event = LeadSourceEvent(
        source_kind="lead.source.received", schema_version="1.0", source_receipt=reference
    )
    now = clock()
    check_event_time(event, now)
    return _PreparedSource(event=event, source_applied=admitted.applied, now=now)
