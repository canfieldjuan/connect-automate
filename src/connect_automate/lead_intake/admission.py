"""Atomic local source custody, not lead creation or a production receiver.

Raw requests are authenticated under SourceStore's writer transaction. No caller
supplied authenticated object is accepted. Host content/lifecycle operations use
the same custody validator and writer; this boundary is not for adoption.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BeforeValidator, Field

from ..entitlement import UuidV4
from .auth import SourceAuthenticationError, authenticate_source
from .receipts import ReceiptReference
from .source import (
    MAX_SOURCE_BYTES,
    Revision,
    SourceIdentity,
    _Closed,
    canonical_source,
    parse_untrusted_source,
    payload_digest,
)
from .source_store import (
    SourceStore,
    SourceStoreError,
    SourceStoreInputError,
    SourceStoreUnavailable,
    _boundary,
    _decode,
)


class SourceReceipt(ReceiptReference):
    schema_name: Literal["lead.source.receipt"] = Field(alias="schema")
    schema_version: Literal["1.0"]
    key_id: UuidV4
    trust_generation: Revision
    policy_id: UuidV4
    policy_version: Revision


def _receipt_value(value: object) -> object:
    if isinstance(value, SourceReceipt):
        return value.model_dump(by_alias=True)
    return value


class SourceAdmissionResult(_Closed):
    receipt: Annotated[SourceReceipt, BeforeValidator(_receipt_value)]
    applied: bool
    content_state: Literal["retained", "purged"]


class SourceAdmissionConflict(SourceStoreError):
    message = "lead source event conflict"


def _json(model: _Closed) -> str:
    return json.dumps(
        model.model_dump(by_alias=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


class SourceAdmission:
    """Host-constructed boundary; the host supplies the store and qualified UTC clock."""

    def __init__(self, store: SourceStore, *, clock: Callable[[], datetime]):
        if not isinstance(store, SourceStore) or not callable(clock):
            raise SourceStoreInputError()
        self._store, self._clock = store, clock

    def _existing(self, db, row) -> tuple[SourceReceipt, str]:
        ident, org, namespace, event, raw_receipt, envelope_hash = row
        receipt = SourceReceipt.model_validate_json(raw_receipt)
        if (
            _json(receipt) != raw_receipt
            or (
                receipt.admission_id,
                receipt.organization_id,
                receipt.namespace_id,
                receipt.event_id,
            )
            != (ident, org, namespace, event)
            or (receipt.host_id, receipt.organization_id)
            != (self._store.host_id, self._store.organization_id)
        ):
            raise SourceStoreUnavailable()
        custody = db.execute(
            "SELECT identity, captured_at, state FROM source_custody WHERE admission_id=?", (ident,)
        ).fetchone()
        if custody is None:
            raise SourceStoreUnavailable()
        identity_raw, captured_at, state = custody
        identity = SourceIdentity.model_validate_json(identity_raw)
        if _json(identity) != identity_raw or identity.namespace_id != receipt.namespace_id:
            raise SourceStoreUnavailable()
        content = db.execute(
            "SELECT envelope FROM source_content WHERE admission_id=?", (ident,)
        ).fetchone()
        if state == "purged":
            if content is not None:
                raise SourceStoreUnavailable()
            return receipt, state
        if state != "retained" or content is None:
            raise SourceStoreUnavailable()
        raw = content[0]
        if hashlib.sha256(raw).hexdigest() != envelope_hash:
            raise SourceStoreUnavailable()
        source = parse_untrusted_source(raw)
        if canonical_source(source) != raw or payload_digest(source) != receipt.payload_digest:
            raise SourceStoreUnavailable()
        if (
            source.payload.source != identity
            or source.payload.snapshot.captured_at != captured_at
            or source.payload.event_id != receipt.event_id
        ):
            raise SourceStoreUnavailable()
        # Reuse the verifier to check the first-auth stamp under its historical
        # authority, without requiring that old key to remain currently active.
        historical = db.execute(
            "SELECT snapshot FROM authority_history WHERE generation=?", (receipt.trust_generation,)
        ).fetchone()
        if historical is None:
            raise SourceStoreUnavailable()
        try:
            original = authenticate_source(
                raw, trust=_decode(historical[0]), now=datetime.fromisoformat(receipt.accepted_at)
            )
        except SourceAuthenticationError:
            original = None
        if original is None or (
            original.host_id,
            original.organization_id,
            original.namespace_id,
            original.key_id,
            original.policy_id,
            original.policy_version,
            original.source.payload.retention.recovery_deadline,
        ) != (
            receipt.host_id,
            receipt.organization_id,
            receipt.namespace_id,
            receipt.key_id,
            receipt.policy_id,
            receipt.policy_version,
            receipt.recovery_deadline,
        ):
            raise SourceStoreUnavailable()
        return receipt, state

    @_boundary
    def admit_source(self, raw: bytes) -> SourceAdmissionResult:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES:
            raise SourceAuthenticationError()
        with self._store._transaction() as db:
            authority, _ = self._store._authority(db)
            first = authenticate_source(
                raw, trust=authority, now=self._store._check_clock(db, self._clock())
            )
            payload = first.source.payload
            self._store._admission_policy(db, payload.source, payload.snapshot.captured_at)
            row = db.execute(
                "SELECT admission_id, organization_id, namespace_id, event_id, receipt, "
                "envelope_sha256 FROM source_receipts "
                "WHERE organization_id=? AND namespace_id=? AND event_id=?",
                (first.organization_id, first.namespace_id, payload.event_id),
            ).fetchone()
            applied = row is None
            state = "retained"
            if row is not None:
                receipt, state = self._existing(db, row)
                if receipt.payload_digest != first.payload_digest:
                    raise SourceAdmissionConflict()
            else:
                ident = str(uuid4())
                canonical = canonical_source(first.source)
                # Deferred FKs let content be staged before the final decision
                # sample. The immutable receipt is the last row written.
                db.execute("INSERT INTO source_content VALUES (?, ?)", (ident, canonical))
                db.execute(
                    "INSERT INTO source_custody VALUES (?, ?, ?, 'retained')",
                    (ident, _json(payload.source), payload.snapshot.captured_at),
                )
            current, _ = self._store._authority(db)
            final = authenticate_source(
                raw, trust=current, now=self._store._check_clock(db, self._clock())
            )
            if (
                final.trust_generation != first.trust_generation
                or final.verified_at < first.verified_at
            ):
                raise SourceAuthenticationError()
            self._store._record_clock(db, final.verified_at, final.trust_generation)
            if applied:
                receipt = SourceReceipt.model_validate(
                    {
                        "schema": "lead.source.receipt",
                        "schema_version": "1.0",
                        "admission_id": ident,
                        "host_id": final.host_id,
                        "organization_id": final.organization_id,
                        "namespace_id": final.namespace_id,
                        "event_id": payload.event_id,
                        "payload_digest": final.payload_digest,
                        "accepted_at": final.verified_at.isoformat(timespec="microseconds").replace(
                            "+00:00", "Z"
                        ),
                        "key_id": final.key_id,
                        "trust_generation": final.trust_generation,
                        "policy_id": final.policy_id,
                        "policy_version": final.policy_version,
                        "recovery_deadline": payload.retention.recovery_deadline,
                    }
                )
                db.execute(
                    "INSERT INTO source_receipts VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        ident,
                        final.organization_id,
                        final.namespace_id,
                        payload.event_id,
                        _json(receipt),
                        hashlib.sha256(canonical).hexdigest(),
                    ),
                )
            result = SourceAdmissionResult(receipt=receipt, applied=applied, content_state=state)
        return result
