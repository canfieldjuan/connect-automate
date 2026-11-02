"""Disposable synthetic stores only; no native authentication or real issuer."""

import base64
import hashlib
import importlib
import json
import multiprocessing
import os
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import wait
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

p = importlib.import_module("qualification.owner_authority.protocol")

START = datetime(2026, 1, 1, tzinfo=UTC)
NOW = START + timedelta(hours=1)


def uid(index):
    return f"{index:08x}-1111-4111-8111-111111111111"


def instant(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class SyntheticWire:
    def __init__(self, seeds=None):
        self.seeds = seeds if seeds is not None else {
            name: secrets.token_bytes(32) for name in ("release", "claim", "receipt", "host")
        }
        self.private = {k: Ed25519PrivateKey.from_private_bytes(v) for k, v in self.seeds.items()}
        self.public = {k: v.public_key().public_bytes_raw() for k, v in self.private.items()}
        self.manifest = self.sign("manifest", {
            "version": "owner-bootstrap/1", "purpose": "owner-bootstrap-activation",
            "origin": "https://fixture.example", "claim_key_ids": ["claim"],
            "receipt_key_ids": ["receipt"], "issued_at": instant(START),
            "expires_at": instant(START + timedelta(days=2)),
        }, "release")

    def sign(self, kind, payload, key):
        raw = p.canonical(payload)
        return p.canonical({
            "version": "owner-bootstrap/1", "key_id": key, "payload_base64url": b64(raw),
            "signature_base64url": b64(self.private[key].sign(p.prefix(kind) + raw)),
        })

    def claim(self, index=1, generation=1, issued=START, expires=None):
        return p.OwnerClaim.model_validate({
            "version": "owner-bootstrap/1", "purpose": "owner-bootstrap", "claim_id": uid(index),
            "organization_id": uid(2), "entitlement_id": uid(3), "generation": generation,
            "issued_at": instant(issued), "not_before": instant(issued),
            "expires_at": instant(issued + timedelta(hours=12) if expires is None else expires),
        })

    def request(self, claim, operation=4, installation=5, now=NOW, attempt=7, **changed):
        payload = p.verify_signed(claim, "claim", self.public, frozenset({"claim"}))
        binding = {
            "version": "owner-bootstrap/1", "operation_id": uid(operation),
            "installation_id": uid(installation), "host_id": uid(6),
            "organization_id": payload.organization_id, "claim_id": payload.claim_id,
            "entitlement_id": payload.entitlement_id, "generation": payload.generation,
            "claim_sha256": hashlib.sha256(claim).hexdigest(), "principal_commitment": "b" * 64,
            "initialization_sha256": "c" * 64, "installation_public_key": b64(self.public["host"]),
        } | changed
        signed = {"version": "owner-bootstrap/1", "binding": binding,
                  "attempt_id": uid(attempt), "requested_at": instant(now)}
        return p.canonical(signed | {"owner_claim": json.loads(claim),
            "installation_signature": b64(self.private["host"].sign(
                p.prefix("consume") + p.canonical(signed)))})

    def issuer(self, root, create=False, hook=None):
        from qualification.owner_authority.licensing_fixture import IssuerFixture

        issuer = IssuerFixture(root, self.manifest, self.public, frozenset({"release"}),
                               ("claim", self.private["claim"]),
                               ("receipt", self.private["receipt"]), hook=hook)
        return issuer.create() if create else issuer

    def host(self, root, create=False, hook=None):
        from qualification.owner_authority.host_fixture import HostFixture

        host = HostFixture(root, self.manifest, self.public, frozenset({"release"}),
                           self.private["host"], hook=hook)
        return host.create(uid(5), uid(6), uid(2)) if create else host


def test_issuer_receipt_is_durable_and_replay_is_identical(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    request = wire.request(claim)
    receipt = issuer.consume(request, lambda: NOW)
    assert p.check_receipt(receipt, request, wire.manifest, wire.public,
                           frozenset({"release"}), NOW).binding.operation_id == uid(4)
    restarted = wire.issuer(tmp_path / "issuer")
    assert restarted.consume(request, lambda: NOW) == receipt
    assert restarted.snapshot()["consumptions"] == 1


def test_operation_identity_conflict_is_typed_not_a_sql_error(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    first = issuer.issue(wire.claim(), START)
    other = wire.claim(index=10).model_copy(update={"entitlement_id": uid(11)})
    second = issuer.issue(other, START)
    issuer.consume(wire.request(first), lambda: NOW)
    before = issuer.snapshot()
    refused = p.parse_refusal(issuer.consume(wire.request(second), lambda: NOW))
    assert refused.code == "OWNER_BINDING_CONFLICT"
    assert issuer.snapshot() == before


@pytest.mark.parametrize("changed", [
    {"operation_id": uid(9)}, {"installation_id": uid(9)}, {"host_id": uid(9)},
    {"principal_commitment": "d" * 64}, {"initialization_sha256": "d" * 64},
])
def test_otherwise_authenticated_changed_binding_never_replaces_owner(tmp_path, changed):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    original = issuer.consume(wire.request(claim), lambda: NOW)
    before = issuer.snapshot()
    reply = issuer.consume(wire.request(claim, **changed), lambda: NOW)
    assert p.parse_refusal(reply).code == "OWNER_BINDING_CONFLICT"
    assert issuer.snapshot() == before
    assert issuer.consume(wire.request(claim), lambda: NOW) == original


def test_expired_claim_recovers_receipt_but_cannot_be_consumed_new(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    receipt = issuer.consume(wire.request(claim), lambda: NOW)
    late = START + timedelta(hours=13)
    replay = wire.request(claim, now=late, attempt=8)
    assert issuer.consume(replay, lambda: late) == receipt
    other = wire.issuer(tmp_path / "other", create=True)
    other_claim = other.issue(wire.claim(), START)
    before = other.snapshot()
    reply = other.consume(wire.request(other_claim, now=late), lambda: late)
    assert p.parse_refusal(reply).code == "OWNER_AUTHORIZATION_EXPIRED"
    assert other.snapshot() == before


@pytest.mark.parametrize("offset", [-61, -60, -59, 0, 59, 60, 61])
@pytest.mark.parametrize("replay", [False, True])
def test_attempt_window_applies_before_lookup_for_new_and_replay(
        tmp_path, monkeypatch, offset, replay):
    from qualification.owner_authority import licensing_fixture as lane

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    if replay:
        issuer.consume(wire.request(claim), lambda: NOW)
    def clock():
        return NOW + timedelta(seconds=offset)
    if abs(offset) > 60:
        monkeypatch.setattr(lane, "connect_store", lambda *a: pytest.fail("clock reached ledger"))
        with pytest.raises(p.ClockSkewError):
            issuer.consume(wire.request(claim), clock)
    else:
        receipt = issuer.consume(wire.request(claim), clock)
        assert p.check_receipt(receipt, wire.request(claim), wire.manifest, wire.public,
                               frozenset({"release"}), clock()).binding.operation_id == uid(4)


def test_authentication_and_clock_rechecked_after_writer_wait(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    before = issuer.snapshot()
    clock = [NOW]

    def waited(name, db):
        if name == "writer":
            clock[0] += timedelta(seconds=61)
            db.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY
                              if action == sqlite3.SQLITE_READ else sqlite3.SQLITE_OK)

    issuer.hook = waited
    with pytest.raises(p.ClockSkewError):
        issuer.consume(wire.request(claim), lambda: clock[0])
    issuer.hook = None
    assert issuer.snapshot() == before


def test_claim_expiry_while_waiting_before_commit_rolls_back(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(expires=NOW + timedelta(seconds=1)), START)
    before = issuer.snapshot()
    clock = [NOW]

    def waited(name, db):
        if name == "before_commit":
            clock[0] += timedelta(seconds=1)

    issuer.hook = waited
    reply = issuer.consume(wire.request(claim), lambda: clock[0])
    assert p.parse_refusal(reply).code == "OWNER_AUTHORIZATION_EXPIRED"
    issuer.hook = None
    assert issuer.snapshot() == before


def test_forged_request_cannot_touch_ledger(tmp_path, monkeypatch):
    from qualification.owner_authority import licensing_fixture as lane

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    request = json.loads(wire.request(claim)) | {"installation_signature": b64(b"\0" * 64)}
    monkeypatch.setattr(lane, "connect_store", lambda *a: pytest.fail("forgery reached ledger"))
    with pytest.raises(p.ProtocolInputError):
        issuer.consume(p.canonical(request), lambda: NOW)


def test_reissue_supersedes_atomically_and_consumed_claim_never_reissues(tmp_path):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    old = issuer.issue(wire.claim(), START)
    new = issuer.reissue(uid(1), wire.claim(index=10, generation=2, issued=NOW), NOW)
    assert p.parse_refusal(issuer.consume(wire.request(old), lambda: NOW)).code == (
        "OWNER_AUTHORIZATION_REVOKED")
    receipt = issuer.consume(wire.request(new), lambda: NOW)
    before = issuer.snapshot()
    assert issuer.revoke(uid(10)) == "CONSUMED"
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        issuer.reissue(uid(10), wire.claim(index=12, generation=3, issued=NOW), NOW)
    assert issuer.snapshot() == before
    assert issuer.consume(wire.request(new), lambda: NOW) == receipt


@pytest.mark.parametrize("change", ["same_id", "same_generation", "organization", "entitlement"])
def test_reissue_binding_and_generation_have_independent_negatives(tmp_path, change):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    issuer.issue(wire.claim(), START)
    data = wire.claim(index=10, generation=2, issued=NOW).model_dump()
    field, value = {"same_id": ("claim_id", uid(1)), "same_generation": ("generation", 1),
                    "organization": ("organization_id", uid(20)),
                    "entitlement": ("entitlement_id", uid(20))}[change]
    before = issuer.snapshot()
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        issuer.reissue(uid(1), p.OwnerClaim.model_validate(data | {field: value}), NOW)
    assert issuer.snapshot() == before


def test_fresh_storage_missing_storage_and_restored_backup_fail_closed(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    with pytest.raises(FileExistsError):
        wire.issuer(tmp_path / "issuer", create=True)
    with pytest.raises(sqlite3.OperationalError):
        wire.issuer(tmp_path / "missing").snapshot()
    restored = issuer.restore_to(tmp_path / "restored")
    assert p.parse_refusal(restored.consume(wire.request(claim), lambda: NOW)).code == (
        "LICENSING_UNAVAILABLE")
    assert issuer.snapshot()["consumptions"] == 0


def _issuer_child(root, seeds, action, argument, channel, start, release, pause, fault):
    wire = SyntheticWire(seeds)

    def hook(name, db):
        if name == pause:
            channel.send(("paused", name))
            if not release.wait(30):
                raise TimeoutError("parent did not release fixture")
        if fault is not None and name == fault[0]:
            if fault[1] == "crash":
                os._exit(71)
            db.execute("SELECT deliberately_missing_fault_column")

    issuer = wire.issuer(root, hook=hook)
    channel.send(("ready", None))
    if not start.wait(30):
        return
    try:
        if action == "consume":
            result = issuer.consume(argument, lambda: NOW)
        elif action == "revoke":
            result = issuer.revoke(uid(1))
        elif action == "issue":
            result = issuer.issue(wire.claim(), START)
        else:
            result = issuer.reissue(uid(1), wire.claim(index=10, generation=2, issued=NOW), NOW)
        channel.send(("result", result))
    except Exception as exc:
        channel.send(("error", type(exc).__name__, str(exc)))
    finally:
        channel.close()


@contextmanager
def worker(wire, root, action, argument=None, pause=None, fault=None):
    context = multiprocessing.get_context("spawn")
    receiving, sending = context.Pipe(duplex=False)
    start, release = context.Event(), context.Event()
    child = context.Process(target=_issuer_child,
                            args=(root, wire.seeds, action, argument, sending, start, release,
                                  pause, fault))
    child.start()
    sending.close()

    def receive():
        assert receiving.poll(30), "fixture child timed out"
        return receiving.recv()

    try:
        assert receive() == ("ready", None)
        yield child, start, release, receive
    finally:
        release.set()
        start.set()
        child.join(10)
        if child.is_alive():
            child.terminate()
            child.join(10)
        receiving.close()


@pytest.mark.parametrize("other", ["consume", "revoke", "reissue"])
@pytest.mark.parametrize("first", ["consume", "other"])
@pytest.mark.parametrize("repeat", range(3))
def test_both_race_winners_in_real_processes(tmp_path, other, first, repeat):
    wire = SyntheticWire()
    root = tmp_path / "issuer"
    issuer = wire.issuer(root, create=True)
    claim = issuer.issue(wire.claim(), START)
    actions = [("consume", wire.request(claim)),
               (other, wire.request(claim, operation=20, installation=21))]
    if first == "other":
        actions.reverse()
    with worker(wire, root, *actions[0], pause="writer") as leader:
        leader[1].set()
        assert leader[3]() == ("paused", "writer")
        with worker(wire, root, *actions[1], pause="before_writer") as follower:
            follower[1].set()
            assert follower[3]() == ("paused", "before_writer")
            follower[2].set()
            leader[2].set()
            outcomes = [leader[3](), follower[3]()]
    assert leader[0].exitcode == follower[0].exitcode == 0
    consumed_first = first == "consume" or other == "consume"
    assert issuer.snapshot()["consumptions"] == int(consumed_first)
    if consumed_first:
        won = p.verify_signed(outcomes[0][1], "receipt", wire.public, frozenset({"receipt"}))
        assert won.binding.operation_id == uid(4 if first == "consume" else 20)
        if other == "consume":
            assert p.parse_refusal(outcomes[1][1]).code == "OWNER_BINDING_CONFLICT"
        elif other == "reissue":
            assert outcomes[1][0:2] == ("error", "Refused")
        else:
            assert outcomes[1] == ("result", "CONSUMED")
    else:
        assert p.parse_refusal(outcomes[1][1]).code == "OWNER_AUTHORIZATION_REVOKED"


@pytest.mark.parametrize("point", [
    "consumption_write", "journal_write", "before_commit", "after_commit",
])
@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_issuer_faults_do_not_publish_partial_receipts(tmp_path, point, fault):
    wire = SyntheticWire()
    root = tmp_path / "issuer"
    issuer = wire.issuer(root, create=True)
    claim = issuer.issue(wire.claim(), START)
    before = issuer.snapshot()
    request = wire.request(claim)
    with worker(wire, root, "consume", request, fault=(point, fault)) as child:
        child[1].set()
        if fault == "sql":
            assert child[3]()[0:2] == ("error", "OperationalError")
        child[0].join(30)
        assert child[0].exitcode == (71 if fault == "crash" else 0)
    restarted = wire.issuer(root)
    if point != "after_commit":
        assert restarted.snapshot() == before
    else:
        assert restarted.snapshot()["consumptions"] == 1
    receipt = restarted.consume(request, lambda: NOW)
    assert restarted.consume(request, lambda: NOW) == receipt
    assert restarted.snapshot()["consumptions"] == 1


@pytest.mark.parametrize("action,point", [
    ("issue", "claim_write"), ("issue", "journal_write"), ("issue", "after_commit"),
    ("revoke", "revocation_write"), ("revoke", "journal_write"), ("revoke", "after_commit"),
    ("reissue", "supersession_write"), ("reissue", "claim_write"),
    ("reissue", "journal_write"), ("reissue", "before_commit"), ("reissue", "after_commit"),
])
@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_admin_fixture_transactions_are_atomic(tmp_path, action, point, fault):
    wire = SyntheticWire()
    root = tmp_path / "issuer"
    issuer = wire.issuer(root, create=True)
    if action != "issue":
        issuer.issue(wire.claim(), START)
    before = issuer.snapshot()
    with worker(wire, root, action, fault=(point, fault)) as child:
        child[1].set()
        if fault == "sql":
            assert child[3]()[0:2] == ("error", "OperationalError")
        child[0].join(30)
        assert child[0].exitcode == (71 if fault == "crash" else 0)
    after = wire.issuer(root).snapshot()
    if point != "after_commit":
        assert after == before
    else:
        assert len(after["journal"]) == len(before["journal"]) + 1
        if action == "reissue":
            assert after["claims"] == [(uid(1), "SUPERSEDED"), (uid(10), "ACTIVE")]
        else:
            assert after["claims"] == [(uid(1), "ACTIVE" if action == "issue" else "REVOKED")]


def test_activation_issuance_time_and_duplicate_issue_do_not_change_state(tmp_path):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    before = issuer.snapshot()
    with pytest.raises(p.ProtocolInputError):
        # An earlier purchase/claim time cannot be activation issuance.
        issuer.issue(wire.claim(), NOW)
    assert issuer.snapshot() == before
    current = wire.claim(issued=NOW)
    assert p.verify_signed(issuer.issue(current, NOW), "claim", wire.public,
                           frozenset({"claim"})).issued_at == instant(NOW)
    before = issuer.snapshot()
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        issuer.issue(wire.claim(index=20, issued=NOW), NOW)
    assert issuer.snapshot() == before


def test_missing_claim_and_unregistered_signed_claim_never_consume(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = wire.sign("claim", wire.claim().model_dump(), "claim")
    before = issuer.snapshot()
    assert p.parse_refusal(issuer.consume(wire.request(claim), lambda: NOW)).code == (
        "OWNER_AUTHORIZATION_INVALID")
    assert issuer.snapshot() == before


def test_signer_mismatch_and_wrong_owner_refuse_before_business_rows(tmp_path):
    from qualification.owner_authority import licensing_fixture as lane

    wire = SyntheticWire()
    with pytest.raises(p.ProtocolInputError):
        lane.IssuerFixture(tmp_path / "missing", wire.manifest, wire.public,
                           frozenset({"release"}), ("claim", wire.private["claim"]),
                           ("receipt", wire.private["host"]))
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    with pytest.raises(lane.FixtureCorrupt), lane.read_store(issuer.root, "host"):
        pytest.fail("wrong storage owner admitted")
    with pytest.raises(lane.FixtureCorrupt), lane.transaction(issuer.root, "host"):
        pytest.fail("wrong writer owner admitted")
    assert issuer.snapshot()["claims"] == []


def test_not_yet_eligible_claim_is_not_reported_expired(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = wire.claim().model_copy(update={"not_before": instant(NOW + timedelta(seconds=1))})
    raw = issuer.issue(claim, START)
    before = issuer.snapshot()
    assert p.parse_refusal(issuer.consume(wire.request(raw), lambda: NOW)).code == (
        "OWNER_AUTHORIZATION_INVALID")
    assert issuer.snapshot() == before
    eligible = NOW + timedelta(seconds=1)
    reply = issuer.consume(wire.request(raw, now=eligible), lambda: eligible)
    assert p.check_receipt(reply, wire.request(raw, now=eligible), wire.manifest, wire.public,
                           frozenset({"release"}), eligible).binding.operation_id == uid(4)


def test_new_consume_refuses_revocation_and_copied_claim_with_another_key(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    raw = issuer.issue(wire.claim(), START)
    receipt = issuer.consume(wire.request(raw), lambda: NOW)
    other = SyntheticWire(wire.seeds | {"host": secrets.token_bytes(32)})
    assert p.parse_refusal(issuer.consume(other.request(raw), lambda: NOW)).code == (
        "OWNER_BINDING_CONFLICT")
    assert issuer.consume(wire.request(raw), lambda: NOW) == receipt
    revoked = wire.issuer(tmp_path / "revoked", create=True)
    claim = revoked.issue(wire.claim(), START)
    assert revoked.revoke(uid(1)) == "REVOKED"
    before = revoked.snapshot()
    assert revoked.revoke(uid(1)) == "REVOKED"
    assert revoked.snapshot() == before
    assert p.parse_refusal(revoked.consume(wire.request(claim), lambda: NOW)).code == (
        "OWNER_AUTHORIZATION_REVOKED")
    assert revoked.snapshot() == before


def test_sql_error_rolls_back_in_issuer_owner(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    before = issuer.snapshot()

    def fault(name, db):
        if name == "consumption_write":
            db.execute("SELECT deliberately_missing_fault_column")

    issuer.hook = fault
    with pytest.raises(sqlite3.OperationalError):
        issuer.consume(wire.request(claim), lambda: NOW)
    issuer.hook = None
    assert issuer.snapshot() == before


def observation(**changed):
    return p.FixtureObservation.model_validate({
        "evidence_class": "OFFLINE_CONFORMANCE", "qualification_pass": False,
        "principal_ref": "owner", "authority_generation": 1, "active": True,
        "authenticated_at_ns": 0, "observed_at_ns": 1,
    } | changed)


def test_host_commits_receipt_admin_audit_once_without_hidden_issuer_calls(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    binding = host.prepare(claim, uid(4), observation, NOW)
    result = host.bootstrap(lambda request: issuer.consume(request, lambda: NOW),
                            observation, lambda: NOW)
    assert result.code == "COMMITTED" and result.committed
    assert result.qualification_pass is False
    snapshot = host.snapshot()
    assert [snapshot[k] for k in ("pending", "receipts", "admins", "audit")] == [1, 1, 1, 1]
    assert snapshot["operation_id"] == binding.operation_id

    def forbidden(_):
        pytest.fail("committed host performed another licensing call")

    restarted = wire.host(tmp_path / "host")
    assert restarted.bootstrap(forbidden, observation, lambda: NOW) == result
    assert restarted.snapshot() == snapshot


def test_changed_stored_scope_is_corruption_not_a_new_owner(tmp_path):
    from qualification.owner_authority.licensing_fixture import FixtureCorrupt

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)

    def corrupt(name, db):
        if name == "prepare_after_commit":
            db.execute("UPDATE configuration SET organization_id=?", (uid(30),))

    host = wire.host(tmp_path / "host", create=True, hook=corrupt)
    host.prepare(claim, uid(4), observation, NOW)
    with pytest.raises(FixtureCorrupt):
        host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW), observation, lambda: NOW)
    assert host.snapshot()["admins"] == issuer.snapshot()["consumptions"] == 0


def test_partial_stored_commit_is_corruption_not_a_cached_success(tmp_path):
    from qualification.owner_authority.licensing_fixture import FixtureCorrupt

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)

    def corrupt(name, db):
        if name == "publish_after_commit":
            db.execute("DELETE FROM audit")

    host = wire.host(tmp_path / "host", create=True, hook=corrupt)
    host.prepare(claim, uid(4), observation, NOW)
    host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW), observation, lambda: NOW)
    assert host.snapshot()["audit"] == 0
    with pytest.raises(FixtureCorrupt):
        host.bootstrap(lambda _: pytest.fail("cached corruption called issuer"),
                        observation, lambda: NOW)


@pytest.mark.parametrize("reply", ["unavailable", "refusal"])
def test_denial_is_rechecked_before_unavailable_or_refusal_result(tmp_path, reply):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    native = [observation()]
    host.prepare(claim, uid(4), lambda: native[0], NOW)

    def consume(raw):
        native[0] = observation(active=False)
        if reply == "unavailable":
            raise TimeoutError("synthetic response lost")
        return p.canonical(p.Refusal.model_validate({
            "version": "owner-bootstrap/1", "operation_id": uid(4),
            "code": "OWNER_AUTHORIZATION_REVOKED", "completion": "NOT_COMMITTED",
        }).model_dump())

    result = host.bootstrap(consume, lambda: native[0], lambda: NOW)
    assert result.code == "NATIVE_SESSION_INACTIVE" and result.committed is False
    assert host.snapshot()["admins"] == 0


def _issuer_service_child(root, manifest, public, claim_seed, receipt_seed, control, clients, drop):
    from qualification.owner_authority.licensing_fixture import IssuerFixture

    issuer = IssuerFixture(root, manifest, public, frozenset({"release"}),
                           ("claim", Ed25519PrivateKey.from_private_bytes(claim_seed)),
                           ("receipt", Ed25519PrivateKey.from_private_bytes(receipt_seed)))
    calls, digest = 0, None
    control.send("ready")
    while True:
        for connection in wait([control, *clients], timeout=30):
            action, raw = connection.recv()
            if action == "stop":
                return
            if action == "inspect":
                control.send({"calls": calls, "receipt_sha256": digest})
                continue
            calls += 1
            receipt = issuer.consume(raw, lambda: NOW)
            digest = hashlib.sha256(receipt).hexdigest()
            connection.send(("lost", None) if drop and calls == 1 else ("reply", receipt))


@contextmanager
def issuer_service(wire, root, *, drop=False, clients=1):
    context = multiprocessing.get_context("spawn")
    control, remote_control = context.Pipe()
    pairs = [context.Pipe() for _ in range(clients)]
    child = context.Process(target=_issuer_service_child, args=(
        root, wire.manifest, wire.public, wire.seeds["claim"], wire.seeds["receipt"],
        remote_control, [pair[1] for pair in pairs], drop))
    child.start()
    remote_control.close()
    for _, remote in pairs:
        remote.close()
    assert control.poll(30) and control.recv() == "ready"

    def inspect():
        control.send(("inspect", None))
        assert control.poll(30)
        return control.recv()

    try:
        yield [pair[0] for pair in pairs], inspect
    finally:
        control.send(("stop", None))
        child.join(10)
        if child.is_alive():
            child.terminate()
            child.join(10)
        for local, _ in pairs:
            local.close()
        control.close()
        assert child.exitcode == 0


def transport(connection):
    def consume(raw):
        connection.send(("consume", raw))
        assert connection.poll(30), "issuer fixture response deadline"
        kind, response = connection.recv()
        if kind == "lost":
            raise TimeoutError("synthetic response lost after issuer commit")
        assert kind == "reply"
        return response
    return consume


def _host_child(root, manifest, public, host_seed, claim, principal, operation,
                mode, endpoint, channel, start, release, pause, fault):
    from qualification.owner_authority.host_fixture import HostFixture

    def hook(name, db):
        if name == pause:
            channel.send(("paused", name))
            if not release.wait(30):
                raise TimeoutError("host barrier deadline")
        if fault is not None and name == fault[0]:
            if fault[1] == "crash":
                os._exit(72)
            db.execute("SELECT deliberately_missing_host_fault_column")

    host = HostFixture(root, manifest, public, frozenset({"release"}),
                       Ed25519PrivateKey.from_private_bytes(host_seed), hook=hook)
    def native():
        return observation(principal_ref=principal)
    channel.send(("ready", None))
    if not start.wait(30):
        return
    try:
        if mode != "bootstrap":
            binding = host.prepare(claim, uid(operation), native, NOW)
        result = (binding if mode == "prepare" else
                  host.bootstrap(transport(endpoint), native, lambda: NOW))
        channel.send(("result", result.model_dump()))
    except Exception as exc:
        channel.send(("error", type(exc).__name__, str(exc)))
    finally:
        channel.close()


@contextmanager
def host_worker(wire, root, claim, endpoint=None, *, mode="bootstrap", principal="owner",
                operation=4, pause=None, fault=None):
    context = multiprocessing.get_context("spawn")
    receiving, sending = context.Pipe(duplex=False)
    start, release = context.Event(), context.Event()
    child = context.Process(target=_host_child, args=(
        root, wire.manifest, wire.public, wire.seeds["host"], claim, principal, operation,
        mode, endpoint, sending, start, release, pause, fault))
    child.start()
    sending.close()

    def receive():
        assert receiving.poll(30), "host fixture child deadline"
        return receiving.recv()

    try:
        assert receive() == ("ready", None)
        yield child, start, release, receive
    finally:
        release.set()
        start.set()
        child.join(10)
        if child.is_alive():
            child.terminate()
            child.join(10)
        receiving.close()


def test_lost_response_recovers_same_receipt_across_separate_issuer_and_host_processes(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    binding = host.prepare(claim, uid(4), observation, NOW)
    with issuer_service(wire, issuer.root, drop=True) as (connections, inspect):
        for expected in ("LICENSING_UNAVAILABLE", "COMMITTED"):
            with host_worker(wire, host.root, claim, connections[0]) as child:
                child[1].set()
                kind, result = child[3]()
                assert kind == "result" and result["code"] == expected
                assert result["operation_id"] == binding.operation_id
                assert result["qualification_pass"] is False
            if expected == "LICENSING_UNAVAILABLE":
                assert host.snapshot()["admins"] == 0
                assert issuer.snapshot()["consumptions"] == 1
                assert host.prepare(claim, uid(4), observation, NOW) == binding
        state = inspect()
        assert state["calls"] == 2
        assert state["receipt_sha256"] == host.snapshot()["receipt_sha256"]
        assert host.bootstrap(lambda _: pytest.fail("hidden licensing call"),
                              observation, lambda: NOW).committed
        assert inspect() == state


@pytest.mark.parametrize("first", ["owner", "other"])
@pytest.mark.parametrize("repeat", range(3))
def test_host_initialization_race_never_elects_two_owners(tmp_path, first, repeat):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    second = "other" if first == "owner" else "owner"
    with issuer_service(wire, issuer.root, clients=2) as (connections, inspect):
        with host_worker(wire, host.root, claim, connections[0], mode="setup", principal=first,
                         operation=4, pause="prepare_writer") as leader:
            leader[1].set()
            assert leader[3]() == ("paused", "prepare_writer")
            with host_worker(wire, host.root, claim, connections[1], mode="setup", principal=second,
                             operation=20, pause="prepare_before_writer") as follower:
                follower[1].set()
                assert follower[3]() == ("paused", "prepare_before_writer")
                follower[2].set()
                leader[2].set()
                assert leader[3]()[1]["code"] == "COMMITTED"
                assert follower[3]()[0:2] == ("error", "Refused")
        assert inspect()["calls"] == 1
    assert host.snapshot()["operation_id"] == uid(4)
    assert [host.snapshot()[key] for key in ("receipts", "admins", "audit")] == [1, 1, 1]
    assert issuer.snapshot()["consumptions"] == 1


@pytest.mark.parametrize("point,fault", [
    ("before_dispatch", "crash"), ("after_response", "crash"),
    *[(point, fault) for point in ("receipt_write", "admin_write", "audit_write",
                                  "publish_before_commit", "publish_after_commit")
      for fault in ("sql", "crash")],
])
def test_host_crash_and_sql_fault_preserve_pending_and_atomic_publication(tmp_path, point, fault):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    binding = host.prepare(claim, uid(4), observation, NOW)
    with issuer_service(wire, issuer.root) as (connections, inspect):
        with host_worker(wire, host.root, claim, connections[0], fault=(point, fault)) as child:
            child[1].set()
            if fault == "sql":
                assert child[3]()[0:2] == ("error", "OperationalError")
            child[0].join(30)
            assert child[0].exitcode == (72 if fault == "crash" else 0)
        after = host.snapshot()
        assert after["pending"] == 1 and after["operation_id"] == binding.operation_id
        committed = int(point == "publish_after_commit")
        assert [after[k] for k in ("receipts", "admins", "audit")] == [committed] * 3
        assert host.bootstrap(transport(connections[0]), observation, lambda: NOW).committed
        assert inspect()["receipt_sha256"] == host.snapshot()["receipt_sha256"]
    assert issuer.snapshot()["consumptions"] == 1


@pytest.mark.parametrize("point", [
    "pending_write", "prepare_before_commit", "prepare_after_commit",
])
@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_pending_commit_precedes_every_dispatch(tmp_path, point, fault):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    with host_worker(wire, host.root, claim, mode="prepare", fault=(point, fault)) as child:
        child[1].set()
        if fault == "sql":
            assert child[3]()[0:2] == ("error", "OperationalError")
        child[0].join(30)
        assert child[0].exitcode == (72 if fault == "crash" else 0)
    assert host.snapshot()["pending"] == int(point == "prepare_after_commit")
    assert issuer.snapshot()["consumptions"] == 0
    binding = host.prepare(claim, uid(4), observation, NOW)
    assert host.prepare(claim, uid(4), observation, NOW) == binding


@pytest.mark.parametrize("phase", ["initial", "publish_writer", "publish_before_commit",
                                   "publish_after_commit"])
@pytest.mark.parametrize("change", [{"active": False}, {"principal_ref": "other"},
                                   {"authority_generation": 2}, {"observed_at_ns": 60000000001}])
def test_synthetic_denial_never_publishes_and_postcommit_denial_is_truthful(
        tmp_path, phase, change):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    native = [observation()]

    def changed(name, db):
        if name == phase:
            native[0] = observation(**change)

    host = wire.host(tmp_path / "host", create=True, hook=changed)
    host.prepare(claim, uid(4), lambda: native[0], NOW)
    if phase == "initial":
        native[0] = observation(**change)
    result = host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW),
                            lambda: native[0], lambda: NOW)
    assert result.code == ("NATIVE_SESSION_INACTIVE" if change == {"active": False}
                           else "NATIVE_AUTH_DENIED")
    assert result.committed == (phase == "publish_after_commit")
    assert host.snapshot()["admins"] == int(phase == "publish_after_commit")
    assert issuer.snapshot()["consumptions"] == int(phase != "initial")


@pytest.mark.parametrize("age,valid", [(-1, False), (0, True), (60000000000, True),
                                     (60000000001, False)])
def test_synthetic_freshness_both_boundaries(tmp_path, age, valid):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    def native():
        return observation(authenticated_at_ns=1, observed_at_ns=age + 1)
    if valid:
        assert host.prepare(claim, uid(4), native, NOW).operation_id == uid(4)
    else:
        with pytest.raises(Refused, match="NATIVE_AUTH_DENIED"):
            host.prepare(claim, uid(4), native, NOW)
        assert host.snapshot()["pending"] == 0


@pytest.mark.parametrize("changed", [{"evidence_class": "NATIVE_QUALIFICATION"},
    {"qualification_pass": True}, {"qualification_pass": 0}, {"active": 0},
    {"authority_generation": False}, {"authority_generation": 0},
    {"authority_generation": 2147483648}, {"principal_ref": ""}, {"observed_at_ns": False}])
def test_observation_overrides_refuse_before_any_host_writer(tmp_path, monkeypatch, changed):
    from qualification.owner_authority import host_fixture as lane

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    invalid = observation().model_copy(update=changed)
    monkeypatch.setattr(lane, "transaction", lambda *a, **k: pytest.fail("bad observation wrote"))
    with pytest.raises(ValueError):
        host.prepare(claim, uid(4), lambda: invalid, NOW)


def test_missing_claim_and_unsigned_noncommit_refusal_cannot_freeze_another_owner(tmp_path):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    host = wire.host(tmp_path / "host", create=True)
    with pytest.raises(Refused, match="OWNER_AUTHORIZATION_REQUIRED"):
        host.prepare(None, uid(4), observation, NOW)
    assert host.snapshot()["pending"] == 0
    claim = issuer.issue(wire.claim(), START)
    frozen = host.prepare(claim, uid(4), observation, NOW)

    def misleading(raw):
        issuer.consume(raw, lambda: NOW)
        return p.canonical({"version": "owner-bootstrap/1", "operation_id": uid(4),
                            "code": "LICENSING_UNAVAILABLE", "completion": "NOT_COMMITTED"})

    assert host.bootstrap(misleading, observation, lambda: NOW).committed is False
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        host.prepare(claim, uid(20), lambda: observation(principal_ref="other"), NOW)
    assert host.prepare(claim, uid(4), observation, NOW) == frozen
    assert host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW),
                          observation, lambda: NOW).committed
    assert issuer.snapshot()["consumptions"] == 1


def test_expired_pending_receipt_recovers_evidence_without_local_publication(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(expires=NOW + timedelta(seconds=1)), START)
    host = wire.host(tmp_path / "host", create=True)
    frozen = host.prepare(claim, uid(4), observation, NOW)

    def lost(raw):
        issuer.consume(raw, lambda: NOW)
        raise TimeoutError("synthetic lost receipt")

    assert host.bootstrap(lost, observation, lambda: NOW).committed is False
    late = NOW + timedelta(seconds=2)
    reply = host.bootstrap(lambda raw: issuer.consume(raw, lambda: late), observation, lambda: late)
    assert reply.code == "OWNER_AUTHORIZATION_EXPIRED" and not reply.committed
    assert host.snapshot()["operation_id"] == frozen.operation_id
    assert host.snapshot()["admins"] == 0 and issuer.snapshot()["consumptions"] == 1


@pytest.mark.parametrize("change", ["signature", "binding", "partial", "oversize"])
def test_unverified_responses_keep_pending_without_publishing(tmp_path, change):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    host.prepare(claim, uid(4), observation, NOW)

    def corrupted(raw):
        receipt = issuer.consume(raw, lambda: NOW)
        if change == "signature":
            return p.canonical(json.loads(receipt) | {"signature_base64url": b64(b"\0" * 64)})
        if change == "binding":
            payload = p.verify_signed(receipt, "receipt", wire.public, frozenset({"receipt"}))
            return wire.sign("receipt", payload.model_dump() | {
                "binding": payload.binding.model_dump() | {"principal_commitment": "d" * 64}},
                "receipt")
        return b"{}" if change == "partial" else b" " * 4097

    reply = host.bootstrap(corrupted, observation, lambda: NOW)
    assert reply.code == "LICENSING_UNAVAILABLE" and not reply.committed
    assert host.snapshot()["pending"] == 1 and host.snapshot()["admins"] == 0
    assert host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW),
                          observation, lambda: NOW).committed


@pytest.mark.parametrize("field,value", [("operation_id", uid(30)), ("claim_sha256", "d" * 64),
                                        ("principal_commitment", "d" * 64),
                                        ("initialization_sha256", "d" * 64)])
def test_pending_consistency_has_independent_corruption_cases(tmp_path, field, value):
    from qualification.owner_authority.licensing_fixture import FixtureCorrupt

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)

    def corrupt(name, db):
        if name == "prepare_after_commit":
            old = db.execute("SELECT binding FROM pending").fetchone()[0]
            changed = json.loads(old) | {field: value}
            if field != "initialization_sha256":
                changed["initialization_sha256"] = host._initialization(changed)
            db.execute("UPDATE pending SET binding=?", (p.canonical(changed),))

    host = wire.host(tmp_path / "host", create=True, hook=corrupt)
    host.prepare(claim, uid(4), observation, NOW)
    with pytest.raises(FixtureCorrupt):
        host.bootstrap(lambda _: pytest.fail("corrupt intent reached issuer"),
                        observation, lambda: NOW)


def test_fixture_result_cannot_claim_uncommitted_or_native_success():
    good = {"evidence_class": "OFFLINE_CONFORMANCE", "qualification_pass": False,
            "operation_id": uid(4), "code": "COMMITTED", "committed": True}
    assert p.FixtureHostResult.model_validate(good).committed
    for change in ({"committed": False}, {"committed": 0}, {"qualification_pass": True},
                   {"qualification_pass": 0}, {"evidence_class": "NATIVE_QUALIFICATION"}):
        with pytest.raises(ValueError):
            p.FixtureHostResult.model_validate(good | change)


def test_refusal_for_another_operation_is_not_this_pending_result(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    host.prepare(claim, uid(4), observation, NOW)
    wrong = p.canonical({"version": "owner-bootstrap/1", "operation_id": uid(20),
                         "code": "OWNER_AUTHORIZATION_REVOKED", "completion": "NOT_COMMITTED"})
    result = host.bootstrap(lambda _: wrong, observation, lambda: NOW)
    assert result.code == "LICENSING_UNAVAILABLE" and not result.committed
    assert host.snapshot()["pending"] == 1 and host.snapshot()["admins"] == 0


@pytest.mark.parametrize("changed", ["operation", "claim", "principal"])
def test_each_frozen_pending_field_has_its_own_conflict_case(tmp_path, changed):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    frozen = host.prepare(claim, uid(4), observation, NOW)
    other = wire.sign("claim", wire.claim(index=20).model_dump(), "claim")
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        host.prepare(other if changed == "claim" else claim,
                     uid(20) if changed == "operation" else uid(4),
                     (lambda: observation(principal_ref="other")) if changed == "principal"
                     else observation, NOW)
    assert host.prepare(claim, uid(4), observation, NOW) == frozen


@pytest.mark.parametrize("bad", ["key", "organization", "missing_config", "missing_pending"])
def test_wrong_host_configuration_refuses_without_any_dispatch(tmp_path, bad):
    from qualification.owner_authority.licensing_fixture import FixtureCorrupt, Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    def hook(name, db):
        if name == "prepare_writer" and bad == "missing_config":
            db.execute("DELETE FROM configuration")
    host = wire.host(tmp_path / "host", create=True, hook=hook)
    if bad == "organization":
        claim = wire.sign("claim", wire.claim().model_dump() | {"organization_id": uid(30)},
                          "claim")
    if bad == "key":
        host.key = wire.private["receipt"]
    expected = Refused if bad == "organization" else FixtureCorrupt
    with pytest.raises(expected):
        if bad == "missing_pending":
            host.bootstrap(lambda _: pytest.fail("unprepared host dispatched"),
                            observation, lambda: NOW)
        else:
            host.prepare(claim, uid(4), observation, NOW)
    assert host.snapshot()["admins"] == 0


@pytest.mark.parametrize("state", ["unknown", "superseded"])
def test_revocation_and_reissue_refuse_ineligible_transition(tmp_path, state):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    issuer.issue(wire.claim(), START)
    claim_id = uid(99) if state == "unknown" else uid(1)
    if state == "superseded":
        issuer.reissue(uid(1), wire.claim(index=10, generation=2, issued=NOW), NOW)
    before = issuer.snapshot()
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        issuer.revoke(claim_id)
    with pytest.raises(Refused, match="OWNER_BINDING_CONFLICT"):
        issuer.reissue(claim_id, wire.claim(index=20, generation=3, issued=NOW), NOW)
    assert issuer.snapshot() == before


@pytest.mark.parametrize("action", ["issue", "reissue"])
@pytest.mark.parametrize("seconds,valid", [(-1, False), (0, True), (172799, True), (172800, False)])
def test_manifest_window_controls_admin_transitions(tmp_path, action, seconds, valid):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    if action == "reissue":
        issuer.issue(wire.claim(), START)
    now = START + timedelta(seconds=seconds)
    claim = wire.claim(index=10, generation=2, issued=now)
    before = issuer.snapshot()
    def call():
        return issuer.issue(claim, now) if action == "issue" else issuer.reissue(uid(1), claim, now)
    if valid:
        value = p.verify_signed(call(), "claim", wire.public, frozenset({"claim"}))
        assert value.claim_id == uid(10)
    else:
        with pytest.raises(p.ProtocolInputError):
            call()
        assert issuer.snapshot() == before


@pytest.mark.parametrize("signer", ["claim", "receipt"])
def test_matching_key_with_wrong_purpose_id_is_refused(tmp_path, signer):
    from qualification.owner_authority.licensing_fixture import IssuerFixture

    wire = SyntheticWire()
    selected = {kind: (kind, wire.private[kind]) for kind in ("claim", "receipt")}
    selected[signer] = ("release", wire.private["release"])
    with pytest.raises(p.ProtocolInputError):
        IssuerFixture(tmp_path / "issuer", wire.manifest, wire.public, frozenset({"release"}),
                      selected["claim"], selected["receipt"])


def test_claim_clock_rejects_datetime_subclass(tmp_path):
    class OtherClock(datetime):
        pass

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    before = issuer.snapshot()
    with pytest.raises(p.ProtocolInputError):
        issuer.issue(wire.claim(), OtherClock(2026, 1, 1, tzinfo=UTC))
    assert issuer.snapshot() == before


@pytest.mark.parametrize("kind,restored", [("other", False), ("", False), (False, False),
                                          ("issuer", 0), ("host", 1), ("issuer", ""),
                                          ("issuer", None)])
def test_storage_kind_and_restored_flag_are_closed(tmp_path, kind, restored):
    from qualification.owner_authority import licensing_fixture as lane

    root = tmp_path / "invalid"
    with pytest.raises(lane.FixtureCorrupt):
        lane.create_store(root, kind, "", restored=restored)
    assert not root.exists()


@pytest.mark.parametrize("target", ["root", "db"])
def test_indirect_fixture_paths_refuse_before_sqlite(tmp_path, monkeypatch, target):
    import subprocess

    from qualification.owner_authority import licensing_fixture as lane

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    assert issuer.snapshot()["claims"] == []
    link = tmp_path / "alias" if target == "root" else issuer.root / "fixture.sqlite"
    destination = issuer.root
    if target == "db":
        destination = issuer.root / "original.sqlite"
        link.rename(destination)
    if os.name == "nt":
        if target == "db":
            destination = tmp_path / "junction-target"
            destination.mkdir()
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(destination)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(destination, target_is_directory=target == "root")
    monkeypatch.setattr(lane.sqlite3, "connect",
                        lambda *a, **k: pytest.fail("indirect path opened"))
    with pytest.raises(lane.FixtureCorrupt):
        wire.issuer(link if target == "root" else issuer.root).snapshot()


def test_stored_envelope_equality_is_independent_of_signature_admission(tmp_path):
    wire = SyntheticWire()
    manifest = p.verify_signed(wire.manifest, "manifest", wire.public, frozenset({"release"}))
    wire.manifest = wire.sign("manifest", manifest.model_dump() | {
        "claim_key_ids": ["claim", "release"]}, "release")
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    alternate = wire.sign("claim", wire.claim().model_dump(), "release")

    def changed(name, db):
        if name == "writer":
            db.execute("UPDATE claims SET envelope=? WHERE claim_id=?", (alternate, uid(1)))

    issuer.hook = changed
    assert p.parse_refusal(issuer.consume(wire.request(claim), lambda: NOW)).code == (
        "OWNER_AUTHORIZATION_INVALID")
    issuer.hook = None
    assert issuer.snapshot()["consumptions"] == 0


def test_stored_receipt_must_verify_on_replay(tmp_path):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    receipt = issuer.consume(wire.request(claim), lambda: NOW)
    corrupt = p.canonical(json.loads(receipt) | {"signature_base64url": b64(b"\0" * 64)})

    def changed(name, db):
        if name == "writer":
            db.execute("UPDATE consumptions SET receipt=?", (corrupt,))

    issuer.hook = changed
    with pytest.raises(p.ProtocolInputError):
        issuer.consume(wire.request(claim), lambda: NOW)
    issuer.hook = None
    assert issuer.consume(wire.request(claim), lambda: NOW) == receipt


@pytest.mark.parametrize("first", [0, 1])
@pytest.mark.parametrize("repeat", range(3))
def test_same_pending_recovery_race_commits_one_identical_receipt(tmp_path, first, repeat):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    host.prepare(claim, uid(4), observation, NOW)
    with issuer_service(wire, issuer.root, clients=2) as (connections, inspect):
        with host_worker(wire, host.root, claim, connections[first],
                         pause="publish_writer") as leader:
            leader[1].set()
            assert leader[3]() == ("paused", "publish_writer")
            with host_worker(wire, host.root, claim, connections[1 - first],
                             pause="publish_before_writer") as follower:
                follower[1].set()
                assert follower[3]() == ("paused", "publish_before_writer")
                follower[2].set()
                leader[2].set()
                assert leader[3]()[1]["code"] == follower[3]()[1]["code"] == "COMMITTED"
        assert inspect()["calls"] == 2
        assert inspect()["receipt_sha256"] == host.snapshot()["receipt_sha256"]
    assert [host.snapshot()[k] for k in ("pending", "receipts", "admins", "audit")] == [1] * 4
    assert issuer.snapshot()["consumptions"] == 1


@pytest.mark.parametrize("point", ["prepare_writer", "prepare_before_commit"])
def test_prepare_rechecks_synthetic_identity_after_waits(tmp_path, point):
    from qualification.owner_authority.licensing_fixture import Refused

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    current = [observation()]
    def hook(name, db):
        if name == point:
            current[0] = observation(active=False)
    host = wire.host(tmp_path / "host", create=True, hook=hook)
    with pytest.raises(Refused, match="NATIVE_SESSION_INACTIVE"):
        host.prepare(claim, uid(4), lambda: current[0], NOW)
    assert host.snapshot()["pending"] == 0


@pytest.mark.parametrize("field", ["principal", "operation", "receipt"])
def test_cached_commit_corruption_never_releases_success(tmp_path, field):
    from qualification.owner_authority.licensing_fixture import FixtureCorrupt

    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    def hook(name, db):
        if name == "publish_after_commit":
            if field == "principal":
                db.execute("UPDATE admins SET principal_commitment=?", ("d" * 64,))
            elif field == "operation":
                db.execute("PRAGMA foreign_keys=OFF")
                db.execute("UPDATE audit SET operation_id=?", (uid(20),))
            else:
                raw = json.loads(db.execute("SELECT envelope FROM receipts").fetchone()[0])
                raw["signature_base64url"] = b64(b"\0" * 64)
                db.execute("UPDATE receipts SET envelope=?", (p.canonical(raw),))
    host = wire.host(tmp_path / "host", create=True, hook=hook)
    host.prepare(claim, uid(4), observation, NOW)
    assert host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW),
                          observation, lambda: NOW).committed
    expected = p.ProtocolInputError if field == "receipt" else FixtureCorrupt
    with pytest.raises(expected):
        host.bootstrap(lambda _: pytest.fail("cached corruption called issuer"),
                        observation, lambda: NOW)


@pytest.mark.parametrize("seconds", [-61, 61])
def test_clock_skew_on_received_receipt_keeps_pending(tmp_path, seconds):
    wire = SyntheticWire()
    issuer = wire.issuer(tmp_path / "issuer", create=True)
    claim = issuer.issue(wire.claim(), START)
    host = wire.host(tmp_path / "host", create=True)
    host.prepare(claim, uid(4), observation, NOW)
    clock = [NOW]
    def consume(raw):
        reply = issuer.consume(raw, lambda: NOW)
        clock[0] += timedelta(seconds=seconds)
        return reply
    result = host.bootstrap(consume, observation, lambda: clock[0])
    assert result.code == "OWNER_CLOCK_SKEW" and not result.committed
    assert host.snapshot()["pending"] == 1 and host.snapshot()["admins"] == 0
    assert host.bootstrap(lambda raw: issuer.consume(raw, lambda: NOW),
                          observation, lambda: NOW).committed
