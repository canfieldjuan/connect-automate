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
