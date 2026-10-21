"""Closed historical workflow results. These values never authorize submission."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .._event_limits import MAX_EVENT_BYTES
from ..entitlement import UuidV4
from .receipts import ReceiptReference
from .source import _Closed


class SourceHandoffUnknown(RuntimeError):
    """Neither source nor workflow absence is known; retry or look up the outcome."""

    def __init__(self):
        super().__init__("lead source handoff outcome unknown")


class _WorkflowResult(_Closed):
    schema_version: Literal["1.0"]
    source_receipt: ReceiptReference | None
    workflow_outcome: Literal["accepted", "no_match", "not_found"]
    workflow_applied: bool
    workflow_record_id: UuidV4 | None
    workflow_event_id: UuidV4 | None
    # The public wire projection retains the workflow vocabulary's stage bound.
    stage: Annotated[str, Field(min_length=1, max_length=80)] | None
    state_version: Annotated[int, Field(ge=1, le=9223372036854775807)] | None

    @model_validator(mode="after")
    def _projection(self):
        fields = (self.workflow_record_id, self.workflow_event_id, self.stage, self.state_version)
        if self.workflow_outcome == "accepted":
            if any(value is None for value in fields):
                raise ValueError("incomplete accepted projection")
        elif any(value is not None for value in fields) or self.workflow_applied:
            raise ValueError("unexpected workflow projection")
        if (self.source_receipt is None) != (self.workflow_outcome == "not_found"):
            raise ValueError("invalid source projection")
        if len(self.model_dump_json(by_alias=True).encode("utf-8")) > MAX_EVENT_BYTES:
            raise ValueError("result exceeds event byte limit")
        return self


class SourceHandoffResult(_WorkflowResult):
    schema_name: Literal["lead.source.handoff.result"] = Field(alias="schema")
    source_receipt: ReceiptReference
    source_applied: bool
    workflow_outcome: Literal["accepted", "no_match"]


class SourceHandoffLookup(_WorkflowResult):
    schema_name: Literal["lead.source.handoff.lookup"] = Field(alias="schema")

    @model_validator(mode="after")
    def _read_only(self):
        if self.workflow_applied:
            raise ValueError("lookup cannot apply a workflow")
        return self


def _workflow_projection(outcome):
    """Map the existing store result once; final model validation checks every variant."""
    if outcome is None:
        return dict(
            workflow_outcome="not_found",
            workflow_applied=False,
            workflow_record_id=None,
            workflow_event_id=None,
            stage=None,
            state_version=None,
        )
    if type(outcome.matched) is not bool or type(outcome.applied) is not bool:
        raise ValueError("invalid store flags")
    record = outcome.record
    return dict(
        workflow_outcome="accepted" if outcome.matched else "no_match",
        workflow_applied=outcome.applied,
        workflow_record_id=record.record_id if record is not None else None,
        workflow_event_id=outcome.event_id,
        stage=record.stage if record is not None else None,
        state_version=record.state_version if record is not None else None,
    )
