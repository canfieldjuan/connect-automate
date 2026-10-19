"""Local content lifecycle proofs through the actual writer; synthetic data only."""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from test_lead_source_admission import counts, tamper
from test_lead_source_auth import NOW, OTHER, encode, envelope, key, resign, trust, trust_data
from test_lead_source_races import Race
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake import (
    SourceAdmission,
    SourceAuthenticationError,
    SourceStoreConflict,
    SourceStoreError,
    SourceStoreInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
    SourceTrustSnapshot,
)
from connect_automate.lead_intake.content import SourceContent, SourceContentUnavailable
from connect_automate.lead_intake.source import SourceIdentity
from connect_automate.lead_intake.source_store import SourceClockAdmin, SourceStore


def test_content_survives_reopen(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    raw = encode(envelope())
    receipt = SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).receipt
    assert (
        SourceContent(store(private_root), clock=lambda: NOW).read_content(receipt.admission_id)
        == raw
    )


def identity(value=None):
    return SourceIdentity.model_validate((value or envelope())["payload"]["source"])


def initialized(root):
    owner = store(root)
    owner.initialize(trust())
    return owner


def admit(owner, *, message=None, captured=None):
    value = envelope()
    value["payload"]["event_id"] = str(uuid4())
    if message is not None:
        value["payload"]["source"]["message_id"] = message
    if captured is not None:
        value["payload"]["snapshot"]["captured_at"] = captured
        value["payload"]["occurred_at"] = captured
    raw = resign(value)
    return SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).receipt, raw


def rows(owner, table):
    with database(owner.path) as db:
        return db.execute("SELECT * FROM " + table).fetchall()


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_expiry_boundary_and_c1_cannot_revive(private_root, offset):
    owner = initialized(private_root)
    receipt, raw = admit(owner)
    deadline = datetime.fromisoformat(receipt.recovery_deadline)
    access = SourceContent(
        store(private_root), clock=lambda: deadline + timedelta(microseconds=offset)
    )
    if offset < 0:
        assert access.read_content(receipt.admission_id) == raw
        assert counts(owner) == (1, 1, 1)
    else:
        with pytest.raises(SourceContentUnavailable):
            access.read_content(receipt.admission_id)
        assert counts(owner) == (1, 0, 1)
        admin = SourceClockAdmin(owner)
        admin.reconcile(
            operation_id=str(uuid4()), expected_sequence=admin.read().sequence, corrected_at=NOW
        )
        with pytest.raises(SourceContentUnavailable):
            SourceContent(owner, clock=lambda: NOW).read_content(receipt.admission_id)
        assert rows(owner, "source_custody")[0][3] == "purged"


def test_read_checks_final_sample_expiry(private_root):
    owner = initialized(private_root)
    receipt, _ = admit(owner)
    deadline = datetime.fromisoformat(receipt.recovery_deadline)
    times = iter([NOW, deadline])
    with pytest.raises(SourceContentUnavailable):
        SourceContent(owner, clock=times.__next__).read_content(receipt.admission_id)
    assert counts(owner) == (1, 0, 1)


def test_host_read_survives_key_revocation(private_root):
    owner = initialized(private_root)
    receipt, raw = admit(owner)
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    assert (
        SourceContent(store(private_root), clock=lambda: NOW).read_content(receipt.admission_id)
        == raw
    )
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW).admit_source(raw)


@pytest.mark.parametrize("damage", ["missing", "hash", "identity"])
def test_host_read_reuses_custody_validation(private_root, damage):
    owner = initialized(private_root)
    receipt, _ = admit(owner)
    with database(owner.path) as db:
        if damage == "missing":
            db.execute("DELETE FROM source_content")
        elif damage == "hash":
            tamper(
                db, "receipt_no_update", "UPDATE source_receipts SET envelope_sha256=?", ("0" * 64,)
            )
        else:
            wrong = identity().model_copy(update={"message_id": "other"})
            from connect_automate.lead_intake.source_store import _identity_text

            tamper(
                db,
                "custody_identity_no_update",
                "UPDATE source_custody SET identity=?",
                (_identity_text(wrong),),
            )
    with pytest.raises(SourceStoreUnavailable) as error:
        SourceContent(owner, clock=lambda: NOW).read_content(receipt.admission_id)
    assert error.value.__context__ is None


def test_foreign_deployment_cannot_read_or_purge(private_root):
    owner = initialized(private_root)
    receipt, _ = admit(owner)
    foreign = SourceStore(
        owner.path, private_root=private_root, host_id=owner.host_id, organization_id=OTHER
    )
    access = SourceContent(foreign, clock=lambda: NOW)
    with pytest.raises(SourceStoreUnavailable):
        access.read_content(receipt.admission_id)
    with pytest.raises(SourceStoreUnavailable):
        access.purge_message(identity(), cutoff=NOW)
    assert counts(owner) == (1, 1, 1)


def test_cleanup_is_bounded_restartable_and_preserves_receipts(private_root):
    owner = initialized(private_root)
    for _ in range(3):
        admit(owner)
    receipts = rows(owner, "source_receipts")
    for remaining in (2, 1, 0):
        assert (
            SourceContent(
                store(private_root), clock=lambda: NOW + timedelta(minutes=30)
            ).cleanup_expired(limit=1)
            == 1
        )
        assert counts(owner) == (3, remaining, 3)
    assert (
        SourceContent(owner, clock=lambda: NOW + timedelta(minutes=30)).cleanup_expired(limit=1)
        == 0
    )
    assert rows(owner, "source_receipts") == receipts


def test_message_wide_purge_preserves_other_message(private_root):
    owner = initialized(private_root)
    first, raw = admit(owner)
    second, _ = admit(owner)
    other, other_raw = admit(owner, message="unrelated")
    receipts = rows(owner, "source_receipts")
    access = SourceContent(owner, clock=lambda: NOW)
    assert access.purge_message(identity(), cutoff=NOW)
    assert counts(owner) == (3, 1, 3)
    assert rows(owner, "source_receipts") == receipts
    for receipt in (first, second):
        with pytest.raises(SourceContentUnavailable):
            access.read_content(receipt.admission_id)
    assert access.read_content(other.admission_id) == other_raw
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW).admit_source(raw)
    assert "Synthetic inquiry" not in str(rows(owner, "source_purge_horizons"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("namespace_id", OTHER),
        ("provider", "different"),
        ("account_id", "different"),
        ("mailbox_identity_key", "f" * 64),
        ("message_id", "different"),
    ],
)
def test_purge_identity_requires_whole_tuple(private_root, field, value):
    owner = initialized(private_root)
    receipt, raw = admit(owner)
    access = SourceContent(owner, clock=lambda: NOW)
    assert access.purge_message(identity().model_copy(update={field: value}), cutoff=NOW)
    assert access.read_content(receipt.admission_id) == raw


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_absent_purge_horizon_boundary_and_refollow(private_root, offset):
    owner = initialized(private_root)
    access = SourceContent(owner, clock=lambda: NOW)
    cutoff = NOW - timedelta(minutes=1)
    assert access.purge_message(identity(), cutoff=cutoff)
    capture = (
        (cutoff + timedelta(seconds=offset)).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    if offset <= 0:
        with pytest.raises(SourceAuthenticationError):
            admit(store(private_root), captured=capture)
        assert counts(owner) == (0, 0, 0)
    else:
        receipt, raw = admit(store(private_root), captured=capture)
        assert not access.purge_message(identity(), cutoff=cutoff)
        assert not access.purge_message(identity(), cutoff=cutoff - timedelta(seconds=1))
        assert access.read_content(receipt.admission_id) == raw
        assert access.purge_message(identity(), cutoff=cutoff + timedelta(seconds=1))
        with pytest.raises(SourceContentUnavailable):
            access.read_content(receipt.admission_id)


def test_retirement_denies_before_bounded_metadata_erasure(private_root):
    owner = initialized(private_root)
    first, raw = admit(owner)
    admit(owner)
    access = SourceContent(owner, clock=lambda: NOW)
    namespace = identity().namespace_id
    with pytest.raises(SourceStoreConflict):
        access.cleanup_retired(namespace, limit=1)
    assert access.purge_message(identity(), cutoff=NOW - timedelta(hours=1))
    assert access.retire_namespace(namespace)
    assert not access.retire_namespace(namespace)
    with pytest.raises(SourceContentUnavailable):
        access.read_content(first.admission_id)
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW).admit_source(raw)
    with pytest.raises(SourceStoreConflict):
        owner.publish_authority(next_snapshot(), expected_generation=1)
    for _ in range(3):
        assert (
            SourceContent(store(private_root), clock=lambda: NOW).cleanup_retired(
                namespace, limit=1
            )
            == 1
        )
    assert access.cleanup_retired(namespace, limit=1) == 0
    assert counts(owner) == (0, 0, 0) and rows(owner, "source_purge_horizons") == []
    assert rows(owner, "source_retired")[0][0] == namespace
    with pytest.raises(SourceAuthenticationError):
        admit(store(private_root))
    assert not access.purge_message(identity(), cutoff=NOW)
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    data = trust_data()
    data["generation"] = 3
    data["key_grants"][0].update(
        key_id=OTHER, public_key=key(b"x" * 32).public_key().public_bytes_raw()
    )
    with pytest.raises(SourceStoreConflict):
        owner.publish_authority(SourceTrustSnapshot.model_validate(data), expected_generation=2)
    data["key_grants"][0]["namespace_id"] = OTHER
    assert owner.publish_authority(SourceTrustSnapshot.model_validate(data), expected_generation=2)


@pytest.mark.parametrize("limit", [0, False, "", -1, 1001])
def test_cleanup_limit_is_strict(private_root, limit):
    owner = initialized(private_root)
    access = SourceContent(owner, clock=lambda: NOW)
    with pytest.raises(SourceStoreInputError):
        access.cleanup_expired(limit=limit)
    with pytest.raises(SourceStoreInputError):
        access.cleanup_retired(identity().namespace_id, limit=limit)


def test_sql_deletion_prevention_and_terminal_markers(private_root):
    owner = initialized(private_root)
    admit(owner)
    access = SourceContent(owner, clock=lambda: NOW)
    access.purge_message(identity(), cutoff=NOW)
    with database(owner.path) as db:
        for sql in (
            "DELETE FROM source_receipts",
            "DELETE FROM source_custody",
            "DELETE FROM source_purge_horizons",
            "UPDATE source_purge_horizons SET cutoff='2026-10-18T12:00:00.000000Z'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
    access.retire_namespace(identity().namespace_id)
    with database(owner.path) as db:
        for sql in (
            "DELETE FROM source_retired",
            "UPDATE source_retired SET retired_at='2026-10-18T12:00:00.000000Z'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)


def invoke(owner, action, raw):
    access = SourceContent(
        owner, clock=lambda: NOW + timedelta(minutes=30) if action == "expire" else NOW
    )
    if action == "admit":
        return SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).applied
    if action == "purge":
        return access.purge_message(identity(), cutoff=NOW)
    if action == "retire":
        return access.retire_namespace(identity().namespace_id)
    if action == "erase":
        return access.cleanup_retired(identity().namespace_id, limit=1)
    if action == "expire":
        return access.cleanup_expired(limit=1)
    if action == "publish":
        return owner.publish_authority(next_snapshot(), expected_generation=1)
    raise AssertionError(action)


def _lifecycle_worker(root, raw, action, pause, release, signals, crash):
    # Faults wrap real SQL/commit. Processes import the actual package, as in Race.
    import os
    from unittest.mock import patch

    owner = store(root, busy_timeout_ms=30000)
    connect = sqlite3.connect
    blocked = False

    class Observed(sqlite3.Connection):
        def execute(self, sql, *args):
            nonlocal blocked
            try:
                result = super().execute(sql, *args)
            except sqlite3.OperationalError as exc:
                if (
                    sql.startswith("BEGIN")
                    and not blocked
                    and exc.sqlite_errorcode & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                ):
                    blocked = True
                    signals.put(("blocked", action))
                raise
            if crash == "write" and sql.startswith("DELETE FROM source_content"):
                os._exit(73)
            return result

        def commit(self):
            if pause:
                signals.put(("paused", action, "commit"))
                assert release.wait(30)
            if crash == "before":
                os._exit(73)
            super().commit()
            if crash == "after":
                os._exit(73)

    with patch.object(sqlite3, "connect", lambda *a, **kw: connect(*a, **kw, factory=Observed)):
        try:
            result = invoke(owner, action, raw)
            outcome = ("ok", result, None)
        except (SourceAuthenticationError, SourceStoreError) as exc:
            assert exc.__context__ is None
            outcome = (type(exc).__name__, None, None)
    if crash == "response":
        os._exit(73)
    signals.put(("result", action, outcome, []))


class LifecycleRace(Race):
    def start(self, action, pause=None, crash=None):
        release = self.context.Event()
        child = self.context.Process(
            target=_lifecycle_worker,
            args=(self.root, self.raw, action, pause, release, self.signals, crash),
        )
        child.start()
        self.workers[action] = child, release


@pytest.mark.parametrize("action", ["purge", "retire"])
@pytest.mark.parametrize("first", ["admit", "lifecycle"])
@pytest.mark.parametrize("replay", [False, True])
def test_admission_and_lifecycle_real_writer_order(private_root, action, first, replay):
    owner = initialized(private_root)
    raw = encode(envelope())
    if replay:
        SourceAdmission(owner, clock=lambda: NOW).admit_source(raw)
    left, right = ("admit", action) if first == "admit" else (action, "admit")
    with LifecycleRace(private_root, raw) as race:
        race.start(left, "commit")
        race.expect("paused", left, "commit")
        race.start(right)
        race.expect("blocked", right)
        race.release(left)
        results = race.finish()
    assert results[action][0] == ("ok", True, None)
    if first == "admit":
        assert results["admit"][0] == ("ok", not replay, None)
    else:
        assert results["admit"][0] == ("SourceAuthenticationError", None, None)
    assert counts(owner)[0] == int(replay or first == "admit")
    if action == "purge":
        assert counts(owner)[1] == 0
    for row in rows(owner, "source_receipts"):
        with pytest.raises(SourceContentUnavailable):
            SourceContent(owner, clock=lambda: NOW).read_content(row[0])
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(store(private_root), clock=lambda: NOW).admit_source(raw)


@pytest.mark.parametrize("first", ["publish", "retire"])
def test_retirement_and_grant_publication_serialize(private_root, first):
    initialized(private_root)
    second = "retire" if first == "publish" else "publish"
    with LifecycleRace(private_root, encode(envelope())) as race:
        race.start(first, "commit")
        race.expect("paused", first, "commit")
        race.start(second)
        race.expect("blocked", second)
        race.release(first)
        results = race.finish()
    assert results["retire"][0] == ("ok", True, None)
    expected = ("ok", True, None) if first == "publish" else ("SourceStoreConflict", None, None)
    assert results["publish"][0] == expected


def prepare_operation(root, action):
    owner = initialized(root)
    receipt, raw = admit(owner)
    access = SourceContent(owner, clock=lambda: NOW)
    if action == "erase":
        access.purge_message(identity(), cutoff=NOW)
        access.retire_namespace(identity().namespace_id)
    return owner, receipt, raw


def snapshot(owner):
    return tuple(
        rows(owner, table)
        for table in (
            "source_receipts",
            "source_content",
            "source_custody",
            "source_purge_horizons",
            "source_retired",
            "authority_clock_history",
        )
    )


@pytest.mark.parametrize("action", ["purge", "retire", "expire", "erase"])
@pytest.mark.parametrize("stage", ["before", "after", "response"])
def test_process_crash_and_lost_response_recover(private_root, action, stage):
    owner, receipt, raw = prepare_operation(private_root, action)
    before = snapshot(owner)
    with LifecycleRace(private_root, raw) as race:
        race.start(action, crash=stage)
        child, _ = race.workers[action]
        child.join(30)
        assert not child.is_alive() and child.exitcode == 73
    if stage == "before":
        assert snapshot(store(private_root)) == before
    else:
        assert snapshot(store(private_root)) != before
    # Retry the same operation after reopening; no body or receipt resurrection.
    invoke(store(private_root), action, raw)
    if action == "erase":
        assert counts(owner) == (0, 0, 0)
        assert len(rows(owner, "source_purge_horizons")) == int(stage == "before")
    else:
        now = NOW + timedelta(minutes=30) if action == "expire" else NOW
        with pytest.raises(SourceContentUnavailable):
            SourceContent(store(private_root), clock=lambda: now).read_content(receipt.admission_id)
        assert counts(owner)[0] == 1


@pytest.mark.parametrize("action", ["purge", "expire"])
def test_process_dies_between_payload_and_custody_writes(private_root, action):
    owner, _, raw = prepare_operation(private_root, action)
    before = snapshot(owner)
    with LifecycleRace(private_root, raw) as race:
        race.start(action, crash="write")
        child, _ = race.workers[action]
        child.join(30)
        assert not child.is_alive() and child.exitcode == 73
    assert snapshot(store(private_root)) == before
    invoke(store(private_root), action, raw)
    assert counts(owner) == (1, 0, 1)


@pytest.mark.parametrize(
    "action,sql",
    [
        ("purge", "DELETE FROM source_content"),
        ("purge", "UPDATE source_custody"),
        ("purge", "INSERT INTO source_purge_horizons"),
        ("retire", "INSERT INTO source_retired"),
        ("erase", "DELETE FROM source_custody"),
        ("erase", "DELETE FROM source_receipts"),
        ("erase_horizon", "DELETE FROM source_purge_horizons"),
        ("expire", "DELETE FROM source_content"),
        ("expire", "UPDATE source_custody"),
    ],
)
def test_sql_failure_rolls_back_every_lifecycle_write(private_root, action, sql):
    owner, _, raw = prepare_operation(
        private_root, "erase" if action == "erase_horizon" else action
    )
    if action == "erase_horizon":
        invoke(owner, "erase", raw)
        action = "erase"
    before = snapshot(owner)
    connect = sqlite3.connect
    hit = []

    class Fault(sqlite3.Connection):
        def execute(self, statement, *args):
            result = super().execute(statement, *args)
            if statement.startswith(sql):
                hit.append(statement)
                raise sqlite3.OperationalError("synthetic failure after write")
            return result

    with (
        patch.object(sqlite3, "connect", lambda *a, **kw: connect(*a, **kw, factory=Fault)),
        pytest.raises(SourceStoreUnavailable) as error,
    ):
        invoke(owner, action, raw)
    assert hit and error.value.__context__ is None
    assert snapshot(store(private_root)) == before
    invoke(store(private_root), action, raw)
    assert snapshot(owner) != before


@pytest.mark.parametrize("action", ["purge", "retire", "expire", "erase"])
@pytest.mark.parametrize("committed", [False, True])
def test_uncertain_commit_can_be_retried(private_root, action, committed):
    owner, _, raw = prepare_operation(private_root, action)
    before = snapshot(owner)
    connect = sqlite3.connect

    class Uncertain(sqlite3.Connection):
        def commit(self):
            if committed:
                super().commit()
            raise sqlite3.OperationalError("synthetic acknowledgement loss")

    with (
        patch.object(sqlite3, "connect", lambda *a, **kw: connect(*a, **kw, factory=Uncertain)),
        pytest.raises(SourceStoreUncertain),
    ):
        invoke(owner, action, raw)
    assert (snapshot(store(private_root)) != before) == committed
    invoke(store(private_root), action, raw)
    assert snapshot(owner) != before


@pytest.mark.parametrize("action", ["read", "expire", "retire"])
@pytest.mark.parametrize(
    "samples", [(NOW - timedelta(seconds=1),), (NOW, NOW - timedelta(seconds=1))]
)
def test_lifecycle_clock_regression_rolls_back(private_root, action, samples):
    owner = initialized(private_root)
    receipt, _ = admit(owner)
    before = snapshot(owner)
    times = iter(samples)
    access = SourceContent(owner, clock=times.__next__)
    with pytest.raises(SourceAuthenticationError):
        if action == "read":
            access.read_content(receipt.admission_id)
        elif action == "expire":
            access.cleanup_expired(limit=1)
        else:
            access.retire_namespace(identity().namespace_id)
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "damage",
    ["identity_canonical", "namespace", "horizon_time", "retired_namespace", "retired_time"],
)
def test_lifecycle_metadata_corruption_fails_closed(private_root, damage):
    owner = initialized(private_root)
    access = SourceContent(owner, clock=lambda: NOW)
    access.purge_message(identity(), cutoff=NOW)
    access.retire_namespace(identity().namespace_id)
    with database(owner.path) as db:
        if damage == "identity_canonical":
            tamper(
                db, "horizon_monotonic", "UPDATE source_purge_horizons SET identity=identity||' '"
            )
        elif damage == "namespace":
            tamper(
                db, "horizon_monotonic", "UPDATE source_purge_horizons SET namespace_id=?", (OTHER,)
            )
        elif damage == "horizon_time":
            tamper(
                db,
                "horizon_monotonic",
                "UPDATE source_purge_horizons SET cutoff='2026-10-18T12:30:00Z'",
            )
        elif damage == "retired_namespace":
            tamper(db, "retired_no_update", "UPDATE source_retired SET namespace_id='invalid'")
        else:
            tamper(
                db,
                "retired_no_update",
                "UPDATE source_retired SET retired_at='2026-10-18T12:30:00Z'",
            )
    with pytest.raises(SourceStoreUnavailable):
        access.cleanup_retired(identity().namespace_id, limit=1)


@pytest.mark.parametrize("state", ["unavailable", "complete", "truncated", "unknown"])
def test_read_preserves_body_availability_metadata(private_root, state):
    owner = initialized(private_root)
    value = envelope()
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": "source_gone"}
    else:
        body = value["payload"]["snapshot"]["body"]
        body["completeness"] = state
        body["source_chars"] = (
            None if state == "unknown" else len(body["text"]) + (state == "truncated")
        )
    raw = resign(value)
    receipt = SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).receipt
    assert (
        SourceContent(store(private_root), clock=lambda: NOW).read_content(receipt.admission_id)
        == raw
    )


def test_cleanup_expired_skips_live_content(private_root):
    owner = initialized(private_root)
    old, _ = admit(owner)
    value = envelope()
    value["payload"]["event_id"] = OTHER
    value["payload"]["snapshot"]["captured_at"] = "2026-10-18T12:30:00Z"
    value["payload"]["occurred_at"] = "2026-10-18T12:30:00Z"
    value["payload"]["retention"]["recovery_deadline"] = "2026-10-18T13:30:00Z"
    raw = resign(value)
    live = SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).receipt
    access = SourceContent(owner, clock=lambda: NOW + timedelta(minutes=30))
    assert access.cleanup_expired(limit=1000) == 1
    with pytest.raises(SourceContentUnavailable):
        access.read_content(old.admission_id)
    assert access.read_content(live.admission_id) == raw
    assert access.cleanup_expired(limit=1000) == 0


def test_retired_cleanup_preserves_active_namespace(private_root):
    from copy import deepcopy

    value, data = envelope(), trust_data()
    value["payload"]["source"]["namespace_id"] = OTHER
    value["authorization"]["key_id"] = OTHER
    grant = deepcopy(data["key_grants"][0])
    signer = key(bytes(reversed(range(32))))
    grant.update(
        key_id=OTHER, namespace_id=OTHER, public_key=signer.public_key().public_bytes_raw()
    )
    data["key_grants"].append(grant)
    owner = store(private_root)
    owner.initialize(SourceTrustSnapshot.model_validate(data))
    original, _ = admit(owner)
    raw = resign(value, signer)
    active = SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).receipt
    access = SourceContent(owner, clock=lambda: NOW)
    access.purge_message(identity(), cutoff=NOW - timedelta(hours=1))
    access.purge_message(identity(value), cutoff=NOW - timedelta(hours=1))
    # Newer captures can arrive again; use fresh event IDs.
    value["payload"]["event_id"] = OTHER
    raw = resign(value, signer)
    live = SourceAdmission(owner, clock=lambda: NOW).admit_source(raw).receipt
    access.retire_namespace(identity().namespace_id)
    with database(owner.path) as db:
        for statement, value in (
            ("DELETE FROM source_receipts WHERE namespace_id=?", OTHER),
            ("DELETE FROM source_custody WHERE admission_id=?", active.admission_id),
            ("DELETE FROM source_purge_horizons WHERE namespace_id=?", OTHER),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(statement, (value,))
    assert access.cleanup_retired(identity().namespace_id, limit=1000) == 2
    assert {r[0] for r in rows(owner, "source_receipts")} == {
        active.admission_id,
        live.admission_id,
    }
    assert rows(owner, "source_purge_horizons")[0][1] == OTHER
    assert access.read_content(live.admission_id) == raw
    with pytest.raises(SourceContentUnavailable):
        access.read_content(original.admission_id)


@pytest.mark.parametrize("bad", [False, 0, "", None, "invalid", OTHER.upper()])
def test_invalid_host_identifiers(private_root, bad):
    # OTHER contains only digits: use an uppercase alphabetic UUID for that case.
    if bad == OTHER:
        bad = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    owner = initialized(private_root)
    access = SourceContent(owner, clock=lambda: NOW)
    with pytest.raises(SourceStoreInputError):
        access.read_content(bad)
    with pytest.raises(SourceStoreInputError):
        access.retire_namespace(bad)
    with pytest.raises(SourceStoreInputError):
        access.cleanup_retired(bad, limit=1)


def test_unknown_read_and_invalid_purge_inputs(private_root):
    owner = initialized(private_root)
    access = SourceContent(owner, clock=lambda: NOW)
    with pytest.raises(SourceContentUnavailable):
        access.read_content(OTHER)
    for bad in (None, False, {}, identity().model_copy(update={"message_id": ""})):
        with pytest.raises(SourceStoreInputError):
            access.purge_message(bad, cutoff=NOW)
    for bad in (None, False, "", NOW.replace(tzinfo=None)):
        with pytest.raises(SourceStoreInputError):
            access.purge_message(identity(), cutoff=bad)
    assert rows(owner, "source_purge_horizons") == []


def test_retired_cleanup_removes_still_retained_content(private_root):
    owner = initialized(private_root)
    receipt, _ = admit(owner)
    access = SourceContent(owner, clock=lambda: NOW)
    assert access.retire_namespace(identity().namespace_id)
    assert counts(owner) == (1, 1, 1)
    assert access.cleanup_retired(identity().namespace_id, limit=1) == 1
    assert counts(owner) == (0, 0, 0)
    with pytest.raises(SourceContentUnavailable):
        access.read_content(receipt.admission_id)


@pytest.mark.parametrize("column,value", [("identity", "{}"), ("namespace_id", OTHER)])
def test_horizon_identity_columns_are_immutable(private_root, column, value):
    owner = initialized(private_root)
    access = SourceContent(owner, clock=lambda: NOW)
    access.purge_message(identity(), cutoff=NOW)
    with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE source_purge_horizons SET " + column + "=?, cutoff=?",
            (value, "2026-10-18T12:31:00.000000Z"),
        )


@pytest.mark.parametrize("operation", ["purge", "expire", "erase"])
def test_deletion_candidates_validate_custody_and_rollback(private_root, operation):
    owner = initialized(private_root)
    first, _ = admit(owner)
    second, _ = admit(owner)
    access = SourceContent(
        owner, clock=lambda: NOW + timedelta(minutes=30) if operation == "expire" else NOW
    )
    if operation == "erase":
        access.retire_namespace(identity().namespace_id)
    # Purge walks insertion order; cleanup orders equal-deadline receipts by ID.
    bad = second if operation == "purge" else max((first, second), key=lambda r: r.admission_id)
    with database(owner.path) as db:
        tamper(
            db,
            "receipt_no_update",
            "UPDATE source_receipts SET envelope_sha256=? WHERE admission_id=?",
            ("0" * 64, bad.admission_id),
        )
    before = snapshot(owner)
    accepted = []
    validate = access._custody._existing

    def observed(db, row):
        result = validate(db, row)
        accepted.append(row[0])
        return result

    with (
        patch.object(access._custody, "_existing", observed),
        pytest.raises(SourceStoreUnavailable) as error,
    ):
        if operation == "purge":
            access.purge_message(identity(), cutoff=NOW)
        elif operation == "expire":
            access.cleanup_expired(limit=2)
        else:
            access.cleanup_retired(identity().namespace_id, limit=2)
    assert error.value.__context__ is None
    assert len(accepted) == 1 and bad.admission_id not in accepted
    assert snapshot(store(private_root)) == before
