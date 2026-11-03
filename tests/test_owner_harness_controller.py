"""Offline controller admission, real fixture dispatch and publication."""
import importlib
import json
import multiprocessing
import os
import socket
import subprocess
import sys
from pathlib import Path
from time import monotonic_ns

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = "qualification.owner_authority.controller"
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

ctl = importlib.import_module(MODULE)
p = ctl.p


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", MODULE, *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
    )


def packet(*case_ids):
    return {
        "version": "owner-harness/1", "evidence_class": "OFFLINE_CONFORMANCE",
        "qualification_pass": False, "contract_commit": ctl.CONTRACT,
        "harness_commit": "a" * 40, "run_id": "11111111-1111-4111-8111-111111111111",
        "dependency_lock_sha256": ctl.digest((ROOT / "uv.lock").read_bytes()),
        "case_ids": list(case_ids or (ctl.REPLAY,)),
        "fixtures": [{
            "alias": "cases", "sha256": ctl.digest((ctl.HERE / "cases.json").read_bytes()),
        }],
    }


def manifest(tmp_path, data=None):
    path = tmp_path / "run.json"
    path.write_bytes(p.canonical(packet() if data is None else data))
    return path


def forbidden(*args, **kwargs):
    pytest.fail("denied path reached an effect")


@pytest.fixture
def denied_effects(monkeypatch):
    from connect_automate import entitlement
    from connect_automate.automate.host import AutomateHost

    for owner, name in (
        (ctl, "_execute"), (ctl, "_offline"), (AutomateHost, "from_installation"),
        (entitlement.EntitlementGate, "from_installation"),
        (entitlement, "_load_installed_release_keyring"), (os, "getlogin"),
        (Path, "home"), (socket.socket, "connect"), (subprocess, "Popen"),
    ):
        monkeypatch.setattr(owner, name, forbidden)


def stop(capsys, reason):
    result = capsys.readouterr()
    assert json.loads(result.out) == {"outcome": "STOP", "reason": reason}
    assert not result.err


def test_native_command_refuses_before_using_input_paths(tmp_path):
    result = cli("preflight", "--manifest", tmp_path / "absent.json")
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout) == {"outcome": "STOP", "reason": "NATIVE_EXECUTION_DISABLED"}
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["preflight", "run", "collect"])
def test_native_before_input_output_or_workers(tmp_path, monkeypatch, capsys, name, denied_effects):
    monkeypatch.setattr(ctl, "_read", forbidden)
    assert ctl.main([name, "--manifest", str(tmp_path / "missing")]) == 2
    stop(capsys, "NATIVE_EXECUTION_DISABLED")


def test_inspect_preserves_selection_without_dispatch(tmp_path, monkeypatch, capsys):
    path = manifest(tmp_path, packet(ctl.REVOKED, ctl.REPLAY))
    monkeypatch.setattr(ctl, "_execute", forbidden)
    assert ctl.main(["inspect", "--manifest", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["run"] == packet(ctl.REVOKED, ctl.REPLAY)
    assert [case["case_id"] for case in result["cases"]] == [ctl.REVOKED, ctl.REPLAY]
    assert sorted(item.name for item in tmp_path.iterdir()) == ["run.json"]


@pytest.mark.parametrize("command", ["inspect", "offline"])
@pytest.mark.parametrize(("case", "reason"), [
    ("unknown", "UNKNOWN_CASE"), ("windows-hello", "NATIVE_EXECUTION_DISABLED"),
    ("linux-fake-user-bus", "NATIVE_EXECUTION_DISABLED"),
    ("device-replacement", "CONTRACT_BLOCKED"),
])
def test_whole_selection_admitted_before_effects(tmp_path, capsys, command, case, reason,
                                                denied_effects):
    path = manifest(tmp_path, packet(ctl.REPLAY, case))
    output = tmp_path / "new-output"
    args = [command, "--manifest", str(path)]
    if command == "offline":
        args += ["--output-root", str(output)]
    assert ctl.main(args) == 2
    stop(capsys, reason)
    assert not output.exists()


@pytest.mark.parametrize(("changes", "reason"), [
    ({"contract_commit": "b" * 40}, "CONTRACT_MISMATCH"),
    ({"dependency_lock_sha256": "b" * 64}, "LOCK_MISMATCH"),
    ({"fixtures": [{"alias": "cases", "sha256": "b" * 64}]}, "FIXTURE_MISMATCH"),
    ({"fixtures": [{"alias": "other", "sha256": "b" * 64}]}, "FIXTURE_MISMATCH"),
    ({"fixtures": []}, "INVALID_PACKET"),
    ({"fixtures": [{"alias": "../native", "sha256": "a" * 64}]}, "INVALID_PACKET"),
    ({"evidence_class": "NATIVE_QUALIFICATION"}, "INVALID_PACKET"),
    ({"qualification_pass": True}, "INVALID_PACKET"),
    ({"qualification_pass": 0}, "INVALID_PACKET"),
    ({"overall": "PASS"}, "INVALID_PACKET"),
    ({"credential": "synthetic-unexpected-secret"}, "INVALID_PACKET"),
])
def test_bad_manifest_refuses_without_echo(tmp_path, monkeypatch, capsys, changes, reason):
    path = manifest(tmp_path, packet() | changes)
    monkeypatch.setattr(ctl, "_offline", forbidden)
    args = ["offline", "--manifest", str(path), "--output-root", str(tmp_path / "out")]
    assert ctl.main(args) == 2
    stop(capsys, reason)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("corruption", [
    "copied-result", "promoted-native", "duplicate", "capability",
])
def test_catalog_schema_refuses_mixed_or_forged_metadata(corruption):
    inventory = json.loads((ctl.HERE / "cases.json").read_bytes())
    native = next(case for case in inventory["cases"] if case["kind"] == "NOT_RUN")
    runnable = inventory["cases"][0]
    if corruption == "copied-result":
        native["outcome"] = "PASS"
    elif corruption == "promoted-native":
        native.update(runnable | {"case_id": native["case_id"]})
    elif corruption == "duplicate":
        inventory["cases"].append(runnable)
    else:
        runnable["capability"] = "native"
    with pytest.raises(p.ProtocolInputError):
        p.parse_inventory(p.canonical(inventory))


def test_real_offline_cli_publishes_hash_bound_results(tmp_path):
    case_ids = (ctl.REPLAY, ctl.REVOKED, ctl.INACTIVE)
    path = manifest(tmp_path, packet(*case_ids))
    output = tmp_path / "new-output"
    command = cli("offline", "--manifest", path, "--output-root", output)
    assert command.returncode == 0, (command.stdout, command.stderr)
    raw = (output / "result.json").read_bytes()
    assert command.stdout.strip().encode("ascii") == raw
    parsed = p.parse_packet(raw, "result")
    assert parsed.evidence_class == "OFFLINE_CONFORMANCE"
    assert parsed.qualification_pass is False
    assert [case.case_id for case in parsed.cases] == list(case_ids)
    assert [case.actual_code for case in parsed.cases] == [
        "COMMITTED", "OWNER_AUTHORIZATION_REVOKED", "NATIVE_SESSION_INACTIVE",
    ]
    assert [case.outcome for case in parsed.cases] == ["PASS"] * len(case_ids)
    hashes = json.loads((output / "hashes.json").read_bytes())
    assert {a["alias"] for a in hashes["artifacts"]} == {
        "run.json", "result.json", *(f"{case}.json" for case in case_ids),
    }
    for item in hashes["artifacts"]:
        assert item["sha256"] == ctl.digest((output / item["alias"]).read_bytes())
    for case in parsed.cases:
        item, = case.artifacts
        evidence = json.loads((output / item.alias).read_bytes())
        assert set(evidence["assertions"]) == set(case.assertion_ids)
        assert all(evidence["assertions"].values())
        assert evidence["fixture_sha256"] == case.fixture_sha256
        assert evidence["environment"]["sources_sha256"]["controller.py"] == ctl.digest(
            (ctl.HERE / "controller.py").read_bytes()
        )
    assert {item.name for item in output.iterdir()} == {
        "hashes.json", *(a["alias"] for a in hashes["artifacts"]),
    }
    if os.name != "nt":
        assert output.stat().st_mode & 0o777 == 0o700
        assert all(item.stat().st_mode & 0o777 == 0o600 for item in output.iterdir())


def test_paths_require_absolute_direct_local_files(tmp_path, monkeypatch):
    path = manifest(tmp_path)
    with pytest.raises(ctl.Stop, match="INVALID_PATH"):
        ctl._read(Path("run.json"))
    with pytest.raises(ctl.Stop, match="INVALID_PATH"):
        ctl._read(tmp_path / ".." / tmp_path.name / path.name)
    link = tmp_path / "indirect"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(tmp_path)],
                       capture_output=True, check=True)
    else:
        link.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(ctl.os, "open", forbidden)
    with pytest.raises(ctl.Stop, match="INDIRECT_PATH"):
        ctl._read(link / path.name)
    with pytest.raises(ctl.Stop, match="INDIRECT_PATH"):
        ctl._direct(link, directory=True)


def test_open_identity_checked_before_bytes_are_read(tmp_path, monkeypatch):
    path = manifest(tmp_path)
    other = tmp_path / "other"
    other.write_bytes(b"synthetic alternate")
    original = os.open

    def swap(filename, *args, **kwargs):
        if filename == path:
            os.replace(other, path)
        return original(filename, *args, **kwargs)

    monkeypatch.setattr(ctl.os, "open", swap)
    with pytest.raises(ctl.Stop, match="FILE_CHANGED"):
        ctl._read(path)


def test_bounded_read_and_write(tmp_path, monkeypatch):
    path = tmp_path / "small"
    path.write_bytes(b"abc")
    assert ctl._read(path, limit=3) == b"abc"
    assert ctl._read(path, limit=4) == b"abc"
    monkeypatch.setattr(ctl.os, "open", forbidden)
    with pytest.raises(ctl.Stop, match="FILE_TOO_LARGE"):
        ctl._read(path, limit=2)
    with pytest.raises(ctl.Stop, match="ARTIFACT_TOO_LARGE"):
        ctl._write(tmp_path / "oversize", b"0" * (p.PACKET_BYTES + 1))


def test_output_must_be_new_and_outside_worktrees(tmp_path, monkeypatch, capsys):
    path = manifest(tmp_path)
    monkeypatch.setattr(ctl, "_execute", forbidden)
    fake_worktree = tmp_path / "nested"
    fake_worktree.mkdir()
    (fake_worktree / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    for output, reason in [(tmp_path, "FILE_UNAVAILABLE"), (fake_worktree / "out",
                                                           "OUTPUT_IN_WORKTREE")]:
        assert ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)]) == 2
        stop(capsys, reason)
        assert not (output / "result.json").exists()


def passing(*args):
    case = p.parse_inventory((ctl.HERE / "cases.json").read_bytes()).cases[0]
    return p.CaseObservation(actual_code=case.expected_code,
                             assertions=dict.fromkeys(case.assertion_ids, True))


@pytest.mark.parametrize("fault", ["partial", "changed"])
def test_publication_failures_leave_no_result_marker(tmp_path, monkeypatch, capsys, fault):
    path = manifest(tmp_path)
    output = tmp_path / "new-output"
    monkeypatch.setattr(ctl, "_execute", passing)
    original = ctl._write

    def fail(target, raw):
        if fault == "partial" and target.name == "result.pending":
            target.write_bytes(raw[:8])
            raise OSError("synthetic partial write")
        result = original(target, raw)
        if fault == "changed" and target.name == f"{ctl.REPLAY}.json":
            target.write_bytes(b"changed")
        return result

    monkeypatch.setattr(ctl, "_write", fail)
    assert ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)]) == 2
    stop(capsys, "FILE_UNAVAILABLE" if fault == "partial" else "ARTIFACT_CHANGED")
    assert not (output / "result.json").exists()


@pytest.mark.parametrize(("fault", "outcome", "status"), [
    ("code", "FAIL", 1), ("assertion", "FAIL", 1), ("wrong-id", "STOP", 2),
    ("timeout", "STOP", 2),
])
def test_only_actual_assertions_and_code_determine_offline_pass(
        tmp_path, monkeypatch, capsys, fault, outcome, status):
    path = manifest(tmp_path)
    output = tmp_path / "out"

    def observe(*args):
        if fault == "timeout":
            raise ctl.Stop("CASE_TIMEOUT")
        data = passing().model_dump()
        if fault == "code":
            data["actual_code"] = "WRONG"
        elif fault == "wrong-id":
            data["assertions"]["unexpected"] = True
        else:
            data["assertions"]["same-receipt"] = False
        return p.CaseObservation.model_validate(data)

    monkeypatch.setattr(ctl, "_execute", observe)
    assert ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)]) == status
    case, = p.parse_packet(capsys.readouterr().out.strip().encode("ascii"), "result").cases
    assert case.outcome == outcome
    assert (output / "result.json").exists()


def test_expired_deadline_reaps_real_children(tmp_path):
    before = {child.pid for child in multiprocessing.active_children()}
    with pytest.raises(ctl.Stop, match="CASE_TIMEOUT"):
        ctl._execute(tmp_path, ctl.REPLAY, monotonic_ns())
    assert {child.pid for child in multiprocessing.active_children()} == before


@pytest.mark.parametrize("args", [
    ["inspect", "--manifest", "ignored", "--credential", "synthetic-secret"],
    ["offline", "--man", "ignored"],
])
def test_invalid_cli_is_sanitized_before_input(args, monkeypatch, capsys):
    monkeypatch.setattr(ctl, "_read", forbidden)
    assert ctl.main(args) == 2
    stop(capsys, "INVALID_ARGUMENTS")


@pytest.mark.parametrize("command, output", [("offline", False), ("inspect", True)])
def test_output_root_cli_contract_precedes_manifest(command, output, monkeypatch, capsys):
    monkeypatch.setattr(ctl, "_read", forbidden)
    args = [command, "--manifest", "ignored"]
    if output:
        args += ["--output-root", "ignored"]
    assert ctl.main(args) == 2
    stop(capsys, "OUTPUT_ROOT_REQUIRED_FOR_OFFLINE")


def test_hard_link_and_directory_refuse_before_open(tmp_path, monkeypatch):
    path = manifest(tmp_path)
    alias = tmp_path / "alias.json"
    os.link(path, alias)
    monkeypatch.setattr(ctl.os, "open", forbidden)
    for candidate in (tmp_path, path, alias):
        with pytest.raises(ctl.Stop, match="INVALID_FILE"):
            ctl._read(candidate)


def test_read_cap_survives_same_file_growth_after_stat(tmp_path, monkeypatch):
    path = tmp_path / "data"
    path.write_bytes(b"abc")
    original = os.open

    def grow(filename, *args, **kwargs):
        if filename == path:
            path.write_bytes(b"abcd")
        return original(filename, *args, **kwargs)

    monkeypatch.setattr(ctl.os, "open", grow)
    with pytest.raises(ctl.Stop, match="FILE_TOO_LARGE"):
        ctl._read(path, limit=3)


def test_write_verification_and_exclusive_file(tmp_path, monkeypatch):
    path = tmp_path / "artifact"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        ctl._write(path, b"replacement")
    assert path.read_bytes() == b"original"
    monkeypatch.setattr(ctl, "_read", lambda *a: b"short")
    with pytest.raises(ctl.Stop, match="ARTIFACT_WRITE_MISMATCH"):
        ctl._write(tmp_path / "new", b"complete")


def test_platform_budget_prevents_case_dispatch(tmp_path, monkeypatch, capsys):
    path = manifest(tmp_path)
    output = tmp_path / "out"
    monkeypatch.setattr(ctl, "PLATFORM_NS", 0)
    monkeypatch.setattr(ctl, "_execute", forbidden)
    assert ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)]) == 2
    case, = p.parse_packet(capsys.readouterr().out.strip().encode("ascii"), "result").cases
    assert (case.outcome, case.actual_code) == ("STOP", "PLATFORM_TIMEOUT")


def test_failed_worker_reaps_real_children_without_leaking_paths(tmp_path, capfd):
    before = {child.pid for child in multiprocessing.active_children()}
    with pytest.raises(ctl.Stop, match="CASE_PROCESS_FAILED"):
        ctl._execute(tmp_path / "missing", ctl.REPLAY, monotonic_ns() + 10_000_000_000)
    assert {child.pid for child in multiprocessing.active_children()} == before
    captured = capfd.readouterr()
    assert not captured.out
    assert not captured.err


def test_catalog_cardinality_boundaries():
    definition = {
        "kind": "NOT_RUN", "case_id": "native", "requirement": "synthetic",
    }

    def inventory(count):
        return p.canonical({
            "version": "owner-harness-cases/1",
            "cases": [definition | {"case_id": f"native-{i}"} for i in range(count)],
        })

    for count in (1, 63, 64):
        assert len(p.parse_inventory(inventory(count)).cases) == count
    for count in (0, 65):
        with pytest.raises(p.ProtocolInputError):
            p.parse_inventory(inventory(count))
