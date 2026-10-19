"""Real writer contention at source authorization boundaries; synthetic input only."""

import multiprocessing
import sqlite3
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from test_lead_source_auth import NOW, envelope, resign, trust_data
from test_lead_source_store import database, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake import (
    SourceAdmission,
    SourceAuthenticationError,
    SourceStoreError,
    SourceTrustSnapshot,
)

STAGES = ["grant", "signature", "lookup", "commit"]
EXPIRY_US = 60_000_000


def _worker(root, raw, authority, action, pause, release, signals, clock):
    import connect_automate.lead_intake.auth as authentication

    owner = store(root, busy_timeout_ms=30000)
    trace, paused, blocked, reads = [], False, False, 0

    def checkpoint(stage):
        nonlocal paused
        trace.append(stage)
        if stage == pause and not paused:
            paused = True
            signals.put(("paused", action, stage))
            assert release.wait(30), "parent did not release checkpoint"

    connect, read, verify = sqlite3.connect, owner._authority, authentication.verify_signature

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, *args):
            nonlocal blocked
            try:
                result = super().execute(sql, *args)
            except sqlite3.OperationalError as exc:
                if (
                    sql.startswith("BEGIN")
                    and exc.sqlite_errorcode & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                    and not blocked
                ):
                    blocked = True
                    signals.put(("blocked", action))
                raise
            if sql.startswith("SELECT admission_id, organization_id"):
                checkpoint("lookup")
            return result

        def commit(self):
            checkpoint("commit")
            super().commit()

    def authority_read(db):
        nonlocal reads
        result = read(db)
        reads += 1
        # The first read is transaction preflight; the next is admission's grant.
        if action == "admit" and reads == 2:
            checkpoint("grant")
        return result

    def signature(*args):
        result = verify(*args)
        checkpoint("signature")
        return result

    def now():
        offset = clock.value
        trace.append(("clock", offset))
        return NOW + timedelta(microseconds=offset)

    with (
        patch.object(
            sqlite3, "connect", lambda *a, **kw: connect(*a, **kw, factory=ObservedConnection)
        ),
        patch.object(owner, "_authority", authority_read),
        patch.object(authentication, "verify_signature", signature),
    ):
        try:
            if action == "admit":
                result = SourceAdmission(owner, clock=now).admit_source(raw)
                outcome = ("accepted", result.applied, result.receipt.model_dump(by_alias=True))
            else:
                data = deepcopy(authority)
                data["generation"] += 1
                if action == "revoke":
                    data["key_grants"][0]["status"] = "revoked"
                applied = owner.publish_authority(
                    SourceTrustSnapshot.model_validate(data), expected_generation=1
                )
                outcome = ("published", applied, None)
        except (SourceAuthenticationError, SourceStoreError) as exc:
            assert exc.__context__ is None
            outcome = (type(exc).__name__, None, None)
        signals.put(("result", action, outcome, trace))


class Race:
    """Rendezvous at observed SQLite operations, never timing-based ordering."""

    def __init__(self, root, raw):
        self.root, self.raw = root, raw
        self.authority = store(root).read_authority().model_dump()
        self.context = multiprocessing.get_context("spawn")
        self.clock = self.context.Value("q", 0)
        self.signals = self.context.Queue()
        self.workers = {}

    def __enter__(self):
        return self

    def start(self, action, pause=None):
        release = self.context.Event()
        child = self.context.Process(
            target=_worker,
            args=(
                self.root,
                self.raw,
                self.authority,
                action,
                pause,
                release,
                self.signals,
                self.clock,
            ),
        )
        child.start()
        self.workers[action] = child, release

    def expect(self, *expected):
        assert self.signals.get(timeout=30) == expected

    def release(self, action):
        self.workers[action][1].set()

    def finish(self):
        results = {}
        for _ in self.workers:
            kind, action, outcome, trace = self.signals.get(timeout=30)
            assert kind == "result"
            results[action] = outcome, trace
        for child, _ in self.workers.values():
            child.join(30)
            assert not child.is_alive()
            assert child.exitcode == 0
        return results

    def __exit__(self, *args):
        for _, release in self.workers.values():
            release.set()
        for child, _ in self.workers.values():
            child.join(5)
            if child.is_alive():
                child.terminate()
                child.join(10)
            child.close()
        self.signals.close()
        self.signals.join_thread()


def prepare(root, replay, bound="key"):
    value, data = envelope(), trust_data()
    if bound == "key":
        data["key_grants"][0]["valid_until"] = "2026-10-18T12:31:00Z"
    else:
        value["payload"]["retention"]["recovery_deadline"] = "2026-10-18T12:31:00Z"
    raw = resign(value)
    store(root).initialize(SourceTrustSnapshot.model_validate(data))
    if replay:
        SourceAdmission(store(root), clock=lambda: NOW).admit_source(raw)
    return raw


def custody(root):
    with database(store(root).path) as db:
        return tuple(
            db.execute(f"SELECT * FROM {name} ORDER BY admission_id").fetchall()
            for name in ("source_receipts", "source_content", "source_custody")
        )


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("replay", [False, True])
def test_admission_serializes_revocation_at_each_checkpoint(private_root, stage, replay):
    raw = prepare(private_root, replay)
    before = custody(private_root)
    with Race(private_root, raw) as race:
        race.start("admit", stage)
        race.expect("paused", "admit", stage)
        race.start("revoke")
        race.expect("blocked", "revoke")
        race.release("admit")
        results = race.finish()
    admitted, _ = results["admit"]
    assert admitted[:2] == ("accepted", not replay)
    assert admitted[2]["trust_generation"] == 1
    assert results["revoke"][0] == ("published", True, None)
    saved = custody(private_root)
    assert tuple(map(len, saved)) == (1, 1, 1)
    if replay:
        assert saved == before
    assert store(private_root).read_authority().key_grants[0].status == "revoked"
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(store(private_root), clock=lambda: NOW).admit_source(raw)
    assert custody(private_root) == saved


@pytest.mark.parametrize("replay", [False, True])
def test_revocation_commits_before_waiting_admission(private_root, replay):
    raw = prepare(private_root, replay)
    before = custody(private_root)
    with Race(private_root, raw) as race:
        race.start("revoke", "commit")
        race.expect("paused", "revoke", "commit")
        race.start("admit")
        race.expect("blocked", "admit")
        race.release("revoke")
        results = race.finish()
    assert results["revoke"][0] == ("published", True, None)
    rejected, trace = results["admit"]
    assert rejected == ("SourceAuthenticationError", None, None)
    assert not {"signature", "lookup", "commit"}.intersection(trace)
    assert custody(private_root) == before


@pytest.mark.parametrize("bound", ["key", "source"])
@pytest.mark.parametrize("replay", [False, True])
@pytest.mark.parametrize("offset", [EXPIRY_US - 1, EXPIRY_US, EXPIRY_US + 1])
def test_expiry_while_waiting_samples_after_lock(private_root, bound, replay, offset):
    raw = prepare(private_root, replay, bound)
    before = custody(private_root)
    with Race(private_root, raw) as race:
        race.start("advance", "commit")
        race.expect("paused", "advance", "commit")
        race.start("admit")
        race.expect("blocked", "admit")
        race.clock.value = offset
        race.release("advance")
        results = race.finish()
    assert results["advance"][0] == ("published", True, None)
    result, trace = results["admit"]
    assert [item for item in trace if isinstance(item, tuple)][0] == ("clock", offset)
    if offset < EXPIRY_US:
        assert result[:2] == ("accepted", not replay)
        assert tuple(map(len, custody(private_root))) == (1, 1, 1)
        if replay:
            assert custody(private_root) == before
    else:
        assert result == ("SourceAuthenticationError", None, None)
        assert "lookup" not in trace and "commit" not in trace
        if bound == "key":
            assert "signature" not in trace
        assert custody(private_root) == before


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("bound", ["key", "source"])
@pytest.mark.parametrize("replay", [False, True])
def test_expiry_uses_final_sample_not_commit_completion(private_root, stage, bound, replay):
    raw = prepare(private_root, replay, bound)
    before = custody(private_root)
    with Race(private_root, raw) as race:
        race.start("admit", stage)
        race.expect("paused", "admit", stage)
        race.clock.value = EXPIRY_US
        race.release("admit")
        results = race.finish()
    result, _ = results["admit"]
    if stage == "commit":
        assert result[:2] == ("accepted", not replay)
        assert result[2]["accepted_at"] == NOW.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )
        saved = custody(private_root)
        assert tuple(map(len, saved)) == (1, 1, 1)
        if replay:
            assert saved == before
        with pytest.raises(SourceAuthenticationError):
            SourceAdmission(
                store(private_root), clock=lambda: NOW + timedelta(microseconds=EXPIRY_US)
            ).admit_source(raw)
        assert custody(private_root) == saved
    else:
        assert result == ("SourceAuthenticationError", None, None)
        assert custody(private_root) == before
