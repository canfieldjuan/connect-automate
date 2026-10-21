"""Strict, bounded source data. Source authentication belongs to the trusted host."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from functools import partial
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, TypeAdapter, model_validator

from .._event_limits import MAX_EVENT_BYTES as MAX_EVENT_BYTES
from ..entitlement import UuidV4
from ..lead_intake.receipts import ReceiptReference

MAX_MESSAGE_ID_BYTES = 512
MAX_SENDER_BYTES = 256
MAX_SUBJECT_BYTES = 1024
MAX_SCOPE_BYTES = 512
MAX_MAIL_FILTERS = 8
MIN_PERIOD_SECONDS = 60
MAX_PERIOD_SECONDS = 604800


class EventInputError(ValueError):
    def __init__(self):
        super().__init__("invalid event input")


class EventBindingError(ValueError):
    def __init__(self):
        super().__init__("invalid event binding")


class EventConflict(ValueError):
    def __init__(self):
        super().__init__("event identity conflict")


class AmbiguousEvent(ValueError):
    def __init__(self):
        super().__init__("event matched multiple definitions")


def _byte_string(value: object, *, minimum: int, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value.encode("utf-8")) <= maximum:
        raise ValueError("invalid bounded string")
    return value


def _bounded(minimum: int, maximum: int):
    return Annotated[str, BeforeValidator(partial(_byte_string, minimum=minimum, maximum=maximum))]


def timestamp(value: object) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is None
    ):
        raise ValueError("invalid UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _instant(value: object) -> str:
    timestamp(value)
    return value


UtcInstant = Annotated[str, BeforeValidator(_instant)]


class _Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


class LeadDeploymentScope(_Strict):
    host_id: UuidV4
    organization_id: UuidV4
    namespace_id: UuidV4


def lead_deployment_scope(scope: str, source_id: str) -> LeadDeploymentScope:
    """Single owner for the new kind's canonical deployment binding."""
    _byte_string(scope, minimum=1, maximum=MAX_SCOPE_BYTES)
    value = LeadDeploymentScope.model_validate(json.loads(scope, object_pairs_hook=_unique))
    canonical = json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":"))
    if scope != canonical or source_id != value.namespace_id:
        raise ValueError("invalid lead deployment scope")
    return value


class SourceBinding(_Strict):
    source_id: UuidV4
    source_kind: Literal["mail.received", "schedule.tick", "lead.source.received"]
    scope: _bounded(1, MAX_SCOPE_BYTES)

    @model_validator(mode="after")
    def _deployment(self):
        if self.source_kind == "lead.source.received":
            lead_deployment_scope(self.scope, self.source_id)
        return self


class MailEvent(_Strict):
    source_kind: Literal["mail.received"]
    message_id: _bounded(1, MAX_MESSAGE_ID_BYTES)
    received_at: UtcInstant
    sender: _bounded(1, MAX_SENDER_BYTES)
    subject: _bounded(0, MAX_SUBJECT_BYTES)


class ScheduleEvent(_Strict):
    source_kind: Literal["schedule.tick"]
    scheduled_at: UtcInstant


class LeadSourceEvent(_Strict):
    source_kind: Literal["lead.source.received"]
    schema_version: Literal["1.0"]
    source_receipt: ReceiptReference


class MailFilter(_Strict):
    field: Literal["sender", "subject"]
    op: Literal["equals", "contains"]
    value: _bounded(1, MAX_SUBJECT_BYTES)

    @model_validator(mode="after")
    def _validate(self):
        if self.field == "sender":
            if self.op != "equals":
                raise ValueError("unsupported filter operator")
            _byte_string(self.value, minimum=1, maximum=MAX_SENDER_BYTES)
        return self


Event = MailEvent | ScheduleEvent | LeadSourceEvent
_EVENT = TypeAdapter(Event)


def canonical_event(event: Event) -> bytes:
    return json.dumps(
        event.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate event member")
        result[key] = value
    return result


def parse_event(raw: bytes) -> Event:
    try:
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EVENT_BYTES:
            raise ValueError("invalid event size")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
        return _EVENT.validate_python(data)
    except (ValueError, TypeError, RecursionError):
        pass
    raise EventInputError()


def check_event_time(event: Event, now: datetime) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise EventInputError()
    if isinstance(event, LeadSourceEvent):
        instant = datetime.fromisoformat(event.source_receipt.accepted_at)
    else:
        instant = timestamp(
            event.received_at if isinstance(event, MailEvent) else event.scheduled_at
        )
    if instant > now:
        raise EventInputError()


def occurrence(event: Event) -> str:
    if isinstance(event, LeadSourceEvent):
        return event.source_receipt.event_id
    return event.message_id if isinstance(event, MailEvent) else event.scheduled_at
