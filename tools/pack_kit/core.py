"""Strict business-spec compiler and the mandatory publisher-signing gate."""

from __future__ import annotations

import base64
import binascii
import json
import tomllib
from typing import Annotated, BinaryIO

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
)

from connect_automate.automate import (
    ACTION_KINDS,
    MAX_PACK_BYTES,
    ActionEmit,
    ConnectInvokeCapability,
    ConnectInvokeRequest,
    DefinitionError,
    PackManifest,
    canonical_workflow,
    load_pack,
    parse_workflow,
)
from connect_automate.automate.definition import (
    ALLOWED_OPS,
    MAX_CONDITIONS,
    MAX_DEFINITION_BYTES,
    Condition,
)
from connect_automate.entitlement import KeyId, UuidV4

SPEC_LIMIT = 64 * 1024
ARTIFACT_LIMIT = 128 * 1024
ARCHETYPE = "approve-then-act"
STAGES = ["ready", "acting", "reporting", "completed", "failed", "declined"]
FAILURE_REQUEST = {
    "title": "Pack action failed",
    "body": "Inspect the durable action outcome before starting a new record.",
}


class KitError(ValueError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InputSpec(StrictModel):
    media_type: StrictStr
    filename: StrictStr
    content: StrictStr


class InvokeSpec(StrictModel):
    capability: ConnectInvokeCapability
    input: InputSpec
    parameters: dict[str, StrictStr | StrictInt | StrictBool] = Field(default_factory=dict)


class Spec(StrictModel):
    format_version: Annotated[StrictInt, Field(ge=1, le=1)]
    archetype: StrictStr
    pack_id: UuidV4
    pack_version: Annotated[StrictInt, Field(ge=1)]
    name: Annotated[StrictStr, Field(min_length=1, max_length=80)]
    conditions: list[Condition] = Field(default_factory=list, max_length=MAX_CONDITIONS - 1)
    invoke: InvokeSpec
    result_action: ActionEmit


def canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise KitError(3, "invalid input") from exc


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate member")
        value[key] = item
    return value


def json_object(raw: bytes, limit: int) -> dict:
    if len(raw) > limit:
        raise KitError(3, "input too large")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if not isinstance(value, dict):
            raise ValueError("not object")
        return value
    except (ValueError, RecursionError) as exc:
        raise KitError(3, "invalid input") from exc


def parse_spec(raw: bytes) -> dict:
    if len(raw) > SPEC_LIMIT:
        raise KitError(3, "input too large")
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise KitError(3, "invalid input") from exc


def _vocabulary(value: dict) -> None:
    result = value.get("result_action")
    if (
        isinstance(result, dict)
        and isinstance(result.get("action"), str)
        and result["action"] not in ACTION_KINDS
    ):
        raise KitError(3, "unsupported vocabulary")
    conditions = value.get("conditions", [])
    if isinstance(conditions, list):
        for condition in conditions:
            if isinstance(condition, dict):
                field, op = condition.get("field"), condition.get("op")
                if isinstance(field, str) and field not in ALLOWED_OPS:
                    raise KitError(3, "unsupported vocabulary")
                if isinstance(op, str) and isinstance(field, str) and op not in ALLOWED_OPS[field]:
                    raise KitError(3, "unsupported vocabulary")
    invoke = value.get("invoke")
    if isinstance(invoke, dict) and "capability" in invoke:
        try:
            ConnectInvokeCapability.model_validate(invoke["capability"])
        except ValidationError as exc:
            raise KitError(3, "unsupported vocabulary") from exc


def _spec(value: dict) -> Spec:
    if not isinstance(value, dict):
        raise KitError(3, "invalid input")
    if isinstance(value.get("archetype"), str) and value["archetype"] != ARCHETYPE:
        raise KitError(3, "unknown archetype")
    _vocabulary(value)
    try:
        spec = Spec.model_validate(value)
        # Business result templates are literal: an overlay object may not bind runtime data.
        if spec.result_action.action == "connect.invoke":
            request = spec.result_action.request
            if not isinstance(request["input"]["content_base64"], str) or any(
                isinstance(v, dict) for v in request["parameters"].values()
            ):
                raise KitError(3, "invalid input")
        return spec
    except ValidationError as exc:
        message = (
            "unsupported vocabulary"
            if any(
                e["loc"][:1] == ("result_action",) and e["type"] != "missing" for e in exc.errors()
            )
            else "invalid input"
        )
        raise KitError(3, message) from exc


def build(value: dict) -> bytes:
    spec = _spec(value)
    try:
        content = spec.invoke.input.content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise KitError(3, "invalid input") from exc
    invoke = {
        "capability": spec.invoke.capability.model_dump(),
        "input": {
            "artifact_id": spec.pack_id,
            "media_type": spec.invoke.input.media_type,
            "filename": spec.invoke.input.filename,
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
        "parameters": spec.invoke.parameters,
        "confirmed": True,
    }
    try:
        invoke = ConnectInvokeRequest.model_validate(invoke).model_dump(
            mode="json", exclude_none=True
        )
    except ValidationError as exc:
        raise KitError(3, "unsupported vocabulary") from exc
    rows = [
        ("approve", "ready", "acting", [{"action": "connect.invoke", "request": invoke}]),
        ("decline", "ready", "declined", []),
        ("complete", "acting", "reporting", [spec.result_action.model_dump(mode="json")]),
        ("finish", "reporting", "completed", []),
        (
            "fail",
            ["acting", "reporting"],
            "failed",
            [{"action": "notify.local", "request": FAILURE_REQUEST}],
        ),
    ]
    definitions = []
    for name, previous, destination, actions in rows:
        conditions = [
            {
                "field": "record.stage",
                "op": "in" if isinstance(previous, list) else "equals",
                "value": previous,
            }
        ]
        if name == "approve":
            conditions += [c.model_dump(mode="json") for c in spec.conditions]
        definitions.append(
            {
                "name": name,
                "trigger": {"source_kind": "operator.decision", "decision": name},
                "conditions": conditions,
                "effects": [
                    {"kind": "record.transition", "to_stage": destination},
                    {"kind": "overlay.set", "key": "pack-kit.status", "value": destination},
                ],
                "actions": actions,
            }
        )
    try:
        workflow = parse_workflow(
            canonical(
                {
                    "name": spec.name,
                    "stages": STAGES,
                    "initial_stage": "ready",
                    "definitions": definitions,
                }
            )
        )
        workflow_data = json.loads(canonical_workflow(workflow))
        manifest = PackManifest.model_validate(
            {
                "format_version": 1,
                "pack_id": spec.pack_id,
                "pack_version": spec.pack_version,
                "workflow": workflow_data,
            }
        )
    except (DefinitionError, ValidationError) as exc:
        message = (
            "input too large"
            if f"exceeds {MAX_DEFINITION_BYTES} bytes" in str(exc)
            else "invalid input"
        )
        raise KitError(3, message) from exc
    return canonical(
        {
            "kit_format_version": 1,
            "archetype": ARCHETYPE,
            "spec": spec.model_dump(mode="json"),
            "manifest": manifest.model_dump(mode="json"),
        }
    )


def validate_artifact(raw: bytes) -> dict:
    data = json_object(raw, ARTIFACT_LIMIT)
    if type(data.get("kit_format_version")) is not int or data["kit_format_version"] != 1:
        raise KitError(3, "invalid input")
    candidate = build(data.get("spec"))
    if candidate != raw:
        raise KitError(4, "build artifact mismatch")
    return data


def _envelope(payload: bytes, key: Ed25519PrivateKey, key_id: str) -> bytes:
    """Internal byte formatter, also used by the disposable offline test authorities."""
    raw = canonical(
        {
            "format_version": 1,
            "key_id": key_id,
            "payload_base64url": encoded(payload),
            "signature_base64url": encoded(key.sign(payload)),
        }
    )
    if len(raw) > MAX_PACK_BYTES:
        raise KitError(3, "input too large")
    return raw


def check(raw: bytes, catalogue: bytes) -> dict:
    # Lazy import keeps the compiler independent of the test harness.
    from .sandbox import run_check

    return run_check(raw, catalogue)


def sign(raw: bytes, catalogue: bytes, key_id: str, public: str, seed_stream: BinaryIO) -> bytes:
    # No receipt/cache/flag may authorize this step. Hold and check the exact bytes signed.
    check(raw, catalogue)
    data = validate_artifact(raw)
    try:
        TypeAdapter(KeyId).validate_python(key_id)
        if not isinstance(public, str):
            raise ValueError("public key type")
        expected = base64.b64decode(
            public + "=" * (-len(public) % 4), altchars=b"-_", validate=True
        )
        if len(expected) != 32 or encoded(expected) != public:
            raise ValueError("public key format")
        if getattr(seed_stream, "isatty", lambda: False)():
            raise ValueError("interactive seed input")
        seed = seed_stream.read(33)
        if len(seed) != 32:
            raise ValueError("seed length")
        key = Ed25519PrivateKey.from_private_bytes(seed)
        if key.public_key().public_bytes_raw() != expected:
            raise ValueError("key mismatch")
    except (ValueError, TypeError, binascii.Error, OSError) as exc:
        raise KitError(6, "invalid signing key") from exc
    signed = _envelope(canonical(data["manifest"]), key, key_id)
    load_pack(signed, keys={key_id: expected})
    return signed


def new_spec(archetype: str, pack_id: str, name: str, pack_version: int) -> bytes:
    # UTF-8 JSON quoting is a TOML basic-string subset. Keep non-BMP scalars literal:
    # ASCII JSON surrogate-pair escapes are not legal TOML Unicode escapes.
    def quoted(value):
        return canonical(value).decode("utf-8")

    text = (
        f"format_version = 1\narchetype = {quoted(archetype)}\n"
        f"pack_id = {quoted(pack_id)}\npack_version = {pack_version}\nname = {quoted(name)}\n"
        "# Edit the business fields below; the lifecycle is generated.\nconditions = []\n\n"
        '[invoke.capability]\nid = "sample.process"\nversion = "1.0"\n\n'
        '[invoke.input]\nmedia_type = "text/plain"\nfilename = "request.txt"\n'
        'content = "Synthetic request"\n\n'
        '[invoke.parameters]\nmode = "review"\n\n[result_action]\naction = "notify.local"\n\n'
        '[result_action.request]\ntitle = "Result reviewed"\n'
        'body = "The operator reviewed the action outcome."\n'
    ).encode()
    build(parse_spec(text))
    return text
