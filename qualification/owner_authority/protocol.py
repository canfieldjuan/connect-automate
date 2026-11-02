"""Private offline conformance values; never authentication or qualification.

No installed configuration, clocks, filesystem, network or native entrypoints.
The model owner derives schemas; consumers must revalidate untrusted packets.
"""

import base64
import hashlib
import ipaddress
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Literal, NamedTuple
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
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

from connect_automate.entitlement import UuidV4, verify_signature

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


# B0-I conformance only. No issuer/host ledger, native facts or network client.
class WireBudget(NamedTuple):
    payload: int
    envelope: int

    @property
    def encoded(self):
        return (self.payload * 4 + 2) // 3


SMALL = WireBudget(1536, 2560)
MANIFEST = WireBudget(3072, 4608)
KeyId = Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]
Generation = Annotated[StrictInt, Field(ge=1, le=2147483647)]
KeyIds = Annotated[
    list[KeyId], Field(min_length=1, max_length=16, json_schema_extra={"uniqueItems": True}),
    AfterValidator(_unique),
]


def _decoded(value: str, limit: int) -> bytes:
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if len(decoded) > limit or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != value:
        raise ValueError("invalid canonical encoding")
    return decoded


Signature = Annotated[
    StrictStr, Field(min_length=86, max_length=86, pattern=r"^[A-Za-z0-9_-]+$"),
    AfterValidator(lambda value: (_decoded(value, 64), value)[1]),
]
PublicKey = Annotated[
    StrictStr, Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$"),
    AfterValidator(lambda value: (_decoded(value, 32), value)[1]),
]


def _time(value):
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


Instant = Annotated[
    StrictStr, Field(min_length=20, max_length=20,
                     pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
                     json_schema_extra={"format": "date-time"}),
    AfterValidator(_time),
]


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _origin(value):
    uri = urlsplit(value)
    host = uri.hostname
    if (uri.scheme != "https" or uri.username is not None or uri.password is not None
            or not host or uri.path or uri.query or uri.fragment or uri.geturl() != value
            or uri.port not in (None, 443)):
        raise ValueError("invalid activation origin")
    if ":" in host:
        address = ipaddress.IPv6Address(host)
        if address.scope_id is not None:
            raise ValueError("scoped host is not an activation origin")
        canonical_host = "[" + address.compressed + "]"
    else:
        # URI parsing above; these are the DNS label grammar and length rules,
        # not a second URL recognizer. No escaped host or Unicode is normalized.
        labels = host.removesuffix(".").split(".")
        if len(host) > 253 or any(
            not 1 <= len(label) <= 63 or not label[0].isalnum() or not label[-1].isalnum()
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in label)
            for label in labels
        ):
            raise ValueError("invalid activation DNS host")
        canonical_host = host
    port = "" if uri.port is None else ":443"
    if value != "https://" + canonical_host + port:
        raise ValueError("noncanonical activation origin")
    return value


class ActivationManifest(Closed):
    version: Literal["owner-bootstrap/1"]
    purpose: Literal["owner-bootstrap-activation"]
    origin: Annotated[StrictStr, Field(min_length=1, max_length=255,
                                     pattern=r"^https://[!-~]+$",
                                     json_schema_extra={"format": "uri"}),
                      AfterValidator(_origin)]
    claim_key_ids: KeyIds
    receipt_key_ids: KeyIds
    issued_at: Instant
    expires_at: Instant

    @model_validator(mode="after")
    def validity(self):
        if not 0 < (_date(self.expires_at) - _date(self.issued_at)).total_seconds() <= 2592000:
            raise ValueError("invalid manifest interval")
        return self


class OwnerClaim(Closed):
    version: Literal["owner-bootstrap/1"]
    purpose: Literal["owner-bootstrap"]
    claim_id: UuidV4
    organization_id: UuidV4
    entitlement_id: UuidV4
    generation: Generation
    issued_at: Instant
    not_before: Instant
    expires_at: Instant

    @model_validator(mode="after")
    def validity(self):
        start, eligible, end = map(_date, (self.issued_at, self.not_before, self.expires_at))
        if not start <= eligible < end or (end - start).total_seconds() > 86400:
            raise ValueError("invalid owner claim interval")
        return self


class ConsumeBinding(Closed):
    version: Literal["owner-bootstrap/1"]
    operation_id: UuidV4
    installation_id: UuidV4
    host_id: UuidV4
    organization_id: UuidV4
    claim_id: UuidV4
    entitlement_id: UuidV4
    generation: Generation
    claim_sha256: Digest
    principal_commitment: Digest
    initialization_sha256: Digest
    installation_public_key: PublicKey


class SmallEnvelope(Closed):
    version: Literal["owner-bootstrap/1"]
    key_id: KeyId
    payload_base64url: Annotated[StrictStr, Field(min_length=1, max_length=SMALL.encoded,
                                                pattern=r"^[A-Za-z0-9_-]+$")]
    signature_base64url: Signature


class ManifestEnvelope(SmallEnvelope):
    payload_base64url: Annotated[StrictStr, Field(min_length=1, max_length=MANIFEST.encoded,
                                                pattern=r"^[A-Za-z0-9_-]+$")]


class ConsumeRequest(Closed):
    version: Literal["owner-bootstrap/1"]
    owner_claim: SmallEnvelope
    binding: ConsumeBinding
    attempt_id: UuidV4
    requested_at: Instant
    installation_signature: Signature


class ConsumedReceipt(Closed):
    version: Literal["owner-bootstrap/1"]
    purpose: Literal["owner-bootstrap-receipt"]
    state: Literal["CONSUMED"]
    receipt_id: UuidV4
    binding: ConsumeBinding
    consumed_at: Instant


class Refusal(Closed):
    version: Literal["owner-bootstrap/1"]
    code: Literal["OWNER_AUTHORIZATION_INVALID", "OWNER_AUTHORIZATION_EXPIRED",
                  "OWNER_AUTHORIZATION_REVOKED", "OWNER_BINDING_CONFLICT",
                  "OWNER_CLOCK_SKEW", "LICENSING_UNAVAILABLE"]
    operation_id: UuidV4
    completion: Literal["NOT_COMMITTED", "UNKNOWN"]

    @model_validator(mode="after")
    def clock_completion(self):
        if self.code == "OWNER_CLOCK_SKEW" and self.completion != "NOT_COMMITTED":
            raise ValueError("invalid clock refusal")
        return self


class ClockSkewError(RuntimeError):
    code = "OWNER_CLOCK_SKEW"
    completion = "NOT_COMMITTED"

    def __init__(self):
        super().__init__("owner attempt outside clock window")


def prefix(kind: Literal["manifest", "claim", "consume", "receipt"]):
    name = {"manifest": "activation", "claim": "claim", "consume": "consume", "receipt": "receipt"}
    return ("local-connect.owner-" + name[kind] + ".v1\0").encode("ascii")


def _wire(raw, model, limit):
    parsed = model.model_validate(_json(raw, limit))
    if canonical(parsed.model_dump()) != raw:
        raise ProtocolInputError()
    return parsed


def verify_signed(raw: bytes, kind: Literal["manifest", "claim", "receipt"],
                  keys: Mapping[str, bytes], allowed_ids: frozenset[str]):
    """Explicit fixture trust only. A parsed value never grants local authority."""
    try:
        model, envelope_model, budget = {
            "manifest": (ActivationManifest, ManifestEnvelope, MANIFEST),
            "claim": (OwnerClaim, SmallEnvelope, SMALL),
            "receipt": (ConsumedReceipt, SmallEnvelope, SMALL),
        }[kind]
        envelope = _wire(raw, envelope_model, budget.envelope)
        if envelope.key_id not in allowed_ids:
            raise ProtocolInputError()
        payload = _decoded(envelope.payload_base64url, budget.payload)
        result = _wire(payload, model, budget.payload)
        verify_signature(keys, envelope.key_id, prefix(kind) + payload,
                         _decoded(envelope.signature_base64url, 64))
        if kind == "manifest" and any(
            key not in keys for key in result.claim_key_ids + result.receipt_key_ids
        ):
            raise ProtocolInputError()
        return result
    except (ValueError, TypeError, KeyError, RecursionError, InvalidSignature):
        raise ProtocolInputError() from None


def check_consume_request(raw: bytes, manifest_raw: bytes, keys: Mapping[str, bytes],
                          release_ids: frozenset[str], issuer_now: datetime):
    """Check signed wire/attempt time only; expiry/new-consume decisions need a ledger."""
    try:
        if type(issuer_now) is not datetime or issuer_now.tzinfo is not UTC:
            raise ProtocolInputError()
        manifest = verify_signed(manifest_raw, "manifest", keys, release_ids)
        if not _date(manifest.issued_at) <= issuer_now < _date(manifest.expires_at):
            raise ProtocolInputError()
        request = _wire(raw, ConsumeRequest, 8192)
        claim_raw = canonical(request.owner_claim.model_dump())
        claim = verify_signed(claim_raw, "claim", keys, frozenset(manifest.claim_key_ids))
        binding = request.binding
        if (any(getattr(binding, k) != getattr(claim, k)
                for k in ("claim_id", "organization_id", "entitlement_id", "generation"))
                or binding.claim_sha256 != hashlib.sha256(claim_raw).hexdigest()):
            raise ProtocolInputError()
        signed = {k: getattr(request, k) for k in ("version", "attempt_id", "requested_at")}
        signed["binding"] = binding.model_dump()
        verify_signature({"installation": _decoded(binding.installation_public_key, 32)},
                         "installation", prefix("consume") + canonical(signed),
                         _decoded(request.installation_signature, 64))
        if abs((issuer_now - _date(request.requested_at)).total_seconds()) > 60:
            raise ClockSkewError()
        return request, claim
    except (ValueError, TypeError, KeyError, RecursionError, InvalidSignature):
        raise ProtocolInputError() from None


def check_receipt(raw: bytes, request_raw: bytes, manifest_raw: bytes,
                  keys: Mapping[str, bytes], release_ids: frozenset[str], issuer_now: datetime):
    """Recheck the request instead of trusting a copied checked value. No publication."""
    request, claim = check_consume_request(request_raw, manifest_raw, keys, release_ids, issuer_now)
    manifest = verify_signed(manifest_raw, "manifest", keys, release_ids)
    receipt = verify_signed(raw, "receipt", keys, frozenset(manifest.receipt_key_ids))
    if (receipt.binding != request.binding
            or not _date(claim.not_before) <= _date(receipt.consumed_at) < _date(claim.expires_at)):
        raise ProtocolInputError()
    return receipt


def parse_refusal(raw: bytes):
    """Untrusted syntax only: an unsigned refusal is never non-consumption proof."""
    try:
        return _wire(raw, Refusal, 4096)
    except (ValueError, TypeError, RecursionError):
        raise ProtocolInputError() from None
