"""Private offline conformance values; never authentication or qualification.

No installed configuration, clocks, filesystem, network or native entrypoints.
The model owner derives schemas; consumers must revalidate untrusted packets.
"""

import json
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    model_validator,
)

from connect_automate.entitlement import UuidV4

PACKET_BYTES = 1048576
Token = Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]
Code = Annotated[StrictStr, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
Digest = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
Commit = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{40}$")]
# Literal[False] alone admits numeric 0 even under Pydantic strict=True.
FalseOnly = Annotated[Literal[False], BeforeValidator(TypeAdapter(StrictBool).validate_python)]


class ProtocolInputError(ValueError):
    def __init__(self):
        super().__init__("invalid offline protocol input")


def _unique(values):
    if len(values) != len(set(values)):
        raise ValueError("duplicate identity")
    return values


Identifiers = Annotated[
    list[Token], Field(min_length=1, max_length=64, json_schema_extra={"uniqueItems": True}),
    AfterValidator(_unique),
]


class Closed(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always",
        hide_input_in_errors=True,
    )


class Artifact(Closed):
    alias: Token
    sha256: Digest


class OfflineCase(Closed):
    case_id: Token
    platform: Literal["linux", "windows"]
    outcome: Literal["PASS", "FAIL", "STOP"]
    expected_code: Code
    actual_code: Code
    assertion_ids: Identifiers
    fixture_sha256: Digest
    duration_ns: Annotated[StrictInt, Field(ge=0, le=180000000000)]
    artifacts: Annotated[list[Artifact], Field(max_length=64)]

    @model_validator(mode="after")
    def unique_artifacts(self):
        _unique([a.alias for a in self.artifacts])
        return self


class Packet(Closed):
    version: Literal["owner-harness/1"]
    evidence_class: Literal["OFFLINE_CONFORMANCE"]
    qualification_pass: FalseOnly
    contract_commit: Commit
    harness_commit: Commit
    run_id: UuidV4
    dependency_lock_sha256: Digest


class OfflineRun(Packet):
    case_ids: Identifiers
    fixtures: Annotated[list[Artifact], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def unique_fixtures(self):
        _unique([a.alias for a in self.fixtures])
        return self


class OfflineResult(Packet):
    cases: Annotated[list[OfflineCase], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def unique_cases(self):
        _unique([c.case_id for c in self.cases])
        return self


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolInputError()
        result[key] = value
    return result


def _nonfinite(_):
    raise ProtocolInputError()


def _json(raw: bytes, limit: int):
    if type(raw) is not bytes or len(raw) > limit:
        raise ProtocolInputError()
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_members, parse_constant=_nonfinite)


def parse_packet(raw: bytes, kind: Literal["run", "result"]):
    try:
        model = {"run": OfflineRun, "result": OfflineResult}[kind]
        return model.model_validate(_json(raw, PACKET_BYTES))
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ProtocolInputError() from None


def packet_bytes(packet: OfflineRun | OfflineResult) -> bytes:
    try:
        if type(packet) not in (OfflineRun, OfflineResult):
            raise ProtocolInputError()
        validated = type(packet).model_validate(packet)
        raw = canonical(validated.model_dump())
        if len(raw) > PACKET_BYTES:
            raise ProtocolInputError()
        return raw
    except (ValueError, TypeError, RecursionError):
        raise ProtocolInputError() from None


def schemas() -> dict[str, bytes]:
    return {
        name + ".schema.json": (json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                **model.model_json_schema(),
            },
            indent=2, sort_keys=True,
        ) + "\n").encode("utf-8")
        for name, model in (("run", OfflineRun), ("result", OfflineResult))
    }
