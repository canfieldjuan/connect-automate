"""Joined caller-driven recovery, with real commits and spawn-process failures.

The signed pack has no actions. This lane qualifies custody/workflow recovery,
not unattended recovery, effect delivery or retention policy.
"""

import io
import json
import logging
import multiprocessing
import os
import re
import sqlite3
from contextlib import redirect_stderr, redirect_stdout
from uuid import uuid4

import pytest
from test_automate_runtime import _licensed_host
from test_lead_host_composition import setup as host_setup
from test_lead_runtime_results import lookup, submit
from test_lead_source_admission import counts
from test_lead_source_auth import NOW, envelope, resign
from test_lead_source_store import private_root, store
from test_workflow_receipt_lookup import rows

from connect_automate.automate import AdapterRegistry, PackRuntime
from connect_automate.automate.store import WorkflowStore
from connect_automate.lead_intake import SourceAdmission, SourceHandoffUnknown
from connect_automate.lead_intake.content import SourceContent

CRASH_EXIT = 81
BODY = envelope()["payload"]["snapshot"]["body"]["text"]
WRITE = re.compile(r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(\w+)", re.I)


@pytest.fixture
def make_case(tmp_path):
    sequence = 0

    def make(state="available"):
        nonlocal sequence
        root = tmp_path / f"case{sequence}"
        sequence += 1
        root.mkdir()
        source_root = private_root.__wrapped__(root)
        args, _, _ = host_setup.__wrapped__(root, source_root)
        PackRuntime.load(**args)  # Freeze binding configuration before the oracle.
        value = envelope()
        if state == "unavailable":
            value["payload"]["snapshot"]["body"] = dict(state=state, reason="source_gone")
        return dict(
            root=root,
            source_root=source_root,
            workflow_path=args["store"].path,
            args={
                name: value
                for name, value in args.items()
                if name not in {"store", "host", "registry", "source_admission", "source_clock"}
            },
            raw=resign(value),
        )

    return make


def open_runtime(case):
    """Reopen both owners; never initialize stores during recovery."""
    owner = store(case["source_root"])
    admission = SourceAdmission(owner, clock=lambda: NOW)
    workflow = WorkflowStore(case["workflow_path"])
    runtime = PackRuntime.load(
        **case["args"],
        store=workflow,
        host=_licensed_host(case["root"] / uuid4().hex),
        registry=AdapterRegistry.with_defaults(),
        source_admission=admission,
        source_clock=lambda: NOW,
    )
    return runtime, owner, admission, workflow


def _write_label(sql):
    match = WRITE.match(sql)
    return " ".join(match.groups()).upper() if match else None


def _child(case, target, fault, channel):
    # Load first: registration/setup commits cannot satisfy a submit checkpoint.
    runtime, owner, admission, _ = open_runtime(case)
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    original_connect = sqlite3.connect
    write_index = 0

    def checkpoint(name):
        channel.send(("checkpoint", name))
        if name != target:
            return
        channel.send(("logs", output.getvalue()))
        if fault == "crash":
            os._exit(CRASH_EXIT)
        raise sqlite3.OperationalError("synthetic workflow write failure")

    class ObservedConnection(sqlite3.Connection):
        role = None
        wrote = False

        def execute(self, sql, *args, **kwargs):
            nonlocal write_index
            start = len(self.trace)
            result = super().execute(sql, *args, **kwargs)
            label = _write_label(sql)
            if label:
                # Derive checkpoints from SQL actually executed, not mock calls.
                assert label in [_write_label(item) for item in self.trace[start:]]
                self.wrote = True
                if self.role == "workflow":
                    write_index += 1
                    channel.send(("write", label))
                    checkpoint(f"write-{write_index}")
            return result

        def commit(self):
            if self.wrote:
                checkpoint(f"{self.role}-before")
            super().commit()
            if self.wrote:
                checkpoint(f"{self.role}-after")
            self.wrote = False

    def connect(database, *args, **kwargs):
        if str(database) == owner.path.as_uri() + "?mode=rw":
            role = "source"
        elif str(database) == str(case["workflow_path"]):
            role = "workflow"
        else:
            return original_connect(database, *args, **kwargs)
        db = original_connect(database, *args, factory=ObservedConnection, **kwargs)
        db.role, db.trace = role, []
        db.set_trace_callback(db.trace.append)
        return db

    original_admit = admission.admit_source

    def admitted(raw):
        result = original_admit(raw)
        checkpoint("source-return")
        return result

    sqlite3.connect = connect
    admission.admit_source = admitted
    try:
        with redirect_stdout(output), redirect_stderr(output):
            try:
                result = submit(runtime, case["raw"])
            except SourceHandoffUnknown as exc:
                channel.send(("unknown", (exc.args, exc.__cause__, exc.__context__)))
            else:
                checkpoint("response-lost")
                channel.send(("result", result.model_dump(mode="json", by_alias=True)))
        channel.send(("logs", output.getvalue()))
    finally:
        sqlite3.connect = original_connect
        logging.getLogger().removeHandler(handler)
        channel.close()


def run_child(case, target=None, fault=None):
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    child = context.Process(target=_child, args=(case, target, fault, writer))
    messages = []
    child.start()
    writer.close()
    try:
        while True:
            assert reader.poll(40), "child failed to reach a checkpoint or close IPC"
            try:
                messages.append(reader.recv())
            except EOFError:
                break
        child.join(10)
        assert not child.is_alive(), "child did not exit after IPC closed"
        assert child.exitcode == (CRASH_EXIT if fault == "crash" else 0), messages
    finally:
        if child.is_alive():
            child.terminate()
        child.join(10)
        reader.close()
        writer.close()
        child.close()
    # All retained instrumentation is metadata. Raw SQL stays in child memory.
    assert BODY and BODY not in json.dumps(messages, default=str)
    print(json.dumps(dict(target=target, fault=fault, messages=messages), default=str))
    if target:
        assert ("checkpoint", target) in messages
    results = [value for kind, value in messages if kind == "result"]
    unknown = [value for kind, value in messages if kind == "unknown"]
    if fault == "crash":
        assert not results and not unknown
    elif fault == "sql":
        assert not results
        assert unknown == [(SourceHandoffUnknown().args, None, None)]
    else:
        assert len(results) == 1 and not unknown
    return messages, results[0] if results else None


def inspect(case):
    runtime, owner, admission, workflow = open_runtime(case)
    # Use the existing custody validator, not a second receipt implementation.
    with owner._transaction() as db:
        durable = db.execute(
            "SELECT admission_id, organization_id, namespace_id, event_id, receipt, "
            "envelope_sha256 FROM source_receipts"
        ).fetchall()
        receipts = [admission._existing(db, row)[0] for row in durable]
    for receipt in receipts:
        assert (
            SourceContent(owner, clock=lambda: NOW).read_content(receipt.admission_id)
            == (case["raw"])
        )
    found = lookup(runtime, case["raw"]).model_dump(mode="json", by_alias=True)
    durable_workflow = rows(workflow)
    assert BODY not in json.dumps([found, durable_workflow], default=str)
    assert durable_workflow["workflow_actions"] == []
    return counts(owner), receipts, found, durable_workflow


def assert_recovered(case, previous_receipts, previous_lookup, *, source_applied, workflow_applied):
    _, result = run_child(case)
    assert result["source_applied"] is source_applied
    assert result["workflow_applied"] is workflow_applied
    assert result["workflow_outcome"] == "accepted"
    assert (result["stage"], result["state_version"]) == ("ready", 2)
    if previous_receipts:
        for field, value in result["source_receipt"].items():
            assert value == getattr(previous_receipts[0], field)
    if previous_lookup["workflow_outcome"] == "accepted":
        for field in ("source_receipt", "workflow_record_id", "workflow_event_id", "stage"):
            assert result[field] == previous_lookup[field]
    count, receipts, found, persisted = inspect(case)
    assert count == (1, 1, 1) and len(receipts) == 1
    if previous_receipts:
        assert receipts == previous_receipts
    for field in ("source_receipt", "workflow_record_id", "workflow_event_id", "stage"):
        assert found[field] == result[field]
    assert len(persisted["workflow_records"]) == 1
    assert len(persisted["workflow_event_receipts"]) == 1
    assert len(persisted["workflow_events"]) == 2  # bootstrap + transition
    assert len(persisted["workflow_operations"]) == 1
    _, replay = run_child(case)
    assert replay == {**result, "source_applied": False, "workflow_applied": False}
    assert inspect(case) == (count, receipts, found, persisted)


@pytest.mark.parametrize("state", ["available", "unavailable"])
@pytest.mark.parametrize(
    "point",
    [
        "source-before",
        "source-after",
        "source-return",
        "workflow-before",
        "workflow-after",
        "response-lost",
    ],
)
def test_joined_crash_reopens_before_authenticated_replay(make_case, state, point):
    case = make_case(state)
    pristine = rows(WorkflowStore(case["workflow_path"]))
    run_child(case, point, "crash")
    count, receipts, found, persisted = inspect(case)
    source_committed = point != "source-before"
    workflow_committed = point in {"workflow-after", "response-lost"}
    assert count == ((1, 1, 1) if source_committed else (0, 0, 0))
    assert len(receipts) == int(source_committed)
    assert found["workflow_outcome"] == ("accepted" if workflow_committed else "not_found")
    if not workflow_committed:
        assert persisted == pristine
    assert_recovered(
        case,
        receipts,
        found,
        source_applied=not source_committed,
        workflow_applied=not workflow_committed,
    )


@pytest.mark.parametrize("fault", ["sql", "crash"])
def test_each_observed_workflow_write_rolls_back(make_case, fault):
    control = make_case()
    trace, result = run_child(control)
    assert result["source_applied"] and result["workflow_applied"]
    writes = [value for kind, value in trace if kind == "write"]
    assert {label.split()[-1] for label in writes} == {
        "WORKFLOW_RECORDS",
        "WORKFLOW_EVENTS",
        "WORKFLOW_OPERATIONS",
        "WORKFLOW_EVENT_RECEIPTS",
    }
    for index in range(1, len(writes) + 1):
        case = make_case()
        pristine = rows(WorkflowStore(case["workflow_path"]))
        observed, _ = run_child(case, f"write-{index}", fault)
        assert [value for kind, value in observed if kind == "write"] == writes[:index]
        count, receipts, found, persisted = inspect(case)
        assert count == (1, 1, 1) and len(receipts) == 1
        assert found["workflow_outcome"] == "not_found"
        assert persisted == pristine  # Includes every table, not only receipts.
        assert_recovered(
            case,
            receipts,
            found,
            source_applied=False,
            workflow_applied=True,
        )
