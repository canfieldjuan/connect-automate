"""Offline controller admission, real fixture dispatch and publication."""
import importlib
import json
import multiprocessing
import os
import socket
import subprocess
import sys
from contextlib import contextmanager, suppress
from functools import partial
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
    case_ids = (ctl.REPLAY, ctl.REVOKED, ctl.INACTIVE, ctl.MALFORMED)
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
        "COMMITTED", "OWNER_AUTHORIZATION_REVOKED", "NATIVE_SESSION_INACTIVE", "COMMITTED",
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


def _changed_first_receipt(monkeypatch):
    consume = ctl.IssuerFixture.consume
    first = True

    def changed(issuer, raw, clock):
        nonlocal first
        receipt = consume(issuer, raw, clock)
        if not first:
            return receipt
        first = False
        payload = p.check_receipt(receipt, raw, issuer.manifest, issuer.keys,
                                  issuer.release_ids, clock()).model_dump()
        payload["consumed_at"] = "2026-01-01T00:59:59Z"
        alternate = ctl.signed("receipt", payload, issuer.receipt_signer)
        p.check_receipt(alternate, raw, issuer.manifest, issuer.keys, issuer.release_ids, clock())
        assert alternate != receipt
        return alternate

    monkeypatch.setattr(ctl.IssuerFixture, "consume", changed)


def _extra_issuer_consumption(monkeypatch):
    from test_owner_harness_recovery import START, SyntheticWire

    consume = ctl.IssuerFixture.consume
    first = True

    def changed(issuer, raw, clock):
        nonlocal first
        receipt = consume(issuer, raw, clock)
        if first:
            first = False
            # Commit another real signed consumption through the fixture owner,
            # rather than fabricating its snapshot count or cross-store SQL.
            wire = SyntheticWire()
            wire.public.update(issuer.keys)
            claim = issuer.issue(wire.claim(index=20).model_copy(update={
                "entitlement_id": ctl._uid(21),
            }), START)
            assert issuer.snapshot()["consumptions"] == 1
            consume(issuer, wire.request(claim, operation=20), clock)
            assert issuer.snapshot()["consumptions"] == 2
        return receipt

    monkeypatch.setattr(ctl.IssuerFixture, "consume", changed)


def _faulted_host(monkeypatch, fault):
    from qualification.owner_authority.licensing_fixture import read_store, transaction

    bootstrap = ctl.HostFixture.bootstrap

    def altered(host, consume, observe, clock):
        def twice(raw):
            result = consume(raw)
            consume(raw)
            return result

        if fault == "cached-no-dispatch" and host.snapshot()["admins"]:
            with read_store(host.root, "host") as db:
                binding, claim, *_ = host._pending(db)
            with suppress(TimeoutError):
                consume(host._request(binding, claim, clock()))

        result = bootstrap(host, twice if fault in ("issuer-effects", "no-auto-retry") else consume,
                           observe, clock)
        if fault == "pending-after-loss" and result.code == "LICENSING_UNAVAILABLE":
            return p.FixtureHostResult.model_validate(result.model_dump() | {"code": "PENDING"})
        if fault == "no-publication":
            # Emulate a bad local writer after the real inactive-session denial.
            with transaction(host.root, "host") as db:
                binding, *_ = host._pending(db)
                op = binding.operation_id
                db.execute("INSERT INTO receipts VALUES(1,?,?)", (op, b"synthetic-fault"))
                db.execute("INSERT INTO admins VALUES(1,?,?,'admin')",
                           (op, binding.principal_commitment))
                db.execute("INSERT INTO audit VALUES(1,?,'FIXTURE_BOOTSTRAP')", (op,))
        return result

    monkeypatch.setattr(ctl.HostFixture, "bootstrap", altered)


def _faulted_child(fault, target, *args):
    """Install deliberate fixture faults inside a spawned child."""
    with pytest.MonkeyPatch.context() as patch:
        if target is ctl._issuer and fault == "same-receipt":
            _changed_first_receipt(patch)
        if target is ctl._issuer and fault == "extra-consumption":
            _extra_issuer_consumption(patch)
        if target is ctl._host:
            _faulted_host(patch, fault)
        ctl._child(target, *args)
        if target is ctl._host and fault == "child-exit":
            raise SystemExit(9)


@pytest.mark.parametrize("fault,case_id", [
    ("issuer-effects", ctl.REPLAY), ("same-receipt", ctl.REPLAY),
    ("pending-after-loss", ctl.REPLAY), ("cached-no-dispatch", ctl.REPLAY),
    ("no-publication", ctl.INACTIVE), ("child-exit", ctl.REPLAY),
    ("no-auto-retry", ctl.MALFORMED), ("extra-consumption", ctl.MALFORMED),
])
def test_real_child_fault_reaches_evidence_verdict(tmp_path, monkeypatch, capfd, fault, case_id):
    path = manifest(tmp_path, packet(case_id))
    output = tmp_path / "out"
    monkeypatch.setattr(ctl, "_child", partial(_faulted_child, fault))
    args = ["offline", "--manifest", str(path), "--output-root", str(output)]
    assert ctl.main(args) == (2 if fault == "child-exit" else 1)
    captured = capfd.readouterr()
    assert not captured.err
    raw = (output / "result.json").read_bytes()
    assert captured.out.strip().encode("ascii") == raw
    case, = p.parse_packet(raw, "result").cases
    evidence = json.loads((output / case.artifacts[0].alias).read_bytes())
    if fault == "child-exit":
        assert (case.outcome, case.actual_code) == ("STOP", "CASE_PROCESS_FAILED")
    else:
        assert case.outcome == "FAIL"
        assert case.actual_code == case.expected_code
        failed = {"issuer-effects"} if fault == "extra-consumption" else {fault}
        if fault == "no-auto-retry":
            failed.add("issuer-effects")
        assert evidence["assertions"] == {key: key not in failed for key in case.assertion_ids}


def test_same_size_input_modified_in_place_during_read(tmp_path, monkeypatch):
    path = tmp_path / "input"
    path.write_bytes(b"first")
    original = os.fdopen
    initial = path.stat()

    @contextmanager
    def open_changed(fd, mode):
        with original(fd, mode) as stream:
            read = stream.read

            def changed(size):
                raw = read(size)
                with path.open("r+b") as writer:
                    writer.write(b"other")
                os.utime(path, ns=(initial.st_atime_ns, initial.st_mtime_ns + 2_000_000_000))
                return raw

            monkeypatch.setattr(stream, "read", changed)
            yield stream

    monkeypatch.setattr(ctl.os, "fdopen", open_changed)
    with pytest.raises(ctl.Stop, match="FILE_CHANGED"):
        ctl._read(path)
    assert path.stat().st_size == initial.st_size
    assert path.read_bytes() == b"other"


@pytest.mark.parametrize("relative,reason", [(True, "INVALID_PATH"),
                                               (False, "UNSUPPORTED_PLATFORM")])
def test_output_guards_precede_parent_access(tmp_path, monkeypatch, capsys, relative, reason):
    path = manifest(tmp_path)
    original = ctl._direct

    def direct(candidate, directory=False):
        if directory:
            forbidden()
        return original(candidate)

    monkeypatch.setattr(ctl, "_direct", direct)
    if not relative:
        monkeypatch.setattr(ctl.sys, "platform", "unsupported")
    output = "relative" if relative else str(tmp_path / "out")
    assert ctl.main(["offline", "--manifest", str(path), "--output-root", output]) == 2
    stop(capsys, reason)


@pytest.mark.parametrize("count", [0, 1, 64, 65])
def test_worker_assertion_count_is_bounded(count):
    raw = p.canonical({"actual_code": "COMMITTED",
                       "assertions": {f"synthetic-{i}": True for i in range(count)}})
    if 1 <= count <= 64:
        assert len(p.parse_observation(raw).assertions) == count
    else:
        with pytest.raises(p.ProtocolInputError):
            p.parse_observation(raw)


def test_real_process_malformed_recovery_recipe(tmp_path):
    root = tmp_path / "fixtures"
    root.mkdir()
    result = ctl._execute(root, ctl.MALFORMED, monotonic_ns() + p.CASE_NS)
    assert result.actual_code == "COMMITTED"
    assert result.assertions == dict.fromkeys([
        "pending-after-loss", "malformed-diagnostic", "derived-unknown", "stable-binding",
        "fresh-attempts", "no-auto-retry", "one-local-triplet", "cached-no-dispatch",
        "malformed-no-ledger", "same-receipt", "issuer-effects",
    ], True)


def _offline_only_child(target, *args):
    from unittest.mock import patch

    from connect_automate import entitlement
    from connect_automate.automate.host import AutomateHost
    with patch.object(socket.socket, "connect", forbidden), \
            patch.object(Path, "home", forbidden), patch.object(os, "getlogin", forbidden), \
            patch.object(subprocess, "Popen", forbidden), \
            patch.object(AutomateHost, "from_installation", forbidden), \
            patch.object(entitlement.EntitlementGate, "from_installation", forbidden), \
            patch.object(entitlement, "_load_installed_release_keyring", forbidden):
        ctl._child(target, *args)


def test_malformed_workers_cannot_call_live_or_installed_owners(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    root.mkdir()
    monkeypatch.setattr(ctl, "_child", _offline_only_child)
    result = ctl._execute(root, ctl.MALFORMED, monotonic_ns() + p.CASE_NS)
    assert result.actual_code == "COMMITTED" and all(result.assertions.values())


RENEWAL_ASSERTIONS = [
    "pending-after-loss", "unavailable-no-dispatch", "derived-unknown", "retained-state",
    "renewal-only-config-effects", "no-implicit-resume", "forward-renewals",
    "installed-issue-monotonic", "installed-expiry-monotonic",
    "fresh-attempts", "one-local-triplet", "cached-no-dispatch", "same-receipt",
    "issuer-exchanges", "issuer-consumptions", "issuer-ledger-preserved",
]


def test_real_renewal_cli_records_complete_proof(tmp_path):
    path = manifest(tmp_path, packet("manifest-renewal"))
    output = tmp_path / "renewal"
    result = cli("offline", "--manifest", path, "--output-root", output)
    assert result.returncode == 0, (result.stdout, result.stderr)
    case, = p.parse_packet(result.stdout.strip().encode(), "result").cases
    assert (case.outcome, case.actual_code) == ("PASS", "COMMITTED")
    receipt = json.loads((output / "manifest-renewal.json").read_bytes())
    assert receipt["assertions"] == dict.fromkeys(RENEWAL_ASSERTIONS, True)
    assert receipt["qualification_pass"] is False
    assert receipt["evidence_class"] == "OFFLINE_CONFORMANCE"
    hashes = json.loads((output / "hashes.json").read_bytes())
    for item in hashes["artifacts"]:
        assert item["sha256"] == ctl.digest((output / item["alias"]).read_bytes())


def _renewal_fault_child(fault, target, *args):
    """Fault real owner effects inside the same spawned workers, never verdict flags."""
    from qualification.owner_authority.licensing_fixture import transaction

    with pytest.MonkeyPatch.context() as patch:
        if target is ctl._issuer:
            if fault == "same-receipt":
                _changed_first_receipt(patch)
            elif fault == "extra-consumption":
                _extra_issuer_consumption(patch)
            elif fault == "zero-consumptions":
                consume = ctl.IssuerFixture.consume
                def lost_ledger(owner, raw, clock):
                    reply = consume(owner, raw, clock)
                    with transaction(owner.root, "issuer") as db:
                        db.execute("DELETE FROM consumptions")
                        db.execute("DELETE FROM journal WHERE event='CONSUME'")
                    return reply
                patch.setattr(ctl.IssuerFixture, "consume", lost_ledger)
            elif fault == "issuer-ledger-preserved":
                adopt = ctl.IssuerFixture.adopt_manifest
                def revoked(issuer, candidate, now):
                    adopt(issuer, candidate, now)
                    with transaction(issuer.root, "issuer") as db:
                        issuer._journal(db, "REVOKE", ctl._uid(1))
                patch.setattr(ctl.IssuerFixture, "adopt_manifest", revoked)
            elif fault == "expired-dispatch":
                consume = ctl.IssuerFixture.consume
                consumed = [0]
                def at_expiry(owner, raw, clock):
                    consumed[0] += 1
                    return consume(owner, raw, ctl._clock if consumed[0] == 2 else clock)
                patch.setattr(ctl.IssuerFixture, "consume", at_expiry)
            elif fault == "hidden-resume":
                adopt = ctl.IssuerFixture.adopt_manifest
                def once(owner, candidate, now):
                    if owner.manifest != candidate:
                        adopt(owner, candidate, now)
                patch.setattr(ctl.IssuerFixture, "adopt_manifest", once)
        if target is ctl._host:
            if fault == "missing-exchange":
                class CachedTransport:
                    def __init__(self, channel):
                        self.channel, self.requests, self.cached = channel, 0, None
                        self.replay = False
                    def __enter__(self):
                        return self
                    def __exit__(self, *exc):
                        self.channel.close()
                    def __getattr__(self, name):
                        return getattr(self.channel, name)
                    def send_bytes(self, raw):
                        if raw not in (ctl.SNAPSHOT, ctl.ADVANCE, ctl.ADOPT,
                                       ctl.INSPECT, ctl.CANDIDATES):
                            self.requests += 1
                            if self.requests == 2:
                                self.replay = True
                                return
                        self.channel.send_bytes(raw)
                    def recv_bytes(self):
                        if self.replay:
                            self.replay = False
                            return self.cached
                        raw = self.channel.recv_bytes()
                        self.cached = raw
                        return raw
                args = (*args[:2], CachedTransport(args[2]), *args[3:])
            bootstrap, renew = ctl.HostFixture.bootstrap, ctl.HostFixture.renew_manifest
            request, select = ctl.HostFixture._request, ctl.HostFixture.select_renewal
            calls, renewals, saved = [0], [0], {}

            def signed_request(host, binding, claim, now, db=None):
                raw = request(host, binding, claim, now, db)
                saved.setdefault("request", raw)
                if fault == "expired-dispatch":
                    saved["request"] = raw
                if fault in ("reused-attempt", "reused-time"):
                    parsed = p.parse_consume_request(raw).model_dump()
                    first = p.parse_consume_request(saved["request"])
                    field = "attempt_id" if fault == "reused-attempt" else "requested_at"
                    parsed[field] = getattr(first, field)
                    data = {k: v for k, v in parsed.items()
                            if k not in ("owner_claim", "installation_signature")}
                    import base64
                    signature = host.key.sign(p.prefix("consume") + p.canonical(data))
                    parsed["installation_signature"] = base64.urlsafe_b64encode(
                        signature).rstrip(b"=").decode()
                    raw = p.canonical(parsed)
                return raw

            def clear_triplet(host):
                with transaction(host.root, "host") as db:
                    for table in ("audit", "admins", "receipts"):
                        db.execute("DELETE FROM " + table)

            def selection(host):
                if fault == "derived-unknown" and saved.pop("early", False):
                    clear_triplet(host)
                return select(host)

            def publication(host, exchange, observe, clock):
                calls[0] += 1
                saved["exchange"], saved["observe"], saved["clock"] = exchange, observe, clock
                if calls[0] == 4 and "triplet" in saved:
                    with transaction(host.root, "host") as db:
                        for table, row in saved["triplet"]:
                            db.execute("INSERT INTO " + table + " VALUES(" +
                                       ",".join("?" for _ in row) + ")", row)
                def twice(raw):
                    value = exchange(raw)
                    exchange(raw)
                    return value
                result = bootstrap(host, twice if fault == "extra-exchange" else exchange,
                                   observe, clock)
                if fault == "expired-dispatch" and calls[0] == 2:
                    exchange(saved["request"])
                if ((fault == "pending-after-loss" and calls[0] == 1)
                        or (fault == "unavailable-no-dispatch" and calls[0] == 2)):
                    result = p.FixtureHostResult.model_validate(
                        result.model_dump() | {"code": "PENDING"})
                if fault == "derived-unknown" and calls[0] == 2:
                    with transaction(host.root, "host") as db:
                        binding, *_ = host._pending(db)
                        db.execute("INSERT INTO receipts VALUES(1,?,?)",
                                   (binding.operation_id, b"synthetic early publication"))
                        db.execute("INSERT INTO admins VALUES(1,?,?,'admin')",
                                   (binding.operation_id, binding.principal_commitment))
                        db.execute("INSERT INTO audit VALUES(1,?,'FIXTURE_BOOTSTRAP')",
                                   (binding.operation_id,))
                    saved["early"] = True
                if fault == "one-local-triplet" and calls[0] == 3:
                    with transaction(host.root, "host") as db:
                        saved["triplet"] = [(table, db.execute(
                            "SELECT * FROM " + table).fetchone())
                            for table in ("receipts", "admins", "audit")]
                    clear_triplet(host)
                return result

            def renewal(host, selected, candidate, observe, clock):
                renewals[0] += 1
                if ((fault == "forward-renewals" and renewals[0] == 1)
                        or (fault == "second-forward-renewal" and renewals[0] == 2)):
                    return selected
                result = renew(host, selected, candidate, observe, clock)
                if fault == "retained-state" and renewals[0] == 1:
                    with transaction(host.root, "host") as db:
                        db.execute("UPDATE pending SET original_manifest=?", (candidate,))
                if fault == "hidden-resume" and renewals[0] == 1:
                    # Adopt through the real issuer owner, then wrongly resume inside renewal.
                    args[2].send_bytes(ctl.ADOPT)
                    assert args[2].recv() is None
                    assert bootstrap(host, saved["exchange"], observe, clock).committed
                return result

            if fault in ("installed-issue-monotonic", "installed-expiry-monotonic"):
                check = p.check_manifest_renewal
                def unchecked(candidate, original, installed, keys, release_ids, now):
                    value = p.verify_signed(candidate, "manifest", keys, release_ids)
                    targeted = ((value.issued_at, value.expires_at) == (
                        "2026-01-01T01:00:00Z", "2026-01-05T00:00:00Z") if
                        fault == "installed-issue-monotonic" else
                        (value.issued_at, value.expires_at) == (
                            "2026-01-01T01:00:01Z", "2026-01-03T00:00:00Z"))
                    return value if targeted else check(
                        candidate, original, installed, keys, release_ids, now)
                patch.setattr(p, "check_manifest_renewal", unchecked)
            patch.setattr(ctl.HostFixture, "_request", signed_request)
            patch.setattr(ctl.HostFixture, "select_renewal", selection)
            patch.setattr(ctl.HostFixture, "bootstrap", publication)
            patch.setattr(ctl.HostFixture, "renew_manifest", renewal)
            if fault == "cached-no-dispatch":
                _faulted_host(patch, fault)
        ctl._child(target, *args)


RENEWAL_FAULTS = [
    ("pending-after-loss", {"pending-after-loss"}),
    ("unavailable-no-dispatch", {"unavailable-no-dispatch"}),
    ("expired-dispatch", {"unavailable-no-dispatch", "no-implicit-resume", "issuer-exchanges"}),
    ("derived-unknown", {"derived-unknown"}),
    ("retained-state", {"retained-state", "renewal-only-config-effects"}),
    ("hidden-resume", {"renewal-only-config-effects", "no-implicit-resume"}),
    ("forward-renewals", {"forward-renewals", "renewal-only-config-effects"}),
    ("installed-issue-monotonic", {"installed-issue-monotonic"}),
    ("installed-expiry-monotonic", {"installed-expiry-monotonic"}),
    ("reused-attempt", {"fresh-attempts"}),
    ("reused-time", {"fresh-attempts"}),
    ("one-local-triplet", {"one-local-triplet", "cached-no-dispatch"}),
    ("cached-no-dispatch", {"cached-no-dispatch", "no-implicit-resume", "issuer-exchanges",
                            "fresh-attempts"}),
    ("same-receipt", {"same-receipt"}),
    ("extra-exchange", {"issuer-exchanges", "no-implicit-resume"}),
    ("extra-consumption", {"issuer-consumptions"}),
    ("zero-consumptions", {"issuer-consumptions", "same-receipt"}),
    ("missing-exchange", {"issuer-exchanges"}),
    ("second-forward-renewal", {"forward-renewals", "renewal-only-config-effects",
                                "installed-issue-monotonic"}),
    ("issuer-ledger-preserved", {"issuer-ledger-preserved"}),
]


@pytest.mark.parametrize("fault,failed", RENEWAL_FAULTS)
def test_renewal_real_fault_records_exact_false_assertions(
        tmp_path, monkeypatch, capfd, fault, failed):
    path = manifest(tmp_path, packet("manifest-renewal"))
    output = tmp_path / "out"
    monkeypatch.setattr(ctl, "_child", partial(_renewal_fault_child, fault))
    status = ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)])
    captured = capfd.readouterr()
    assert not captured.err
    raw = (output / "result.json").read_bytes()
    assert captured.out.strip().encode() == raw
    case, = p.parse_packet(raw, "result").cases
    receipt = json.loads((output / case.artifacts[0].alias).read_bytes())
    assert (status, case.outcome, case.actual_code) == (1, "FAIL", "COMMITTED"), receipt
    assert receipt["assertions"] == {key: key not in failed for key in RENEWAL_ASSERTIONS}


def test_renewal_workers_cannot_call_live_or_installed_owners(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    root.mkdir()
    monkeypatch.setattr(ctl, "_child", _offline_only_child)
    result = ctl._execute(root, "manifest-renewal", monotonic_ns() + p.CASE_NS)
    assert result.actual_code == "COMMITTED" and all(result.assertions.values())


def _lost_again_child(target, *args):
    with pytest.MonkeyPatch.context() as patch:
        if target is ctl._host:
            bootstrap = ctl.HostFixture.bootstrap
            calls = [0]
            def altered(host, consume, observe, clock):
                calls[0] += 1
                def lost(raw):
                    consume(raw)
                    raise TimeoutError
                return bootstrap(host, lost if calls[0] == 3 else consume, observe, clock)
            patch.setattr(ctl.HostFixture, "bootstrap", altered)
        ctl._child(target, *args)


def test_renewal_lost_recovery_does_not_trigger_cached_retry(tmp_path, monkeypatch, capfd):
    path = manifest(tmp_path, packet("manifest-renewal"))
    output = tmp_path / "out"
    monkeypatch.setattr(ctl, "_child", _lost_again_child)
    assert ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)]) == 1
    case, = p.parse_packet(capfd.readouterr().out.strip().encode(), "result").cases
    assert (case.outcome, case.actual_code) == ("FAIL", "LICENSING_UNAVAILABLE")
    receipt = json.loads((output / "manifest-renewal.json").read_bytes())
    assert receipt["assertions"]["no-implicit-resume"] is True
    assert receipt["assertions"]["issuer-exchanges"] is True
    assert receipt["assertions"]["issuer-consumptions"] is True
    assert receipt["assertions"]["one-local-triplet"] is False
    assert receipt["assertions"]["same-receipt"] is False


def _renewal_denial_child(control, target, *args):
    from datetime import timedelta

    from qualification.owner_authority.licensing_fixture import transaction

    with pytest.MonkeyPatch.context() as patch:
        if target is ctl._issuer and control == "expired-claim":
            consume, calls = ctl.IssuerFixture.consume, [0]
            def expired(owner, raw, clock):
                calls[0] += 1
                return consume(owner, raw, (lambda: ctl.NOW + timedelta(hours=12))
                               if calls[0] == 2 else clock)
            patch.setattr(ctl.IssuerFixture, "consume", expired)
        if target is ctl._host:
            bootstrap, calls = ctl.HostFixture.bootstrap, [0]
            def denied(host, consume, observe, clock):
                calls[0] += 1
                if calls[0] == 2 and control in ("missing-installed", "corrupt-installed",
                                                "corrupt-original"):
                    with transaction(host.root, "host") as db:
                        if control == "corrupt-original":
                            db.execute("UPDATE pending SET original_manifest=?", (b"{}",))
                        else:
                            db.execute("UPDATE configuration SET manifest=?", (
                                None if control == "missing-installed" else b"{}",))
                if calls[0] == 3:
                    if control == "inactive":
                        def observe():
                            return ctl._observe(False)
                    elif control == "expired-claim":
                        def clock():
                            return ctl.NOW + timedelta(hours=12)
                return bootstrap(host, consume, observe, clock)
            patch.setattr(ctl.HostFixture, "bootstrap", denied)
        ctl._child(target, *args)


@pytest.mark.parametrize("control,code", [("inactive", "NATIVE_SESSION_INACTIVE"),
                                         ("expired-claim", "OWNER_AUTHORIZATION_EXPIRED"),
                                         ("missing-installed", "CASE_PROCESS_FAILED"),
                                         ("corrupt-installed", "CASE_PROCESS_FAILED"),
                                         ("corrupt-original", "CASE_PROCESS_FAILED")])
def test_renewal_negative_outcomes_are_recorded(tmp_path, monkeypatch, capfd, control, code):
    path = manifest(tmp_path, packet("manifest-renewal"))
    output = tmp_path / "out"
    monkeypatch.setattr(ctl, "_child", partial(_renewal_denial_child, control))
    stopped = code == "CASE_PROCESS_FAILED"
    assert ctl.main(["offline", "--manifest", str(path), "--output-root", str(output)]) == (
        2 if stopped else 1)
    captured = capfd.readouterr()
    assert not captured.err
    case, = p.parse_packet(captured.out.strip().encode(), "result").cases
    assert (case.outcome, case.actual_code) == ("STOP" if stopped else "FAIL", code)
    receipt = json.loads((output / "manifest-renewal.json").read_bytes())
    assert receipt["assertions"]["one-local-triplet"] is False
    assert receipt["assertions"]["cached-no-dispatch"] is False
    if not stopped:
        assert receipt["assertions"]["issuer-consumptions"] is True
        assert receipt["assertions"]["retained-state"] is True
        assert receipt["assertions"]["same-receipt"] is False
