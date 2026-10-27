"""Native-process migration/observation proof, using the joined IPC protocol."""

import hashlib
import io
import logging
import multiprocessing
import os
import sqlite3
from contextlib import redirect_stderr, redirect_stdout

import pytest
from test_lead_custody_store import legacy, seed_legacy, snapshot
from test_lead_joined_recovery import read_trace
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake.source_store import (
    _CUSTODY_SCHEMA,
    _SCHEMA_V4,
    SourceStoreConflict,
    SourceStoreError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
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
    initial_now=None,
):
    from datetime import datetime

    from test_lead_custody_store import RESERVATION, reader
    from test_lead_source_auth import NOW

    from connect_automate.lead_intake.admission import SourceAdmission
    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.content import SourceContent
    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    owner = store(root, busy_timeout_ms=10000)
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
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
            pipe.send(("logs", output.getvalue()))
            if fault == "crash":
                pipe.send(("complete", None))
                os._exit(CRASH)
            raise sqlite3.OperationalError(packet.get("fault_text", "synthetic managed failure"))

    class Observed(sqlite3.Connection):
        blocked = False

        def execute(self, sql, *args, **kwargs):
            nonlocal writes
            if sql == "BEGIN IMMEDIATE":
                checkpoint("before-writer")
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

    def clock():
        sample = (
            datetime.fromisoformat(now)
            if now and (late is None or late.is_set())
            else datetime.fromisoformat(initial_now)
            if initial_now
            else NOW
        )
        pipe.send(("clock", sample.isoformat()))
        checkpoint("clock-sampled")
        return sample

    sqlite3.connect = connect
    with redirect_stdout(output), redirect_stderr(output):
        try:
            access = reader(
                owner,
                expected_incarnation=packet["incarnation"],
                clock=clock,
                max_handoffs=packet.get("max_handoffs", 10),
                max_mutation_records=packet.get("max_mutation_records", 30),
            )
            prepared = parse_untrusted_request(packet["prepare"])
            upload = parse_untrusted_request(packet["upload"])
            settle = parse_untrusted_request(packet["settle"])
            try:
                result = None
                if action == "register":
                    access.register_intent(prepared, reservation_expires_at=RESERVATION)
                elif action == "bind":
                    access.bind_upload(upload)
                elif action == "admit":
                    result = access.admit_bound(upload, packet["raw"])
                elif action == "close":
                    access.close_admission(settle)
                elif action == "legacy":
                    SourceAdmission(owner, clock=lambda: NOW).admit_source(packet["raw"])
                elif action == "purge":
                    SourceContent(owner, clock=lambda: NOW).purge_message(
                        prepared.payload.source,
                        cutoff=datetime.fromisoformat(packet["cutoff"])
                        if "cutoff" in packet
                        else NOW,
                    )
                elif action == "retire":
                    SourceContent(owner, clock=lambda: NOW).retire_namespace(
                        prepared.scope.namespace_id
                    )
                elif action == "resume":
                    result = access.revalidate_existing(
                        parse_untrusted_request(packet["resume"]),
                        packet["raw"],
                        admission_id=packet["admission_id"],
                    )
                elif action == "revoke":
                    authority = owner.read_authority()
                    grants = authority.model_dump()["key_grants"]
                    grants[0]["status"] = "revoked"
                    owner.publish_authority(
                        next_snapshot(authority, key_grants=grants),
                        expected_generation=authority.generation,
                    )
                elif action == "cleanup":
                    SourceContent(owner, clock=clock).cleanup_retired(
                        prepared.scope.namespace_id, limit=100
                    )
                elif action == "expire":
                    SourceContent(owner, clock=clock).cleanup_expired(limit=100)
                elif action == "read":
                    assert (
                        SourceContent(owner, clock=clock).read_content(packet["admission_id"])
                        == packet["raw"]
                    )
                elif action == "observe":
                    access.observe(
                        handoff_id=prepared.handoff_id,
                        scope=prepared.scope,
                        enrolled_machine_id=prepared.enrolled_machine_id,
                    )
                else:
                    raise AssertionError(action)
                checkpoint("response-lost")
                if result is not None:
                    pipe.send(
                        (
                            "receipt",
                            (result.receipt.admission_id, result.applied, result.content_state),
                        )
                    )
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
            pipe.send(("logs", output.getvalue()))
            pipe.send(("complete", None))
        finally:
            logging.getLogger().removeHandler(handler)
            pipe.close()


def managed_start(context, root, packet, action, **kwargs):
    receive, send = context.Pipe(duplex=False)
    process = context.Process(
        target=managed_child, args=(root, send, packet, action), kwargs=kwargs
    )
    process.start()
    send.close()
    return process, receive


def managed_packet(root, phase="bound", *, value=None):
    from test_lead_custody_store import RESERVATION, capture, managed_operation, managed_setup
    from test_lead_source_auth import encode, envelope

    from connect_automate.lead_intake.custody_protocol import canonical_request

    if phase == "closed":
        owner, packet, _ = closed_packet(root)
        return owner, packet
    if phase == "retired":
        owner, packet = managed_packet(root, "admitted", value=value)
        run_managed(root, packet, "retire")
        return owner, packet
    value = envelope() if value is None else value
    owner, access, prepared = managed_setup(root, value)
    upload = managed_operation(prepared, "upload", capture(value))
    settle = managed_operation(prepared, "settle")
    if phase != "empty":
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
    if phase in ("bound", "admitted"):
        access.bind_upload(upload)
    if phase == "admitted":
        access.admit_bound(upload, encode(value))
    return owner, dict(
        incarnation=owner.read_incarnation(),
        prepare=canonical_request(prepared),
        upload=canonical_request(upload),
        settle=canonical_request(settle),
        raw=encode(value),
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
        ("cleanup", "retired"),
        ("expire", "admitted"),
        ("resume", "closed"),
    ],
)
@pytest.mark.parametrize("fault", ["crash", "sql"])
def test_managed_every_write_and_commit(private_root, action, phase, fault):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    context = multiprocessing.get_context("spawn")
    baseline_root = native_directory(private_root, "baseline")
    _, packet = managed_packet(baseline_root, phase)
    options = dict(now="2026-10-18T12:30:01Z") if action == "resume" else {}
    if action == "expire":
        options["now"] = parse_untrusted_request(packet["upload"]).payload.capture.recovery_deadline
    process, receive = managed_start(context, baseline_root, packet, action, **options)
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
        packet["fault_text"] = packet["raw"].decode()
        process, receive = managed_start(
            context, root, packet, action, target=point, fault=fault, **options
        )
        messages = []
        finish(process, receive, messages, crashed=fault == "crash")
        managed_diagnostics(packet, messages)
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
            if action in ("close", "purge", "retire", "cleanup", "expire", "resume"):
                assert facts.closed
            if action == "cleanup":
                assert facts.ever_custodied and facts.receipt is None
                assert facts.content_state == "unknown"
                assert not any(
                    after[name] for name in ("source_content", "source_custody", "source_receipts")
                )
            if action == "expire":
                assert facts.content_state == "purged" and facts.receipt is not None
                assert not after["source_content"]
            if action == "resume":
                assert facts.content_state == "retained" and facts.receipt is not None
                assert after["source_handoff_operations"] == before["source_handoff_operations"]
                assert after["source_receipts"] == before["source_receipts"]
        errors = [v for k, v in messages if k == "error"]
        if fault == "sql":
            expected = SourceStoreUncertain if "commit" in point else SourceStoreUnavailable
            assert errors == [(expected.__name__, str(expected()), True, True)]
        process, receive = managed_start(context, root, packet, action, **options)
        retried = []
        finish(process, receive, retried)
        managed_outcome(packet, retried)
        if committed:
            assert snapshot(reopened) == after
        print(dict(action=action, point=point, fault=fault, committed=committed, writes=writes))


def ordered_managed(
    root,
    packet,
    first,
    second,
    *,
    other=None,
    second_options=None,
    first_options=None,
    before_release=None,
    pause="locked",
    wait_for_block=True,
):
    """Order real writers by IPC and SQLITE_BUSY; all cases use the same protocol."""
    context = multiprocessing.get_context("spawn")
    release = context.Event()
    one, r1 = managed_start(
        context,
        root,
        packet,
        first,
        pause=pause,
        release=release,
        **({} if first_options is None else first_options),
    )
    m1, m2 = [], []
    two = r2 = None
    try:
        while read_trace(r1, m1) != ("paused", pause):
            assert m1[-1][0] != "error"
        two, r2 = managed_start(
            context,
            root,
            packet if other is None else other,
            second,
            **({} if second_options is None else second_options),
        )
        if wait_for_block:
            while read_trace(r2, m2) != ("blocked", None):
                assert m2[-1][0] != "error"
        else:
            finish(two, r2, m2)
            two = None
        if before_release is not None:
            before_release()
        release.set()
        finish(one, r1, m1)
        one = None
        if two is not None:
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
    return m1, m2


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
    m1, m2 = ordered_managed(private_root, packet, first, second)
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
    late = context.Event()
    first = "register" if case == "capacity" else "bind"
    second = "register" if case == "capacity" else "admit"
    before = snapshot(owner)
    m1, m2 = ordered_managed(
        private_root,
        packet,
        first,
        second,
        other=other,
        second_options=dict(
            now=RESERVATION
            if case == "reservation"
            else "2026-10-18T12:31:00Z"
            if case == "grant"
            else None,
            late=late,
        ),
        before_release=late.set,
    )
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


def managed_diagnostics(packet, messages):
    """Assert fixed errors and captured diagnostics without exposing source content."""
    from test_lead_source_auth import envelope

    value = envelope()
    for secret in (
        value["payload"]["snapshot"]["body"]["text"],
        value["authorization"]["signature"],
        packet["raw"].decode(),
    ):
        assert secret not in repr(messages)
    logs = [v for k, v in messages if k == "logs"]
    assert logs and not any(logs), messages


def managed_outcome(packet, messages, error=None):
    managed_diagnostics(packet, messages)
    errors = [v for k, v in messages if k == "error"]
    assert errors == ([] if error is None else [(error.__name__, str(error()), True, True)]), (
        messages
    )
    assert bool([v for k, v in messages if k == "result"]) is (error is None)


def run_managed(root, packet, action, error=None, **options):
    process, receive = managed_start(
        multiprocessing.get_context("spawn"), root, packet, action, **options
    )
    messages = []
    finish(process, receive, messages)
    managed_outcome(packet, messages, error)
    return messages


@pytest.mark.parametrize(
    "first,second,phase",
    [
        ("bind", "purge", "prepared"),
        ("purge", "bind", "prepared"),
        ("admit", "retire", "bound"),
        ("retire", "admit", "bound"),
        ("close", "purge", "bound"),
        ("purge", "close", "bound"),
        ("close", "retire", "bound"),
        ("retire", "close", "bound"),
        ("register", "retire", "empty"),
        ("retire", "register", "empty"),
        ("admit", "revoke", "bound"),
        ("revoke", "admit", "bound"),
    ],
)
def test_managed_remaining_lifecycle_orders(private_root, first, second, phase):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    _, packet = managed_packet(private_root, phase)
    m1, m2 = ordered_managed(private_root, packet, first, second)
    refused = first in ("purge", "retire", "revoke")
    managed_outcome(packet, m1)
    managed_outcome(packet, m2, SourceAuthenticationError if refused else None)
    reopened = store(private_root)
    rows = snapshot(reopened)
    facts = observe(reader(reopened), parse_untrusted_request(packet["prepare"]))
    if (first, second) == ("retire", "register"):
        assert facts is None and not rows["source_handoffs"]
    else:
        assert facts is not None
        assert facts.closed is (
            (first, second) != ("purge", "bind") and "revoke" not in (first, second)
        )
        assert facts.ever_custodied is (first == "admit")
    assert len(rows["source_receipts"]) == len(rows["source_content"]) == (first == "admit")
    # Neither a restarted stale upload nor the unfenced entry point may reopen it.
    for action in ("admit", "legacy"):
        expected = (
            SourceStoreConflict
            if action == "admit" and facts is not None and facts.capture is None
            else SourceAuthenticationError
        )
        run_managed(private_root, packet, action, expected)
        assert snapshot(reopened) == rows
    print(dict(first=first, second=second, first_messages=m1, second_messages=m2))


@pytest.mark.parametrize("newer", [False, True], ids=["equal", "later"])
@pytest.mark.parametrize("first,second", [("purge", "bind"), ("bind", "purge")])
def test_managed_unbound_capture_horizon_orders(private_root, newer, first, second):
    from test_lead_custody_store import observe, reader
    from test_lead_source_auth import envelope, resign

    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    value = envelope()
    if newer:
        value["payload"]["snapshot"]["captured_at"] = "2026-10-18T12:00:01Z"
        value["payload"]["occurred_at"] = "2026-10-18T12:00:01Z"
        resign(value)
    _, packet = managed_packet(private_root, "prepared", value=value)
    packet["cutoff"] = "2026-10-18T12:00:00Z"
    m1, m2 = ordered_managed(private_root, packet, first, second)
    managed_outcome(packet, m1)
    managed_outcome(
        packet, m2, SourceAuthenticationError if first == "purge" and not newer else None
    )
    owner = store(private_root)
    facts = observe(reader(owner), parse_untrusted_request(packet["prepare"]))
    assert facts.closed is (first == "bind" and not newer)
    assert (facts.capture is None) is (first == "purge" and not newer)
    before = snapshot(owner)
    expected = (
        None if newer else SourceStoreConflict if first == "purge" else SourceAuthenticationError
    )
    run_managed(private_root, packet, "admit", expected)
    if newer:
        assert len(snapshot(owner)["source_receipts"]) == 1
    else:
        assert snapshot(owner) == before
    print(dict(newer=newer, first_messages=m1, second_messages=m2))


def test_managed_stalled_before_writer_observes_committed_close(private_root):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    _, packet = managed_packet(private_root)
    m1, m2 = ordered_managed(
        private_root, packet, "admit", "close", pause="before-writer", wait_for_block=False
    )
    managed_outcome(packet, m1, SourceAuthenticationError)
    managed_outcome(packet, m2)
    owner = store(private_root)
    facts = observe(reader(owner), parse_untrusted_request(packet["prepare"]))
    assert facts.closed and not facts.ever_custodied and facts.receipt is None
    assert not snapshot(owner)["source_content"]
    assert not [v for k, v in m1 if k == "write"]
    print(dict(stalled=m1, closer=m2))


@pytest.mark.parametrize("when", ["waiting", "final"])
@pytest.mark.parametrize("change", ["backward", "reservation", "grant"])
def test_managed_native_clock_changes_refuse_without_partial_rows(private_root, when, change):
    from test_lead_custody_store import RESERVATION
    from test_lead_source_auth import trust

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, packet = managed_packet(private_root)
    if change == "grant":
        grants = trust().model_dump()["key_grants"]
        grants[0]["valid_until"] = "2026-10-18T12:31:00Z"
        owner.publish_authority(next_snapshot(key_grants=grants), expected_generation=1)
    before = snapshot(owner)
    late = multiprocessing.get_context("spawn").Event()
    options = dict(
        late=late,
        initial_now="2026-10-18T12:30:02Z" if when == "final" else None,
        now=("2026-10-18T12:30:01Z" if when == "final" else "2026-10-18T12:29:59Z")
        if change == "backward"
        else RESERVATION
        if change == "reservation"
        else "2026-10-18T12:31:00Z",
    )
    if when == "waiting":
        m1, m2 = ordered_managed(
            private_root, packet, "bind", "admit", second_options=options, before_release=late.set
        )
        managed_outcome(packet, m1)
        rejected = m2
    else:
        # The first sample is already read when paused; move time before the final sample.
        # A metadata reader completes while the writer is paused, without affecting its rows.
        rejected, observed = ordered_managed(
            private_root,
            packet,
            "admit",
            "observe",
            first_options=options,
            pause="clock-sampled",
            wait_for_block=False,
            before_release=late.set,
        )
        managed_outcome(packet, observed)
    managed_outcome(packet, rejected, SourceAuthenticationError)
    assert snapshot(store(private_root)) == before
    assert bool([v for k, v in rejected if k == "write"]) is (when == "final")
    print(dict(when=when, change=change, rejected=rejected))


def closed_packet(root):
    from test_lead_custody_store import managed_operation, observe, reader

    from connect_automate.lead_intake.custody_protocol import (
        canonical_request,
        parse_untrusted_request,
    )

    owner, packet = managed_packet(root, "admitted")
    run_managed(root, packet, "close")
    prepared = parse_untrusted_request(packet["prepare"])
    facts = observe(reader(owner), prepared)
    packet.update(
        resume=canonical_request(
            managed_operation(
                prepared, "resume", facts.capture.model_dump(), facts.fence_generation
            )
        ),
        admission_id=facts.receipt.admission_id,
        max_handoffs=1,
        max_mutation_records=3,
    )
    return owner, packet, facts


@pytest.mark.parametrize(
    "case",
    [
        "retained",
        "stale-upload",
        "stale-resume",
        "wrong-receipt",
        "purge",
        "revoke",
        "expiry",
        "retired-cleanup",
    ],
)
def test_managed_closed_revalidation_after_restart(private_root, case):
    from uuid import uuid4

    from test_lead_custody_store import managed_operation, observe, reader

    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.custody_protocol import (
        canonical_request,
        parse_untrusted_request,
    )

    owner, packet, original = closed_packet(private_root)
    prepared = parse_untrusted_request(packet["prepare"])
    action, options = "resume", {}
    if case == "stale-upload":
        action = "admit"
    elif case == "stale-resume":
        packet["resume"] = canonical_request(
            managed_operation(prepared, "resume", original.capture.model_dump(), 1)
        )
    elif case == "wrong-receipt":
        packet["admission_id"] = str(uuid4())
    elif case in ("purge", "revoke"):
        run_managed(private_root, packet, case)
    elif case == "expiry":
        options["now"] = original.receipt.recovery_deadline
    elif case == "retired-cleanup":
        run_managed(private_root, packet, "retire")
        run_managed(private_root, packet, "cleanup")
    before = snapshot(store(private_root))
    messages = run_managed(
        private_root,
        packet,
        action,
        None if case == "retained" else SourceAuthenticationError,
        **options,
    )
    assert snapshot(store(private_root)) == before
    facts = observe(reader(store(private_root)), prepared)
    assert facts.closed and facts.ever_custodied
    if case == "retained":
        assert [v for k, v in messages if k == "receipt"] == [
            (original.receipt.admission_id, False, "retained")
        ]
        run_managed(private_root, packet, "read")
    elif case == "retired-cleanup":
        assert facts.receipt is None and facts.content_state == "unknown"
        for table in ("source_content", "source_receipts", "source_custody"):
            assert not before[table]
        for action in ("register", "bind", "admit", "legacy"):
            run_managed(private_root, packet, action, SourceAuthenticationError)
            assert snapshot(store(private_root)) == before
    else:
        assert facts.receipt == original.receipt
    if case == "expiry":
        from connect_automate.lead_intake.content import SourceContentUnavailable

        run_managed(private_root, packet, "read", SourceContentUnavailable, **options)
        expired = observe(reader(store(private_root)), prepared)
        assert expired.closed and expired.content_state == "purged"
        assert expired.receipt == original.receipt
        assert not snapshot(store(private_root))["source_content"]
        run_managed(private_root, packet, "resume", SourceAuthenticationError, **options)
    assert not [v for k, v in messages if k == "write"]
    print(dict(case=case, messages=messages))


def test_managed_snapshot_spans_native_closure_commit(private_root):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    owner, packet = managed_packet(private_root)
    prepared = parse_untrusted_request(packet["prepare"])
    with owner._read_snapshot() as db:
        before = owner._handoff_metadata(db, prepared.handoff_id)[0]
        run_managed(private_root, packet, "close")
        assert owner._handoff_metadata(db, prepared.handoff_id)[0] == before
        assert not before.closed
    after = observe(reader(store(private_root)), prepared)
    assert after.closed and after.fence_generation == before.fence_generation + 1
    assert after.state_revision == before.state_revision + 1


@pytest.mark.parametrize("action", ["register", "bind", "admit", "close", "resume", "observe"])
def test_managed_new_incarnation_refuses_restarted_old_packet(private_root, action):
    from test_lead_source_auth import trust

    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner, packet, _ = closed_packet(private_root)
    # Synthetic store only. Keep the old database; replace at the identical path/host/org.
    owner.path.rename(private_root / "preserved.sqlite3")
    owner.initialize(trust())
    assert owner.read_incarnation() != packet["incarnation"]
    before = snapshot(owner)
    run_managed(private_root, packet, action, SourceStoreConflict)
    assert snapshot(store(private_root)) == before


def test_managed_unknown_is_not_closed_empty_after_restart(private_root):
    from test_lead_custody_store import observe, reader

    from connect_automate.lead_intake.auth import SourceAuthenticationError
    from connect_automate.lead_intake.custody_protocol import parse_untrusted_request

    owner, packet = managed_packet(private_root, "empty")
    prepared = parse_untrusted_request(packet["prepare"])
    before = snapshot(owner)
    run_managed(private_root, packet, "close", SourceAuthenticationError)
    assert snapshot(store(private_root)) == before
    assert observe(reader(store(private_root)), prepared) is None
    run_managed(private_root, packet, "register")
    run_managed(private_root, packet, "close")
    closed = observe(reader(store(private_root)), prepared)
    assert closed.closed and not closed.ever_custodied and closed.receipt is None
    assert closed.content_state == "not_received"


@pytest.mark.parametrize("action,phase", [("admit", "bound"), ("resume", "closed")])
def test_managed_lost_response_publishes_no_receipt(private_root, action, phase):
    owner, packet = managed_packet(private_root, phase)
    process, receive = managed_start(
        multiprocessing.get_context("spawn"),
        private_root,
        packet,
        action,
        target="response-lost",
        fault="crash",
    )
    messages = []
    finish(process, receive, messages, crashed=True)
    assert ("checkpoint", "after-commit") in messages
    assert ("checkpoint", "response-lost") in messages
    assert not [v for k, v in messages if k in ("result", "receipt")]
    committed = snapshot(store(private_root))
    assert len(committed["source_receipts"]) == 1
    recovered = run_managed(private_root, packet, action)
    assert [v for k, v in recovered if k == "receipt"] == [
        (committed["source_receipts"][0][0], False, "retained")
    ]
    assert snapshot(store(private_root)) == committed
