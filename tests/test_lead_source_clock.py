"""Durable clock floor and host-only C1 recovery; synthetic inputs only."""

import sqlite3
from datetime import timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from test_lead_source_admission import counts, tamper
from test_lead_source_auth import NOW, OTHER, encode, envelope, resign, trust
from test_lead_source_races import Race
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake import (
    SourceAdmission,
    SourceAuthenticationError,
    SourceStoreConflict,
    SourceStoreInputError,
    SourceStoreUnavailable,
)
from connect_automate.lead_intake.source_store import SourceClockAdmin


def test_reopened_admission_rejects_committed_clock_regression(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    raw = encode(envelope())
    SourceAdmission(owner, clock=lambda: NOW + timedelta(seconds=1)).admit_source(raw)
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(store(private_root), clock=lambda: NOW).admit_source(raw)


def seeded(root, offset=10):
    owner = store(root)
    owner.initialize(trust())
    result = SourceAdmission(owner, clock=lambda: NOW + timedelta(seconds=offset)).admit_source(
        encode(envelope())
    )
    return owner, result


def history(owner):
    with database(owner.path) as db:
        return db.execute("SELECT * FROM authority_clock_history ORDER BY sequence").fetchall()


def preserved(owner):
    with database(owner.path) as db:
        return {
            table: db.execute("SELECT * FROM " + table).fetchall()
            for table in (
                "authority_history",
                "source_receipts",
                "source_content",
                "source_custody",
            )
        }


@pytest.mark.parametrize("replay", [False, True])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_floor_boundary_before_lookup(private_root, replay, offset):
    owner, _ = seeded(private_root, 0)
    value = envelope()
    if not replay:
        value["payload"]["event_id"] = OTHER
    called = []
    original = sqlite3.connect

    class Observe(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql.startswith("SELECT admission_id, organization_id"):
                called.append(sql)
            return super().execute(sql, *args)

    before = history(owner)
    with patch.object(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=Observe)):
        boundary = SourceAdmission(
            store(private_root), clock=lambda: NOW + timedelta(microseconds=offset)
        )
        if offset < 0:
            with pytest.raises(SourceAuthenticationError):
                boundary.admit_source(resign(value))
            assert called == []
        else:
            assert boundary.admit_source(resign(value)).applied is not replay
            assert called
    assert len(history(owner)) == len(before) + (offset > 0)


@pytest.mark.parametrize(
    "bad",
    [None, False, 0, "", NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1)))],
)
def test_untrusted_clock_cannot_record(private_root, bad):
    owner, _ = seeded(private_root)
    before = history(owner)
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: bad).admit_source(encode(envelope()))
    assert history(owner) == before


def test_final_sample_is_recorded_on_new_and_replay(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    for n in range(2):
        times = iter([NOW + timedelta(seconds=n * 2), NOW + timedelta(seconds=n * 2 + 1)])
        result = SourceAdmission(owner, clock=times.__next__).admit_source(encode(envelope()))
        assert result.applied is (n == 0)
        assert SourceClockAdmin(store(private_root)).read().floor == NOW + timedelta(
            seconds=n * 2 + 1
        )
    assert len(history(owner)) == 2


@pytest.mark.parametrize("kind", ["signature", "expired", "conflict", "final-regression"])
def test_rejected_request_does_not_advance_clock(private_root, kind):
    owner, _ = seeded(private_root, 0)
    before = history(owner), preserved(owner)
    value = envelope()
    times = [NOW + timedelta(seconds=10)] * 2
    error = SourceAuthenticationError
    if kind == "signature":
        value["payload"]["event_id"] = OTHER
        raw = encode(value)
    elif kind == "conflict":
        from connect_automate.lead_intake import SourceAdmissionConflict

        value["payload"]["source"]["message_id"] = "different"
        raw, error = resign(value), SourceAdmissionConflict
    else:
        raw = encode(value)
        times = (
            [NOW + timedelta(hours=3)] * 2
            if kind == "expired"
            else [NOW + timedelta(seconds=10), NOW + timedelta(seconds=9)]
        )
    clock = iter(times)
    with pytest.raises(error):
        SourceAdmission(owner, clock=lambda: next(clock)).admit_source(raw)
    assert (history(owner), preserved(owner)) == before


def test_c1_restores_fresh_admission_preserving_records(private_root):
    owner, first = seeded(private_root, 1200)
    before = preserved(owner)
    admin = SourceClockAdmin(store(private_root))
    state = admin.read()
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope()))
    operation = str(uuid4())
    result = admin.reconcile(
        operation_id=operation, expected_sequence=state.sequence, corrected_at=NOW
    )
    assert result.sequence == 2 and result.floor == NOW
    assert preserved(owner) == before
    value = envelope()
    value["payload"]["event_id"] = OTHER
    fresh = SourceAdmission(
        store(private_root), clock=lambda: NOW + timedelta(seconds=1)
    ).admit_source(resign(value))
    assert fresh.applied
    # A lost response retry cannot reset again after subsequent admissions.
    advanced = history(owner)
    assert admin.reconcile(operation_id=operation, expected_sequence=1, corrected_at=NOW) == result
    assert history(owner) == advanced
    assert first.receipt.recovery_deadline == fresh.receipt.recovery_deadline
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW + timedelta(hours=1)).admit_source(resign(value))
    current = SourceAdmission(owner, clock=lambda: NOW + timedelta(seconds=1))
    assert not current.admit_source(resign(value)).applied
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    with pytest.raises(SourceAuthenticationError):
        current.admit_source(resign(value))


@pytest.mark.parametrize("change", ["sequence", "time", "raise", "missing-floor"])
def test_c1_conflicts(private_root, change):
    owner, _ = seeded(private_root)
    admin = SourceClockAdmin(owner)
    op = str(uuid4())
    admin.reconcile(operation_id=op, expected_sequence=1, corrected_at=NOW)
    before = history(owner)
    kwargs = dict(operation_id=op, expected_sequence=1, corrected_at=NOW)
    if change == "sequence":
        kwargs["expected_sequence"] = 2
    if change == "time":
        kwargs["corrected_at"] = NOW - timedelta(seconds=1)
    if change == "raise":
        kwargs.update(
            operation_id=str(uuid4()), expected_sequence=2, corrected_at=NOW + timedelta(seconds=1)
        )
    if change == "missing-floor":
        kwargs.update(operation_id=str(uuid4()), expected_sequence=99)
    with pytest.raises(SourceStoreConflict):
        admin.reconcile(**kwargs)
    assert history(owner) == before


@pytest.mark.parametrize(
    "field,bad",
    [
        ("operation_id", False),
        ("operation_id", ""),
        ("operation_id", "not-a-uuid"),
        ("expected_sequence", 0),
        ("expected_sequence", False),
        ("expected_sequence", ""),
        ("corrected_at", None),
        ("corrected_at", NOW.replace(tzinfo=None)),
    ],
)
def test_c1_invalid_input(private_root, field, bad):
    owner, _ = seeded(private_root)
    args = dict(operation_id=str(uuid4()), expected_sequence=1, corrected_at=NOW)
    args[field] = bad
    before = history(owner)
    with pytest.raises(SourceStoreInputError):
        SourceClockAdmin(owner).reconcile(**args)
    assert history(owner) == before


def test_source_api_cannot_reconcile(private_root):
    owner, _ = seeded(private_root)
    boundary = SourceAdmission(owner, clock=lambda: NOW + timedelta(seconds=10))
    assert not boundary.admit_source(encode(envelope())).applied
    assert not hasattr(boundary, "reconcile")
    for field in ("corrected_at", "expected_sequence", "operation_id"):
        value = envelope()
        value[field] = "untrusted"
        with pytest.raises(SourceAuthenticationError):
            boundary.admit_source(encode(value))
    assert SourceClockAdmin(owner).read().floor == NOW + timedelta(seconds=10)


@pytest.mark.parametrize(
    "stage", ["history-write", "receipt-write", "commit-before", "commit-after"]
)
def test_floor_atomic_with_custody_and_commit_ambiguity(private_root, stage):
    from connect_automate.lead_intake import SourceStoreUncertain

    owner = store(private_root)
    owner.initialize(trust())
    original = sqlite3.connect

    class Fail(sqlite3.Connection):
        def execute(self, sql, *args):
            result = super().execute(sql, *args)
            if (
                stage == "history-write" and sql.startswith("INSERT INTO authority_clock_history")
            ) or (stage == "receipt-write" and sql.startswith("INSERT INTO source_receipts")):
                raise sqlite3.OperationalError("private synthetic detail")
            return result

        def commit(self):
            if stage == "commit-before":
                raise sqlite3.OperationalError("private")
            super().commit()
            if stage == "commit-after":
                raise sqlite3.OperationalError("private")

    with patch.object(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=Fail)):
        with pytest.raises(
            SourceStoreUncertain if stage.startswith("commit") else SourceStoreUnavailable
        ) as caught:
            SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope()))
        assert caught.value.__context__ is None
    committed = stage == "commit-after"
    assert counts(owner) == ((1, 1, 1) if committed else (0, 0, 0))
    assert len(history(owner)) == int(committed)
    recovered = SourceAdmission(store(private_root), clock=lambda: NOW).admit_source(
        encode(envelope())
    )
    assert recovered.applied is not committed


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE authority_clock_history SET sequence=2",
        "UPDATE authority_clock_history SET old_floor='2026-10-18T12:00:00.000000Z'",
        "UPDATE authority_clock_history SET new_floor='2026-10-18T12:30:10+00:00'",
        "UPDATE authority_clock_history SET new_floor='2026-10-18T12:30:10.000000+01:00'",
        "UPDATE authority_clock_history SET generation=99",
        "UPDATE authority_clock_history SET operation_id='00000000-0000-4000-8000-000000000002'",
        "UPDATE authority_clock_history SET kind='reconcile',"
        "operation_id='00000000-0000-4000-8000-000000000002'",
    ],
    ids=[
        "sequence",
        "old",
        "format",
        "timezone",
        "generation",
        "sample-operation",
        "initial-reset",
    ],
)
def test_corrupt_clock_row_fails_closed(private_root, sql):
    owner, _ = seeded(private_root)
    with database(owner.path) as db:
        tamper(db, "clock_no_update", sql)
    with pytest.raises(SourceStoreUnavailable):
        SourceClockAdmin(store(private_root)).read()


def _clock_child(root, action, offset, op, expected, pause, crash, release, signals):
    import os

    from connect_automate.lead_intake import SourceStoreError

    connect = sqlite3.connect
    stopped = blocked = False

    def checkpoint(stage):
        nonlocal stopped
        if stage == crash:
            os._exit(24)
        if stage == pause and not stopped:
            stopped = True
            signals.put(("paused", action, stage))
            assert release.wait(30)

    class Observed(sqlite3.Connection):
        def execute(self, sql, *args):
            nonlocal blocked
            try:
                result = super().execute(sql, *args)
            except sqlite3.OperationalError as exc:
                if (
                    sql == "BEGIN IMMEDIATE"
                    and exc.sqlite_errorcode & 255 in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                    and not blocked
                ):
                    blocked = True
                    signals.put(("blocked", action))
                raise
            if sql.startswith("INSERT INTO authority_clock_history"):
                checkpoint("write")
            return result

        def commit(self):
            checkpoint("before-commit")
            super().commit()
            checkpoint("after-commit")

    with patch.object(sqlite3, "connect", lambda *a, **kw: connect(*a, **kw, factory=Observed)):
        owner = store(root, busy_timeout_ms=30000)
        try:
            if action.startswith("admit"):
                result = SourceAdmission(
                    owner, clock=lambda: NOW + timedelta(seconds=offset)
                ).admit_source(encode(envelope()))
                outcome = ("accepted", result.applied, None)
            else:
                result = SourceClockAdmin(owner).reconcile(
                    operation_id=op,
                    expected_sequence=expected,
                    corrected_at=NOW + timedelta(seconds=offset),
                )
                outcome = ("reconciled", result.sequence, None)
        except (SourceStoreError, SourceAuthenticationError) as exc:
            outcome = (type(exc).__name__, None, None)
        checkpoint("lost-response")
        signals.put(("result", action, outcome, []))


class ClockRace(Race):
    def start(self, action, *, offset=0, op=OTHER, expected=1, pause=None, crash=None):
        release = self.context.Event()
        child = self.context.Process(
            target=_clock_child,
            args=(self.root, action, offset, op, expected, pause, crash, release, self.signals),
        )
        child.start()
        self.workers[action] = child, release


@pytest.mark.parametrize("first", ["admit", "reset"])
def test_c1_serializes_with_admission(private_root, first):
    owner, _ = seeded(private_root)
    with ClockRace(private_root, encode(envelope())) as race:
        race.start(first, offset=20 if first == "admit" else 0, pause="before-commit")
        race.expect("paused", first, "before-commit")
        second = "reset" if first == "admit" else "admit"
        race.start(second)
        race.expect("blocked", second)
        race.release(first)
        results = race.finish()
    assert results["admit"][0][0] == "accepted"
    assert results["reset"][0][0] == ("SourceStoreConflict" if first == "admit" else "reconciled")
    state = SourceClockAdmin(store(private_root)).read()
    assert state.floor == NOW + timedelta(seconds=20 if first == "admit" else 0)
    assert state.sequence == 2


@pytest.mark.parametrize("same", [False, True])
def test_concurrent_c1_uses_sequence_and_operation_identity(private_root, same):
    owner, _ = seeded(private_root)
    with ClockRace(private_root, encode(envelope())) as race:
        race.start("reset-a", pause="before-commit")
        race.expect("paused", "reset-a", "before-commit")
        race.start("reset-b", op=OTHER if same else str(uuid4()))
        race.expect("blocked", "reset-b")
        race.release("reset-a")
        results = race.finish()
    assert results["reset-a"][0][:2] == ("reconciled", 2)
    assert results["reset-b"][0][0] == ("reconciled" if same else "SourceStoreConflict")
    assert len(history(owner)) == 2


@pytest.mark.parametrize("action", ["admit", "reset"])
@pytest.mark.parametrize("crash", ["write", "before-commit", "after-commit", "lost-response"])
def test_clock_process_crash_recovery(private_root, action, crash):
    owner, _ = seeded(private_root)
    before = history(owner)
    with ClockRace(private_root, encode(envelope())) as race:
        race.start(action, offset=20 if action == "admit" else 0, crash=crash)
        child, _ = race.workers[action]
        child.join(30)
        assert child.exitcode == 24
    committed = crash in ("after-commit", "lost-response")
    assert len(history(owner)) == len(before) + int(committed)
    if action == "reset":
        result = SourceClockAdmin(store(private_root)).reconcile(
            operation_id=OTHER, expected_sequence=1, corrected_at=NOW
        )
        assert result.sequence == 2 and result.floor == NOW
        assert len(history(owner)) == 2
    else:
        assert SourceClockAdmin(owner).read().floor == NOW + timedelta(
            seconds=20 if committed else 10
        )
        result = SourceAdmission(
            store(private_root), clock=lambda: NOW + timedelta(seconds=20)
        ).admit_source(encode(envelope()))
        assert not result.applied
    assert counts(owner) == (1, 1, 1)


@pytest.mark.parametrize(
    "kind", ["sample-decrease", "reset-increase", "reset-id", "generation-regression"]
)
def test_corruption_reaches_each_history_guard(private_root, kind):
    owner, _ = seeded(private_root)
    if kind == "generation-regression":
        owner.publish_authority(next_snapshot(), expected_generation=1)
        SourceAdmission(owner, clock=lambda: NOW + timedelta(seconds=11)).admit_source(
            encode(envelope())
        )
        SourceAdmission(owner, clock=lambda: NOW + timedelta(seconds=12)).admit_source(
            encode(envelope())
        )
        sql = "UPDATE authority_clock_history SET generation=1 WHERE sequence=3"
    else:
        SourceClockAdmin(owner).reconcile(operation_id=OTHER, expected_sequence=1, corrected_at=NOW)
        sql = {
            "sample-decrease": (
                "UPDATE authority_clock_history SET kind='sample',"
                "operation_id=NULL WHERE sequence=2"
            ),
            "reset-increase": (
                "UPDATE authority_clock_history SET "
                "new_floor='2026-10-18T12:30:11.000000Z' WHERE sequence=2"
            ),
            "reset-id": (
                "UPDATE authority_clock_history SET operation_id='invalid' WHERE sequence=2"
            ),
        }[kind]
    with database(owner.path) as db:
        tamper(db, "clock_no_update", sql)
    with pytest.raises(SourceStoreUnavailable) as caught:
        SourceClockAdmin(store(private_root)).read()
    assert caught.value.__context__ is None


def test_history_is_immutable_and_old_schema_is_not_upgraded(private_root):
    owner, _ = seeded(private_root)
    before = preserved(owner), history(owner)
    for sql in (
        "DELETE FROM authority_clock_history",
        "UPDATE authority_clock_history SET sequence=8",
    ):
        with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    with database(owner.path) as db:
        db.execute("PRAGMA user_version=2")
    for operation in (
        lambda: owner.initialize(trust()),
        lambda: SourceClockAdmin(owner).read(),
        lambda: SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope())),
    ):
        with pytest.raises(SourceStoreUnavailable):
            operation()
    assert (preserved(owner), history(owner)) == before


def test_c1_empty_floor_and_confirmation(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    admin = SourceClockAdmin(owner)
    assert admin.read().floor is None
    with pytest.raises(SourceStoreConflict):
        admin.reconcile(operation_id=OTHER, expected_sequence=1, corrected_at=NOW)
    assert history(owner) == []
    SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope()))
    admin.reconcile(operation_id=OTHER, expected_sequence=1, corrected_at=NOW)
    assert len(history(owner)) == 2


def test_c1_preserves_terminal_content_state(private_root):
    owner, receipt = seeded(private_root)
    with database(owner.path) as db:
        db.execute("DELETE FROM source_content")
        db.execute("UPDATE source_custody SET state='purged'")
    before = preserved(owner)
    SourceClockAdmin(owner).reconcile(operation_id=OTHER, expected_sequence=1, corrected_at=NOW)
    assert preserved(owner) == before
    result = SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope()))
    assert result.receipt == receipt.receipt and result.content_state == "purged"
    assert counts(owner) == (1, 0, 1)


def test_missing_history_with_receipt_fails_closed(private_root):
    owner, _ = seeded(private_root)
    with database(owner.path) as db:
        tamper(db, "clock_no_delete", "DELETE FROM authority_clock_history")
    with pytest.raises(SourceStoreUnavailable):
        SourceClockAdmin(owner).read()


@pytest.mark.parametrize("stage", ["write", "commit-before", "commit-after"])
def test_c1_sql_failure_replays_without_reapplying(private_root, stage):
    from connect_automate.lead_intake import SourceStoreUncertain

    owner, _ = seeded(private_root)
    before = preserved(owner)
    connect = sqlite3.connect

    class Fail(sqlite3.Connection):
        def execute(self, sql, *args):
            result = super().execute(sql, *args)
            if stage == "write" and sql.startswith("INSERT INTO authority_clock_history"):
                raise sqlite3.OperationalError("synthetic-private-detail")
            return result

        def commit(self):
            if stage == "commit-before":
                raise sqlite3.OperationalError("synthetic-private-detail")
            super().commit()
            if stage == "commit-after":
                raise sqlite3.OperationalError("synthetic-private-detail")

    args = dict(operation_id=OTHER, expected_sequence=1, corrected_at=NOW)
    with patch.object(sqlite3, "connect", lambda *a, **kw: connect(*a, **kw, factory=Fail)):
        with pytest.raises(
            SourceStoreUnavailable if stage == "write" else SourceStoreUncertain
        ) as error:
            SourceClockAdmin(owner).reconcile(**args)
        assert error.value.__context__ is None
    assert len(history(owner)) == (2 if stage == "commit-after" else 1)
    assert SourceClockAdmin(store(private_root)).reconcile(**args).sequence == 2
    assert len(history(owner)) == 2 and preserved(owner) == before
