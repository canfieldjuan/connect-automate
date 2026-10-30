"""Native source snapshots/restarts; reuse custody writer actors and state oracles."""

import multiprocessing
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict

import pytest
from test_lead_custody_races import CRASH, finish, managed_packet, managed_start
from test_lead_custody_status import status
from test_lead_custody_store import reader, snapshot
from test_lead_joined_recovery import read_trace
from test_lead_source_auth import NOW
from test_lead_source_store import private_root as private_root
from test_lead_source_store import store

from connect_automate.lead_intake.custody_protocol import canonical_request, parse_untrusted_request
from connect_automate.lead_intake.custody_store import SourceCustodyStore
from connect_automate.lead_intake.source_store import SourceStoreError


def inspect(access, request):
    try:
        found = access.observe_status(request=request)
        return None if found is None else asdict(found)
    except SourceStoreError as error:
        assert error.__context__ is None and error.__cause__ is None
        return type(error).__name__


def child(root, packet, channel, pause, release, fault):
    assert set(packet) == {"request", "incarnation"}  # No raw body, authority or live objects.
    owner = store(root)
    original = sqlite3.connect

    def checkpoint(name):
        channel.send(("checkpoint", name))
        if name != pause:
            return
        if fault == "crash":
            channel.send(("complete", None))
            os._exit(CRASH)
        if fault == "sql":
            raise sqlite3.OperationalError("SYNTHETIC-PRIVATE")
        channel.send(("paused", name))
        assert release.wait(30), "source reader not released"

    class Observed(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            pin = sql == "SELECT sql FROM sqlite_master LIMIT 1"
            if pin:
                checkpoint("pin-before")
            result = super().execute(sql, *args, **kwargs)
            if pin:
                checkpoint("pin-after")
            return result

        def close(self):
            checkpoint("release-before")
            super().close()
            checkpoint("release-after")

    def connect(path, *args, **kwargs):
        assert str(path) == owner.path.as_uri() + "?mode=ro"
        return original(path, *args, factory=Observed, **kwargs)

    def clock():
        checkpoint("clock")
        return NOW

    sqlite3.connect = connect
    try:
        access = SourceCustodyStore(
            owner,
            expected_incarnation=packet["incarnation"],
            clock=clock,
            max_handoffs=10,
            max_mutation_records=30,
            max_reservation_seconds=3600,
        )
        result = inspect(access, parse_untrusted_request(packet["request"]))
        checkpoint("response")
        channel.send(("result", result))
        channel.send(("complete", None))
    finally:
        channel.close()


@contextmanager
def reading(root, packet, point=None, fault=None):
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    release = context.Event()
    process = context.Process(target=child, args=(root, packet, send, point, release, fault))
    process.start()
    send.close()
    messages = []
    try:
        yield receive, release, messages
        closing = process
        process = None
        finish(closing, receive, messages, crashed=fault == "crash")
    finally:
        release.set()
        if process is not None:
            if process.is_alive():
                process.terminate()
            process.join(10)
            process.close()
            receive.close()


def references(packet, captured=True):
    prepared = parse_untrusted_request(packet["prepare"])
    upload = parse_untrusted_request(packet["upload"]) if captured else None
    return dict(
        request=canonical_request(status(prepared, upload)), incarnation=packet["incarnation"]
    )


def write(root, packet, action):
    process, channel = managed_start(multiprocessing.get_context("spawn"), root, packet, action)
    messages = []
    finish(process, channel, messages)
    assert ("result", action) in messages and not any(k == "error" for k, _ in messages)


@pytest.mark.parametrize(
    "action,phase",
    [
        ("bind", "prepared"),
        ("admit", "bound"),
        ("close", "admitted"),
        ("purge", "admitted"),
        ("retire", "admitted"),
        ("cleanup", "retired"),
        ("resume", "admitted"),
    ],
)
@pytest.mark.parametrize("point", ["pin-before", "pin-after", "clock", "release-after"])
def test_snapshot_orders(private_root, action, phase, point):
    owner, packet = managed_packet(private_root, phase)
    refs = references(packet, phase != "prepared")
    request = parse_untrusted_request(refs["request"])
    old = inspect(reader(owner, clock=lambda: NOW), request)
    if action == "resume":
        prepared = parse_untrusted_request(packet["prepare"])
        upload = parse_untrusted_request(packet["upload"])
        from test_lead_custody_store import managed_operation

        packet.update(
            resume=canonical_request(
                managed_operation(prepared, "resume", upload.payload.capture.model_dump())
            ),
            admission_id=old["admission_id"],
        )
    with reading(private_root, refs, point) as (channel, release, messages):
        while read_trace(channel, messages) != ("paused", point):
            assert messages[-1][0] != "error"
        write(private_root, packet, action)
        after_write = snapshot(owner)
        current = inspect(reader(owner, clock=lambda: NOW), request)
        release.set()
    expected = current if point == "pin-before" else old
    assert [v for k, v in messages if k == "result"] == [expected]
    for checkpoint in ("pin-before", "pin-after", "release-before", "release-after"):
        assert messages.count(("checkpoint", checkpoint)) == 1
    assert messages.count(("checkpoint", "clock")) == (expected != "SourceStoreConflict")
    assert snapshot(owner) == after_write
    with reading(private_root, refs) as (_, _, replay):
        pass
    assert [v for k, v in replay if k == "result"] == [current]
    print(dict(action=action, point=point, snapshot="new" if point == "pin-before" else "old"))


@pytest.mark.parametrize(
    "point,fault",
    [
        *(
            (p, "crash")
            for p in (
                "pin-before",
                "pin-after",
                "clock",
                "release-before",
                "release-after",
                "response",
            )
        ),
        *((p, "sql") for p in ("pin-before", "pin-after", "clock")),
    ],
)
def test_crash_failure_and_lost_response(private_root, point, fault):
    owner, packet = managed_packet(private_root, "admitted")
    refs = references(packet)
    before = snapshot(owner)
    expected = inspect(reader(owner, clock=lambda: NOW), parse_untrusted_request(refs["request"]))
    with reading(private_root, refs, point, fault) as (_, _, messages):
        pass
    assert ("checkpoint", point) in messages
    if fault == "sql":
        assert ("result", "SourceStoreUnavailable") in messages
    assert snapshot(owner) == before
    with reading(private_root, refs) as (_, _, replay):
        pass
    assert [v for k, v in replay if k == "result"] == [expected]
    assert snapshot(owner) == before
