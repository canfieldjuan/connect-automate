"""Native-process migration/observation proof, using the joined IPC protocol."""

import hashlib
import multiprocessing
import os
import sqlite3

import pytest
from test_lead_custody_store import legacy, seed_legacy, snapshot
from test_lead_joined_recovery import read_trace
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake.source_store import (
    _CUSTODY_SCHEMA,
    _SCHEMA_V4,
    SourceStoreError,
    _encode,
)

CRASH = 73
WRITES = len(_CUSTODY_SCHEMA) + 2


def child(root, pipe, target=None, fault=None, pause=None, release=None, action="migrate"):
    owner = store(root)
    real_connect = sqlite3.connect
    writes = 0
    paused = False

    def checkpoint(point):
        nonlocal paused
        pipe.send(("checkpoint", point))
        if point == pause and not paused:
            paused = True
            pipe.send(("paused", point))
            assert release.wait(30), "parent did not release observed writer"
        if point != target:
            return
        if fault == "crash":
            pipe.send(("complete", None))
            os._exit(CRASH)
        raise sqlite3.OperationalError("synthetic migration failure")

    class Observed(sqlite3.Connection):
        blocked = False

        def execute(self, sql, *args, **kwargs):
            nonlocal writes
            writing = sql.startswith(
                ("CREATE ", "INSERT INTO source_store_identity", "PRAGMA user_version=")
            )
            if writing:
                checkpoint(f"before-{writes + 1}")
            try:
                result = super().execute(sql, *args, **kwargs)
            except sqlite3.OperationalError as exc:
                if (
                    sql == "BEGIN IMMEDIATE"
                    and not self.blocked
                    and getattr(exc, "sqlite_errorcode", 0) & 0xFF
                    in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                ):
                    self.blocked = True
                    pipe.send(("blocked", None))
                raise
            if sql == "BEGIN IMMEDIATE":
                checkpoint("locked")
            if writing:
                writes += 1
                pipe.send(("write", writes))
                checkpoint(f"after-{writes}")
            return result

        def commit(self):
            checkpoint("before-commit")
            super().commit()
            checkpoint("after-commit")

    def connect(path, *args, **kwargs):
        if str(path) == owner.path.as_uri() + "?mode=rw":
            return real_connect(path, *args, factory=Observed, **kwargs)
        return real_connect(path, *args, **kwargs)

    sqlite3.connect = connect
    try:
        try:
            if action == "migrate":
                result = owner.migrate()
                checkpoint("response-lost")
                pipe.send(("result", (result.applied, result.incarnation)))
            elif action == "new-writer":
                owner.publish_authority(next_snapshot(), expected_generation=1)
                pipe.send(("result", "new-writer"))
            else:
                # The frozen v4 exact-manifest check, under the same writer as
                # its publication; no fabricated version-5-compatible old host.
                db = connect(
                    owner.path.as_uri() + "?mode=rw", uri=True, timeout=0, isolation_level=None
                )
                try:
                    owner._wait(db, "BEGIN IMMEDIATE", __import__("time").monotonic() + 5)
                    version = db.execute("PRAGMA user_version").fetchone()[0]
                    manifest = sorted(
                        r[0]
                        for r in db.execute(
                            "SELECT sql FROM sqlite_master WHERE substr(name,1,7)!='sqlite_'"
                        )
                    )
                    if version != 4 or manifest != sorted(_SCHEMA_V4):
                        pipe.send(("old-refused", None))
                    else:
                        raw = _encode(next_snapshot())
                        db.execute(
                            "INSERT INTO authority_history VALUES (2,?,?)",
                            (raw, hashlib.sha256(raw.encode()).hexdigest()),
                        )
                        db.commit()
                        pipe.send(("result", "old-writer"))
                finally:
                    db.close()
        except SourceStoreError as error:
            pipe.send(
                (
                    "error",
                    (
                        type(error).__name__,
                        str(error),
                        error.__context__ is None,
                        error.__cause__ is None,
                    ),
                )
            )
        pipe.send(("complete", None))
    finally:
        pipe.close()


def start(context, root, **kwargs):
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=child, args=(root, send), kwargs=kwargs)
    process.start()
    send.close()
    return process, receive


def finish(process, receive, messages, *, crashed=False):
    try:
        while read_trace(receive, messages) is not None:
            pass
        process.join(10)
        assert not process.is_alive(), "child did not terminate after completion"
        assert process.exitcode == (CRASH if crashed else 0), messages
    finally:
        if process.is_alive():
            process.terminate()
        process.join(10)
        process.close()
        receive.close()


@pytest.mark.parametrize(
    "target,fault",
    [
        (target, fault)
        for target in [
            *[f"{side}-{i}" for i in range(1, WRITES + 1) for side in ("before", "after")],
            "before-commit",
            "after-commit",
            "response-lost",
        ]
        for fault in ("crash", "sql")
        if (target, fault) != ("response-lost", "sql")
    ],
)
def test_migration_each_write_and_commit_reopens(private_root, target, fault):
    owner = legacy(private_root)
    seed_legacy(owner)
    before = snapshot(owner)
    process, receive = start(
        multiprocessing.get_context("spawn"), private_root, target=target, fault=fault
    )
    messages = []
    finish(process, receive, messages, crashed=fault == "crash")
    assert ("checkpoint", target) in messages
    committed = target in ("after-commit", "response-lost")
    with database(owner.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == (5 if committed else 4)
    after = snapshot(owner)
    assert {name: after[name] for name in before} == before
    if not committed:
        assert after == before
    prior_identity = store(private_root).read_incarnation() if committed else None
    retry = store(private_root).migrate()
    assert retry.applied is not committed
    if committed:
        assert retry.incarnation == prior_identity
    errors = [v for k, v in messages if k == "error"]
    if fault == "sql":
        expected = "SourceStoreUncertain" if "commit" in target else "SourceStoreUnavailable"
        assert errors and errors[0][0] == expected
        assert errors[0][2:] == (True, True)
    print(
        dict(
            target=target,
            fault=fault,
            writes=[v for k, v in messages if k == "write"],
            committed=committed,
            retry_applied=retry.applied,
        )
    )


@pytest.mark.parametrize(
    "first,second",
    [
        ("migrate", "migrate"),
        ("old-writer", "migrate"),
        ("migrate", "old-writer"),
        ("new-writer", "migrate"),
        ("migrate", "new-writer"),
    ],
)
def test_two_process_writer_orders(private_root, first, second):
    owner = legacy(private_root)
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    one, r1 = start(context, private_root, action=first, pause="locked", release=release)
    m1, m2 = [], []
    two = r2 = None
    try:
        while read_trace(r1, m1) != ("paused", "locked"):
            assert m1[-1][0] != "error"
        two, r2 = start(context, private_root, action=second)
        while read_trace(r2, m2) != ("blocked", None):
            assert m2[-1][0] != "error"
        release.set()
        finish(one, r1, m1)
        one = None
        finish(two, r2, m2)
        two = None
    finally:
        release.set()
        for process, receive in ((one, r1), (two, r2)):
            if process is not None:
                if process.is_alive():
                    process.terminate()
                process.join(10)
                process.close()
                receive.close()
    assert owner.migrate().applied is False
    assert owner.read_authority().generation == (
        2 if first == "old-writer" or second == "new-writer" else 1
    )
    if first == second:
        results = [v for k, v in m1 + m2 if k == "result"]
        assert sorted(v[0] for v in results) == [False, True]
        assert results[0][1] == results[1][1]
    if first == "new-writer":
        assert any(k == "error" and v[0] == "SourceStoreUnavailable" for k, v in m1)
    if second == "old-writer":
        assert ("old-refused", None) in m2


# Managed proof shares the same spawned-process/observed-SQL protocol above.
def managed_child(
    root,
    pipe,
    packet,
    action,
    *,
    target=None,
    fault=None,
    pause=None,
    release=None,
    now=None,
    late=None,
):
    from datetime import datetime

    from test_lead_custody_store import RESERVATION, reader
    from test_lead_source_auth import NOW

    from connect_automate.lead_intake.admission import SourceAdmission
    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.content import SourceContent
    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    owner = store(root, busy_timeout_ms=10000)
    real_connect = sqlite3.connect
    writes = 0
    paused = False

    def checkpoint(point):
        nonlocal paused
        pipe.send(("checkpoint", point))
        if point == pause and not paused:
            paused = True
            pipe.send(("paused", point))
            assert release.wait(30), "parent did not release managed writer"
        if point == target:
            if fault == "crash":
                pipe.send(("complete", None))
                os._exit(CRASH)
            raise sqlite3.OperationalError("synthetic managed failure")

    class Observed(sqlite3.Connection):
        blocked = False

        def execute(self, sql, *args, **kwargs):
            nonlocal writes
            writing = sql.startswith(("INSERT ", "UPDATE ", "DELETE "))
            if writing:
                checkpoint(f"before-{writes + 1}")
            try:
                result = super().execute(sql, *args, **kwargs)
            except sqlite3.OperationalError as error:
                if (
                    sql == "BEGIN IMMEDIATE"
                    and not self.blocked
                    and getattr(error, "sqlite_errorcode", 0) & 0xFF
                    in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                ):
                    self.blocked = True
                    pipe.send(("blocked", None))
                raise
            if sql == "BEGIN IMMEDIATE":
                checkpoint("locked")
            if writing:
                writes += 1
                pipe.send(
                    (
                        "write",
                        (
                            writes,
                            sql.split()[0],
                            sql.split()[2] if sql.startswith("INSERT") else sql.split()[1],
                        ),
                    )
                )
                checkpoint(f"after-{writes}")
            return result

        def commit(self):
            checkpoint("before-commit")
            super().commit()
            checkpoint("after-commit")

    def connect(path, *args, **kwargs):
        if str(path) == owner.path.as_uri() + "?mode=rw":
            return real_connect(path, *args, factory=Observed, **kwargs)
        return real_connect(path, *args, **kwargs)

    sqlite3.connect = connect
    try:
        access = reader(
            owner,
            expected_incarnation=packet["incarnation"],
            clock=lambda: (
                datetime.fromisoformat(now) if now and (late is None or late.is_set()) else NOW
            ),
            max_handoffs=packet.get("max_handoffs", 10),
            max_mutation_records=packet.get("max_mutation_records", 30),
        )
        prepared = parse_untrusted_request(packet["prepare"])
        upload = parse_untrusted_request(packet["upload"])
        settle = parse_untrusted_request(packet["settle"])
        try:
            if action == "register":
                access.register_intent(prepared, reservation_expires_at=RESERVATION)
            elif action == "bind":
                access.bind_upload(upload)
            elif action == "admit":
                access.admit_bound(upload, packet["raw"])
            elif action == "close":
                access.close_admission(settle)
            elif action == "legacy":
                SourceAdmission(owner, clock=lambda: NOW).admit_source(packet["raw"])
            elif action == "purge":
                SourceContent(owner, clock=lambda: NOW).purge_message(
                    prepared.payload.source, cutoff=NOW
                )
            elif action == "retire":
                SourceContent(owner, clock=lambda: NOW).retire_namespace(
                    prepared.scope.namespace_id
                )
            else:
                raise AssertionError(action)
            checkpoint("response-lost")
            pipe.send(("result", action))
        except (SourceStoreError, SourceAuthenticationError) as error:
            pipe.send(
                (
                    "error",
                    (
                        type(error).__name__,
                        str(error),
                        error.__context__ is None,
                        error.__cause__ is None,
                    ),
                )
            )
        pipe.send(("complete", None))
    finally:
        pipe.close()


def managed_start(context, root, packet, action, **kwargs):
    receive, send = context.Pipe(duplex=False)
    process = context.Process(
        target=managed_child, args=(root, send, packet, action), kwargs=kwargs
    )
    process.start()
    send.close()
    return process, receive


def managed_packet(root, phase="bound"):
    from test_lead_custody_store import RESERVATION, capture, managed_operation, managed_setup
    from test_lead_source_auth import encode, envelope

    from connect_automate.lead_intake.custody_protocol import canonical_request

    owner, access, prepared = managed_setup(root)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    settle = managed_operation(prepared, "settle")
    if phase != "empty":
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
    if phase in ("bound", "admitted"):
        access.bind_upload(upload)
    if phase == "admitted":
        access.admit_bound(upload, encode(envelope()))
    return owner, dict(
        incarnation=owner.read_incarnation(),
        prepare=canonical_request(prepared),
        upload=canonical_request(upload),
        settle=canonical_request(settle),
        raw=encode(envelope()),
    )


def native_directory(parent, name):
    path = parent / name
    path.mkdir(mode=0o700)
    if os.name == "nt":
        from connect_automate.connect_windows import _protect_windows_directory

        _protect_windows_directory(path)
    return path


@pytest.mark.parametrize(
    "action,phase",
    [
        ("register", "empty"),
        ("bind", "prepared"),
        ("admit", "bound"),
        ("close", "bound"),
        ("purge", "admitted"),
        ("retire", "admitted"),
    ],
)
@pytest.mark.parametrize("fault", ["crash", "sql"])
def test_managed_every_write_and_commit(private_root, action, phase, fault):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    context = multiprocessing.get_context("spawn")
    baseline_root = native_directory(private_root, "baseline")
    _, packet = managed_packet(baseline_root, phase)
    process, receive = managed_start(context, baseline_root, packet, action)
    baseline = []
    finish(process, receive, baseline)
    assert not [v for k, v in baseline if k == "error"], baseline
    writes = [v for k, v in baseline if k == "write"]
    assert writes, "real mutation not exercised"
    points = [f"{side}-{i}" for i, _, _ in writes for side in ("before", "after")] + [
        "before-commit",
        "after-commit",
    ]
    if fault == "crash":
        points += ["response-lost"]
    for index, point in enumerate(points):
        root = native_directory(private_root, f"case-{index}")
        owner, packet = managed_packet(root, phase)
        before = snapshot(owner)
        process, receive = managed_start(context, root, packet, action, target=point, fault=fault)
        messages = []
        finish(process, receive, messages, crashed=fault == "crash")
        assert ("checkpoint", point) in messages
        committed = point in ("after-commit", "response-lost")
        reopened = store(root)
        after = snapshot(reopened)
        if not committed:
            assert after == before, (action, point)
        if committed:
            assert after != before
            facts = observe(reader(reopened), parse_untrusted_request(packet["prepare"]))
            assert facts is not None
            if action == "admit":
                assert facts.ever_custodied and facts.receipt is not None
                assert (
                    len(after["source_content"])
                    == len(after["source_custody"])
                    == len(after["source_receipts"])
                    == 1
                )
                assert [r[6] for r in after["source_handoff_operations"] if r[3] == "upload"] == [
                    "admitted"
                ]
            if action in ("close", "purge", "retire"):
                assert facts.closed
        errors = [v for k, v in messages if k == "error"]
        if fault == "sql":
            expected = "SourceStoreUncertain" if "commit" in point else "SourceStoreUnavailable"
            assert len(errors) == 1 and errors[0][0] == expected and errors[0][2:] == (True, True)
        process, receive = managed_start(context, root, packet, action)
        retried = []
        finish(process, receive, retried)
        assert not [v for k, v in retried if k == "error"], retried
        if committed:
            assert snapshot(reopened) == after
        print(dict(action=action, point=point, fault=fault, committed=committed, writes=writes))


@pytest.mark.parametrize(
    "first,second,phase",
    [
        ("admit", "close", "bound"),
        ("close", "admit", "bound"),
        ("register", "legacy", "empty"),
        ("legacy", "register", "empty"),
        ("admit", "admit", "bound"),
        ("close", "close", "bound"),
        ("bind", "bind", "prepared"),
        ("register", "register", "empty"),
        ("purge", "admit", "bound"),
        ("admit", "purge", "bound"),
        ("retire", "bind", "prepared"),
        ("bind", "retire", "prepared"),
    ],
)
def test_managed_two_process_writer_orders(private_root, first, second, phase):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    owner, packet = managed_packet(private_root, phase)
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    one, r1 = managed_start(context, private_root, packet, first, pause="locked", release=release)
    m1, m2 = [], []
    two = r2 = None
    try:
        while read_trace(r1, m1) != ("paused", "locked"):
            assert m1[-1][0] != "error"
        two, r2 = managed_start(context, private_root, packet, second)
        while read_trace(r2, m2) != ("blocked", None):
            assert m2[-1][0] != "error"
        release.set()
        finish(one, r1, m1)
        one = None
        finish(two, r2, m2)
        two = None
    finally:
        release.set()
        for process, receive in ((one, r1), (two, r2)):
            if process is not None:
                if process.is_alive():
                    process.terminate()
                process.join(10)
                process.close()
                receive.close()
    assert not [v for k, v in m1 if k == "error"], m1
    refused = (first, second) in [
        ("close", "admit"),
        ("register", "legacy"),
        ("legacy", "register"),
        ("purge", "admit"),
        ("retire", "bind"),
    ]
    errors = [v for k, v in m2 if k == "error"]
    assert bool(errors) == refused, (m1, m2)
    if errors:
        assert errors[0][2:] == (True, True)
    after = snapshot(owner)
    facts = observe(reader(owner), parse_untrusted_request(packet["prepare"]))
    if first == "legacy":
        assert facts is None and len(after["source_receipts"]) == 1
    else:
        assert facts is not None
        if "close" in (first, second) or "purge" in (first, second) or "retire" in (first, second):
            assert facts.closed
        if first == "admit" or (first == second == "admit"):
            assert facts.ever_custodied
        if first in ("close", "purge", "retire"):
            assert not after["source_content"]
    print(dict(first=first, second=second, first_messages=m1, second_messages=m2))


@pytest.mark.parametrize("case", ["reservation", "grant", "capacity"])
def test_managed_wait_rechecks_time_and_capacity(private_root, case):
    from test_lead_custody_store import (
        RESERVATION,
        capture,
        managed_operation,
        managed_request,
        observe,
        reader,
    )
    from test_lead_source_auth import envelope, resign, trust

    from connect_automate.lead_intake.custody_protocol import (
        canonical_request,
        parse_untrusted_request,
    )

    owner, packet = managed_packet(private_root, "empty" if case == "capacity" else "bound")
    other = dict(packet)
    if case == "capacity":
        packet["max_mutation_records"] = other["max_mutation_records"] = 3
        value = envelope()
        value["payload"]["event_id"] = str(__import__("uuid").uuid4())
        resign(value)
        prepared = managed_request(value)
        other.update(
            prepare=canonical_request(prepared),
            upload=canonical_request(managed_operation(prepared, "upload", capture(value))),
            settle=canonical_request(managed_operation(prepared, "settle")),
        )
    elif case == "grant":
        grants = trust().model_dump()["key_grants"]
        grants[0]["valid_until"] = "2026-10-18T12:31:00Z"
        owner.publish_authority(next_snapshot(key_grants=grants), expected_generation=1)
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    late = context.Event()
    first = "register" if case == "capacity" else "bind"
    second = "register" if case == "capacity" else "admit"
    one, r1 = managed_start(context, private_root, packet, first, pause="locked", release=release)
    m1, m2 = [], []
    two = r2 = None
    before = snapshot(owner)
    try:
        while read_trace(r1, m1) != ("paused", "locked"):
            assert m1[-1][0] != "error"
        two, r2 = managed_start(
            context,
            private_root,
            other,
            second,
            now=RESERVATION
            if case == "reservation"
            else "2026-10-18T12:31:00Z"
            if case == "grant"
            else None,
            late=late,
        )
        while read_trace(r2, m2) != ("blocked", None):
            assert m2[-1][0] != "error"
        late.set()
        release.set()
        finish(one, r1, m1)
        one = None
        finish(two, r2, m2)
        two = None
    finally:
        release.set()
        for process, receive in ((one, r1), (two, r2)):
            if process is not None:
                if process.is_alive():
                    process.terminate()
                process.join(10)
                process.close()
                receive.close()
    assert not [v for k, v in m1 if k == "error"]
    errors = [v for k, v in m2 if k == "error"]
    assert len(errors) == 1 and errors[0][0] == (
        "SourceStoreConflict" if case == "capacity" else "SourceAuthenticationError"
    )
    assert not snapshot(owner)["source_content"]
    if case == "capacity":
        assert observe(reader(owner), parse_untrusted_request(other["prepare"])) is None
        assert len(snapshot(owner)["source_handoffs"]) == 1
    else:
        assert snapshot(owner) == before
