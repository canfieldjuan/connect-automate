"""The v2 authoring lanes reuse the real offline pack-kit harness."""

import errno
import io
import json
import os
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_pack_kit import ROOT, cli, kit

from connect_automate.automate import load_pack

k = kit()

PACK_ID = "11111111-1111-4111-8111-111111111111"
APPS = (Path(__file__).parent / "fixtures" / "pack_kit" / "fake-apps.json").read_bytes()
GOLDENS = Path(__file__).parent / "fixtures" / "pack_events"


def test_fixture_bytes_survive_windows_git_checkout():
    for folder in ["pack_kit", "pack_events"]:
        for path in sorted((Path(__file__).parent / "fixtures" / folder).iterdir()):
            relative = path.relative_to(ROOT).as_posix()
            converted = subprocess.check_output(
                ["git", "-c", "core.autocrlf=true", "cat-file", "--filters", f"HEAD:{relative}"],
                cwd=ROOT,
            )
            assert converted == path.read_bytes(), relative


def test_legacy_sandbox_storage_rejection_reason(tmp_path, monkeypatch):
    from tempfile import TemporaryDirectory

    from connect_automate import connect_windows

    if os.name != "nt":
        trusted = tmp_path / "LocalAppData"
        trusted.mkdir(mode=0o700)
        monkeypatch.setattr(connect_windows, "local_app_data_root", lambda: trusted)
        monkeypatch.setattr(connect_windows, "_private_windows_acl", lambda path: True)
    # Reproduce the original sandbox construction, before _sandbox_root/_host
    # began using the SDK's Windows storage owner. The native CI log retains
    # the exact reader rejection rather than assuming chmod sets a private ACL.
    with TemporaryDirectory(prefix="pack-kit-legacy-") as name:
        directory = Path(name) / "local-connect"
        directory.mkdir(mode=0o700)
        path = directory / "entitlement-v1.json"
        path.write_bytes(b"synthetic reader probe")
        path.chmod(0o600)
        with pytest.raises(OSError) as caught:
            connect_windows.read_bounded_regular_file(path, 1024)
        assert caught.value.errno == errno.EACCES
        assert caught.value.strerror in {
            "private directory escapes its root",
            "private directory is unsafe",
            "private file is unsafe",
        }
        print("legacy sandbox Windows storage rejection:", caught.value.strerror)


@pytest.mark.parametrize(
    "archetype", ["approve-then-act", "mail-review-then-act", "schedule-review-then-act"]
)
def test_sandbox_uses_windows_private_storage(tmp_path, monkeypatch, archetype):
    from types import SimpleNamespace

    from connect_automate import connect_windows, entitlement
    from tools.pack_kit import sandbox

    rejections = []
    if os.name != "nt":
        # Exercise the real Windows path/reader/writer policy on Linux, replacing
        # only the OS ACL primitives. Native Windows runs without these doubles.
        trusted = tmp_path / "LocalAppData"
        trusted.mkdir(mode=0o700)
        protected = {trusted}

        def protect(path):
            path.chmod(0o700)
            protected.add(path)

        monkeypatch.setattr(sandbox, "os", SimpleNamespace(name="nt"), raising=False)
        monkeypatch.setattr(entitlement, "os", SimpleNamespace(name="nt"))
        monkeypatch.setattr(connect_windows, "local_app_data_root", lambda: trusted)
        monkeypatch.setattr(connect_windows, "_protect_windows_directory", protect)
        monkeypatch.setattr(
            connect_windows,
            "_private_windows_acl",
            lambda path: path in protected or any(parent in protected for parent in path.parents),
        )

    read = entitlement.read_bounded_regular_file

    def traced_read(*args, **kwargs):
        try:
            return read(*args, **kwargs)
        except OSError as exc:
            rejections.append(str(exc))
            raise

    monkeypatch.setattr(entitlement, "read_bounded_regular_file", traced_read)
    raw = k.build(k.parse_spec(k.new_spec(archetype, PACK_ID, "Event proof", 1)))
    events = None if archetype == "approve-then-act" else event_catalogue(archetype)
    try:
        result = k.check(raw, APPS, events)
    except k.KitError:
        print("Windows private-reader rejections:", rejections)
        raise
    assert "success" in result["scenarios"]
    assert not rejections


def test_windows_storage_protection_failure_blocks_check_and_cleans_up(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from connect_automate import connect_windows
    from tools.pack_kit import sandbox

    attempted = []

    def deny(path):
        attempted.append(path)
        raise OSError(errno.EACCES, "injected private storage refusal")

    monkeypatch.setattr(sandbox, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(connect_windows, "local_app_data_root", lambda: tmp_path)
    monkeypatch.setattr(connect_windows, "_protect_windows_directory", deny)
    raw = k.build(k.parse_spec(k.new_spec("approve-then-act", PACK_ID, "Event proof", 1)))
    with pytest.raises(k.KitError) as caught:
        k.check(raw, APPS)
    assert caught.value.code == 5
    assert len(attempted) == 1 and not attempted[0].exists()


def event_catalogue(archetype):
    mail = archetype == "mail-review-then-act"
    kind = "mail.received" if mail else "schedule.tick"
    event = {
        "source_kind": kind,
        **(
            {
                "message_id": "synthetic-message-1",
                "received_at": "2026-01-01T00:00:00Z",
                "sender": "sender@example.invalid",
                "subject": "Synthetic input",
            }
            if mail
            else {"scheduled_at": "2026-01-02T00:00:00Z"}
        ),
    }
    return k.canonical(
        {
            "format_version": 1,
            "binding": {
                "name": "incoming-mail" if mail else "timer",
                "source_id": "22222222-2222-4222-8222-222222222222",
                "source_kind": kind,
                "scope": "synthetic-source",
            },
            "matching_event": event,
        }
    )


@pytest.mark.parametrize("archetype", ["mail-review-then-act", "schedule-review-then-act"])
def test_event_kit_builds_checks_and_signs_real_v2(archetype):
    spec = k.parse_spec(k.new_spec(archetype, PACK_ID, "Event proof", 1))
    raw = k.build(spec)
    assert (
        k.new_spec(archetype, PACK_ID, "Event proof", 1)
        == (GOLDENS / f"{archetype}.toml").read_bytes()
    )
    assert raw == (GOLDENS / f"{archetype}.build.json").read_bytes()
    artifact = json.loads(raw)
    assert artifact["kit_format_version"] == artifact["manifest"]["format_version"] == 2
    assert artifact["manifest"]["workflow"]["vocabulary_version"] == 2
    first = artifact["manifest"]["workflow"]["definitions"][0]
    assert first["trigger"]["source_kind"] != "operator.decision"
    assert [item["action"] for item in first["actions"]] == ["notify.local"]
    assert k.build(dict(reversed(list(spec.items())))) == raw
    catalogue = event_catalogue(archetype)
    assert catalogue == (GOLDENS / f"{archetype}.events.json").read_bytes()
    assert (
        k.canonical(artifact["manifest"]["workflow"])
        == (GOLDENS / f"{archetype}.workflow.json").read_bytes()
    )
    result = k.check(raw, APPS, catalogue)
    assert {"success", "replay", "event-replay", "event-boundaries"} <= set(result["scenarios"])
    seed = bytes(range(32))
    key = Ed25519PrivateKey.from_private_bytes(seed)
    signed = k.sign(
        raw,
        APPS,
        "development",
        k.encoded(key.public_key().public_bytes_raw()),
        io.BytesIO(seed),
        event_catalogue=catalogue,
    )
    assert signed == (GOLDENS / f"{archetype}.signed.json").read_bytes()
    assert (
        load_pack(
            signed, keys={"development": key.public_key().public_bytes_raw()}
        ).workflow.vocabulary_version
        == 2
    )


def test_missing_or_incompatible_event_catalogue_precedes_seed():
    raw = k.build(k.parse_spec(k.new_spec("mail-review-then-act", PACK_ID, "Event proof", 1)))

    class Unreadable:
        def read(self, size):
            raise AssertionError("publisher seed was read before check")

    for events in [None, b"{}", event_catalogue("schedule-review-then-act")]:
        with pytest.raises(k.KitError) as caught:
            k.sign(raw, APPS, "development", "invalid", Unreadable(), event_catalogue=events)
        assert caught.value.code in (3, 5)


def test_nonmatching_positive_catalogue_is_not_repaired():
    raw = k.build(k.parse_spec(k.new_spec("mail-review-then-act", PACK_ID, "Event proof", 1)))
    catalogue = json.loads(event_catalogue("mail-review-then-act"))
    catalogue["matching_event"]["sender"] = "wrong@example.invalid"
    with pytest.raises(k.KitError) as caught:
        k.check(raw, APPS, k.canonical(catalogue))
    assert caught.value.code == 5


def test_smallest_utc_year_is_supported_in_check():
    spec = k.parse_spec(k.new_spec("schedule-review-then-act", PACK_ID, "Event proof", 1))
    spec["trigger"]["anchor"] = "0001-01-01T00:00:00Z"
    catalogue = json.loads(event_catalogue("schedule-review-then-act"))
    catalogue["matching_event"]["scheduled_at"] = "0001-01-01T00:00:00Z"
    assert "event-boundaries" in k.check(k.build(spec), APPS, k.canonical(catalogue))["scenarios"]


@pytest.mark.parametrize("archetype", ["mail-review-then-act", "schedule-review-then-act"])
def test_cli_event_roundtrip_and_dash_leading_catalogue_path(tmp_path, archetype):
    task_env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [os.environ.get("PYTHONPATH"), str(ROOT), str(ROOT / "src")])
        ),
    }
    (tmp_path / "-events.json").write_bytes(event_catalogue(archetype))
    apps = Path(__file__).parent / "fixtures" / "pack_kit" / "fake-apps.json"
    created = cli(
        "new",
        "--archetype",
        archetype,
        "--pack-id",
        PACK_ID,
        "--name",
        "Event proof",
        "--out",
        "source.toml",
        cwd=tmp_path,
        env=task_env,
    )
    assert created.returncode == 0, created.stderr
    built = cli("build", "source.toml", "--out", "build.json", cwd=tmp_path, env=task_env)
    assert built.returncode == 0, built.stderr
    checked = cli(
        "check",
        "build.json",
        "--fake-apps",
        apps,
        "--fake-events",
        "-events.json",
        cwd=tmp_path,
        env=task_env,
    )
    assert (checked.returncode, checked.stdout, checked.stderr) == (
        0,
        ("pack-kit: check passed (offline only)" + os.linesep).encode(),
        b"",
    )
    seed = bytes(range(32))
    key = Ed25519PrivateKey.from_private_bytes(seed)
    signed = cli(
        "sign",
        "build.json",
        "--fake-apps",
        apps,
        "--fake-events",
        "-events.json",
        "--key-id",
        "development",
        "--public-key-base64url",
        k.encoded(key.public_key().public_bytes_raw()),
        "--out",
        "signed.json",
        seed=seed,
        cwd=tmp_path,
        env=task_env,
    )
    assert signed.returncode == 0, signed.stderr
    assert (tmp_path / "signed.json").read_bytes() == (
        GOLDENS / f"{archetype}.signed.json"
    ).read_bytes()


def test_v1_rejects_an_unused_event_catalogue():
    from test_pack_kit import spec

    with pytest.raises(k.KitError) as caught:
        k.check(k.build(spec()), APPS, event_catalogue("mail-review-then-act"))
    assert caught.value.code == 3


def test_tampered_version_is_artifact_mismatch_before_runtime_routing():
    raw = k.build(k.parse_spec(k.new_spec("mail-review-then-act", PACK_ID, "Event proof", 1)))
    tampered = json.loads(raw)
    tampered["kit_format_version"] = 1
    with pytest.raises(k.KitError) as caught:
        k.check(k.canonical(tampered), APPS, event_catalogue("mail-review-then-act"))
    assert caught.value.code == 4
