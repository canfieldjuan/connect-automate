"""Pure, shared receipt projection. Parsing is never authentication or admission."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BeforeValidator, model_validator

from ..entitlement import UuidV4
from .source import Digest, Instant, _Closed


def _decision_time(value: object) -> str:
    if (
        type(value) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value)
        is None
    ):
        raise ValueError("invalid decision time")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


class ReceiptReference(_Closed):
    admission_id: UuidV4
    host_id: UuidV4
    organization_id: UuidV4
    namespace_id: UuidV4
    event_id: UuidV4
    payload_digest: Digest
    accepted_at: Annotated[str, BeforeValidator(_decision_time)]
    recovery_deadline: Instant

    @model_validator(mode="after")
    def _interval(self):
        if datetime.fromisoformat(self.accepted_at) >= datetime.fromisoformat(
            self.recovery_deadline
        ):
            raise ValueError("empty custody interval")
        return self
