"""Private offline harness CLI. Entry point: python -m qualification.owner_authority.controller."""

import argparse
import base64
import hashlib
import multiprocessing
import os
import stat
import sys
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic_ns
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import licensing_fixture as lf
from . import protocol as p
from .host_fixture import HostFixture
from .licensing_fixture import IssuerFixture, signed

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
CONTRACT = p.CONTRACT_COMMIT
NATIVE_COMMANDS = frozenset({"preflight", "run", "collect"})
PLATFORM_NS = 3_600_000_000_000
REPLAY = "lost-response-replay"
REVOKED = "revoked-claim"
INACTIVE = "inactive-session"
MALFORMED = "malformed-request-refusal"
RENEWAL = "manifest-renewal"
RECOVERY = "recovery-evidence-admission"
RECOVERY_BEGIN = b"recovery-begin"
CANDIDATES = b"renewal-candidates"
ADVANCE = b"renewal-clock"
ADOPT = b"renewal-adopt"
INSPECT = b"renewal-inspect"
START = "2026-01-01T00:00:00Z"
NOW = datetime(2026, 1, 1, 1, tzinfo=UTC)
SNAPSHOT = b"snapshot"


class Stop(RuntimeError):
    """Only fixed diagnostic codes cross the CLI boundary."""


class RecoveryDeclined(Exception):
    """A valid domain refusal, distinct from a corrupt or failed worker."""

    def __init__(self, refusal: p.RecoveryEvidenceRefusal):
        self.refusal = refusal
        super().__init__(refusal.code)


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
            "expires_at": ("2026-01-01T01:00:01Z" if case_id == RENEWAL else
                           "2026-01-03T00:00:00Z"),
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
        clock = [NOW]
        candidates = _renewal_candidates(issuer, ("release", keys["release"])) \
            if case_id == RENEWAL else None
        first_receipt = receipt_hash = None
        malformed_entries = 0
        connect = lf.connect_store

        def counted_connect(*args, **kwargs):
            nonlocal malformed_entries
            malformed_entries += 1
            return connect(*args, **kwargs)

        while (request := channel.recv_bytes()) != SNAPSHOT:
            if case_id == RECOVERY and request == RECOVERY_BEGIN:
                _recovery_issuer(issuer, channel)
                return
            if case_id == RENEWAL:
                if request == CANDIDATES:
                    channel.send(candidates)
                    continue
                if request == ADVANCE:
                    clock[0] = NOW + timedelta(seconds=2)
                    channel.send(None)
                    continue
                if request == ADOPT:
                    issuer.adopt_manifest(candidates[1], clock[0])
                    channel.send(None)
                    continue
                if request == INSPECT:
                    channel.send((calls, issuer.snapshot()))
                    continue
            calls += 1
            if case_id == MALFORMED:
                if calls == 2:
                    with patch.object(lf, "connect_store", counted_connect):
                        reply = issuer.exchange(request, _clock)
                else:
                    reply = issuer.exchange(request, _clock)
                    receipt_hash = digest(p.admit_fixture_response(reply))
                    if calls == 1:
                        first_receipt = receipt_hash
            else:
                reply = issuer.consume(request, lambda: clock[0])
            if case_id in (REPLAY, RENEWAL):
                receipt_hash = digest(reply)
                if calls == 1:
                    first_receipt = receipt_hash
            channel.send_bytes(reply)
        stats = (calls, issuer.snapshot()["consumptions"], first_receipt, receipt_hash)
        channel.send((*stats, malformed_entries) if case_id == MALFORMED else stats)


def _renewal_candidates(issuer, signer):
    payload = p.verify_signed(issuer.manifest, "manifest", issuer.keys,
                              issuer.release_ids).model_dump()
    return tuple(signed("manifest", payload | {"issued_at": issued, "expires_at": expires}, signer)
                 for issued, expires in (
                     ("2026-01-01T01:00:00Z", "2026-01-03T00:00:00Z"),
                     ("2026-01-01T01:00:01Z", "2026-01-04T00:00:00Z"),
                     ("2026-01-01T01:00:00Z", "2026-01-05T00:00:00Z"),
                     ("2026-01-01T01:00:01Z", "2026-01-03T00:00:00Z"),
                 ))


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


def _malformed_recovery(host, consume):
    requests, diagnostics, replies, counts = [], [], [], []
    clock = [NOW]
    host.hook = lambda name, db: diagnostics.append(name) if name == "malformed_response" else None

    def fresh():
        tick = int((clock[0] - NOW).total_seconds()) * 1_000_000_000
        return _observe().model_copy(update={"authenticated_at_ns": tick, "observed_at_ns": tick})

    def exchange(raw):
        requests.append(p.parse_consume_request(raw))
        if len(requests) == 2:
            changed = requests[-1].model_dump()
            del changed["attempt_id"]
            raw = p.canonical(changed)
        reply = consume(raw)
        replies.append(reply)
        if len(requests) == 1:
            raise TimeoutError  # Issuer committed; host deliberately loses its reply.
        return reply

    original = host.snapshot()
    failed = host.bootstrap_exchange(exchange, fresh, lambda: clock[0])
    pending = host.snapshot()
    counts.append(len(requests))
    clock[0] += timedelta(seconds=1)
    malformed = host.bootstrap_exchange(exchange, fresh, lambda: clock[0])
    unresolved = host.snapshot()
    counts.append(len(requests))
    clock[0] += timedelta(seconds=1)
    result = host.bootstrap_exchange(exchange, fresh, lambda: clock[0])
    published = host.snapshot()
    cached = host.bootstrap_exchange(exchange, fresh, lambda: clock[0])
    counts.append(len(requests))
    diagnostic = p.parse_fixture_response(replies[1])
    return result.code, {
        "pending-after-loss": failed.code == "LICENSING_UNAVAILABLE" and not failed.committed
            and pending == original,
        "malformed-diagnostic": diagnostics == ["malformed_response"]
            and diagnostic.status == 400 and diagnostic.content_type == "application/json"
            and diagnostic.body == p.MALFORMED_BODY,
        "derived-unknown": malformed.code == "LICENSING_UNAVAILABLE" and not malformed.committed
            and unresolved == original and original["pending"] == 1
            and all(original[k] == 0 for k in ("receipts", "admins", "audit")),
        "stable-binding": original["pending_binding_sha256"] is not None
            and all(r.binding == requests[0].binding for r in requests),
        "fresh-attempts": len({r.attempt_id for r in requests}) == 3
            and len({r.requested_at for r in requests}) == 3,
        "no-auto-retry": counts == [1, 2, 3],
        "one-local-triplet": result.committed
            and all(published[k] == 1 for k in ("pending", "receipts", "admins", "audit")),
        "cached-no-dispatch": cached == result and host.snapshot() == published,
    }


def _renewal(host, consume, control):
    clock, requests, counts = [NOW], [], []

    def fresh():
        tick = int((clock[0] - NOW).total_seconds()) * 1_000_000_000
        return _observe().model_copy(update={"authenticated_at_ns": tick, "observed_at_ns": tick})

    def exchange(raw):
        requests.append(p.parse_consume_request(raw))
        reply = consume(raw)
        if len(requests) == 1:
            raise TimeoutError
        return reply

    original = host.snapshot()
    failed = host.bootstrap(exchange, fresh, lambda: clock[0])
    pending = host.snapshot()
    counts.append(len(requests))
    issuer_before = control(INSPECT)
    control(ADVANCE)
    clock[0] = NOW + timedelta(seconds=2)
    unavailable = host.bootstrap(exchange, fresh, lambda: clock[0])
    unresolved = host.snapshot()
    counts.append(len(requests))
    first, second, regressed_issue, regressed_expiry = control(CANDIDATES)
    host.renew_manifest(host.select_renewal(), first, fresh, lambda: clock[0])
    renewed = host.snapshot()
    counts.append(len(requests))
    host.renew_manifest(host.select_renewal(), second, fresh, lambda: clock[0])
    advanced = host.snapshot()
    counts.append(len(requests))

    def refuses(candidate):
        before = host.snapshot()
        rejected = False
        try:
            host.renew_manifest(host.select_renewal(), candidate, fresh, lambda: clock[0])
        except p.ProtocolInputError as error:
            rejected = type(error) is p.ProtocolInputError
        return rejected and host.snapshot() == before

    issue_refused = refuses(regressed_issue)
    expiry_refused = refuses(regressed_expiry)
    checked = host.snapshot()
    control(ADOPT)
    issuer_after = control(INSPECT)
    # Reopen the same root; constructor input cannot replace durable configuration.
    host = HostFixture(host.root, b"ignored restart seed", host.keys, host.release_ids, host.key)
    result = host.bootstrap(exchange, fresh, lambda: clock[0])
    published = host.snapshot()
    counts.append(len(requests))
    cached = host.bootstrap(exchange, fresh, lambda: clock[0]) if result.committed else None
    counts.append(len(requests))
    return result.code, {
        "pending-after-loss": failed.code == "LICENSING_UNAVAILABLE"
            and not failed.committed and pending == original,
        "unavailable-no-dispatch": unavailable.code == "LICENSING_UNAVAILABLE"
            and not unavailable.committed and counts[1] == counts[0],
        "derived-unknown": unresolved == original and unresolved["pending"] == 1
            and all(unresolved[k] == 0 for k in ("receipts", "admins", "audit")),
        "retained-state": all(state["pending_state_sha256"] == original["pending_state_sha256"]
            for state in (pending, unresolved, renewed, advanced, checked, published,
                          host.snapshot())),
        "renewal-only-config-effects": renewed == pending | {
            "installed_manifest_sha256": digest(first)} and advanced == renewed | {
            "installed_manifest_sha256": digest(second)},
        "no-implicit-resume": counts == [1, 1, 1, 1, 2, 2]
            and issuer_before[0] == issuer_after[0] == 1,
        "forward-renewals": renewed["installed_manifest_sha256"] == digest(first)
            and advanced["installed_manifest_sha256"] == digest(second),
        "installed-issue-monotonic": issue_refused,
        "installed-expiry-monotonic": expiry_refused,
        "fresh-attempts": len({r.attempt_id for r in requests}) == 2
            and len({r.requested_at for r in requests}) == 2,
        "one-local-triplet": result.committed and all(
            published[k] == 1 for k in ("pending", "receipts", "admins", "audit")),
        "cached-no-dispatch": cached == result and host.snapshot() == published
            and counts[-1] == counts[-2],
        "issuer-ledger-preserved": issuer_before[1] == issuer_after[1],
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

        def control(command):
            issuer.send_bytes(command)
            return issuer.recv()

        if case_id == RECOVERY:
            try:
                observed = _recovery_host(host, binding, issuer, consume)
            except RecoveryDeclined as declined:
                issuer.send_bytes(p.recovery_control_bytes(
                    p.RecoveryAction(command="finish"), "command"))
                finished = p.parse_recovery_control(issuer.recv_bytes(p.CONTROL_BYTES), "reply")
                if not isinstance(finished, p.RecoveryStatusReply) or finished.kind != "status":
                    raise Stop("RECOVERY_PREREQUISITE_FAILED") from None
                case = next(case for case in p.parse_inventory(_read(HERE / "cases.json")).cases
                            if case.case_id == RECOVERY)
                observed = p.CaseObservation(actual_code=declined.refusal.code,
                    assertions=dict.fromkeys(case.assertion_ids, False))
            report.send_bytes(p.canonical(observed.model_dump()))
            return
        if case_id == REPLAY:
            code, assertions = _replay(host, claim, binding, consume)
        elif case_id == MALFORMED:
            code, assertions = _malformed_recovery(host, consume)
        elif case_id == RENEWAL:
            code, assertions = _renewal(host, consume, control)
        else:
            result = host.bootstrap(consume, lambda: _observe(case_id != INACTIVE), _clock)
            snapshot = host.snapshot()
            code = result.code
            assertions = {"no-publication": not result.committed
                          and snapshot["operation_id"] == binding.operation_id
                          and [snapshot[k] for k in ("pending", "receipts", "admins", "audit")]
                          == [1, 0, 0, 0]}
        issuer.send_bytes(SNAPSHOT)
        stats = issuer.recv()
        calls, consumed, first, receipt = stats[:4]
        if case_id == MALFORMED:
            assertions["malformed-no-ledger"] = stats[4] == 0
        if case_id in (REPLAY, MALFORMED, RENEWAL):
            assertions["same-receipt"] = (
                first is not None and first == receipt == host.snapshot()["receipt_sha256"]
            )
        if case_id == RENEWAL:
            assertions["issuer-exchanges"] = calls == 2
            assertions["issuer-consumptions"] = consumed == 1
        else:
            assertions["issuer-effects"] = (calls, consumed) == {
                REPLAY: (2, 1), REVOKED: (1, 0), INACTIVE: (0, 0), MALFORMED: (3, 1),
            }[case_id]
        report.send_bytes(p.canonical({"actual_code": code, "assertions": assertions}))


@contextmanager
def _count_recovery_calls(owner, methods):
    """Count actual owner entry, including nested/implicit calls, after setup."""
    counts = dict.fromkeys(set(methods.values()), 0)
    with ExitStack() as patches:
        for name, counter in methods.items():
            original = getattr(owner, name)

            def wrapped(function, field):
                @wraps(function)
                def call(*args, **kwargs):
                    counts[field] += 1
                    return function(*args, **kwargs)
                return call

            patches.enter_context(patch.object(owner, name, wrapped(original, counter)))
        yield counts


def _reopen_recovery_issuer(issuer):
    return IssuerFixture(issuer.root, issuer.manifest, issuer.keys, issuer.release_ids,
                         issuer.claim_signer, issuer.receipt_signer)


def _recovery_issuer(issuer, channel):
    clock = [NOW]
    first = None
    methods = {"open_recovery_case": "opens", "select_recovery_evidence": "selections",
               "admit_recovery_evidence": "admissions", "__init__": "reopens"}
    methods.update(dict.fromkeys(
        ("consume", "exchange", "issue", "reissue", "revoke", "adopt_manifest"), "dispatches"))
    with _count_recovery_calls(IssuerFixture, methods) as counts:
        def status():
            original, recovery = issuer.snapshot(), issuer.recovery_snapshot()
            return p.RecoveryStatus.model_validate({
                "ledger_sha256": original["ledger_sha256"],
                "recovery_sha256": recovery["sha256"], "cases": recovery["cases"],
                "admissions": recovery["admissions"], "consumptions": original["consumptions"],
                "first_admission_sha256": first, "calls": counts,
            })

        while True:
            command = p.parse_recovery_control(channel.recv_bytes(p.CONTROL_BYTES), "command")
            result = None
            if isinstance(command, p.RecoveryOpen):
                raw = issuer.open_recovery_case(
                    command.case_id, command.predecessor_claim_id, command.predecessor_operation_id,
                    command.replacement, command.opened_at, command.expires_at,
                    clock=lambda: clock[0])
                kind = "case"
            elif isinstance(command, p.RecoverySelect):
                raw = issuer.select_recovery_evidence(command.case_id, lambda: clock[0])
                kind = "selection"
            elif isinstance(command, p.RecoveryAdmit):
                raw = issuer.admit_recovery_evidence(
                    command.selection, p.recovery_bytes(command.envelope), lambda: clock[0])
                kind = "admission"
            else:
                if command.command == "reopen":
                    issuer = _reopen_recovery_issuer(issuer)
                elif command.command == "expire":
                    clock[0] = NOW + timedelta(minutes=30)
                result = p.RecoveryStatusReply(kind="status", status=status())
            if result is None:
                # Explicit expected type; a refusal never means a prior commit did not occur.
                try:
                    value = p.parse_recovery(raw, kind)
                except p.ProtocolInputError:
                    value = p.parse_recovery(raw, "refusal")
                    kind = "refusal"
                if kind == "admission" and first is None:
                    first = digest(raw)
                if kind == "admission" and command.command == "admit-lost":
                    result = p.RecoveryStatusReply(kind="lost", status=status())
                else:
                    model = {"case": p.RecoveryCaseReply, "selection": p.RecoverySelectionReply,
                             "admission": p.RecoveryAdmissionReply,
                             "refusal": p.RecoveryRefusalReply}
                    result = model[kind](kind=kind, value=value, status=status())
            channel.send_bytes(p.recovery_control_bytes(result, "reply"))
            if command.command == "finish":
                return


def _retirement_envelope(host, case, evidence_id):
    common = {"version": "offline-recovery-evidence/1", "evidence_class": "OFFLINE_CONFORMANCE",
              "qualification_pass": False}
    evidence = p.RetirementEvidence.model_validate(common | {
        "purpose": "offline-predecessor-retirement-evidence", "evidence_id": evidence_id,
        "case_id": case.case_id, "case_sha256": digest(p.recovery_bytes(case)),
        "predecessor_receipt_sha256": case.predecessor_receipt_sha256,
        "replacement_sha256": digest(p.recovery_bytes(case.replacement)),
        "asserted_at": "2026-01-01T01:00:00Z", "expires_at": "2026-01-01T01:30:00Z",
        "assertion": "SYNTHETIC_RETIREMENT_ONLY",
    })
    raw = p.recovery_bytes(evidence)
    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    return p.RetirementEvidenceEnvelope.model_validate(common | {
        "payload_base64url": encode(raw),
        "signature_base64url": encode(host.key.sign(p.RETIREMENT_PREFIX + raw)),
    })


def _recovery_document(reply, expected):
    if isinstance(reply, p.RecoveryRefusalReply):
        raise RecoveryDeclined(reply.value)
    if not isinstance(reply, expected):
        raise Stop("RECOVERY_PREREQUISITE_FAILED")
    return reply.value


def _recovery_host(host, binding, channel, consume):
    setup = host.bootstrap(consume, _observe, _clock)
    if not setup.committed:
        raise Stop("RECOVERY_SETUP_FAILED")
    replacement = HostFixture(host.root.parent / "replacement", host._initial_manifest,
                              host.keys, host.release_ids, Ed25519PrivateKey.generate()).create(
                                  _uid(21), _uid(22), binding.organization_id)
    original_before, replacement_before = host.recovery_snapshot(), replacement.recovery_snapshot()
    original_receipt = host.snapshot()["receipt_sha256"]
    common = {"version": "offline-recovery-evidence/1", "evidence_class": "OFFLINE_CONFORMANCE",
              "qualification_pass": False}
    target = p.ReplacementTarget.model_validate(common | {
        "operation_id": _uid(20), "installation_id": replacement_before.installation_id,
        "host_id": replacement_before.host_id,
        "organization_id": replacement_before.organization_id,
        "entitlement_id": binding.entitlement_id,
        "installation_public_key": replacement_before.installation_public_key,
        "principal_commitment": binding.principal_commitment,
        "initialization_sha256": replacement_before.configuration_sha256,
    })
    opening = p.RecoveryOpen(command="open", case_id=_uid(23),
                             predecessor_claim_id=binding.claim_id,
                             predecessor_operation_id=binding.operation_id, replacement=target,
                             opened_at="2026-01-01T01:00:00Z", expires_at="2026-01-01T03:00:00Z")

    def rpc(command):
        channel.send_bytes(p.recovery_control_bytes(command, "command"))
        return p.parse_recovery_control(channel.recv_bytes(p.CONTROL_BYTES), "reply")

    def action(name):
        reply = rpc(p.RecoveryAction(command=name))
        if not isinstance(reply, p.RecoveryStatusReply) or reply.kind != "status":
            raise Stop("RECOVERY_PREREQUISITE_FAILED")
        return reply.status

    channel.send_bytes(RECOVERY_BEGIN)
    methods = dict.fromkeys(("bootstrap", "bootstrap_exchange", "prepare", "renew_manifest"),
                            "dispatches")
    with _count_recovery_calls(HostFixture, methods) as calls:
        before = action("inspect")
        case = _recovery_document(rpc(opening), p.RecoveryCaseReply)
        selected = _recovery_document(rpc(p.RecoverySelect(command="select", case_id=case.case_id)),
                                      p.RecoverySelectionReply)
        envelope = _retirement_envelope(host, case, _uid(24))
        lost_reply = rpc(p.RecoveryAdmit(
            command="admit-lost", selection=selected, envelope=envelope))
        if isinstance(lost_reply, p.RecoveryRefusalReply):
            raise RecoveryDeclined(lost_reply.value)
        lost = action("inspect")
        reopened = action("reopen")
        case_again = _recovery_document(rpc(opening), p.RecoveryCaseReply)
        reply = rpc(p.RecoveryAdmit(command="admit", selection=selected, envelope=envelope))
        admission = _recovery_document(reply, p.RecoveryAdmissionReply)
        replayed = reply.status
        changed = _retirement_envelope(host, case, _uid(25))
        conflict = rpc(p.RecoveryAdmit(command="admit", selection=selected, envelope=changed))
        action("expire")
        expired = rpc(p.RecoveryAdmit(command="admit", selection=selected, envelope=envelope))
        finished = action("finish")
        original_after = host.recovery_snapshot()
        replacement_after = replacement.recovery_snapshot()
        trace = p.RecoveryProof(
            before=before, lost=lost, replayed=replayed, conflicted=conflict.status,
            expired=expired.status, finished=finished, case_sha256=digest(p.recovery_bytes(case)),
            reopened_case_sha256=digest(p.recovery_bytes(case_again)),
            admission_sha256=digest(p.recovery_bytes(admission)),
            predecessor_before_sha256=original_before.state_sha256,
            predecessor_after_sha256=original_after.state_sha256,
            replacement_before_sha256=replacement_before.state_sha256,
            replacement_after_sha256=replacement_after.state_sha256,
            host_dispatches=calls["dispatches"],
        )
    states = (lost, replayed, conflict.status, expired.status, finished)
    assertions = {
        "source-bound-case": case.predecessor_binding == binding
            and case.predecessor_receipt_sha256 == original_receipt and case.replacement == target,
        "same-case-on-reopen": trace.case_sha256 == trace.reopened_case_sha256
            and reopened.calls.reopens == 1 and replayed.calls.opens == 2,
        "admission-evidence-only": admission.state == "EVIDENCE_RECORDED_ONLY"
            and admission.case_id == case.case_id and admission.evidence_id == _uid(24)
            and admission.case_sha256 == trace.case_sha256
            and admission.evidence_sha256 == digest(p.recovery_bytes(envelope))
            and admission.predecessor_receipt_sha256 == original_receipt
            and admission.replacement_sha256 == digest(p.recovery_bytes(target)),
        "lost-reply-retained": isinstance(lost_reply, p.RecoveryStatusReply)
            and lost_reply.kind == "lost" and lost.admissions == 1,
        "explicit-replay-only": [state.calls.admissions for state in (before, *states)]
            == [0, 1, 2, 3, 4, 4] and reopened.calls.admissions == 1,
        "same-admission-on-reopen": trace.admission_sha256 == lost.first_admission_sha256
            and replayed.calls.reopens == 1,
        "one-recovery-pair": all(state.cases == state.admissions == 1
            and state.recovery_sha256 == lost.recovery_sha256 for state in states),
        "changed-evidence-conflict": isinstance(conflict, p.RecoveryRefusalReply)
            and conflict.value.code == "RECOVERY_BINDING_CONFLICT"
            and conflict.status.recovery_sha256 == replayed.recovery_sha256,
        "expired-replay-preserves-history": isinstance(expired, p.RecoveryRefusalReply)
            and expired.value.code == "RECOVERY_EVIDENCE_EXPIRED"
            and expired.status.recovery_sha256 == conflict.status.recovery_sha256,
        "issuer-original-preserved": all(state.ledger_sha256 == before.ledger_sha256
            and state.consumptions == 1 for state in states),
        "predecessor-host-preserved": original_after == original_before,
        "replacement-host-unpublished": replacement_after == replacement_before
            and all(getattr(replacement_after, k) == 0
                    for k in ("pending", "receipts", "admins", "audit")),
        "recovery-no-bootstrap-dispatch": trace.host_dispatches == 0
            and all(state.calls.dispatches == 0 for state in (before, *states)),
    }
    return p.CaseObservation(actual_code=admission.state, assertions=assertions, recovery=trace)


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
    observed = None
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
        if ((case.case_id != RECOVERY and observed.recovery is not None)
                or (case.case_id == RECOVERY and observed.actual_code == case.expected_code
                    and observed.recovery is None)):
            raise Stop("RECOVERY_PROOF_MISMATCH")
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
        **({"recovery": observed.recovery.model_dump()}
           if observed is not None and observed.recovery is not None else {}),
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
        if isinstance(error, p.ContractMismatchError):
            reason = "CONTRACT_MISMATCH"
        if isinstance(error, Stop):
            reason = str(error)
        print(p.canonical({"outcome": "STOP", "reason": reason}).decode("ascii"))
        return 2
    print(raw.decode("ascii"))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
