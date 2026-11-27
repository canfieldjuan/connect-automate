"""Private V1c record owner. The host supplies the fresh custody/workflow join."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field

from ..entitlement import UuidV4
from .form import FormFields, FormInputError, parse_synthetic_form
from .receipts import ReceiptReference
from .results import SourceHandoffResult
from .source import (
    Digest,
    FormPayload,
    Opaque,
    SourceIdentity,
    _canonical,
    _Closed,
    parse_untrusted_source,
    payload_digest,
)
from .source_store import (
    _UUID,
    SourceStoreError,
    SourceStoreInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
    _boundary,
    _PrivateDatabaseFile,
)

_DEFAULT_LABELS = ("New", "In progress", "Closed")
_SOURCE_COLUMNS = tuple(SourceIdentity.model_fields)
_UNIQUE_COLUMNS = ", ".join(("organization_id", *_SOURCE_COLUMNS))
_SOURCE_LOOKUP = " AND ".join(f"{name}=?" for name in ("organization_id", *_SOURCE_COLUMNS))


def _json_column(name, selector):
    return f"{name} TEXT GENERATED ALWAYS AS (json_extract(record, '{selector}')) STORED NOT NULL"


_RECORD_KEYS = (
    _json_column("lead_id", "$.reference.lead_id") + " UNIQUE",
    _json_column("organization_id", "$.reference.organization_id"),
    *(_json_column(name, f"$.source.{name}") for name in _SOURCE_COLUMNS),
    _json_column("stage_set_id", "$.stage_set_id"),
    _json_column("stage_id", "$.stage_id"),
)
_SCHEMA = (
    "CREATE TABLE lead_scope (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
    "host_id TEXT NOT NULL, organization_id TEXT NOT NULL, owner_id TEXT NOT NULL, "
    "stage_set_id TEXT NOT NULL UNIQUE, UNIQUE(organization_id, stage_set_id)) STRICT",
    "CREATE TABLE lead_stages (stage_set_id TEXT NOT NULL REFERENCES lead_scope(stage_set_id), "
    "stage_id TEXT NOT NULL, label TEXT NOT NULL, position INTEGER NOT NULL, "
    "PRIMARY KEY(stage_set_id, stage_id), UNIQUE(stage_set_id, position)) STRICT",
    "CREATE TABLE leads (record TEXT NOT NULL, "
    + ", ".join(_RECORD_KEYS)
    + f", UNIQUE({_UNIQUE_COLUMNS}), "
    "FOREIGN KEY(organization_id, stage_set_id) "
    "REFERENCES lead_scope(organization_id, stage_set_id), "
    "FOREIGN KEY(stage_set_id, stage_id) REFERENCES lead_stages(stage_set_id, stage_id)) STRICT",
)


class LeadRecordRefused(SourceStoreError):
    message = "lead record input refused"


class LeadRecordConflict(SourceStoreError):
    message = "lead form binding conflicts with the committed record"


class _LeadScope(_Closed):
    host_id: UuidV4
    organization_id: UuidV4
    owner_id: UuidV4


class LeadReference(_Closed):
    organization_id: UuidV4
    lead_id: UuidV4


class _Stage(_Closed):
    stage_set_id: UuidV4
    stage_id: UuidV4
    label: str


class _FormBinding(_Closed):
    template_id: Literal["synthetic-form-v1"]
    part_id: Opaque
    part_sha256: Digest


class _LeadRecord(_Closed):
    binding: _FormBinding
    reference: LeadReference
    source: SourceIdentity
    source_receipt: ReceiptReference
    fields_version: Literal["1.0"]
    fields: FormFields = Field(repr=False)
    review_state: Literal["NEEDS_REVIEW"]
    stage_set_id: UuidV4
    stage_id: UuidV4


class _LeadStore(_PrivateDatabaseFile):
    """Local private store. A callback inside its writer must refresh host authority."""

    @_boundary
    def __init__(
        self,
        path: Path,
        *,
        private_root: Path,
        host_id: str,
        organization_id: str,
        owner_id: str,
    ):
        self.path, self.root = Path(path), Path(private_root)
        if not self.path.is_absolute() or self.path.parent != self.root or ".." in self.path.parts:
            raise SourceStoreInputError()
        self.scope = _LeadScope(host_id=host_id, organization_id=organization_id, owner_id=owner_id)

    @contextmanager
    def _open(self, *, write: bool = False, initialize: bool = False):
        self._paths()
        mode = "rw" if write else "ro"
        with closing(sqlite3.connect(self.path.as_uri() + f"?mode={mode}", uri=True)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            if write:
                db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            self._paths()
            layout = sorted(
                row[0] for row in db.execute("SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL")
            )
            stage_set_id = None
            if layout == sorted(_SCHEMA):
                row = db.execute(
                    "SELECT host_id, organization_id, owner_id, stage_set_id FROM lead_scope"
                ).fetchone()
                if row is None or row[:3] != (
                    self.scope.host_id,
                    self.scope.organization_id,
                    self.scope.owner_id,
                ):
                    raise SourceStoreUnavailable()
                stage_set_id = _UUID.validate_python(row[3])
            elif layout or not initialize:
                raise SourceStoreUnavailable()
            yield db, stage_set_id
            if write:
                self._paths()
                failed = False
                try:
                    db.commit()
                except sqlite3.Error:
                    failed = True
                if failed:
                    raise SourceStoreUncertain()

    @_boundary
    def initialize(self) -> None:
        self._create()
        with self._open(write=True, initialize=True) as (db, stage_set_id):
            if stage_set_id is None:
                stage_set_id = str(uuid4())
                for statement in _SCHEMA:
                    db.execute(statement)
                db.execute(
                    "INSERT INTO lead_scope VALUES (1, ?, ?, ?, ?)",
                    (
                        self.scope.host_id,
                        self.scope.organization_id,
                        self.scope.owner_id,
                        stage_set_id,
                    ),
                )
                db.executemany(
                    "INSERT INTO lead_stages VALUES (?, ?, ?, ?)",
                    [
                        (stage_set_id, str(uuid4()), label, position)
                        for position, label in enumerate(_DEFAULT_LABELS)
                    ],
                )

    def _stages(self, db, stage_set_id):
        return tuple(
            _Stage(stage_set_id=stage_set_id, stage_id=stage_id, label=label)
            for stage_id, label in db.execute(
                "SELECT stage_id, label FROM lead_stages WHERE stage_set_id=? ORDER BY position",
                (stage_set_id,),
            )
        )

    @_boundary
    def default_stages(self):
        with self._open() as (db, stage_set_id):
            return self._stages(db, stage_set_id)

    @_boundary
    def read(self, lead_id: str) -> _LeadRecord | None:
        """Internal exact-ID lookup for the proof. No listing or field projection."""
        ident = _UUID.validate_python(lead_id)
        with self._open() as (db, _):
            row = db.execute(
                "SELECT record FROM leads WHERE lead_id=? AND organization_id=?",
                (ident, self.scope.organization_id),
            ).fetchone()
            return _LeadRecord.model_validate_json(row[0]) if row else None

    def _candidate(self, raw: bytes, workflow: SourceHandoffResult):
        workflow = SourceHandoffResult.model_validate(workflow, by_name=True)
        source = parse_untrusted_source(raw)
        payload = source.payload
        receipt = workflow.source_receipt
        if (
            not isinstance(payload, FormPayload)
            or workflow.workflow_outcome != "accepted"
            or workflow.actions
        ):
            raise LeadRecordRefused()
        if (
            receipt.host_id,
            receipt.organization_id,
            receipt.namespace_id,
            receipt.event_id,
            receipt.payload_digest,
            receipt.recovery_deadline,
        ) != (
            self.scope.host_id,
            self.scope.organization_id,
            payload.source.namespace_id,
            payload.event_id,
            payload_digest(source),
            payload.retention.recovery_deadline,
        ) or (source.authorization.host_id, payload.organization_id) != (
            self.scope.host_id,
            self.scope.organization_id,
        ):
            raise LeadRecordRefused()
        snapshot = payload.snapshot
        part = snapshot.part
        binding = _FormBinding(
            template_id=snapshot.template_id, part_id=part.part_id, part_sha256=part.sha256
        )
        return payload.source, snapshot, binding, receipt

    @_boundary
    def commit(
        self, *, authorize: Callable[[], tuple[bytes, SourceHandoffResult]]
    ) -> LeadReference:
        """Called only by trusted host composition after both earlier commits.

        The callback runs after obtaining the lead writer lock, on replay too.
        A receipt, an envelope, or a caller-supplied field model grants nothing.
        """
        with self._open(write=True) as (db, stage_set_id):
            raw, workflow = authorize()
            source, snapshot, binding, receipt = self._candidate(raw, workflow)
            row = db.execute(
                f"SELECT record FROM leads WHERE {_SOURCE_LOOKUP}",
                (self.scope.organization_id, *(getattr(source, name) for name in _SOURCE_COLUMNS)),
            ).fetchone()
            if row is not None:
                original = _LeadRecord.model_validate_json(row[0])
                if original.binding != binding:
                    raise LeadRecordConflict()
                return original.reference
            invalid_form = False
            try:
                fields = parse_synthetic_form(snapshot)
            except FormInputError:
                invalid_form = True
            if invalid_form:
                raise LeadRecordRefused()
            stage = db.execute(
                "SELECT stage_id FROM lead_stages WHERE stage_set_id=? AND position=0",
                (stage_set_id,),
            ).fetchone()
            if stage is None:
                raise SourceStoreUnavailable()
            record = _LeadRecord(
                binding=binding,
                reference=LeadReference(
                    organization_id=self.scope.organization_id, lead_id=str(uuid4())
                ),
                source=source,
                source_receipt=receipt,
                fields_version="1.0",
                fields=fields,
                review_state="NEEDS_REVIEW",
                stage_set_id=stage_set_id,
                stage_id=stage[0],
            )
            db.execute(
                "INSERT INTO leads (record) VALUES (?)", (_canonical(record.model_dump()).decode(),)
            )
            return record.reference
