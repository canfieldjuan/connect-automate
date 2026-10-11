"""Real client boundary regressions for negotiated fixed parameters."""

import httpx
import pytest
from test_connect import discovered_v2_capability, generic_job_status

from connect_automate import connect


@pytest.mark.parametrize("http_status", [409, 503, 200])
def test_invalid_fixed_refusal_is_permanent(http_status):
    capability = discovered_v2_capability()
    job = connect.prepare_capability_job(capability, b"pdf", "application/pdf", "file.pdf")
    calls = []

    def handler(request):
        calls.append(request.method)
        error = {"code": "FIXED_PARAMETER_MISMATCH", "message": "Mismatch", "retryable": True}
        value = (
            generic_job_status(job, "failed", error=error)
            if http_status == 200
            else {"protocol_version": 2, "error": error}
        )
        return httpx.Response(http_status, json=value)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = connect.ConnectV2Client(capability, client=http_client)
        with pytest.raises(connect.ConnectError) as raised:
            if http_status == 200:
                client.get(job)
            else:
                client.submit(job, b"pdf")
    assert raised.value.code == "RESPONSE_INVALID"
    assert raised.value.retryable is False
    assert len(calls) == 1


def test_fixed_decoder_and_binding_preserve_false():
    parameter = {
        "name": "flag",
        "value_type": "boolean",
        "required": True,
        "label": "Flag",
        "description": "Fixed flag",
        "fixed_value": False,
    }
    decoded = connect._FixedParameterDeclaration.model_validate(parameter)
    assert decoded.fixed_value is False


def test_frozen_feature_requirement_blocks_unacknowledged_same_target():
    from test_automate_connect import fake_discover, invoke_request, make_capability

    from connect_automate import automate_connect

    capability = make_capability()
    request = invoke_request()
    request["required_manifest_features"] = ["fixed-parameters-v1"]
    with pytest.raises(connect.ConnectError) as raised:
        automate_connect._select_capability(
            fake_discover(capability)(), automate_connect._parse_request(request)
        )
    assert raised.value.code == "CAPABILITY_NOT_FOUND"


@pytest.mark.parametrize(
    "kind,value",
    [
        ("string", ""),
        ("integer", 0),
        ("boolean", False),
        ("integer", 1.0),
        ("integer", 9007199254740991),
    ],
)
def test_fixed_binding_and_restore_rotation(kind, value):
    from dataclasses import replace

    parameter = connect.CapabilityParameter("pin", kind, True, "Pin", "Pinned", True, value)
    capability = discovered_v2_capability(parameters=(parameter,))
    job = connect.prepare_capability_job(capability, b"pdf", "application/pdf", "file.pdf")
    assert dict(job.parameters) == {"pin": value}
    assert parameter.public_dict()["fixed_value"] == value
    rotated = replace(capability, parameters=(replace(parameter, fixed_value="new"),))
    restored = connect.restore_persisted_capability_job(rotated, job.request_json)
    assert restored.request_json == job.request_json
    assert restored.parameters == job.parameters
    with pytest.raises(connect.ConnectError, match="cannot be overridden"):
        connect.prepare_capability_job(
            capability, b"pdf", "application/pdf", "file.pdf", parameters={"pin": "different"}
        )
    with pytest.raises(connect.ConnectError, match="missing"):
        connect.restore_capability_job(
            capability,
            job_id=job.job_id,
            artifact_id=job.artifact.artifact_id,
            media_type="application/pdf",
            byte_size=3,
            sha256=job.artifact.sha256,
            filename="file.pdf",
            parameters={},
        )


@pytest.mark.parametrize("status", [409, 503, 200])
@pytest.mark.parametrize("code,retryable", [("FIXED_PARAMETER_MISMATCH", False), ("OTHER", True)])
def test_valid_error_outcomes_preserved(status, code, retryable):
    capability = discovered_v2_capability()
    job = connect.prepare_capability_job(capability, b"pdf", "application/pdf", "file.pdf")
    error = {"code": code, "message": "Refused", "retryable": retryable}

    def handler(request):
        return httpx.Response(
            status,
            json=(
                generic_job_status(job, "failed", error=error)
                if status == 200
                else {"protocol_version": 2, "error": error}
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = connect.ConnectV2Client(capability, client=http_client)
        if status == 200:
            result = client.get(job).error
        else:
            with pytest.raises(connect.ConnectError) as raised:
                client.submit(job, b"pdf")
            result = raised.value
    assert result.code == code
    assert result.retryable is retryable


@pytest.mark.parametrize("retryability", [None, "false", 0, {}, "MISSING"])
@pytest.mark.parametrize("status", [409, 503, 200])
def test_malformed_refusals_never_authorize_retry(retryability, status):
    capability = discovered_v2_capability()
    job = connect.prepare_capability_job(capability, b"pdf", "application/pdf", "file.pdf")
    error = {"code": "FIXED_PARAMETER_MISMATCH", "message": "Refused"}
    if retryability != "MISSING":
        error["retryable"] = retryability

    def handler(request):
        return httpx.Response(
            status,
            json=(
                generic_job_status(job, "failed", error=error)
                if status == 200
                else {"protocol_version": 2, "error": error}
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = connect.ConnectV2Client(capability, client=http_client)
        with pytest.raises(connect.ConnectError) as raised:
            client.get(job) if status == 200 else client.submit(job, b"pdf")
    assert raised.value.code == "RESPONSE_INVALID"
    assert raised.value.retryable is False


@pytest.mark.parametrize(
    "invalid",
    [None, False, 0, "", "fixed-parameters-v1", ["unknown"], ["fixed-parameters-v1"] * 2, [False]],
)
def test_invalid_frozen_requirements_reject_before_discovery(invalid):
    from test_automate_connect import ACTION_ID, invoke_request

    from connect_automate import automate_connect

    calls = []
    request = invoke_request()
    request["required_manifest_features"] = invalid
    invoker = automate_connect.ConnectV2CapabilityInvoker(discover=lambda *a, **k: calls.append(k))
    with pytest.raises(connect.ConnectError) as raised:
        invoker.invoke(request, job_id=ACTION_ID)
    assert raised.value.code == "CONNECT_INVOKE_REQUEST_INVALID"
    assert calls == []


def test_real_invoker_frozen_reload_rotation_and_ack_loss(tmp_path, monkeypatch):
    import json
    from datetime import UTC, datetime

    from test_automate_connect import multipart_parts
    from test_connect import (
        INSTANCE_A,
        capability_v2,
        manifest_v2,
        providers_dir_v2,
        registration_v2,
        write_registration,
    )

    from connect_automate import automate_connect
    from connect_automate.automate.store import WorkflowStore

    monkeypatch.setattr(
        connect.entitlement,
        "connect_entitlement_decision",
        lambda: connect.entitlement.EntitlementDecision.ACTIVE,
    )
    folder = providers_dir_v2(tmp_path)
    write_registration(
        folder / "provider.json",
        registration_v2(
            instance_id=INSTANCE_A, app_id="generic-provider", base_url="http://127.0.0.1:32123/"
        ),
    )
    state = {"pin": "old", "ack": True}
    manifest_requests, wire_requests = [], []

    def handler(request):
        if request.url.path == "/v2/manifest":
            manifest_requests.append(request.headers.get("local-connect-manifest-features"))
            parameters = [
                {
                    "name": "pin",
                    "value_type": "string",
                    "required": True,
                    "label": "Pin",
                    "description": "Pin",
                }
            ]
            headers = {}
            if state["ack"]:
                parameters[0]["fixed_value"] = state["pin"]
                headers = {
                    "Local-Connect-Manifest-Features": "fixed-parameters-v1",
                    "Cache-Control": "no-store",
                    "Vary": "Local-Connect-Manifest-Features",
                }
            declaration = capability_v2(
                "document.translate",
                label="Translate",
                accepts="application/pdf",
                produces="text/plain",
                parameters=parameters,
            )
            return httpx.Response(
                200,
                headers=headers,
                json=manifest_v2(INSTANCE_A, "generic-provider", capabilities=[declaration]),
            )
        wire_requests.append(multipart_parts(request)["request"])
        # A permanent refusal lets us inspect the submission without fabricated results.
        return httpx.Response(
            409,
            json={
                "protocol_version": 2,
                "error": {
                    "code": "FIXED_PARAMETER_MISMATCH",
                    "message": "Refused",
                    "retryable": False,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        catalog = connect.discover_capabilities(
            tmp_path, client=http_client, required_manifest_features=("fixed-parameters-v1",)
        )
        capability = catalog.items[0]
        assert capability.public_dict()["acknowledged_manifest_features"] == ["fixed-parameters-v1"]
        frozen = automate_connect.prepare_capability_invocation(
            capability, b"pdf", "application/pdf", "file.pdf"
        )
        store = WorkflowStore(tmp_path / "automate/workflow.db")
        store.initialize()
        now = datetime.now(UTC)
        record = store.create_record(
            "fixture", "captured", now=now, allowed_stages=frozenset({"captured"})
        )
        admission = store.admit_action(
            record.record_id, kind="connect.invoke", dedupe_key="fixed", request=frozen, now=now
        )
        action_id = admission.view.action_id
        store = WorkflowStore(tmp_path / "automate/workflow.db")
        reloaded = store.get_action(action_id).request
        assert reloaded == frozen
        invoker = automate_connect.ConnectV2CapabilityInvoker(
            runtime_dir=tmp_path, client=http_client
        )
        for pin in ("old", "rotated"):
            state["pin"] = pin
            with pytest.raises(connect.ConnectError) as raised:
                invoker.invoke(reloaded, job_id=action_id)
            assert raised.value.code == "FIXED_PARAMETER_MISMATCH"
        assert wire_requests[0] == wire_requests[1]
        assert json.loads(wire_requests[1])["parameters"] == {"pin": "old"}
        state["ack"] = False
        with pytest.raises(connect.ConnectError) as raised:
            invoker.invoke(reloaded, job_id=action_id)
        assert raised.value.code == "CAPABILITY_NOT_FOUND"
        assert len(wire_requests) == 2
        assert manifest_requests == ["fixed-parameters-v1"] * 4
        # Pre-feature frozen work still selects an actually advertised legacy declaration.
        legacy = dict(reloaded)
        legacy.pop("required_manifest_features")
        with pytest.raises(connect.ConnectError) as raised:
            invoker.invoke(legacy, job_id=action_id)
        assert raised.value.code == "FIXED_PARAMETER_MISMATCH"
        assert manifest_requests[-1] is None
        assert wire_requests[-1] == wire_requests[0]


def test_checked_shared_policy_sources_and_extension_ownership():
    import hashlib
    import json
    from pathlib import Path

    from connect_automate import _manifest_policy

    directory = Path(_manifest_policy.__file__).parent / "manifest_policy"
    receipt = json.loads((directory / "manifest_policy_sources.json").read_text())
    fixtures = Path(__file__).parent / "fixtures/fixed-parameters"
    sources = {
        "tests/fixed_parameters.py": fixtures / "shared-oracle.py.txt",
        "fixtures/v2/features/fixed-parameters-v1/README.md": directory / "README.md",
        "fixtures/v2/features/fixed-parameters-v1/golden-fixtures.json": fixtures
        / "golden-fixtures.json",
    }
    for name, file in sources.items():
        assert hashlib.sha256(file.read_bytes()).hexdigest() == receipt["sources"][name]
    original = (fixtures / "shared-oracle.py.txt").read_text()
    segment = original[
        original.index("def header_values(") : original.index("def exchange_errors(")
    ]
    copied = Path(_manifest_policy.__file__).read_text()
    assert copied[copied.index("def header_values(") :] == segment
    assert hashlib.sha256(segment.encode()).hexdigest() == receipt["extracted_segment_sha256"]
    # Inheritance, not cloned validation, owns every unchanged legacy field and constraint.
    assert connect._FixedParameterDeclaration.__bases__ == (connect._ParameterDeclaration,)
    assert connect._FixedCapabilityDeclarationV2.__bases__ == (connect._CapabilityDeclarationV2,)
    assert connect._FixedAppManifestV2.__bases__ == (connect._AppManifestV2,)
    for fixed, legacy, extension in [
        (connect._FixedParameterDeclaration, connect._ParameterDeclaration, "fixed_value"),
        (connect._FixedCapabilityDeclarationV2, connect._CapabilityDeclarationV2, "parameters"),
        (connect._FixedAppManifestV2, connect._AppManifestV2, "capabilities"),
    ]:
        for field in legacy.model_fields:
            if field != extension:
                assert (
                    fixed.model_json_schema()["properties"][field]
                    == legacy.model_json_schema()["properties"][field]
                )


def shared_vectors(kind):
    import json
    from pathlib import Path

    vectors = json.loads(
        (Path(__file__).parent / "fixtures/fixed-parameters/golden-fixtures.json").read_text()
    )["vectors"]
    return [vector for vector in vectors if vector["kind"] == kind]


@pytest.mark.parametrize(
    "vector",
    [v for v in shared_vectors("manifest") if not v["name"].startswith("classifier-reject")],
    ids=lambda v: v["name"],
)
def test_canonical_generic_manifest_vectors(vector):
    try:
        connect._FixedAppManifestV2.model_validate(vector["input"])
        valid = True
    except ValueError:
        valid = False
    assert valid is vector["valid"]


@pytest.mark.parametrize(
    "vector",
    [
        v
        for v in shared_vectors("exchange")
        if v["input"].get("validation_role") == "consumer_admission"
        and not v["input"].get("from_cache")
        and v["name"]
        not in {
            "consumer-exchange-reject-legacy-classifier",
            "consumer-exchange-reject-extended-vary-not-preserved",
        }
    ],
    ids=lambda v: v["name"],
)
def test_canonical_consumer_header_and_decoder_vectors(vector):
    from connect_automate import _manifest_policy

    value = vector["input"]
    # Synthetic cache reuse and producer's preservation of its own existing Vary are
    # outside the consumer decoder; real rediscovery is separately exercised above.
    try:
        request_headers = _manifest_policy.header_values(value["request_headers"])
        requested = (
            ("fixed-parameters-v1",)
            if request_headers.get(_manifest_policy.HEADER) == "fixed-parameters-v1"
            else ()
        )
        response = httpx.Response(
            200,
            headers=[
                (name.encode("ascii"), field.encode("latin-1"))
                for name, field in value["response_headers"].items()
            ],
        )
        acknowledged = connect._admitted_manifest_features(response, requested)
        decoder = connect._FixedAppManifestV2 if acknowledged else connect._AppManifestV2
        decoder.model_validate(value["manifest"])
        valid = True
    except (ValueError, UnicodeError):
        valid = False
    assert valid is vector["valid"]


def test_persisted_wire_bytes_never_reserialized():
    import json

    capability = discovered_v2_capability()
    job = connect.prepare_capability_job(capability, b"pdf", "application/pdf", "file.pdf")
    frozen = json.dumps(json.loads(job.request_json), indent=2).encode() + b"\n"
    assert connect.restore_persisted_capability_job(capability, frozen).request_json == frozen


@pytest.mark.parametrize(
    "mutation",
    [
        "http-refusal",
        "terminal-refusal",
        "falsy-binding",
        "supplied-override",
        "restore-rebinding",
        "restore-reserialization",
        "requirement-persistence",
        "requirement-forwarding",
        "ack-selection",
        "requested-is-ack",
    ],
)
def test_runtime_boundary_mutations_are_killed(tmp_path, mutation):
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    package = tmp_path / "src/connect_automate"
    shutil.copytree(Path(connect.__file__).parent, package)
    source = package / "connect.py"
    text = source.read_text()
    target = "test_real_invoker_frozen_reload_rotation_and_ack_loss"
    if mutation in {"http-refusal", "terminal-refusal"}:
        owner = "class _ErrorEnvelopeV2" if mutation == "http-refusal" else "class _JobStatusV2"
        start = text.index(owner)
        end = (
            text.index("\n\nclass ", start + 1)
            if mutation == "terminal-refusal"
            else text.index("\n\n@dataclass", start)
        )
        fragment = text[start:end].replace("error: _JobErrorV2", "error: _JobError")
        text = text[:start] + fragment + text[end:]
        target = "test_invalid_fixed_refusal_is_permanent"
    elif mutation == "falsy-binding":
        text = text.replace("if not parameter.has_fixed_value:", "if not parameter.fixed_value:")
        target = "test_fixed_binding_and_restore_rotation"
    elif mutation == "supplied-override":
        text = text.replace("or value != fixed", "")
        target = "test_fixed_binding_and_restore_rotation"
    elif mutation == "restore-rebinding":
        text = text.replace(
            "validated_parameters = _validated_parameters(capability, parameters)",
            "validated_parameters = _bound_parameters(capability, parameters)",
        )
    elif mutation == "restore-reserialization":
        text = text.replace(
            "request_json=request_json,", "request_json=json.dumps(request.model_dump()).encode(),"
        )
        target = "test_persisted_wire_bytes_never_reserialized"
    elif mutation == "requested-is-ack":
        text = text.replace(
            "return (_manifest_policy.FEATURE,) if extended else ()", "return requested"
        )
    source.write_text(text)
    source = package / "automate_connect.py"
    text = source.read_text()
    if mutation == "requirement-persistence":
        text = text.replace('request["required_manifest_features"] = list(features)', "pass")
    elif mutation == "requirement-forwarding":
        text = text.replace(
            'discovery_options["required_manifest_features"] = parsed.required_manifest_features',
            "pass",
        )
    elif mutation == "ack-selection":
        text = text.replace(
            "and set(request.required_manifest_features).issubset(\n"
            "            capability.acknowledged_manifest_features\n        )",
            "",
        )
    source.write_text(text)
    env = {**os.environ, "PYTHONPATH": str(tmp_path / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__ + "::" + target, "-q", "--no-header"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAILED" in result.stdout and target in result.stdout, result.stdout + result.stderr
    assert "ERROR collecting" not in result.stdout, result.stdout
