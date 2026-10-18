"""Explicit offline capability declarations and a closed in-memory Connect provider."""

from __future__ import annotations

import hashlib
import json
from email.parser import BytesParser
from email.policy import default
from typing import Annotated

import httpx
from pydantic import Field, StrictBool, StrictInt, StrictStr, ValidationError, model_validator

from connect_automate import connect

from .core import SPEC_LIMIT, KitError, StrictModel, canonical, json_object

INSTANCE = "22222222-2222-4222-8222-222222222222"
APP_ID = "pack-kit-fake"
BASE_URL = "http://127.0.0.1:32123/"
TOKEN = "A" * 43


class Accepted(StrictModel):
    media_type: connect.MediaType
    max_bytes: Annotated[StrictInt, Field(ge=1, le=1024 * 1024 * 1024)]


class Parameter(StrictModel):
    name: connect.Identifier
    value_type: StrictStr
    required: StrictBool
    label: Annotated[StrictStr, Field(min_length=1, max_length=80)]
    description: Annotated[StrictStr, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def supported(self):
        if self.value_type not in ("string", "integer", "boolean"):
            raise ValueError("unknown parameter type")
        return self


class Capability(StrictModel):
    id: connect.Identifier
    version: connect.CapabilityVersion
    accepts: list[Accepted] = Field(min_length=1, max_length=16)
    produces: list[connect.MediaType] = Field(min_length=1, max_length=16)
    parameters: list[Parameter] = Field(max_length=16)
    external_effects: StrictBool
    confirmation_required: StrictBool

    @model_validator(mode="after")
    def unique(self):
        for values in [
            [a.media_type for a in self.accepts],
            self.produces,
            [p.name for p in self.parameters],
        ]:
            if len(values) != len(set(values)):
                raise ValueError("duplicate declaration")
        return self

    def discovered(self):
        return connect.DiscoveredCapability(
            protocol_version=2,
            base_url=BASE_URL,
            token=TOKEN,
            app_id=APP_ID,
            app_name="Pack kit fake",
            app_version="1.0.0",
            instance_id=INSTANCE,
            capability_id=self.id,
            capability_version=self.version,
            action_label="Synthetic action",
            action_description="Offline check only",
            accepts=tuple(connect.AcceptedArtifactType(**a.model_dump()) for a in self.accepts),
            produces=tuple(self.produces),
            parameters=tuple(
                connect.CapabilityParameter(**p.model_dump()) for p in self.parameters
            ),
            external_effects=self.external_effects,
            confirmation_required=self.confirmation_required,
        )


class Catalogue(StrictModel):
    format_version: Annotated[StrictInt, Field(ge=1, le=1)]
    capabilities: list[Capability] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique(self):
        ids = [(c.id, c.version) for c in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate capability")
        return self


def parse_catalogue(raw: bytes) -> Catalogue:
    try:
        return Catalogue.model_validate(json_object(raw, SPEC_LIMIT))
    except ValidationError as exc:
        raise KitError(3, "invalid input") from exc


class FakeApps:
    """No sockets: every discovery and HTTP request terminates at these injected seams."""

    def __init__(self, catalogue: Catalogue):
        self.catalogue = catalogue
        self.jobs = {}
        self.submitted = []
        self.contents = []
        self.fail = False
        self.client = httpx.Client(
            transport=httpx.MockTransport(self.handle), trust_env=False, follow_redirects=False
        )

    def discover(self, runtime_dir=None, *, client=None, provider_instance_id=None):
        if runtime_dir is not None or client is not self.client:
            raise KitError(5, "check failed")
        return connect.CapabilityCatalog(
            items=tuple(
                c.discovered()
                for c in self.catalogue.capabilities
                if provider_instance_id is None or provider_instance_id == INSTANCE
            )
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "127.0.0.1" or request.url.port != 32123:
            raise KitError(5, "check failed")
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            raise KitError(5, "check failed")
        if request.method == "POST" and request.url.path == "/v2/jobs":
            header = (
                f"Content-Type: {request.headers['content-type']}\r\nMIME-Version: 1.0\r\n\r\n"
            ).encode()
            message = BytesParser(policy=default).parsebytes(header + request.read())
            parts = {
                str(p.get_param("name", header="content-disposition")): p.get_payload(decode=True)
                for p in message.iter_parts()
            }
            observed = json.loads(parts["request"])
            artifact = observed["inputs"][0]
            content = parts["artifact"]
            if (
                len(content) != artifact["byte_size"]
                or hashlib.sha256(content).hexdigest() != artifact["sha256"]
            ):
                raise KitError(5, "check failed")
            self.contents.append(content)
            self.submitted.append(observed)
            self.jobs[observed["job_id"]] = observed
            return httpx.Response(202, json=self.status(observed, "accepted"))
        if request.method == "GET" and request.url.path.startswith("/v2/jobs/"):
            observed = self.jobs[request.url.path.removeprefix("/v2/jobs/")]
            return httpx.Response(
                200, json=self.status(observed, "failed" if self.fail else "completed")
            )
        raise KitError(5, "check failed")

    def status(self, request: dict, status: str):
        artifact = request["inputs"][0]
        value = {
            "protocol_version": 2,
            "job_id": request["job_id"],
            "capability": request["capability"],
            "provider": {"app_id": APP_ID, "instance_id": INSTANCE},
            "status": status,
            "created_at": "2026-06-01T00:00:00Z",
            "updated_at": "2026-06-01T00:00:01Z",
            "input_artifacts": [
                {k: artifact[k] for k in ["artifact_id", "media_type", "byte_size", "sha256"]}
            ],
        }
        if status == "failed":
            value["error"] = {
                "code": "SYNTHETIC_FAILURE",
                "message": "Offline injected failure",
                "retryable": False,
            }
        if status == "completed":
            output = canonical({"receipt": "synthetic"})
            declaration = next(
                c
                for c in self.catalogue.capabilities
                if c.id == request["capability"]["id"]
                and c.version == request["capability"]["version"]
            )
            import base64

            value["result"] = {
                "outputs": [
                    {
                        "artifact_id": "33333333-3333-4333-8333-333333333333",
                        "media_type": declaration.produces[0],
                        "display_name": "result.json",
                        "byte_size": len(output),
                        "sha256": hashlib.sha256(output).hexdigest(),
                        "payload_base64": base64.b64encode(output).decode("ascii"),
                    }
                ]
            }
        return value
