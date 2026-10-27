"""Private host-bound metadata reader. No SQL or source mutation entry points.

References are untrusted values, not machine/employee authentication. The host
supplies its previously retained store incarnation; this facade never enrolls one.
"""

from .custody_protocol import CaptureReference, ScopeReference
from .source import SourceIdentity
from .source_store import (
    _DIGEST,
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


class SourceCustodyStore:
    def __init__(
        self,
        store: SourceStore,
        *,
        expected_incarnation: str,
        max_handoffs: int,
        max_mutation_records: int,
        max_reservation_seconds: int,
    ):
        if not isinstance(store, SourceStore):
            raise SourceStoreInputError()
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
