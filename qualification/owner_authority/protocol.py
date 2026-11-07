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

from cryptography.exceptions import InvalidSignature
from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from connect_automate.entitlement import UuidV4, verify_signature

PACKET_BYTES = 1048576
CASE_NS = 180_000_000_000
CONTRACT_COMMIT = "ba7f7cf7db9b14c050d87021fddd7333ff149851"
Token = Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]
Code = Annotated[StrictStr, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
Digest = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
Commit = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{40}$")]
# Literal[False] alone admits numeric 0 even under Pydantic strict=True.
FalseOnly = Annotated[Literal[False], BeforeValidator(TypeAdapter(StrictBool).validate_python)]


class ProtocolInputError(ValueError):
    def __init__(self):
        super().__init__("invalid offline protocol input")


class ContractMismatchError(ProtocolInputError):
    """Sole schema error is an otherwise valid but different profile."""


class MalformedConsumeRequest(ProtocolInputError):
    """Structural request wire rejection only; never a verification failure."""


class MalformedConsumeResponse(ProtocolInputError):
    """Recognized fixed diagnostic; no operation or completion claim."""


class ManifestUnavailable(ProtocolInputError):
    """Absent active configuration or a verified expired manifest only."""


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
    duration_ns: Annotated[StrictInt, Field(ge=0, le=CASE_NS)]
    artifacts: Annotated[list[Artifact], Field(max_length=64)]

    @model_validator(mode="after")
    def unique_artifacts(self):
        _unique([a.alias for a in self.artifacts])
        return self


class Packet(Closed):
    version: Literal["owner-harness/1"]
    evidence_class: Literal["OFFLINE_CONFORMANCE"]
    qualification_pass: FalseOnly
    contract_commit: Annotated[
        Literal[CONTRACT_COMMIT], BeforeValidator(TypeAdapter(Commit).validate_python),
    ]
    harness_commit: Commit
    run_id: UuidV4
    dependency_lock_sha256: Digest


class OfflineRun(Packet):
    case_ids: Identifiers
    fixtures: Annotated[list[Artifact], Field(min_length=1, max_length=64)]

    @field_validator("fixtures")
    @classmethod
    def unique_fixtures(cls, values):
        _unique([a.alias for a in values])
        return values


class OfflineResult(Packet):
    cases: Annotated[list[OfflineCase], Field(min_length=1, max_length=64)]

    @field_validator("cases")
    @classmethod
    def unique_cases(cls, values):
        _unique([c.case_id for c in values])
        return values


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
    except ValidationError as error:
        errors = error.errors(include_input=False, include_url=False)
        if all(e["loc"] == ("contract_commit",) and e["type"] == "literal_error" for e in errors):
            raise ContractMismatchError() from None
        raise ProtocolInputError() from None
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


RESPONSE_BYTES = 4096
FRAME_BYTES = 8192
MEDIA_CHARS = 256
BODY_CHARS = (RESPONSE_BYTES * 4 + 2) // 3


class FixtureResponse(Closed):
    """Private synthetic metadata, never an HTTP transport qualification."""

    status: Annotated[StrictInt, Field(ge=100, le=599)]
    content_type: Annotated[StrictStr, Field(max_length=MEDIA_CHARS)] | None
    body_base64url: Annotated[
        StrictStr, Field(max_length=BODY_CHARS, pattern=r"^[A-Za-z0-9_-]*$"),
        AfterValidator(lambda value: (_decoded(value, RESPONSE_BYTES), value)[1]),
    ]

    @property
    def body(self):
        return _decoded(self.body_base64url, RESPONSE_BYTES)


def fixture_response(status, content_type, body):
    try:
        value = FixtureResponse(status=status, content_type=content_type,
                                body_base64url=base64.urlsafe_b64encode(body).rstrip(b"=").decode())
        return canonical(value.model_dump())
    except (ValueError, TypeError):
        raise ProtocolInputError() from None


def parse_fixture_response(raw):
    try:
        return _wire(raw, FixtureResponse, FRAME_BYTES)
    except (ValueError, TypeError, RecursionError):
        raise ProtocolInputError() from None


REFUSAL_STATUS = {
    "OWNER_AUTHORIZATION_INVALID": 403, "OWNER_AUTHORIZATION_REVOKED": 403,
    "OWNER_BINDING_CONFLICT": 409, "OWNER_AUTHORIZATION_EXPIRED": 410,
    "OWNER_CLOCK_SKEW": 422, "LICENSING_UNAVAILABLE": 503,
}


def admit_fixture_response(raw):
    """Admit metadata before the existing receipt/refusal verification owner."""
    response = parse_fixture_response(raw)
    if (response.status == 400 and response.content_type == "application/json"
            and response.body == MALFORMED_BODY):
        raise MalformedConsumeResponse()
    if response.content_type != "application/json":
        raise ProtocolInputError()
    if response.status != 200:
        refusal = parse_refusal(response.body)
        if response.status != REFUSAL_STATUS[refusal.code]:
            raise ProtocolInputError()
    return response.body


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
    # Native URL parsing normalizes IPv4 alternate spellings, IPv6, case and
    # default ports. Compare with its canonical HTTPS origin, never raw netloc.
    host = AnyHttpUrl(value).host
    if not host.startswith("["):
        try:
            ipaddress.IPv4Address(host)
        except ValueError:
            pass
        else:
            raise ValueError("IPv4 is not an activation DNS host")
        labels = host.split(".")
        if any(
            not 1 <= len(label) <= 63 or not label[0].isalnum() or not label[-1].isalnum()
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in label)
            for label in labels
        ):
            raise ValueError("invalid activation DNS host")
    if value != "https://" + host:
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


class RenewalSelection(Closed):
    """Host-derived selection; equality must be rechecked by the store writer."""

    operation_id: UuidV4
    pending_binding_sha256: Digest
    original_manifest_sha256: Digest
    installed_manifest_sha256: Digest


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


class MalformedConsumeDiagnostic(Closed):
    code: Literal["MALFORMED_CONSUME_REQUEST"]
    version: Literal["owner-bootstrap/1"]


MALFORMED_BODY = canonical(MalformedConsumeDiagnostic(
    code="MALFORMED_CONSUME_REQUEST", version="owner-bootstrap/1").model_dump())


def parse_consume_request(raw):
    try:
        return _wire(raw, ConsumeRequest, 8192)
    except (ValueError, TypeError, RecursionError):
        raise MalformedConsumeRequest() from None


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


def _verify_current_manifest(raw: bytes | None, keys: Mapping[str, bytes],
                             release_ids: frozenset[str], now: datetime, *,
                             unavailable_error: type[ProtocolInputError]):
    """One window rule; the owning entry point supplies its failure category."""
    if type(now) is not datetime or now.tzinfo is not UTC:
        raise ProtocolInputError()
    if raw is None:
        raise unavailable_error()
    manifest = verify_signed(raw, "manifest", keys, release_ids)
    if now < _date(manifest.issued_at):
        raise ProtocolInputError()
    if now >= _date(manifest.expires_at):
        raise unavailable_error()
    return manifest


def verify_active_manifest(raw: bytes | None, keys: Mapping[str, bytes],
                           release_ids: frozenset[str], now: datetime):
    """Only unavailable active configuration receives the availability category."""
    return _verify_current_manifest(raw, keys, release_ids, now,
                                    unavailable_error=ManifestUnavailable)


def check_manifest_renewal(candidate_raw: bytes, original_raw: bytes, installed_raw: bytes,
                           keys: Mapping[str, bytes], release_ids: frozenset[str], now: datetime):
    """Verify signed policy and monotonic intervals; no selection or publication effect."""
    original = verify_signed(original_raw, "manifest", keys, release_ids)
    installed = verify_signed(installed_raw, "manifest", keys, release_ids)
    candidate = _verify_current_manifest(candidate_raw, keys, release_ids, now,
                                         unavailable_error=ProtocolInputError)
    # Version/purpose are constants in the closed signed manifest model.
    # Historical verification does not require an unexpired original/installed interval.
    for prior in (original, installed):
        if (candidate.origin != prior.origin
                or set(candidate.claim_key_ids) != set(prior.claim_key_ids)
                or set(candidate.receipt_key_ids) != set(prior.receipt_key_ids)
                or _date(candidate.issued_at) < _date(prior.issued_at)
                or _date(candidate.expires_at) <= _date(prior.expires_at)):
            raise ProtocolInputError()
    return candidate


def check_consume_request(raw: bytes, manifest_raw: bytes, keys: Mapping[str, bytes],
                          release_ids: frozenset[str], issuer_now: datetime):
    """Check signed wire/attempt time only; expiry/new-consume decisions need a ledger."""
    request = parse_consume_request(raw)
    try:
        manifest = verify_active_manifest(manifest_raw, keys, release_ids, issuer_now)
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
    except ManifestUnavailable:
        raise
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


class FixtureObservation(Closed):
    """Synthetic principal reference and time, never acquired native identity."""

    evidence_class: Literal["OFFLINE_CONFORMANCE"]
    qualification_pass: FalseOnly
    principal_ref: Token
    authority_generation: Generation
    active: StrictBool
    authenticated_at_ns: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)]
    observed_at_ns: Annotated[StrictInt, Field(ge=0, le=9223372036854775807)]


class FixtureHostResult(Closed):
    evidence_class: Literal["OFFLINE_CONFORMANCE"]
    qualification_pass: FalseOnly
    operation_id: UuidV4
    committed: StrictBool
    code: Literal["COMMITTED", "PENDING", "OWNER_AUTHORIZATION_REQUIRED",
                  "OWNER_AUTHORIZATION_INVALID", "OWNER_AUTHORIZATION_EXPIRED",
                  "OWNER_AUTHORIZATION_REVOKED", "OWNER_BINDING_CONFLICT", "OWNER_CLOCK_SKEW",
                  "LICENSING_UNAVAILABLE", "NATIVE_AUTH_DENIED", "NATIVE_SESSION_INACTIVE"]

    @model_validator(mode="after")
    def truthful_commit(self):
        if self.code == "COMMITTED" and not self.committed:
            raise ValueError("uncommitted fixture result")
        return self


class RunnableCase(Closed):
    kind: Literal["OFFLINE_CONFORMANCE"]
    case_id: Literal["lost-response-replay", "revoked-claim", "inactive-session",
                     "malformed-request-refusal"]
    requirement: Token
    expected_code: Code
    assertion_ids: Identifiers
    capability: Literal["disposable-fixtures"]


class DeferredCase(Closed):
    kind: Literal["NOT_RUN", "BLOCKED"]
    case_id: Token
    requirement: Token


class CaseInventory(Closed):
    version: Literal["owner-harness-cases/1"]
    cases: Annotated[list[RunnableCase | DeferredCase], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def unique_cases(self):
        _unique([case.case_id for case in self.cases])
        return self


class CaseObservation(Closed):
    actual_code: Code
    assertions: Annotated[dict[Token, StrictBool], Field(min_length=1, max_length=64)]


def parse_inventory(raw: bytes):
    try:
        return CaseInventory.model_validate(_json(raw, PACKET_BYTES))
    except (ValueError, TypeError, RecursionError):
        raise ProtocolInputError() from None


def parse_observation(raw: bytes):
    try:
        return CaseObservation.model_validate(_json(raw, PACKET_BYTES))
    except (ValueError, TypeError, RecursionError):
        raise ProtocolInputError() from None
