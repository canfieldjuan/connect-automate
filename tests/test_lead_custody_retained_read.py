"""R3.2 bound reads through the existing source writer; synthetic content only."""

import multiprocessing
import os
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import test_lead_custody_races as races
from test_lead_custody_races import (
    CRASH,
    finish,
    managed_outcome,
    managed_packet,
    ordered_managed,
)
from test_lead_custody_store import (
    RESERVATION,
    managed_operation,
    managed_request,
    observe,
    reader,
    rewrite_request,
    snapshot,
    upload_setup,
)
from test_lead_source_admission import tamper
from test_lead_source_auth import NOW, OTHER, encode, envelope, resign, trust
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake.admission import SourceAdmission
from connect_automate.lead_intake.auth import SourceAuthenticationError
from connect_automate.lead_intake.content import SourceContent, SourceContentUnavailable
from connect_automate.lead_intake.custody_protocol import (
    ResumeRequest,
    canonical_request,
    parse_untrusted_request,
)
from connect_automate.lead_intake.source_store import (
    SourceClockAdmin,
    SourceStoreBusy,
    SourceStoreConflict,
    SourceStoreInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
)


def resumed(prepared, upload, generation=1):
    return managed_operation(prepared, "resume", upload.payload.capture.model_dump(), generation)


def envelope_probe(monkeypatch, *, forbidden=False):
    """Stop at the first actual envelope access, including content validation."""
    original = sqlite3.connect
    seen = []

    class Observed(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql.startswith("SELECT envelope FROM source_content"):
                assert self.in_transaction
                seen.append(sql)
                assert not forbidden, "bound checks reached forbidden envelope access"
            return super().execute(sql, *args, **kwargs)

    def connect(*args, **kwargs):
        return original(*args, factory=Observed, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
    return seen


def test_read_retained_returns_original_bytes(private_root):
    owner, access, prepared, upload, raw, admitted = upload_setup(private_root, admit=True)
    request = managed_operation(prepared, "resume", upload.payload.capture.model_dump())
    assert access.read_retained(request) == raw


@pytest.mark.parametrize("state", ["complete", "truncated", "unknown", "unavailable"])
@pytest.mark.parametrize("closed", [False, True])
def test_reopen_body_states_and_repeated_reads(private_root, state, closed):
    value = envelope()
    body = value["payload"]["snapshot"]["body"]
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = {"state": state, "reason": "source_gone"}
    else:
        body["completeness"] = state
        if state == "truncated":
            body["source_chars"] = body["stored_chars"] + 1
        elif state == "unknown":
            body["source_chars"] = None
    resign(value)
    owner, access, prepared, upload, raw, result = upload_setup(
        private_root, admit=True, value=value
    )
    if closed:
        access.close_admission(managed_operation(prepared, "settle"))
    # Reservation expiry alone must not suppress still-live retained content.
    request = resumed(prepared, upload, 2 if closed else 1)
    before = snapshot(owner)
    reopened = reader(store(private_root), clock=lambda: datetime.fromisoformat(RESERVATION))
    assert reopened.read_retained(request) == raw
    assert reopened.read_retained(request) == raw
    after = snapshot(owner)
    assert {k: v for k, v in after.items() if k != "authority_clock_history"} == {
        k: v for k, v in before.items() if k != "authority_clock_history"
    }
    assert (
        SourceContent(owner, clock=lambda: datetime.fromisoformat(RESERVATION)).read_content(
            result.receipt.admission_id
        )
        == raw
    )


BINDINGS = [
    *((["scope", f], OTHER) for f in ("host_id", "organization_id", "namespace_id", "event_id")),
    (["scope", "route_digest"], "0" * 64),
    (["enrolled_machine_id"], OTHER),
    *(
        (["payload", "capture", f], v)
        for f, v in (
            ("envelope_sha256", "0" * 64),
            ("payload_digest", "0" * 64),
            ("snapshot_id", OTHER),
            ("captured_at", "2026-10-18T12:00:01Z"),
            ("recovery_deadline", "2026-10-18T13:00:01Z"),
            ("artifact_size", 1),
        )
    ),
]


@pytest.mark.parametrize("path,value", BINDINGS, ids=[p[-1] for p, _ in BINDINGS])
def test_each_binding_before_first_envelope(private_root, monkeypatch, path, value):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = rewrite_request(resumed(prepared, upload), path, value)
    before = snapshot(owner)
    seen = envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(SourceStoreConflict):
        access.read_retained(request)
    assert seen == [] and snapshot(owner) == before


@pytest.mark.parametrize("case", ["incarnation", "generation", "handoff"])
def test_read_owner_checks_before_envelope(private_root, monkeypatch, case):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = resumed(prepared, upload)
    expected = SourceStoreConflict
    if case == "incarnation":
        access = reader(owner, expected_incarnation=OTHER, clock=lambda: NOW)
    elif case == "generation":
        request = request.model_copy(update={"expected_fence_generation": 2})
        expected = SourceAuthenticationError
    else:
        request = request.model_copy(update={"handoff_id": OTHER})
        expected = SourceContentUnavailable
    seen = envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(expected):
        access.read_retained(request)
    assert seen == []


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_deployment_guard_independent_of_later_scope_guard(private_root, monkeypatch, field):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = rewrite_request(resumed(prepared, upload), ["scope", field], OTHER)

    def forbidden(*args):
        pytest.fail("deployment mismatch reached metadata observation")

    monkeypatch.setattr(owner, "_observe_custody", forbidden)
    envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(SourceStoreConflict):
        access.read_retained(request)


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_scope_guard_independent_of_deployment_guard(private_root, monkeypatch, field):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = rewrite_request(resumed(prepared, upload), ["scope", field], OTHER)
    # Remove only the earlier deployment comparison, retaining the real metadata
    # owner under the actual read writer, so it cannot mask a missing scope field.
    monkeypatch.setattr(
        owner,
        "_custody_request_state",
        lambda db, req: owner._observe_custody(
            db, req.handoff_id, req.scope, req.enrolled_machine_id, req.payload.capture
        ),
    )
    envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(SourceStoreConflict):
        access.read_retained(request)


@pytest.mark.parametrize("field", ["ever_custodied", "receipt", "content_state"])
def test_retained_link_guard_independent(private_root, monkeypatch, field):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    facts = observe(access, prepared)
    changed = {"ever_custodied": False, "receipt": None, "content_state": "purged"}[field]
    # Isolate each read-owner precondition from upstream consistency validators.
    monkeypatch.setattr(
        owner, "_custody_request_state", lambda db, req: replace(facts, **{field: changed})
    )
    envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(SourceContentUnavailable):
        access.read_retained(resumed(prepared, upload))


@pytest.mark.parametrize(
    "case", ["unregistered", "bound", "closed-empty", "purged", "retired", "erased"]
)
def test_absence_and_terminal_lifecycle(private_root, monkeypatch, case):
    owner, access, prepared, upload, _, _ = upload_setup(
        private_root, admit=case in ("purged", "retired", "erased")
    )
    generation = 1
    if case == "unregistered":
        prepared = prepared.model_copy(update={"handoff_id": str(uuid4())})
    elif case == "closed-empty":
        access.close_admission(managed_operation(prepared, "settle"))
        generation = 2
    elif case in ("purged", "retired", "erased"):
        content = SourceContent(owner, clock=lambda: NOW)
        if case == "purged":
            content.purge_message(prepared.payload.source, cutoff=NOW)
        else:
            content.retire_namespace(prepared.scope.namespace_id)
            if case == "erased":
                content.cleanup_retired(prepared.scope.namespace_id, limit=100)
        generation = 2
    before = snapshot(owner)
    envelope_probe(monkeypatch, forbidden=True)
    with pytest.raises(SourceContentUnavailable):
        access.read_retained(resumed(prepared, upload, generation))
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "case",
    ["dict", "wrong-operation", "missing-capture", "partial-scope", "bad-proof", "mixed-capture"],
)
def test_invalid_input_before_writer(private_root, monkeypatch, case):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = resumed(prepared, upload)
    if case == "dict":
        request = request.model_dump()
    elif case == "wrong-operation":
        request = upload
    else:
        field, value = {
            "missing-capture": ("payload", {"capture": None}),
            "partial-scope": ("scope", {"host_id": owner.host_id}),
            "bad-proof": ("proof_reference", "private-marker"),
            "mixed-capture": (
                "payload",
                {"capture": {**request.payload.capture.model_dump(), "extra": 1}},
            ),
        }[case]
        request = request.model_copy(update={field: value})

    def forbidden(*args):
        pytest.fail("invalid input reached writer")

    monkeypatch.setattr(owner, "_transaction", forbidden)
    with pytest.raises(SourceStoreInputError):
        access.read_retained(request)


@pytest.mark.parametrize("field", ["expected_fence_generation", "artifact_size"])
@pytest.mark.parametrize(
    "bad", [0, "", False, -1, 2147483648], ids=["zero", "empty", "false", "negative", "over-max"]
)
def test_copied_scalar_boundaries_before_writer(private_root, monkeypatch, field, bad):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = resumed(prepared, upload)
    data = request.model_dump()
    if field == "artifact_size":
        data["payload"]["capture"][field] = bad
    else:
        data[field] = bad
    copied = ResumeRequest.model_construct(**data)
    monkeypatch.setattr(owner, "_transaction", lambda: pytest.fail("invalid scalar reached writer"))
    with pytest.raises(SourceStoreInputError):
        access.read_retained(copied)


def test_canonical_request_consumed_and_fresh_control_refs_allowed(private_root, monkeypatch):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root, admit=True)
    request = resumed(prepared, upload)
    data = request.model_dump()
    for field in ("control_id", "job_id", "proof_reference"):
        data[field] = str(uuid4())
    copied = ResumeRequest.model_construct(**data)
    original = owner._custody_request_state

    def checked(db, canonical):
        assert db.in_transaction and canonical is not copied
        assert canonical == parse_untrusted_request(encode(data))
        return original(db, canonical)

    monkeypatch.setattr(owner, "_custody_request_state", checked)
    assert access.read_retained(copied) == raw


def test_missing_clock_refuses_before_writer(private_root, monkeypatch):
    owner, _, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    access = reader(owner)
    monkeypatch.setattr(owner, "_transaction", lambda: pytest.fail("missing clock reached writer"))
    with pytest.raises(SourceStoreInputError):
        access.read_retained(resumed(prepared, upload))


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_fence_generation", 2147483647),
        ("artifact_size", 1),
        ("artifact_size", 2097152),
    ],
)
def test_valid_scalar_boundaries_reach_binding_owner(private_root, field, value):
    _, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    path = [field] if field == "expected_fence_generation" else ["payload", "capture", field]
    request = rewrite_request(resumed(prepared, upload), path, value)
    expected = (
        SourceAuthenticationError if field == "expected_fence_generation" else SourceStoreConflict
    )
    with pytest.raises(expected):
        access.read_retained(request)


def test_writer_timeout_returns_no_content(private_root, monkeypatch):
    owner, _, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    access = reader(store(private_root, busy_timeout_ms=25), clock=lambda: NOW)
    envelope_probe(monkeypatch, forbidden=True)
    with owner._transaction(), pytest.raises(SourceStoreBusy) as failure:
        access.read_retained(resumed(prepared, upload))
    assert failure.value.__context__ is None and failure.value.__cause__ is None


def test_revoked_key_read_is_not_submission_authority(private_root):
    owner, access, prepared, upload, raw, admitted = upload_setup(private_root, admit=True)
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    request = resumed(prepared, upload)
    assert access.read_retained(request) == raw
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        access.revalidate_existing(request, raw, admission_id=admitted.receipt.admission_id)
    assert snapshot(owner) == before


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("final_only", [False, True])
def test_deadline_and_terminal_expiry(private_root, offset, final_only):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root, admit=True)
    request = resumed(prepared, upload)
    deadline = datetime.fromisoformat(request.payload.capture.recovery_deadline)
    at = deadline + timedelta(microseconds=offset)
    times = iter([NOW if final_only else at, at])
    access = reader(owner, clock=times.__next__)
    if offset < 0:
        assert access.read_retained(request) == raw
        return
    with pytest.raises(SourceContentUnavailable):
        access.read_retained(request)
    facts = observe(reader(store(private_root)), prepared)
    assert facts.closed and facts.fence_generation == 2 and facts.content_state == "purged"
    admin = SourceClockAdmin(owner)
    admin.reconcile(
        operation_id=str(uuid4()), expected_sequence=admin.read().sequence, corrected_at=NOW
    )
    with pytest.raises(SourceContentUnavailable):
        reader(store(private_root), clock=lambda: NOW).read_retained(resumed(prepared, upload, 2))
    assert snapshot(owner)["source_content"] == []


@pytest.mark.parametrize("when", ["first", "final"])
def test_backward_clock_rolls_back(private_root, when):
    owner, _, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    times = iter(
        [NOW if when == "final" else NOW - timedelta(seconds=1), NOW - timedelta(seconds=1)]
    )
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        reader(owner, clock=times.__next__).read_retained(resumed(prepared, upload))
    assert snapshot(owner) == before


@pytest.mark.parametrize("damage", ["blob", "missing-content", "receipt", "metadata", "schema"])
def test_corruption_is_not_unavailable_or_content_leak(private_root, monkeypatch, caplog, damage):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root, admit=True)
    marker = "synthetic-private-marker"
    with database(owner.path) as db:
        if damage == "blob":
            tamper(
                db, "content_no_update", "UPDATE source_content SET envelope=?", (marker.encode(),)
            )
        elif damage == "missing-content":
            db.execute("DELETE FROM source_content")
        elif damage == "receipt":
            tamper(db, "receipt_no_update", "UPDATE source_receipts SET receipt=?", (marker,))
        elif damage == "schema":
            db.execute("CREATE TABLE incompatible (id)")
        else:
            tamper(
                db, "handoff_progress", "UPDATE source_handoffs SET enrolled_machine_id=?", (OTHER,)
            )
    with pytest.raises(SourceStoreUnavailable) as failure:
        access.read_retained(resumed(prepared, upload))
    assert failure.value.__context__ is None and failure.value.__cause__ is None
    assert marker not in str(failure.value) + caplog.text
    assert raw.decode() not in str(failure.value) + caplog.text


def test_message_wide_cutoff_and_query_only_observe(private_root, monkeypatch):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    requests = [resumed(prepared, upload)]
    for seconds in (1, 2):
        value = envelope()
        value["payload"]["event_id"] = str(uuid4())
        value["payload"]["snapshot"]["captured_at"] = value["payload"]["occurred_at"] = (
            f"2026-10-18T12:00:0{seconds}Z"
        )
        resign(value)
        intent = managed_request(value)
        access.register_intent(intent, reservation_expires_at=RESERVATION)
        from test_lead_custody_store import capture

        uploading = managed_operation(intent, "upload", capture(value))
        access.bind_upload(uploading)
        access.admit_bound(uploading, encode(value))
        requests.append(resumed(intent, uploading))
    SourceContent(owner, clock=lambda: NOW).purge_message(
        prepared.payload.source, cutoff=datetime.fromisoformat("2026-10-18T12:00:01Z")
    )
    for request in requests[:2]:
        with pytest.raises(SourceContentUnavailable):
            access.read_retained(request.model_copy(update={"expected_fence_generation": 2}))
    assert access.read_retained(requests[2])
    before = snapshot(owner)
    envelope_probe(monkeypatch, forbidden=True)
    monkeypatch.setattr(owner, "_transaction", lambda: pytest.fail("observe acquired writer"))
    assert observe(access, prepared).content_state == "purged"
    assert snapshot(owner) == before


# Reuse the qualified process harness, SQL writer checkpoints, lifecycle actors,
# privacy assertions and IPC ordering. Only its legacy read target is replaced
# with the new request-only facade; the harness's admission-ID argument is ignored.
_legacy_start = races.managed_start


def retained_child(root, pipe, packet, action, **options):
    original_validate = SourceAdmission._validate_content
    target, fault = options.get("target"), options.get("fault")

    def validated(db, metadata):
        result = original_validate(db, metadata)
        pipe.send(("checkpoint", "after-envelope"))
        if target == "after-envelope":
            if fault == "crash":
                pipe.send(("complete", None))
                os._exit(CRASH)
            raise sqlite3.OperationalError("synthetic private read failure")
        return result

    def bound_read(content, ignored_admission_id):
        request = parse_untrusted_request(packet["resume"])
        return reader(
            content._store,
            expected_incarnation=packet["incarnation"],
            clock=content._clock,
        ).read_retained(request)

    SourceAdmission._validate_content = staticmethod(validated)
    SourceContent.read_content = bound_read
    races.managed_child(root, pipe, packet, action, **options)


def retained_start(context, root, packet, action, **options):
    if action != "read":
        return _legacy_start(context, root, packet, action, **options)
    receive, send = context.Pipe(duplex=False)
    process = context.Process(
        target=retained_child, args=(root, send, packet, action), kwargs=options
    )
    process.start()
    send.close()
    return process, receive


def retained_packet(root):
    owner, packet = managed_packet(root, "admitted")
    prepared = parse_untrusted_request(packet["prepare"])
    upload = parse_untrusted_request(packet["upload"])
    facts = observe(reader(owner), prepared)
    packet.update(
        resume=canonical_request(resumed(prepared, upload)),
        admission_id=facts.receipt.admission_id,
    )
    return owner, packet


@pytest.mark.parametrize("mutation", ["close", "purge", "retire"])
@pytest.mark.parametrize("read_first", [False, True])
def test_native_writer_orders(private_root, monkeypatch, mutation, read_first):
    owner, packet = retained_packet(private_root)
    monkeypatch.setattr(races, "managed_start", retained_start)
    first, second = ("read", mutation) if read_first else (mutation, "read")
    one, two = ordered_managed(private_root, packet, first, second)
    assert ("blocked", None) in two
    read, changed = (one, two) if read_first else (two, one)
    managed_outcome(packet, changed)
    managed_outcome(packet, read, None if read_first else SourceAuthenticationError)
    prepared = parse_untrusted_request(packet["prepare"])
    request = parse_untrusted_request(packet["resume"]).model_copy(
        update={"expected_fence_generation": 2}
    )
    facts = observe(reader(store(private_root)), prepared)
    assert facts.closed and facts.fence_generation == 2
    access = reader(store(private_root), clock=lambda: NOW)
    if mutation == "close":
        assert access.read_retained(request) == packet["raw"]
    else:
        with pytest.raises(SourceContentUnavailable):
            access.read_retained(request)
    assert len(snapshot(owner)["source_receipts"]) == 1


@pytest.mark.parametrize("case", ["expiry", "clock-backward"])
def test_waiting_read_samples_after_writer(private_root, monkeypatch, case):
    owner, packet = retained_packet(private_root)
    request = parse_untrusted_request(packet["resume"])
    monkeypatch.setattr(races, "managed_start", retained_start)
    if case == "expiry":
        first_options = {}
        second_options = {"now": request.payload.capture.recovery_deadline}
        expected = SourceContentUnavailable
    else:
        first_options = {"now": (NOW + timedelta(seconds=1)).isoformat()}
        second_options = {}
        expected = SourceAuthenticationError
    one, two = ordered_managed(
        private_root,
        packet,
        "read",
        "read",
        first_options=first_options,
        second_options=second_options,
    )
    managed_outcome(packet, one)
    managed_outcome(packet, two, expected)
    assert ("blocked", None) in two
    if case == "expiry":
        assert snapshot(owner)["source_content"] == []


@pytest.mark.parametrize(
    "target,fault",
    [
        (target, fault)
        for target in ("locked", "after-envelope", "before-commit", "after-commit", "response-lost")
        for fault in ("crash", "sql")
        if (target, fault) != ("response-lost", "sql")
    ],
)
def test_native_read_fault_and_recovery(private_root, target, fault):
    owner, packet = retained_packet(private_root)
    before = snapshot(owner)
    now = (NOW + timedelta(seconds=1)).isoformat()
    process, receive = retained_start(
        multiprocessing.get_context("spawn"),
        private_root,
        packet,
        "read",
        target=target,
        fault=fault,
        now=now,
    )
    messages = []
    finish(process, receive, messages, crashed=fault == "crash")
    assert ("checkpoint", target) in messages
    assert not [v for k, v in messages if k in ("result", "receipt")]
    if fault == "sql":
        expected = SourceStoreUncertain if "commit" in target else SourceStoreUnavailable
        managed_outcome(packet, messages, expected)
    else:
        # Abrupt exits after validation may omit the harness's final logs record.
        assert packet["raw"].decode() not in repr(messages)
    after = snapshot(store(private_root))
    committed = target in ("after-commit", "response-lost")
    assert (after["authority_clock_history"] != before["authority_clock_history"]) is committed
    assert {k: v for k, v in after.items() if k != "authority_clock_history"} == {
        k: v for k, v in before.items() if k != "authority_clock_history"
    }
    if target in ("before-commit", "after-commit", "response-lost"):
        assert ("checkpoint", "after-envelope") in messages
    process, receive = retained_start(
        multiprocessing.get_context("spawn"), private_root, packet, "read", now=now
    )
    recovered = []
    finish(process, receive, recovered)
    managed_outcome(packet, recovered)
    assert len(snapshot(store(private_root))["source_receipts"]) == 1


@pytest.mark.parametrize("target", ["before-commit", "after-commit"])
@pytest.mark.parametrize("fault", ["crash", "sql"])
def test_native_expiry_commit_recovery(private_root, target, fault):
    owner, packet = retained_packet(private_root)
    request = parse_untrusted_request(packet["resume"])
    deadline = request.payload.capture.recovery_deadline
    process, receive = retained_start(
        multiprocessing.get_context("spawn"),
        private_root,
        packet,
        "read",
        target=target,
        fault=fault,
        now=deadline,
    )
    messages = []
    finish(process, receive, messages, crashed=fault == "crash")
    assert ("checkpoint", "after-envelope") in messages
    assert ("checkpoint", target) in messages
    assert not [v for k, v in messages if k in ("result", "receipt")]
    if fault == "sql":
        managed_outcome(packet, messages, SourceStoreUncertain)
    prepared = parse_untrusted_request(packet["prepare"])
    facts = observe(reader(store(private_root)), prepared)
    committed = target == "after-commit"
    assert facts.closed is committed
    assert facts.content_state == ("purged" if committed else "retained")
    # Same request never silently refreshes a stale generation after a lost reply.
    process, receive = retained_start(
        multiprocessing.get_context("spawn"), private_root, packet, "read", now=deadline
    )
    retried = []
    finish(process, receive, retried)
    managed_outcome(
        packet, retried, SourceAuthenticationError if committed else SourceContentUnavailable
    )
    assert snapshot(store(private_root))["source_content"] == []
    admin = SourceClockAdmin(owner)
    admin.reconcile(
        operation_id=str(uuid4()), expected_sequence=admin.read().sequence, corrected_at=NOW
    )
    packet["resume"] = canonical_request(
        request.model_copy(update={"expected_fence_generation": 2})
    )
    process, receive = retained_start(
        multiprocessing.get_context("spawn"), private_root, packet, "read"
    )
    restored_clock = []
    finish(process, receive, restored_clock)
    managed_outcome(packet, restored_clock, SourceContentUnavailable)


def test_new_store_at_same_path_refuses_retained_binding(private_root):
    owner, packet = retained_packet(private_root)
    owner.path.rename(private_root / "preserved.sqlite3")
    owner.initialize(trust())
    assert owner.read_incarnation() != packet["incarnation"]
    before = snapshot(owner)
    process, receive = retained_start(
        multiprocessing.get_context("spawn"), private_root, packet, "read"
    )
    messages = []
    finish(process, receive, messages)
    managed_outcome(packet, messages, SourceStoreConflict)
    assert snapshot(store(private_root)) == before
