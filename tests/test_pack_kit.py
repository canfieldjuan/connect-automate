"""Behavioral contract probes: public parser, deterministic bytes and CLI boundaries."""

from __future__ import annotations

import importlib
import io
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from connect_automate.automate import canonical_workflow, load_pack, parse_workflow

FIXTURES = Path(__file__).parent / "fixtures" / "pack_kit"
ROOT = Path(__file__).resolve().parents[1]
# The kit intentionally has no wheel entry. Support pytest's console-script loader
# as well as python -m pytest, preserving an explicit PYTHONPATH (mutation copies).
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def fixed_key(index=0):
    """Public deterministic development seeds; never used by kit authorities."""
    return Ed25519PrivateKey.from_private_bytes(index.to_bytes(32, "big"))


def kit():
    return importlib.import_module("tools.pack_kit.core")


def spec():
    return tomllib.loads((FIXTURES / "sample.toml").read_text())


def catalog():
    return (FIXTURES / "fake-apps.json").read_bytes()


def cli(*args, seed=b"", cwd=ROOT, env=None):
    return subprocess.run(
        [sys.executable, "-m", "tools.pack_kit", *map(str, args)],
        input=seed,
        capture_output=True,
        cwd=cwd,
        env=env,
    )


def test_build_matches_public_parser():
    k = kit()
    raw = k.build(spec())
    data = json.loads(raw)
    workflow = parse_workflow(json.dumps(data["manifest"]["workflow"]))
    assert canonical_workflow(workflow) == k.canonical(data["manifest"]["workflow"])
    assert workflow.stages == ["ready", "acting", "reporting", "completed", "failed", "declined"]
    assert [d.name for d in workflow.definitions] == [
        "approve",
        "decline",
        "complete",
        "finish",
        "fail",
    ]
    approve = workflow.definitions[0]
    assert approve.conditions[0].model_dump() == {
        "field": "record.stage",
        "op": "equals",
        "value": "ready",
    }
    assert [e.kind for e in approve.effects] == ["record.transition", "overlay.set"]
    assert approve.actions[0].request["confirmed"] is True
    assert approve.actions[0].request["input"]["artifact_id"] == spec()["pack_id"]
    assert k.validate_artifact(raw) == data


def test_golden_bytes():
    k = kit()
    assert k.build(spec()) == (FIXTURES / "build.json").read_bytes()
    data = json.loads(k.build(spec()))
    assert k.canonical(data["spec"]) == (FIXTURES / "spec.json").read_bytes()
    assert (
        canonical_workflow(parse_workflow(k.canonical(data["manifest"]["workflow"])))
        == (FIXTURES / "workflow.json").read_bytes()
    )
    seed = bytes(range(32))  # public development fixture only
    public = k.encoded(Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw())
    signed = k.sign(k.build(spec()), catalog(), "development", public, io.BytesIO(seed))
    assert signed == (FIXTURES / "signed.json").read_bytes()
    loaded = load_pack(
        signed,
        keys={
            "development": Ed25519PrivateKey.from_private_bytes(seed)
            .public_key()
            .public_bytes_raw()
        },
    )
    assert canonical_workflow(loaded.workflow) == (FIXTURES / "workflow.json").read_bytes()


@pytest.mark.parametrize(
    "change,code,message",
    [
        (lambda s: s.update(archetype="unknown"), 3, "unknown archetype"),
        (lambda s: s.update(pack_version=0), 3, "invalid input"),
        (lambda s: s.update(format_version=True), 3, "invalid input"),
        (lambda s: s.update(unexpected=True), 3, "invalid input"),
        (lambda s: s["result_action"].update(action="shell.exec"), 3, "unsupported vocabulary"),
        (
            lambda s: s["invoke"]["capability"].update(id="BAD CAPABILITY"),
            3,
            "unsupported vocabulary",
        ),
        (
            lambda s: s.update(conditions=[{"field": "mail.sender", "op": "equals", "value": "x"}]),
            3,
            "unsupported vocabulary",
        ),
        (
            lambda s: s.update(
                conditions=[{"field": "record.stage", "op": "equals", "value": "completed"}]
            ),
            3,
            "invalid input",
        ),
        (lambda s: s["invoke"]["parameters"].update(mode={"overlay": "value"}), 3, "invalid input"),
        (lambda s: s["result_action"]["request"].update(body="x" * 17000), 3, "input too large"),
    ],
)
def test_invalid_specs(change, code, message):
    k = kit()
    value = spec()
    change(value)
    with pytest.raises(k.KitError) as exc:
        k.build(value)
    assert (exc.value.code, exc.value.message) == (code, message)


def test_tamper_and_noncanonical_artifacts():
    k = kit()
    raw = k.build(spec())
    data = json.loads(raw)
    for modified in [
        raw + b"\n",
        json.dumps(data).encode(),
        raw.replace(b"sample-pack", b"other-pack", 1),
    ]:
        with pytest.raises(k.KitError, match="build artifact mismatch"):
            k.validate_artifact(modified)
    data["manifest"]["pack_version"] += 1
    with pytest.raises(k.KitError, match="build artifact mismatch"):
        k.validate_artifact(k.canonical(data))


def test_duplicate_json_and_malformed_utf8():
    k = kit()
    for raw in [b'{"x":1,"x":2}', b"\xff", b'{"x":NaN}', b"[]", b"{"]:
        with pytest.raises(k.KitError):
            k.validate_artifact(raw)


def test_literal_falsy_values_and_defaults():
    k = kit()
    value = spec()
    value["invoke"]["parameters"] = {"zero": 0, "empty": "", "disabled": False}
    output = json.loads(k.build(value))
    assert output["spec"]["invoke"]["parameters"] == value["invoke"]["parameters"]
    assert (
        output["manifest"]["workflow"]["definitions"][0]["actions"][0]["request"]["parameters"]
        == value["invoke"]["parameters"]
    )
    for name in ["conditions"]:
        value.pop(name)
    value["invoke"].pop("parameters")
    output = json.loads(k.build(value))
    assert output["spec"]["conditions"] == []
    assert output["spec"]["invoke"]["parameters"] == {}


def test_independent_process_determinism(tmp_path):
    source = FIXTURES / "sample.toml"
    outputs = []
    for n, seed in enumerate(["0", "42", "random"]):
        path = tmp_path / f"build-{n}.json"
        result = cli("build", source, "--out", path, env={**os.environ, "PYTHONHASHSEED": seed})
        assert result.returncode == 0, result.stderr
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1] == outputs[2] == kit().build(spec())
    changed = spec()
    changed["invoke"]["input"]["content"] += "!"
    assert kit().build(changed) != outputs[0]
    assert kit().build(dict(reversed(list(spec().items())))) == outputs[0]


def test_new_cli_roundtrip_and_no_overwrite(tmp_path):
    source = tmp_path / "spec.toml"
    built = tmp_path / "build.json"
    result = cli(
        "new",
        "--archetype",
        "approve-then-act",
        "--pack-id",
        spec()["pack_id"],
        "--name",
        "sample-pack",
        "--out",
        source,
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        b"pack-kit: created spec\n",
        b"",
    )
    assert tomllib.loads(source.read_text()) == spec()
    result = cli("build", source, "--out", built)
    assert result.returncode == 0, result.stderr
    assert built.read_bytes() == kit().build(spec())
    result = cli("build", source, "--out", built)
    assert (result.returncode, result.stderr) == (7, b"pack-kit: output exists\n")
    assert built.read_bytes() == kit().build(spec())


def test_oversized_input_missing_file_and_usage(tmp_path):
    path = tmp_path / "large.toml"
    path.write_bytes(b" " * (65536 + 1))
    cases = [
        (("build", path, "--out", tmp_path / "x"), 3, b"pack-kit: input too large\n"),
        (("build", tmp_path / "missing", "--out", tmp_path / "x"), 7, b"pack-kit: I/O error\n"),
        (("build",), 2, b"pack-kit: usage:\n"),
    ]
    for args, code, error in cases:
        result = cli(*args)
        assert (result.returncode, result.stderr, result.stdout) == (code, error, b"")
    assert not (tmp_path / "x").exists()


def test_skipped_check_never_signs(monkeypatch):
    k = kit()
    called = []

    def failed(*args):
        raise k.KitError(5, "check failed")

    class UnreadableSeed:
        def read(self, *args):
            called.append("read")
            raise AssertionError("publisher seed touched before check")

    monkeypatch.setattr(k, "check", failed)
    with pytest.raises(k.KitError, match="check failed"):
        key = fixed_key()
        public = k.encoded(key.public_key().public_bytes_raw())
        k.sign(k.build(spec()), catalog(), "development", public, UnreadableSeed())
    assert called == []


@pytest.mark.parametrize("seed", [b"", b"x" * 31, b"x" * 33, b"x" * 32])
def test_missing_or_wrong_seed(seed):
    k = kit()
    good = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    with pytest.raises(k.KitError, match="invalid signing key"):
        k.sign(
            k.build(spec()),
            catalog(),
            "development",
            k.encoded(good.public_key().public_bytes_raw()),
            io.BytesIO(seed),
        )


def test_check_runs_real_scenarios():
    report = kit().check(kit().build(spec()), catalog())
    assert report["scenarios"] == [
        "success",
        "decline",
        "replay",
        "invoke-failure",
        "result-failure",
        "missing-invoke",
        "missing-result",
        "load-refusals",
    ]


def test_unknown_capability_and_invalid_parameters_fail_check():
    k = kit()
    for field, value in [("id", "unknown.capability"), ("version", "2.0")]:
        candidate = spec()
        candidate["invoke"]["capability"][field] = value
        with pytest.raises(k.KitError, match="check failed"):
            k.check(k.build(candidate), catalog())
    candidate = spec()
    candidate["invoke"]["parameters"]["mode"] = False
    with pytest.raises(k.KitError, match="check failed"):
        k.check(k.build(candidate), catalog())
