"""Historical source projection at the workflow owner; no authenticated handoff."""

import hashlib
from dataclasses import FrozenInstanceError

import pytest
from test_automate_events import NOW, encoded
from test_automate_runtime import PACK_ID, SUBJECT
from test_lead_receipt_vocabulary import EVENT, KIND, OTHER, binding, configuration, event
from test_workflow_receipt_lookup import corrupt, rows

from connect_automate.automate.events import (
    MAX_EVENT_BYTES,
    EventBindingError,
    EventConflict,
    EventInputError,
    SourceBinding,
)
from connect_automate.automate.store import (
    WorkflowStore,
    WorkflowStoreError,
    _EventVersionConflict,
    request_fingerprint,
)


def configured_store(path):
    store = WorkflowStore(path)
    store.initialize()
    store.register_bindings(SUBJECT, PACK_ID, configuration())
    return store


def lookup_args(**updates):
    return {
        "subject": SUBJECT,
        "pack_id": PACK_ID,
        "pack_version": 1,
        "binding": "inbox",
        "source": SourceBinding(**binding()),
        "event_id": EVENT,
        "expected_payload_digest": event()["source_receipt"]["payload_digest"],
        **updates,
    }


def seed(store, *, matched=True, value=None):
    value = event() if value is None else value
    return store.admit_event(
        subject=SUBJECT,
        pack_id=PACK_ID,
        pack_version=1,
        binding="inbox",
        source_id=binding()["source_id"],
        source_kind=KIND,
        occurrence=value["source_receipt"]["event_id"],
        payload=encoded(value),
        workflow="receipt-proof",
        initial_stage="waiting",
        allowed_stages=frozenset({"waiting", "ready", "completed"}),
        allowed_action_kinds=frozenset(),
        now=NOW,
        select=lambda: (
            ("intake", [{"kind": "record.transition", "to_stage": "ready"}], [])
            if matched
            else None
        ),
    )


@pytest.mark.parametrize("matched", [True, False])
def test_source_projection_retains_receipt_and_original_outcome(tmp_path, matched):
    store = configured_store(tmp_path / "workflow.db")
    intake = seed(store, matched=matched)
    result = WorkflowStore(store.path).lookup_source_event(**lookup_args())
    assert result.source_receipt.model_dump(mode="json") == event()["source_receipt"]
    assert result.outcome.matched is matched and result.outcome.applied is False
    assert result.outcome.record == intake.record
    assert result.outcome.event_id == intake.event_id
    assert store.lookup_source_event(**lookup_args(event_id=OTHER)) is None


def test_original_outcome_is_immutable_after_advancement(tmp_path):
    store = configured_store(tmp_path / "workflow.db")
    intake = seed(store)
    store.apply_effects(
        intake.record.record_id,
        [{"kind": "record.transition", "to_stage": "completed"}],
        operation_key="later",
        operation_name="operator.decision",
        request={},
        expected_version=2,
        now=NOW,
        allowed_stages=frozenset({"waiting", "ready", "completed"}),
    )
    result = WorkflowStore(store.path).lookup_source_event(**lookup_args())
    assert result.outcome.record == intake.record
    assert store.get_record(intake.record.record_id).stage == "completed"
    with pytest.raises(FrozenInstanceError):
        result.outcome = None
    with pytest.raises(FrozenInstanceError):
        result.outcome.matched = False
    with pytest.raises(FrozenInstanceError):
        result.outcome.record.stage = "invented"
    with pytest.raises(ValueError, match="frozen"):
        result.source_receipt.payload_digest = "b" * 64
    assert store.lookup_source_event(**lookup_args()) == result


@pytest.mark.parametrize("matched", [False, True])
def test_digest_domains_are_independently_required(tmp_path, matched):
    store = configured_store(tmp_path / "workflow.db")
    seed(store, matched=matched)
    source_digest = event()["source_receipt"]["payload_digest"]
    workflow_digest = hashlib.sha256(encoded(event())).hexdigest()
    assert workflow_digest != source_digest
    expected = store.lookup_source_event(**lookup_args())
    generic_args = dict(
        subject=SUBJECT,
        pack_id=PACK_ID,
        pack_version=1,
        binding="inbox",
        source_id=binding()["source_id"],
        source_kind=KIND,
        occurrence=EVENT,
    )
    assert (
        store.lookup_event(**generic_args, expected_payload_digest=workflow_digest)
        == expected.outcome
    )
    for wrong in [workflow_digest, "b" * 64]:
        with pytest.raises(EventConflict):
            store.lookup_source_event(**lookup_args(expected_payload_digest=wrong))
    with pytest.raises(EventConflict):
        store.lookup_event(**generic_args, expected_payload_digest=source_digest)
    # Matching the source digest cannot compensate for a broken workflow fingerprint.
    corrupt(store, "workflow_event_receipts", "fingerprint=?", (source_digest,))
    with pytest.raises(WorkflowStoreError, match="^invalid event receipt payload$"):
        store.lookup_source_event(**lookup_args())


@pytest.mark.parametrize("field", ["subject", "pack_id", "binding"])
@pytest.mark.parametrize("value", [None, "", False, 0, [], b"bytes"])
def test_input_identity_before_open(tmp_path, monkeypatch, field, value):
    store = WorkflowStore(tmp_path / "missing.db")
    monkeypatch.setattr(store, "read_connection", lambda: pytest.fail("opened store"))
    with pytest.raises(EventInputError):
        store.lookup_source_event(**lookup_args(**{field: value}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("pack_version", None),
        ("pack_version", False),
        ("pack_version", True),
        ("pack_version", 0),
        ("pack_version", -1),
        ("pack_version", "1"),
        ("pack_version", 1.0),
        ("expected_payload_digest", None),
        ("expected_payload_digest", False),
        ("expected_payload_digest", 0),
        ("expected_payload_digest", ""),
        ("expected_payload_digest", "a" * 63),
        ("expected_payload_digest", "a" * 65),
        ("expected_payload_digest", "A" * 64),
        ("expected_payload_digest", "g" * 64),
        ("event_id", None),
        ("event_id", False),
        ("event_id", 0),
        ("event_id", ""),
        ("event_id", "not-a-uuid"),
        ("event_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa".upper()),
        ("source", None),
        ("source", False),
        ("source", {}),
        ("source", binding()),
        ("source", SourceBinding(source_id=OTHER, source_kind="mail.received", scope="mailbox")),
        ("source", SourceBinding.model_construct(**{**binding(), "scope": "corrupt"})),
        ("source", SourceBinding(**binding()).model_copy(update={"source_id": OTHER})),
    ],
)
def test_source_lookup_inputs_fail_closed_before_open(tmp_path, monkeypatch, field, value):
    store = WorkflowStore(tmp_path / "missing.db")
    monkeypatch.setattr(store, "read_connection", lambda: pytest.fail("opened store"))
    with pytest.raises(EventInputError) as caught:
        store.lookup_source_event(**lookup_args(**{field: value}))
    assert caught.value.__context__ is None and caught.value.__cause__ is None


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize(
    "field", ["subject", "pack_id", "binding", "host_id", "organization_id", "namespace_id"]
)
def test_scope_denial_precedes_absence(tmp_path, present, field):
    store = configured_store(tmp_path / "workflow.db")
    if present:
        seed(store)
    args = lookup_args()
    if field in ("subject", "pack_id", "binding"):
        args[field] = OTHER
    else:
        args["source"] = SourceBinding(**binding(**{field: OTHER}))
    with pytest.raises(EventBindingError):
        store.lookup_source_event(**args)


@pytest.mark.parametrize("matched", [False, True])
def test_pack_revision_is_not_absence(tmp_path, matched):
    store = configured_store(tmp_path / "workflow.db")
    seed(store, matched=matched)
    with pytest.raises(_EventVersionConflict):
        store.lookup_source_event(**lookup_args(pack_version=2))


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("fault", ["snapshot", "snapshot-shape", "policy"])
def test_persisted_configuration_is_checked_before_absence(tmp_path, present, fault):
    store = configured_store(tmp_path / "workflow.db")
    if present:
        seed(store)
    changed = configuration()
    if fault == "policy":
        changed["inbox"]["policy"] = {"schema_version": "2.0"}
        corrupt(
            store,
            "workflow_source_bindings",
            "policy=?",
            (encoded(changed["inbox"]["policy"]).decode(),),
        )
    elif fault == "snapshot":
        changed["inbox"]["scope"] = "different"
    else:
        changed = []
    corrupt(store, "workflow_binding_sets", "bindings_json=?", (encoded(changed).decode(),))
    with pytest.raises(EventBindingError):
        store.lookup_source_event(**lookup_args())


@pytest.mark.parametrize("entry", ["lookup", "register"])
@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize(
    "fault",
    ["same", "foreign", "invalid", "generic", "snapshot-only", "missing-snapshot"],
)
def test_complete_binding_snapshot_required(tmp_path, entry, present, fault):
    store = configured_store(tmp_path / "workflow.db")
    if present:
        seed(store)
    changed = configuration()
    ghost = configuration(namespace_id=OTHER)["inbox"]
    if fault == "foreign":
        ghost = configuration(host_id=OTHER, namespace_id=OTHER)["inbox"]
    elif fault == "invalid":
        ghost = None
    elif fault == "generic":
        ghost = dict(source_kind="mail.received", source_id=OTHER, scope="mail", policy={})
    if fault == "missing-snapshot":
        corrupt(store, "workflow_binding_sets", delete=True)
    elif fault == "snapshot-only":
        # A different subject/pack has only a snapshot: no lead row can discover it.
        with store.connection() as db:
            db.execute(
                "INSERT INTO workflow_binding_sets VALUES (?, ?, ?)",
                ("ghost-subject", OTHER, encoded({"ghost": ghost}).decode()),
            )
    else:
        changed["ghost"] = ghost
        corrupt(store, "workflow_binding_sets", "bindings_json=?", (encoded(changed).decode(),))
    before = rows(store)
    reopened = WorkflowStore(store.path)
    with pytest.raises(EventBindingError):
        if entry == "lookup":
            reopened.lookup_source_event(**lookup_args())
        else:
            reopened.register_bindings("new-subject", OTHER, configuration(namespace_id=EVENT))
    assert rows(store) == before


def test_complete_binding_snapshots_accept_mixed_and_empty_sets(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    mixed = configuration()
    mixed["mail"] = dict(source_kind="mail.received", source_id=EVENT, scope="mail", policy={})
    mixed["second"] = configuration(namespace_id=OTHER)["inbox"]
    store.register_bindings(SUBJECT, PACK_ID, mixed)
    store.register_bindings("other-subject", OTHER, configuration(namespace_id=EVENT))
    store.register_bindings("empty-subject", OTHER, {})
    store.register_bindings("generic-subject", OTHER, {"mail": mixed["mail"]})
    reopened = WorkflowStore(store.path)
    reopened.register_bindings(SUBJECT, PACK_ID, mixed)
    assert reopened.lookup_source_event(**lookup_args()) is None
    original = seed(reopened)
    result = reopened.lookup_source_event(**lookup_args())
    assert result.outcome.record == original.record


@pytest.mark.parametrize("matched", [False, True])
@pytest.mark.parametrize("field", ["host_id", "organization_id", "namespace_id"])
def test_embedded_scope_corruption_isolated(tmp_path, matched, field):
    store = configured_store(tmp_path / "workflow.db")
    seed(store, matched=matched)
    changed = event()
    changed["source_receipt"][field] = OTHER
    raw = encoded(changed)
    corrupt(
        store,
        "workflow_event_receipts",
        "payload=?,fingerprint=?",
        (raw.decode(), hashlib.sha256(raw).hexdigest()),
    )
    if matched:
        corrupt(store, "workflow_events", "request_fingerprint=?", (request_fingerprint(changed),))
    # All row digests and record ownership agree: only deployment binding can reject.
    with pytest.raises(WorkflowStoreError, match="^invalid source receipt scope$"):
        store.lookup_source_event(**lookup_args())


@pytest.mark.parametrize("matched", [False, True])
@pytest.mark.parametrize(
    "fault", ["malformed", "noncanonical", "oversize", "occurrence", "kind", "interval", "extra"]
)
def test_canonical_source_projection_is_validated(tmp_path, matched, fault):
    store = configured_store(tmp_path / "workflow.db")
    seed(store, matched=matched)
    changed = event()
    if fault == "occurrence":
        changed["source_receipt"]["event_id"] = OTHER
    elif fault == "kind":
        changed = {
            "source_kind": "mail.received",
            "message_id": EVENT,
            "received_at": "2026-01-01T00:00:00Z",
            "sender": "sender@example.invalid",
            "subject": "",
        }
    elif fault == "interval":
        changed["source_receipt"]["recovery_deadline"] = "2026-01-01T00:00:00Z"
    elif fault == "extra":
        changed["source_receipt"]["body"] = "private-sentinel"
    raw = encoded(changed)
    if fault == "malformed":
        raw = b'{"private-sentinel":'
    elif fault == "noncanonical":
        raw += b" "
    elif fault == "oversize":
        raw += b" " * MAX_EVENT_BYTES
    corrupt(
        store,
        "workflow_event_receipts",
        "payload=?,fingerprint=?",
        (raw.decode(), hashlib.sha256(raw).hexdigest()),
    )
    if matched and fault != "malformed":
        corrupt(store, "workflow_events", "request_fingerprint=?", (request_fingerprint(changed),))
    with pytest.raises(WorkflowStoreError, match="^invalid event receipt payload$") as caught:
        store.lookup_source_event(**lookup_args())
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "private-sentinel" not in str(caught.value)


@pytest.mark.parametrize(
    "table,assignment,value",
    [
        ("workflow_event_receipts", "record_id=?", None),
        ("workflow_event_receipts", "event_id=?", None),
        ("workflow_event_receipts", "record_id=?", "missing"),
        ("workflow_event_receipts", "event_id=?", "missing"),
        ("workflow_events", "record_id=?", "different"),
        ("workflow_events", "operation_key=?", "different"),
        ("workflow_events", "operation_name=?", "different"),
        ("workflow_events", "request_fingerprint=?", "0" * 64),
        ("workflow_records", "pack_id=?", "different"),
        ("workflow_records", "pack_version=?", 2),
    ],
)
def test_source_lookup_preserves_shared_ownership_guards(tmp_path, table, assignment, value):
    store = configured_store(tmp_path / "workflow.db")
    seed(store)
    corrupt(store, table, assignment, (value,))
    with pytest.raises(WorkflowStoreError, match="^invalid event receipt ownership$"):
        store.lookup_source_event(**lookup_args())


def test_receipt_binding_conflict_is_not_absence(tmp_path):
    store = configured_store(tmp_path / "workflow.db")
    seed(store, matched=False)
    corrupt(store, "workflow_event_receipts", "binding=?", ("different",))
    with pytest.raises(EventConflict):
        store.lookup_source_event(**lookup_args())


def test_historical_read_has_no_writer_dispatch_source_or_clock_access(tmp_path, monkeypatch):
    from connect_automate.automate.actions import ActionRunner
    from connect_automate.lead_intake.admission import SourceAdmission
    from connect_automate.lead_intake.source_store import SourceStore

    store = configured_store(tmp_path / "workflow.db")
    seed(store)
    before = rows(store)

    def forbidden(*args, **kwargs):
        pytest.fail("historical read crossed a write or source boundary")

    monkeypatch.setattr(store, "connection", forbidden)
    monkeypatch.setattr(store, "admit_event", forbidden)
    monkeypatch.setattr(ActionRunner, "dispatch", forbidden)
    monkeypatch.setattr(SourceAdmission, "admit_source", forbidden)
    monkeypatch.setattr(SourceStore, "_transaction", forbidden)
    monkeypatch.setattr(SourceStore, "_record_clock", forbidden)
    assert store.lookup_source_event(**lookup_args()) is not None
    assert store.lookup_source_event(**lookup_args(event_id=OTHER)) is None
    assert rows(store) == before


def _commit_source_event(path, queue):
    outcome = seed(WorkflowStore(path))
    queue.put(outcome.event_id)


def test_source_lookup_snapshot_during_separate_process_commit(tmp_path, monkeypatch):
    import multiprocessing
    from contextlib import contextmanager

    store = configured_store(tmp_path / "workflow.db")
    native = store.read_connection
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    writer = ctx.Process(target=_commit_source_event, args=(store.path, queue))
    committed = []

    @contextmanager
    def concurrent_read():
        with native() as db:
            writer.start()
            committed.append(queue.get(timeout=30))
            writer.join(timeout=30)
            assert writer.exitcode == 0
            yield db

    try:
        with monkeypatch.context() as patch:
            patch.setattr(store, "read_connection", concurrent_read)
            assert store.lookup_source_event(**lookup_args()) is None
        result = WorkflowStore(store.path).lookup_source_event(**lookup_args())
        assert result.outcome.event_id == committed[0]
    finally:
        if writer.is_alive():
            writer.terminate()
            writer.join(timeout=30)
        queue.close()
        queue.join_thread()


def test_multiple_namespaces_and_absence_keep_their_identity(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    second = SourceBinding(**binding(namespace_id=OTHER))
    configs = configuration()
    configs["second"] = {**second.model_dump(), "policy": {"schema_version": "1.0"}}
    store.register_bindings(SUBJECT, PACK_ID, configs)
    first = seed(store)
    # Same event id in another configured namespace is valid scoped absence.
    assert store.lookup_source_event(**lookup_args(source=second, binding="second")) is None
    assert store.lookup_source_event(**lookup_args()).outcome.record == first.record
