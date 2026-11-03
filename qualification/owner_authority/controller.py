"""Private offline harness CLI. Entry point: python -m qualification.owner_authority.controller."""

import argparse
import hashlib
import multiprocessing
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic_ns

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import protocol as p
from .host_fixture import HostFixture
from .licensing_fixture import IssuerFixture, signed

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
CONTRACT = "314b43a6a8d4860fd6ca0f17bab1427059f7dea7"
NATIVE_COMMANDS = frozenset({"preflight", "run", "collect"})
PLATFORM_NS = 3_600_000_000_000
REPLAY = "lost-response-replay"
REVOKED = "revoked-claim"
INACTIVE = "inactive-session"
START = "2026-01-01T00:00:00Z"
NOW = datetime(2026, 1, 1, 1, tzinfo=UTC)
SNAPSHOT = b"snapshot"


class Stop(RuntimeError):
    """Only fixed diagnostic codes cross the CLI boundary."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _absolute(path):
    if (not path.is_absolute() or ".." in path.parts
            or (os.name == "nt" and (len(path.drive) != 2 or os.path.isreserved(path)))):
        raise Stop("INVALID_PATH")


def _direct(path, directory=False):
    _absolute(path)
    for part in [*reversed(path.parents), path]:
        info = part.lstat()
        if (stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise Stop("INDIRECT_PATH")
        if (directory or part != path) and not stat.S_ISDIR(info.st_mode):
            raise Stop("INVALID_PATH")
    return info


def _read(path, limit=p.PACKET_BYTES):
    before = _direct(path)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise Stop("INVALID_FILE")
    if before.st_size > limit:
        raise Stop("FILE_TOO_LARGE")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as file:
        opened = os.fstat(file.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or not os.path.samestat(before, opened)
                or not os.path.samestat(_direct(path), opened)):
            raise Stop("FILE_CHANGED")
        raw = file.read(limit + 1)
        after = os.fstat(file.fileno())
        if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise Stop("FILE_CHANGED")
    if len(raw) > limit:
        raise Stop("FILE_TOO_LARGE")
    return raw


def _admit(manifest):
    run = p.parse_packet(_read(manifest), "run")
    if run.contract_commit != CONTRACT:
        raise Stop("CONTRACT_MISMATCH")
    raw = _read(HERE / "cases.json")
    if {item.alias: item.sha256 for item in run.fixtures} != {"cases": digest(raw)}:
        raise Stop("FIXTURE_MISMATCH")
    if run.dependency_lock_sha256 != digest(_read(ROOT / "uv.lock")):
        raise Stop("LOCK_MISMATCH")
    catalog = {case.case_id: case for case in p.parse_inventory(raw).cases}
    cases = []
    for case_id in run.case_ids:
        case = catalog.get(case_id)
        if case is None:
            raise Stop("UNKNOWN_CASE")
        if not isinstance(case, p.RunnableCase):
            reason = "NATIVE_EXECUTION_DISABLED" if case.kind == "NOT_RUN" else "CONTRACT_BLOCKED"
            raise Stop(reason)
        cases.append(case)
    return run, cases


def _uid(index):
    return f"{index:08x}-1111-4111-8111-111111111111"


def _clock():
    return NOW


def _issuer(root, case_id, channel):
    with channel:
        keys = {name: Ed25519PrivateKey.generate() for name in ("release", "claim", "receipt")}
        public = {name: key.public_key().public_bytes_raw() for name, key in keys.items()}
        manifest = signed("manifest", {
            "version": "owner-bootstrap/1", "purpose": "owner-bootstrap-activation",
            "origin": "https://fixture.example", "claim_key_ids": ["claim"],
            "receipt_key_ids": ["receipt"], "issued_at": START,
            "expires_at": "2026-01-03T00:00:00Z",
        }, ("release", keys["release"]))
        issuer = IssuerFixture(root, manifest, public, frozenset({"release"}),
                               ("claim", keys["claim"]), ("receipt", keys["receipt"])).create()
        claim = issuer.issue(p.OwnerClaim(
            version="owner-bootstrap/1", purpose="owner-bootstrap", claim_id=_uid(1),
            organization_id=_uid(2), entitlement_id=_uid(3), generation=1, issued_at=START,
            not_before=START, expires_at="2026-01-01T12:00:00Z",
        ), datetime.fromisoformat(START))
        if case_id == REVOKED:
            issuer.revoke(_uid(1))
        channel.send((manifest, public, claim))
        calls = 0
        first_receipt = receipt_hash = None
        while (request := channel.recv_bytes()) != SNAPSHOT:
            reply = issuer.consume(request, _clock)
            calls += 1
            if case_id == REPLAY:
                receipt_hash = digest(reply)
                if calls == 1:
                    first_receipt = receipt_hash
            channel.send_bytes(reply)
        channel.send((calls, issuer.snapshot()["consumptions"], first_receipt, receipt_hash))


def _observe(active=True):
    return p.FixtureObservation(
        evidence_class="OFFLINE_CONFORMANCE", qualification_pass=False, principal_ref="synthetic",
        authority_generation=1, active=active, authenticated_at_ns=0, observed_at_ns=0,
    )


def _replay(host, claim, binding, consume):
    def lost(request):
        consume(request)
        raise TimeoutError

    failed = host.bootstrap(lost, _observe, _clock)
    pending = host.snapshot()
    same = host.prepare(claim, binding.operation_id, _observe, NOW) == binding
    result = host.bootstrap(consume, _observe, _clock)
    published = host.snapshot()
    unexpected = []

    def forbidden(_):
        unexpected.append(True)
        raise TimeoutError

    cached = host.bootstrap(forbidden, _observe, _clock)
    return result.code, {
        "pending-after-loss": (
            failed.code == "LICENSING_UNAVAILABLE" and not failed.committed
            and pending["operation_id"] == binding.operation_id
            and [pending[k] for k in ("pending", "receipts", "admins", "audit")] == [1, 0, 0, 0]
        ),
        "stable-binding": same and result.operation_id == binding.operation_id,
        "one-local-triplet": result.committed and all(
            published[k] == 1 for k in ("receipts", "admins", "audit")
        ),
        "cached-no-dispatch": not unexpected and cached == result and host.snapshot() == published,
    }


def _host(root, case_id, issuer, report):
    with issuer, report:
        manifest, public, claim = issuer.recv()
        host = HostFixture(root, manifest, public, frozenset({"release"}),
                           Ed25519PrivateKey.generate()).create(_uid(5), _uid(6), _uid(2))
        binding = host.prepare(claim, _uid(4), _observe, NOW)

        def consume(request):
            issuer.send_bytes(request)
            return issuer.recv_bytes()

        if case_id == REPLAY:
            code, assertions = _replay(host, claim, binding, consume)
        else:
            result = host.bootstrap(consume, lambda: _observe(case_id != INACTIVE), _clock)
            snapshot = host.snapshot()
            code = result.code
            assertions = {"no-publication": not result.committed
                          and snapshot["operation_id"] == binding.operation_id
                          and [snapshot[k] for k in ("pending", "receipts", "admins", "audit")]
                          == [1, 0, 0, 0]}
        issuer.send_bytes(SNAPSHOT)
        calls, consumed, first, receipt = issuer.recv()
        if case_id == REPLAY:
            assertions["same-receipt"] = (
                first is not None and first == receipt == host.snapshot()["receipt_sha256"]
            )
        assertions["issuer-effects"] = (calls, consumed) == {
            REPLAY: (2, 1), REVOKED: (1, 0), INACTIVE: (0, 0),
        }[case_id]
        report.send_bytes(p.canonical({"actual_code": code, "assertions": assertions}))


def _child(target, *args):
    try:
        target(*args)
    except (Exception, KeyboardInterrupt):
        # Private paths and exception input never cross the worker boundary.
        raise SystemExit(1) from None


def _seconds_left(deadline):
    return max(0, deadline - monotonic_ns()) / 1_000_000_000


def _execute(root, case_id, deadline):
    ctx = multiprocessing.get_context("spawn")
    a, b = ctx.Pipe()
    receive, send = ctx.Pipe(duplex=False)
    children = [
        ctx.Process(target=_child, args=(_issuer, root / "issuer", case_id, a)),
        ctx.Process(target=_child, args=(_host, root / "host", case_id, b, send)),
    ]
    started = []
    try:
        for child in children:
            child.start()
            started.append(child)
        for channel in (a, b, send):
            channel.close()
        if not receive.poll(_seconds_left(deadline)):
            raise Stop("CASE_TIMEOUT")
        observation = p.parse_observation(receive.recv_bytes(p.PACKET_BYTES))
        for child in started:
            child.join(_seconds_left(deadline))
            if child.is_alive():
                raise Stop("CASE_TIMEOUT")
            if child.exitcode:
                raise Stop("CASE_PROCESS_FAILED")
        if _seconds_left(deadline) == 0:
            raise Stop("CASE_TIMEOUT")
        return observation
    except (EOFError, OSError, p.ProtocolInputError):
        raise Stop("CASE_PROCESS_FAILED") from None
    finally:
        for channel in (a, b, send, receive):
            channel.close()
        for child in started:
            if child.is_alive():
                child.kill()
            child.join(5)
            child.close()


def _write(path, raw):
    if len(raw) > p.PACKET_BYTES:
        raise Stop("ARTIFACT_TOO_LARGE")
    _direct(path.parent, directory=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    if _read(path) != raw:
        raise Stop("ARTIFACT_WRITE_MISMATCH")
    return p.Artifact(alias=path.name, sha256=digest(raw))


def _run_case(case, output, common, environment, platform, deadline):
    started = monotonic_ns()
    try:
        limit = min(started + p.CASE_NS, deadline)
        if _seconds_left(limit) == 0:
            raise Stop("PLATFORM_TIMEOUT")
        with TemporaryDirectory(dir=output) as scratch:
            observed = _execute(Path(scratch), case.case_id, limit)
        if _seconds_left(limit) == 0:
            raise Stop("CASE_TIMEOUT")
        if set(observed.assertions) != set(case.assertion_ids):
            raise Stop("ASSERTION_SET_MISMATCH")
        actual, assertions = observed.actual_code, observed.assertions
        outcome = ("PASS" if actual == case.expected_code and all(assertions.values()) else "FAIL")
    except Stop as stop:
        actual, outcome = str(stop), "STOP"
        assertions = dict.fromkeys(case.assertion_ids, False)
    elapsed = monotonic_ns() - started
    details = {
        "case_id": case.case_id, "platform": platform, "outcome": outcome,
        "expected_code": case.expected_code, "actual_code": actual,
        "assertion_ids": case.assertion_ids,
        "fixture_sha256": digest(p.canonical({
            "case": case.model_dump(), "recipe": environment["sources_sha256"]["controller.py"],
        })),
        "duration_ns": min(elapsed, p.CASE_NS),
    }
    artifact = _write(output / f"{case.case_id}.json", p.canonical({
        **common, **details, "assertions": assertions, "environment": environment,
        "elapsed_ns": elapsed,
    }))
    return p.OfflineCase(**details, artifacts=[artifact])


def _offline(run, cases, output):
    platform = {"linux": "linux", "win32": "windows"}.get(sys.platform)
    if platform is None:
        raise Stop("UNSUPPORTED_PLATFORM")
    _absolute(output)
    _direct(output.parent, directory=True)
    if ROOT in (output, *output.parents) or any(
        os.path.lexists(parent / ".git") for parent in output.parents
    ):
        raise Stop("OUTPUT_IN_WORKTREE")
    environment = {
        "python": list(sys.version_info[:3]),
        "sources_sha256": {
            name: digest(_read(HERE / name)) for name in (
                "controller.py", "protocol.py", "host_fixture.py", "licensing_fixture.py",
            )
        },
    }
    output.mkdir(mode=0o700)
    _direct(output, directory=True)
    common = run.model_dump(exclude={"fixtures", "case_ids"})
    artifacts = [_write(output / "run.json", p.packet_bytes(run))]
    deadline = monotonic_ns() + PLATFORM_NS
    results = []
    for case in cases:
        result = _run_case(case, output, common, environment, platform, deadline)
        results.append(result)
        artifacts.extend(result.artifacts)
    raw = p.packet_bytes(p.OfflineResult(**common, cases=results))
    for item in artifacts:
        if digest(_read(output / item.alias)) != item.sha256:
            raise Stop("ARTIFACT_CHANGED")
    artifacts.append(p.Artifact(alias="result.json", sha256=digest(raw)))
    _write(output / "hashes.json", p.canonical({
        **common, "artifacts": [item.model_dump() for item in artifacts],
    }))
    _write(output / "result.pending", raw)
    os.replace(output / "result.pending", output / "result.json")
    outcomes = {result.outcome for result in results}
    return raw, 2 if "STOP" in outcomes else int("FAIL" in outcomes)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop("INVALID_ARGUMENTS")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv and argv[0] in NATIVE_COMMANDS:
            raise Stop("NATIVE_EXECUTION_DISABLED")
        parser = Parser(allow_abbrev=False)
        parser.add_argument("command", choices=("inspect", "offline"))
        parser.add_argument("--manifest", required=True, type=Path)
        parser.add_argument("--output-root", type=Path)
        args = parser.parse_args(argv)
        if (args.command == "offline") != (args.output_root is not None):
            raise Stop("OUTPUT_ROOT_REQUIRED_FOR_OFFLINE")
        run, cases = _admit(args.manifest)
        if args.command == "inspect":
            raw = p.canonical({"run": run.model_dump(),
                               "cases": [case.model_dump() for case in cases]})
            status = 0
        else:
            raw, status = _offline(run, cases, args.output_root)
    except (Stop, p.ProtocolInputError, OSError) as error:
        reason = "INVALID_PACKET" if isinstance(error, p.ProtocolInputError) else "FILE_UNAVAILABLE"
        if isinstance(error, Stop):
            reason = str(error)
        print(p.canonical({"outcome": "STOP", "reason": reason}).decode("ascii"))
        return 2
    print(raw.decode("ascii"))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
