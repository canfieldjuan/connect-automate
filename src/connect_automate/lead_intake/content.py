"""Privileged host content lifecycle; no remote API or cleanup scheduler.

The embedding host must restrict construction/access under the private OS-user
boundary. This is not employee authorization or proof of cross-application purge.
"""

from contextlib import suppress
from datetime import datetime

from .admission import SourceAdmission
from .auth import SourceAuthenticationError
from .source import SourceIdentity
from .source_store import (
    _UUID,
    SourceStoreConflict,
    SourceStoreError,
    SourceStoreInputError,
    SourceStoreUnavailable,
    _boundary,
    _capture_at_or_before,
    _clock_text,
    _identity_text,
)


class SourceContentUnavailable(SourceStoreError):
    message = "lead source content unavailable"


def _id(value):
    result = None
    with suppress(ValueError, TypeError):
        result = _UUID.validate_python(value)
    if result is None:
        raise SourceStoreInputError()
    return result


def _limit(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise SourceStoreInputError()
    return value


class SourceContent:
    def __init__(self, store, *, clock):
        # Reuse construction validation and the existing single custody validator.
        self._custody = SourceAdmission(store, clock=clock)
        self._store, self._clock = store, clock

    def _row(self, db, ident):
        return db.execute(
            "SELECT admission_id, organization_id, namespace_id, event_id, receipt, "
            "envelope_sha256 FROM source_receipts WHERE admission_id=?",
            (ident,),
        ).fetchone()

    def _final(self, db, first):
        final = self._store._check_clock(db, self._clock())
        if final < first:
            raise SourceAuthenticationError()
        authority, _ = self._store._authority(db)
        self._store._record_clock(db, final, authority.generation)
        return final

    def _purge(self, db, ident):
        self._store._close_custody_for_receipt(db, ident)
        db.execute("DELETE FROM source_content WHERE admission_id=?", (ident,))
        db.execute(
            "UPDATE source_custody SET state='purged' WHERE admission_id=? AND state='retained'",
            (ident,),
        )

    @_boundary
    def read_content(self, admission_id: str) -> bytes:
        ident = _id(admission_id)
        with self._store._transaction() as db:
            raw = self._read_in_transaction(db, ident)
        if raw is None:
            raise SourceContentUnavailable()
        return raw

    @_boundary
    def _read_retained(self, request, *, incarnation) -> bytes:
        with self._store._transaction() as db:
            self._store._incarnation(db, incarnation)
            facts = self._store._custody_request_state(db, request)
            if facts is None:
                raise SourceContentUnavailable()
            if facts.fence_generation != request.expected_fence_generation:
                raise SourceAuthenticationError()
            if (
                not facts.ever_custodied
                or facts.receipt is None
                or facts.content_state != "retained"
            ):
                raise SourceContentUnavailable()
            raw = self._read_in_transaction(db, facts.receipt.admission_id)
        if raw is None:
            raise SourceContentUnavailable()
        return raw

    def _read_in_transaction(self, db, ident):
        """Shared validation, clock and terminal-expiry owner for both readers."""
        first = self._store._check_clock(db, self._clock())
        row = self._row(db, ident)
        retired, _ = self._store._lifecycle(db)
        if row is None or row[2] in retired:
            raise SourceContentUnavailable()
        receipt, state = self._custody._existing(db, row)
        if state == "purged":
            raise SourceContentUnavailable()
        final = self._final(db, first)
        if final >= datetime.fromisoformat(receipt.recovery_deadline):
            # Commit terminal expiry before reporting unavailable. C1 must
            # never revive content whose expiry has already been observed.
            self._purge(db, ident)
            return None
        return db.execute(
            "SELECT envelope FROM source_content WHERE admission_id=?", (ident,)
        ).fetchone()[0]

    @_boundary
    def cleanup_expired(self, *, limit: int) -> int:
        limit = _limit(limit)
        with self._store._transaction() as db:
            first = self._store._check_clock(db, self._clock())
            # Signed deadlines have whole-second precision; exclude none that
            # expire in this second, then validate the exact receipt below.
            cutoff = first.isoformat(timespec="seconds").replace("+00:00", "Z")
            ids = db.execute(
                "SELECT r.admission_id FROM source_receipts r JOIN source_custody c "
                "USING(admission_id) WHERE c.state='retained' "
                "AND json_extract(r.receipt, '$.recovery_deadline')<=? "
                "ORDER BY json_extract(r.receipt, '$.recovery_deadline'), r.admission_id LIMIT ?",
                (cutoff, limit),
            ).fetchall()
            for (ident,) in ids:
                receipt, _ = self._custody._existing(db, self._row(db, ident))
                if datetime.fromisoformat(receipt.recovery_deadline) > first:
                    raise SourceStoreUnavailable()
                self._purge(db, ident)
            self._final(db, first)
        return len(ids)

    @_boundary
    def purge_message(self, identity: SourceIdentity, *, cutoff: datetime) -> bool:
        valid = False
        try:
            if isinstance(identity, SourceIdentity):
                identity = SourceIdentity.model_validate(identity)
                key, stamp = _identity_text(identity), _clock_text(cutoff)
                valid = True
        except (ValueError, TypeError):
            pass
        if not valid:
            raise SourceStoreInputError()
        with self._store._transaction() as db:
            retired, horizons = self._store._lifecycle(db)
            if identity.namespace_id in retired or (key in horizons and cutoff <= horizons[key]):
                return False
            ids = db.execute(
                "SELECT admission_id, captured_at FROM source_custody "
                "WHERE identity=? AND state='retained'",
                (key,),
            ).fetchall()
            for ident, captured_at in ids:
                self._custody._existing(db, self._row(db, ident))
                if _capture_at_or_before(captured_at, cutoff):
                    self._purge(db, ident)
            self._store._close_custody_for_lifecycle(db, identity.namespace_id, identity, cutoff)
            db.execute(
                "INSERT INTO source_purge_horizons VALUES (?, ?, ?) "
                "ON CONFLICT(identity) DO UPDATE SET cutoff=excluded.cutoff",
                (key, identity.namespace_id, stamp),
            )
        return True

    @_boundary
    def retire_namespace(self, namespace_id: str) -> bool:
        namespace = _id(namespace_id)
        with self._store._transaction() as db:
            retired, _ = self._store._lifecycle(db)
            if namespace in retired:
                return False
            first = self._store._check_clock(db, self._clock())
            final = self._final(db, first)
            self._store._close_custody_for_lifecycle(db, namespace)
            db.execute("INSERT INTO source_retired VALUES (?, ?)", (namespace, _clock_text(final)))
        return True

    @_boundary
    def cleanup_retired(self, namespace_id: str, *, limit: int) -> int:
        namespace, limit = _id(namespace_id), _limit(limit)
        with self._store._transaction() as db:
            retired, _ = self._store._lifecycle(db)
            if namespace not in retired:
                raise SourceStoreConflict()
            ids = db.execute(
                "SELECT admission_id FROM source_receipts WHERE namespace_id=? "
                "ORDER BY admission_id LIMIT ?",
                (namespace, limit),
            ).fetchall()
            for (ident,) in ids:
                self._custody._existing(db, self._row(db, ident))
                db.execute("DELETE FROM source_content WHERE admission_id=?", (ident,))
                db.execute("DELETE FROM source_custody WHERE admission_id=?", (ident,))
                db.execute("DELETE FROM source_receipts WHERE admission_id=?", (ident,))
            horizons = db.execute(
                "SELECT identity FROM source_purge_horizons WHERE namespace_id=? "
                "ORDER BY identity LIMIT ?",
                (namespace, limit - len(ids)),
            ).fetchall()
            for (identity,) in horizons:
                db.execute("DELETE FROM source_purge_horizons WHERE identity=?", (identity,))
        return len(ids) + len(horizons)
