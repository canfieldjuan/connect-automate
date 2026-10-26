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
