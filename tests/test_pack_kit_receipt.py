"""Receipt-only authoring proves vocabulary and binding, never authenticated submission."""

import io
import json

import pytest
from test_lead_receipt_vocabulary import HOST, OTHER, binding, encoded, event
from test_pack_kit import catalog, cli, fixed_key, kit

from connect_automate.automate import load_pack

k = kit()


def receipt_spec():
    return k.parse_spec(k.new_spec("lead-source-receipt", HOST, "Receipt proof", 1))


def catalogue():
    return encoded(
        {
            "format_version": 1,
            "binding": dict(binding(), name="lead-source"),
            "matching_event": event(),
        }
    )


def test_receipt_kit_roundtrip_no_actions_and_qualification_label():
    artifact = k.build(receipt_spec())
    data = k.validate_artifact(artifact)
    assert data["manifest"]["workflow"]["stages"] == ["waiting", "source-received"]
    assert len(data["manifest"]["workflow"]["definitions"]) == 1
    assert data["manifest"]["workflow"]["definitions"][0]["actions"] == []
    assert k.check(artifact, catalog(), catalogue()) == {
        "scenarios": ["receipt-vocabulary-binding-only"]
    }
    key = fixed_key()
    signed = k.sign(
        artifact,
        catalog(),
        "receipt-proof",
        k.encoded(key.public_key().public_bytes_raw()),
        io.BytesIO(key.private_bytes_raw()),
        event_catalogue=catalogue(),
    )
    loaded = load_pack(signed, keys={"receipt-proof": key.public_key().public_bytes_raw()})
    assert loaded.workflow.model_dump(mode="json") == data["manifest"]["workflow"]
    assert k.build(receipt_spec()) == artifact


def test_receipt_kit_cli_roundtrip(tmp_path):
    spec, artifact, signed = (
        tmp_path / name for name in ["proof.toml", "proof.json", "signed.json"]
    )
    apps, events = tmp_path / "apps.json", tmp_path / "events.json"
    apps.write_bytes(catalog())
    events.write_bytes(catalogue())
    result = cli(
        "new",
        "--archetype",
        "lead-source-receipt",
        "--pack-id",
        HOST,
        "--name",
        "Receipt proof",
        "--out",
        spec,
    )
    assert result.returncode == 0, result.stderr
    result = cli("build", spec, "--out", artifact)
    assert result.returncode == 0, result.stderr
    result = cli("check", artifact, "--fake-apps", apps, "--fake-events", events)
    assert result.returncode == 0, result.stderr
    key = fixed_key()
    result = cli(
        "sign",
        artifact,
        "--fake-apps",
        apps,
        "--fake-events",
        events,
        "--key-id",
        "receipt-proof",
        "--public-key-base64url",
        k.encoded(key.public_key().public_bytes_raw()),
        "--out",
        signed,
        seed=key.private_bytes_raw(),
    )
    assert result.returncode == 0, result.stderr
    assert (
        load_pack(
            signed.read_bytes(), keys={"receipt-proof": key.public_key().public_bytes_raw()}
        ).workflow.initial_stage
        == "waiting"
    )


@pytest.mark.parametrize("field", ["host_id", "organization_id", "namespace_id"])
def test_kit_refuses_cross_scope_catalogue(field):
    data = json.loads(catalogue())
    data["matching_event"]["source_receipt"][field] = OTHER
    with pytest.raises(k.KitError) as error:
        k.check(k.build(receipt_spec()), catalog(), encoded(data))
    assert error.value.code == 5


@pytest.mark.parametrize("change", ["actions", "trigger", "manifest", "extra", "no-catalogue"])
def test_kit_refuses_edits_and_never_bypasses_sign_check(change):
    spec = receipt_spec()
    if change == "extra":
        spec["invoke"] = {}
        with pytest.raises(k.KitError):
            k.build(spec)
        return
    data = json.loads(k.build(spec))
    if change == "actions":
        data["manifest"]["workflow"]["definitions"][0]["actions"] = [
            {"action": "notify.local", "request": {"title": "x", "body": "x"}}
        ]
    if change == "trigger":
        data["spec"]["trigger"]["match_all"] = False
    if change == "manifest":
        data["manifest"]["workflow"]["initial_stage"] = "source-received"

    class UnreadSeed:
        def read(self, *args):
            pytest.fail("signing key read before qualification")

    with pytest.raises(k.KitError):
        k.sign(
            encoded(data),
            catalog(),
            "test",
            "unused",
            UnreadSeed(),
            event_catalogue=None if change == "no-catalogue" else catalogue(),
        )


def test_kit_detects_generic_receipt_submission_becoming_accepted(monkeypatch):
    from connect_automate.automate import PackRuntime

    monkeypatch.setattr(PackRuntime, "submit_event", lambda *args, **kwargs: None)
    with pytest.raises(k.KitError) as error:
        k.check(k.build(receipt_spec()), catalog(), catalogue())
    assert error.value.code == 5


def test_receipt_golden_bytes():
    from pathlib import Path

    root = Path(__file__).parent / "fixtures" / "lead_receipt"
    assert (
        k.new_spec("lead-source-receipt", HOST, "Receipt proof", 1)
        == (root / "proof.toml").read_bytes()
    )
    artifact = k.build(receipt_spec())
    assert artifact == (root / "proof.build.json").read_bytes()
    assert catalogue() == (root / "proof.events.json").read_bytes()
    key = fixed_key()
    signed = k.sign(
        artifact,
        catalog(),
        "receipt-proof",
        k.encoded(key.public_key().public_bytes_raw()),
        io.BytesIO(key.private_bytes_raw()),
        event_catalogue=catalogue(),
    )
    assert signed == (root / "proof.signed.json").read_bytes()
