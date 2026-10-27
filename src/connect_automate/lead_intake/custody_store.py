"""Private host-bound custody facade. SQL and raw authentication stay at their owners.

References are untrusted values, not machine/employee authentication. The host
supplies its previously retained store incarnation; this facade never enrolls one.
"""

from .admission import SourceAdmission
from .custody_protocol import (
    CaptureReference,
    ScopeReference,
    canonical_request,
    parse_untrusted_request,
)
from .source import SourceIdentity
from .source_store import (
    _DIGEST,
    _INSTANT,
    _UUID,
    SourceStore,
    SourceStoreConflict,
    SourceStoreInputError,
    _boundary,
)


def _input(parse, value):
    try:
        return parse(value, strict=True)
    except (TypeError, ValueError, RecursionError):
        pass
    raise SourceStoreInputError()


def _bound(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise SourceStoreInputError()
    return value


def _request(value, kind):
    try:
        result = parse_untrusted_request(canonical_request(value))
        if result.operation == kind:
            return result
    except (ValueError, TypeError, RecursionError):
        pass
    raise SourceStoreInputError()


class SourceCustodyStore:
    def __init__(
        self,
        store: SourceStore,
        *,
        expected_incarnation: str,
        max_handoffs: int,
        max_mutation_records: int,
        max_reservation_seconds: int,
        clock=None,
    ):
        if not isinstance(store, SourceStore):
            raise SourceStoreInputError()
        if clock is not None and not callable(clock):
            raise SourceStoreInputError()
        self._clock = clock
        self._store = store
        self._incarnation = _input(_UUID.validate_python, expected_incarnation)
        self._max_handoffs = _bound(max_handoffs)
        self._max_mutation_records = _bound(max_mutation_records)
        self._max_reservation_seconds = _bound(max_reservation_seconds)

    @_boundary
    def observe(
        self,
        *,
        handoff_id: str,
        scope: ScopeReference,
        enrolled_machine_id: str,
        capture: CaptureReference | None = None,
    ):
        ident = _input(_UUID.validate_python, handoff_id)
        scope = _input(ScopeReference.model_validate, scope)
        machine = _input(_UUID.validate_python, enrolled_machine_id)
        if capture is not None:
            capture = _input(CaptureReference.model_validate, capture)
        if (scope.host_id, scope.organization_id) != (
            self._store.host_id,
            self._store.organization_id,
        ):
            raise SourceStoreConflict()
        with self._store._read_snapshot(expected_incarnation=self._incarnation) as db:
            return self._store._observe_custody(db, ident, scope, machine, capture)

    @_boundary
    def lookup_receipt(
        self,
        *,
        identity: SourceIdentity,
        event_id: str,
        payload_digest: str,
        envelope_sha256: str,
    ):
        """Exact legacy facts; never infer a snapshot ID, route or handoff from them."""
        identity = _input(SourceIdentity.model_validate, identity)
        event = _input(_UUID.validate_python, event_id)
        payload = _input(_DIGEST.validate_python, payload_digest)
        envelope = _input(_DIGEST.validate_python, envelope_sha256)
        with self._store._read_snapshot(expected_incarnation=self._incarnation) as db:
            return self._store._lookup_receipt(db, identity, event, payload, envelope)

    def _writer(self):
        if not callable(self._clock):
            raise SourceStoreInputError()
        return self._store._transaction()

    @_boundary
    def register_intent(self, request, *, reservation_expires_at):
        request = _request(request, "prepare")
        deadline = _input(_INSTANT.validate_python, reservation_expires_at)
        with self._writer() as db:
            self._store._incarnation(db, self._incarnation)
            result = self._store._register_custody(
                db,
                request,
                deadline,
                self._clock,
                self._max_handoffs,
                self._max_mutation_records,
                self._max_reservation_seconds,
            )
        return result

    @_boundary
    def bind_upload(self, request):
        request = _request(request, "upload")
        with self._writer() as db:
            self._store._incarnation(db, self._incarnation)
            result = self._store._bind_custody(db, request, self._clock)
        return result

    @_boundary
    def close_admission(self, request):
        request = _request(request, "settle")
        with self._writer() as db:
            self._store._incarnation(db, self._incarnation)
            result = self._store._settle_custody(db, request, self._clock)
        return result

    @_boundary
    def admit_bound(self, request, raw):
        request = _request(request, "upload")
        admission = SourceAdmission(self._store, clock=self._clock)
        return admission._admit_managed(request, raw, incarnation=self._incarnation)

    @_boundary
    def revalidate_existing(self, request, raw, *, admission_id):
        request = _request(request, "resume")
        ident = _input(_UUID.validate_python, admission_id)
        admission = SourceAdmission(self._store, clock=self._clock)
        return admission._admit_managed(
            request,
            raw,
            incarnation=self._incarnation,
            existing_admission=ident,
        )
