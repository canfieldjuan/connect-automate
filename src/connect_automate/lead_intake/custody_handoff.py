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

from pydantic import TypeAdapter

from ..automate.events import EventBindingError, SourceBinding, lead_deployment_scope
from ..automate.runtime import PackRuntime
from ..entitlement import UuidV4
from .custody_protocol import (
    RouteReference,
    UploadRequest,
    canonical_request,
    parse_untrusted_request,
)
from .custody_store import SourceCustodyStore
from .handoff import _prepared_source, _source_for_binding
from .source import _canonical


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

    def _prepare(self, request: UploadRequest, raw: bytes):
        self._check_runtime()
        valid = False
        try:
            request = parse_untrusted_request(canonical_request(request))
            scope = lead_deployment_scope(self._source.scope, self._source.source_id)
            valid = type(request) is UploadRequest and (
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
        parsed = _source_for_binding(self._source, raw)
        admitted = self.custody.admit_bound(request, raw)
        return _prepared_source(self._source, parsed, admitted, self.clock)

    def submit(self, *, request: UploadRequest, raw_source_bytes: bytes):
        return self.runtime._submit_custody_source(
            custody=self, request=request, raw_source_bytes=raw_source_bytes
        )
