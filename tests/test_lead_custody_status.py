"""R3.5 first slice: precise values and source-owned, read-only observations."""

import sqlite3
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_lead_custody_composition import composition, prepare
from test_lead_custody_protocol import (
    GUARDS,
    assert_input_free_refusal,
    capture,
    known,
    result,
    set_path,
    unresolved,
    wire,
)
from test_lead_custody_retained_read import BINDINGS
from test_lead_custody_store import (
    RESERVATION,
    managed_operation,
    managed_setup,
    observe,
    reader,
    rewrite_request,
    snapshot,
    upload_setup,
)
from test_lead_host_composition import setup as setup
from test_lead_source_admission import tamper
from test_lead_source_auth import NOW, OTHER, envelope, resign, trust
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root
from test_workflow_receipt_lookup import rows

from connect_automate.automate import PackRuntime
from connect_automate.automate.engine import PackVersionError
from connect_automate.automate.events import EventBindingError, EventConflict, EventInputError
from connect_automate.automate.host import AutomateLicenseError
from connect_automate.lead_intake import custody_protocol as cp
from connect_automate.lead_intake.content import SourceContent
from connect_automate.lead_intake.custody_handoff import _CustodyHandoff
from connect_automate.lead_intake.results import SourceHandoffLookup, SourceHandoffUnknown
from connect_automate.lead_intake.source_store import (
    SourceClockAdmin,
    SourceStoreBusy,
    SourceStoreConflict,
    SourceStoreInputError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
)


def precise(value=None):
    value = result() if value is None else value
    value["schema_version"] = "1.1"
    value["observed_at"] = value["observed_at"].replace("Z", ".000000Z")
    return value


def status(prepared, upload=None, generation=1):
    cap = upload.payload.capture.model_dump() if upload else None
    return managed_operation(prepared, "status", cap, generation)


def test_same_second_precision():
    data = result("custodied", "retained", reason="custody_confirmed")
    data["source_receipt"]["accepted_at"] = "2026-10-18T12:30:00.250000Z"
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_result(wire(data))
    data["observed_at"] = "2026-10-18T12:30:00.500000Z"
    with pytest.raises(cp.CustodyInputError):
        cp.parse_untrusted_result(wire(data))
    data["schema_version"] = "1.1"
    parsed = cp.parse_untrusted_status_result(wire(data))
    assert cp.canonical_status_result(parsed) == wire(data)
    assert parsed.observed_at == "2026-10-18T12:30:00.500000Z"


def test_source_observation_owns_exact_facts(private_root):
    owner, access, prepared, upload, _, admitted = upload_setup(private_root, admit=True)
    before = snapshot(owner)
    samples = []

    def clock():
        samples.append(NOW + timedelta(microseconds=500000))
        return samples[-1]

    access._clock = clock
    facts = access.observe_status(request=status(prepared, upload))
    assert facts.custody.receipt == admitted.receipt
    assert facts.admission_id == admitted.receipt.admission_id
    assert facts.reservation_expires_at == RESERVATION
    assert facts.observed_at == "2026-10-18T12:30:00.500000Z"
    assert facts.namespace_retired is False
    assert (facts.content_state, facts.unavailable_reason) == ("retained", None)
    assert len(samples) == 1 and snapshot(owner) == before


@pytest.mark.parametrize("resolved", [False, True])
def test_versions_and_encoders_are_separate(resolved):
    old = result() if resolved else unresolved()
    new = precise(result()) if resolved else {**unresolved(), "schema_version": "1.1"}
    a, b = cp.parse_untrusted_result(wire(old)), cp.parse_untrusted_status_result(wire(new))
    assert cp.canonical_result(a) == wire(old)
    assert cp.canonical_status_result(b) == wire(new)
    for call in (
        lambda: cp.parse_untrusted_result(wire(new)),
        lambda: cp.parse_untrusted_status_result(wire(old)),
        lambda: cp.canonical_result(b),
        lambda: cp.canonical_status_result(a),
    ):
        assert_input_free_refusal(call)
    for version in ["1.0", "1.2", "2.0", 1.1, False, None, ""]:
        assert_input_free_refusal(
            lambda version=version: cp.parse_untrusted_status_result(
                wire({**new, "schema_version": version})
            )
        )


@pytest.mark.parametrize(
    "name,kind,factory,path,value,message",
    [g for g in GUARDS if g[1] == "result"],
    ids=[g[0] for g in GUARDS if g[1] == "result"],
)
def test_precise_guards_independently(name, kind, factory, path, value, message):
    data = precise(factory())
    if path == ("observed_at",):
        value = value.replace("Z", ".000000Z")
    set_path(data, path, value)
    with pytest.raises(ValueError, match=message):
        cp.ResolvedStatusResult.model_validate(data)
    assert_input_free_refusal(lambda: cp.parse_untrusted_status_result(wire(data)))


@pytest.mark.parametrize("boundary", ["capture", "receipt", "reservation"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_mixed_precision_boundaries(boundary, offset):
    data = precise(result() if boundary == "reservation" else known())
    stamp = (
        data["reservation_expires_at"]
        if boundary == "reservation"
        else data["capture"]["captured_at"]
    )
    if boundary != "reservation":
        data["source_receipt"]["accepted_at"] = stamp.replace("Z", ".000000Z")
        if boundary == "receipt":
            data["source_receipt"]["accepted_at"] = stamp.replace("Z", ".250000Z")
        data["workflow"]["source_receipt"] = dict(data["source_receipt"])
        stamp = data["source_receipt"]["accepted_at"]
    data["observed_at"] = (
        (datetime.fromisoformat(stamp) + timedelta(microseconds=offset))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    allowed = offset < 0 if boundary == "reservation" else offset >= 0
    if allowed:
        assert cp.canonical_status_result(cp.parse_untrusted_status_result(wire(data))) == wire(
            data
        )
    else:
        assert_input_free_refusal(lambda: cp.parse_untrusted_status_result(wire(data)))


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-10-18T12:30:00Z",
        "2026-10-18T12:30:00.1Z",
        "2026-10-18T12:30:00.0000000Z",
        "2026-10-18T12:30:00.000000+00:00",
        "2026-02-30T12:30:00.000000Z",
        None,
        False,
        0,
        "",
    ],
)
def test_precise_time_is_strict(stamp):
    data = {**precise(), "observed_at": stamp}
    assert_input_free_refusal(lambda: cp.parse_untrusted_status_result(wire(data)))


def test_precise_parser_and_encoder_fail_closed(monkeypatch):
    data = precise(known())
    data["workflow"]["stage"] = "😀" * 80
    raw = wire(data)
    assert len(raw) > len(raw.decode())
    parsed = cp.parse_untrusted_status_result(raw)
    for size in (len(raw), cp.MAX_RESULT_BYTES - 1, cp.MAX_RESULT_BYTES):
        assert (
            cp.canonical_status_result(
                cp.parse_untrusted_status_result(raw + b" " * (size - len(raw)))
            )
            == raw
        )
    for bad in (
        b"",
        b"\xff",
        raw + b" " * cp.MAX_RESULT_BYTES,
        b'{"schema_version":"1.1",' + raw[1:],
        None,
        False,
        0,
        "",
        bytearray(raw),
    ):
        assert_input_free_refusal(lambda bad=bad: cp.parse_untrusted_status_result(bad))
    for path, value in [
        (["workflow", "schema_version"], "1.1"),
        (["scope", "extra"], "SECRET"),
        (["state_revision"], False),
        (["capture", "artifact_size"], 0),
    ]:
        modified = precise(known())
        set_path(modified, path, value)
        assert_input_free_refusal(
            lambda modified=modified: cp.parse_untrusted_status_result(wire(modified))
        )
    for key in data:
        assert_input_free_refusal(
            lambda key=key: cp.parse_untrusted_status_result(
                wire({k: v for k, v in data.items() if k != key})
            )
        )
    for bad in (
        parsed.model_copy(update={"observed_at": "SECRET"}),
        cp.ResolvedStatusResult.model_construct(),
        data,
        None,
    ):
        assert_input_free_refusal(lambda bad=bad: cp.canonical_status_result(bad))
    monkeypatch.setattr(cp, "MAX_RESULT_BYTES", len(raw))
    assert cp.canonical_status_result(parsed) == raw
    monkeypatch.setattr(cp, "MAX_RESULT_BYTES", len(raw) - 1)
    with pytest.raises(ValueError, match="result byte limit"):
        cp.ResolvedStatusResult.model_validate(data)
    assert_input_free_refusal(lambda: cp.canonical_status_result(parsed))


@pytest.mark.parametrize(
    "phase",
    [
        "prepared",
        "bound",
        "admitted",
        "closed",
        "closed-empty",
        "closed-bound",
        "purged",
        "retired",
        "cleaned",
    ],
)
@pytest.mark.parametrize("body", ["available", "unavailable"])
def test_real_lifecycle_and_reopen(private_root, phase, body):
    value = envelope()
    if body == "unavailable":
        value["payload"]["snapshot"]["body"] = {"state": body, "reason": "source_gone"}
        resign(value)
    if phase in ("prepared", "closed-empty"):
        owner, access, prepared = managed_setup(private_root, value)
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
        upload = admitted = None
    else:
        owner, access, prepared, upload, _, admitted = upload_setup(
            private_root, admit=phase not in ("bound", "closed-bound"), value=value
        )
    content = SourceContent(owner, clock=lambda: NOW)
    if phase in ("closed", "closed-empty", "closed-bound"):
        access.close_admission(managed_operation(prepared, "settle"))
    if phase == "purged":
        content.purge_message(prepared.payload.source, cutoff=NOW)
    if phase in ("retired", "cleaned"):
        content.retire_namespace(prepared.scope.namespace_id)
    if phase == "cleaned":
        content.cleanup_retired(prepared.scope.namespace_id, limit=1)
    before = snapshot(owner)
    reopened = reader(store(private_root), clock=lambda: NOW)
    found = reopened.observe_status(request=status(prepared, upload, 2147483647))
    assert found.custody == observe(reopened, prepared, upload.payload.capture if upload else None)
    assert found.reservation_expires_at == RESERVATION
    assert found.admission_id == (admitted.receipt.admission_id if admitted else None)
    assert found.namespace_retired is (phase in ("retired", "cleaned"))
    expected = (
        ("unavailable", "retired")
        if found.namespace_retired
        else (
            ("unavailable", "purged")
            if phase == "purged"
            else ("retained", None)
            if admitted
            else ("not_received", None)
        )
    )
    assert (found.content_state, found.unavailable_reason) == expected
    assert snapshot(owner) == before
    with pytest.raises(FrozenInstanceError):
        found.admission_id = OTHER


@pytest.mark.parametrize("boundary", ["reservation", "recovery"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_source_expiry_is_projection_only(private_root, boundary, offset):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    stamp = RESERVATION if boundary == "reservation" else upload.payload.capture.recovery_deadline
    access._clock = lambda: datetime.fromisoformat(stamp) + timedelta(microseconds=offset)
    before = snapshot(owner)
    found = access.observe_status(request=status(prepared, upload))
    expired = boundary == "recovery" and offset >= 0
    assert found.content_state == ("unavailable" if expired else "retained")
    assert found.unavailable_reason == ("expired" if expired else None)
    assert snapshot(owner) == before
    access._clock = lambda: NOW
    assert access.observe_status(request=status(prepared, upload)).content_state == "retained"


@pytest.mark.parametrize("generation", [1, 2, 2147483647])
def test_generation_is_only_a_hint(private_root, generation):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    before = snapshot(owner)
    found = access.observe_status(request=status(prepared, upload, generation))
    assert found.custody.fence_generation == 1 and snapshot(owner) == before


@pytest.mark.parametrize("path,value", BINDINGS, ids=[p[-1] for p, _ in BINDINGS])
def test_exact_status_binding(private_root, path, value):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    request = rewrite_request(status(prepared, upload), path, value)
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        access.observe_status(request=request)
    assert snapshot(owner) == before


@pytest.mark.parametrize("captured", [False, True])
def test_absent_capture_must_match(private_root, captured):
    _, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    if captured:
        access.bind_upload(upload)
    request = status(prepared, None if captured else upload)
    with pytest.raises(SourceStoreConflict):
        access.observe_status(request=request)


@pytest.mark.parametrize("bad", [0, False, "", 2147483648])
def test_copied_hint_cannot_bypass_parser(private_root, bad):
    _, access, prepared, upload, _, _ = upload_setup(private_root)
    request = status(prepared, upload).model_copy(update={"expected_fence_generation": bad})
    with pytest.raises(SourceStoreInputError):
        access.observe_status(request=request)


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_deployment_check_precedes_snapshot(private_root, monkeypatch, field):
    owner, access, prepared, upload, _, _ = upload_setup(private_root)
    request = rewrite_request(status(prepared, upload), ["scope", field], OTHER)
    monkeypatch.setattr(owner, "_read_snapshot", forbidden)
    with pytest.raises(SourceStoreConflict):
        access.observe_status(request=request)


def forbidden(*args, **kwargs):
    pytest.fail("status reached a forbidden body/authentication/writer path")


def test_readonly_after_revocation_and_old_clock_free(private_root, monkeypatch):
    from connect_automate.lead_intake import admission

    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    before = snapshot(owner)
    monkeypatch.setattr(admission, "authenticate_source", forbidden)
    monkeypatch.setattr(owner, "_transaction", forbidden)
    monkeypatch.setattr(owner, "_record_clock", forbidden)
    monkeypatch.setattr(SourceContent, "read_content", forbidden)
    found = access.observe_status(request=status(prepared, upload))
    assert found.content_state == "retained"
    access._clock = forbidden
    monkeypatch.setattr(owner, "_check_clock", forbidden)
    assert observe(access, prepared, upload.payload.capture) == found.custody
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "sample",
    [
        None,
        False,
        0,
        "",
        NOW.replace(tzinfo=None),
        NOW.astimezone(timezone(timedelta(hours=1))),
        NOW - timedelta(microseconds=1),
    ],
)
def test_bad_clock_and_floor_refuse_without_writes(private_root, sample):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    before = snapshot(owner)
    access._clock = lambda: sample
    with pytest.raises(SourceStoreUnavailable) as error:
        access.observe_status(request=status(prepared, upload))
    assert error.value.__cause__ is None and error.value.__context__ is None
    assert snapshot(owner) == before


def test_clock_exception_is_input_free(private_root):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    before = snapshot(owner)

    def broken():
        raise RuntimeError("SECRET")

    access._clock = broken
    with pytest.raises(SourceStoreUnavailable) as error:
        access.observe_status(request=status(prepared, upload))
    assert str(error.value) == "lead source store unavailable"
    assert error.value.__context__ is None and error.value.__cause__ is None
    assert snapshot(owner) == before


def test_clock_reset_does_not_restore_purged_content(private_root):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    future = NOW + timedelta(minutes=20)
    # A real content read, not status, advances the floor without expiring the bytes.
    SourceContent(owner, clock=lambda: future).read_content(
        observe(access, prepared, upload.payload.capture).receipt.admission_id
    )
    admin = SourceClockAdmin(owner)
    floor = admin.read()
    with pytest.raises(SourceStoreUnavailable):
        access.observe_status(request=status(prepared, upload))
    admin.reconcile(operation_id=str(uuid4()), expected_sequence=floor.sequence, corrected_at=NOW)
    assert access.observe_status(request=status(prepared, upload)).content_state == "retained"
    SourceContent(owner, clock=lambda: NOW).purge_message(prepared.payload.source, cutoff=NOW)
    before = snapshot(owner)
    assert access.observe_status(request=status(prepared, upload)).unavailable_reason == "purged"
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["deadline", "admission", "missing-content", "corrupt-blob"])
def test_shared_metadata_guards_and_body_limit(private_root, kind):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    with database(owner.path) as db:
        if kind == "deadline":
            tamper(
                db,
                "handoff_progress",
                "UPDATE source_handoffs SET reservation_expires_at=?",
                ("invalid",),
            )
        elif kind == "admission":
            tamper(db, "handoff_progress", "UPDATE source_handoffs SET admission_id=?", (OTHER,))
        elif kind == "missing-content":
            db.execute("DELETE FROM source_content")
        else:
            tamper(db, "content_no_update", "UPDATE source_content SET envelope=?", (b"SECRET",))
    before = snapshot(owner)
    if kind == "corrupt-blob":
        assert access.observe_status(request=status(prepared, upload)).content_state == "retained"
    else:
        with pytest.raises(SourceStoreUnavailable):
            access.observe_status(request=status(prepared, upload))
    assert snapshot(owner) == before


def test_missing_handoff_and_wrong_operation(private_root):
    owner, access, prepared = managed_setup(private_root)
    before = snapshot(owner)
    assert access.observe_status(request=status(prepared)) is None
    with pytest.raises(SourceStoreInputError):
        access.observe_status(request=prepared)
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT envelope FROM source_content",
        "UPDATE source_handoffs SET revision=revision+1",
        "PRAGMA query_only=OFF",
    ],
)
def test_actual_status_snapshot_denies_sql(private_root, monkeypatch, sql):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    original = owner._custody_metadata
    denied = []

    def metadata(db, ident):
        with pytest.raises(sqlite3.DatabaseError):
            db.execute(sql)
        denied.append(sql)
        return original(db, ident)

    monkeypatch.setattr(owner, "_custody_metadata", metadata)
    before = snapshot(owner)
    assert access.observe_status(request=status(prepared, upload)).content_state == "retained"
    assert denied == [sql] and snapshot(owner) == before


@pytest.mark.parametrize("kind", ["missing", "replaced", "incarnation"])
def test_status_pins_existing_store(private_root, kind):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    if kind == "incarnation":
        access = reader(owner, expected_incarnation=OTHER, clock=lambda: NOW)
    else:
        owner.path.rename(private_root / "preserved.sqlite3")
        if kind == "replaced":
            owner.initialize(trust())
    with pytest.raises(SourceStoreUnavailable) as error:
        access.observe_status(request=status(prepared, upload))
    assert error.value.__cause__ is None and error.value.__context__ is None
    if kind == "missing":
        assert not owner.path.exists()


@pytest.mark.parametrize("removed", ["envelope_sha256", "payload_digest"])
def test_partial_copied_capture_refused(private_root, removed):
    _, access, prepared, upload, _, _ = upload_setup(private_root)
    request = status(prepared, upload)
    data = request.payload.capture.model_dump()
    del data[removed]
    bad = request.model_copy(
        update={"payload": request.payload.model_copy(update={"capture": data})}
    )
    with pytest.raises(SourceStoreInputError):
        access.observe_status(request=bad)


def test_persisted_deletion_precedes_elapsed_expiry(private_root):
    owner, access, prepared, upload, _, _ = upload_setup(private_root, admit=True)
    content = SourceContent(owner, clock=lambda: NOW)
    content.purge_message(prepared.payload.source, cutoff=NOW)
    access._clock = lambda: NOW + timedelta(hours=4)
    request = status(prepared, upload)
    assert access.observe_status(request=request).unavailable_reason == "purged"
    content.retire_namespace(prepared.scope.namespace_id)
    assert access.observe_status(request=request).unavailable_reason == "retired"
    content.cleanup_retired(prepared.scope.namespace_id, limit=1)
    before = snapshot(owner)
    found = access.observe_status(request=request)
    assert found.unavailable_reason == "retired" and found.admission_id is not None
    assert snapshot(owner) == before


@pytest.fixture
def status_case(setup):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    intent, upload, raw = prepare(runtime, access)
    access.admit_bound(upload, raw)
    return SimpleNamespace(
        args=args,
        owner=owner,
        runtime=runtime,
        access=access,
        intent=intent,
        upload=upload,
        raw=raw,
        request=status(intent, upload),
        handoff=composition(runtime, access, intent),
    )


@contextmanager
def status_only(c, monkeypatch):
    from test_lead_custody_retained_read import envelope_probe

    from connect_automate.lead_intake import admission

    before = snapshot(c.owner), rows(c.args["store"])
    with monkeypatch.context() as patch:
        for target, names in (
            (c.owner, ("_transaction", "_record_clock")),
            (c.access, ("read_retained", "revalidate_existing", "admit_bound", "observe")),
            (admission, ("authenticate_source",)),
            (_CustodyHandoff, ("submit", "resume", "recover")),
            (c.runtime, ("_dispatch_event_actions", "_prepare_source")),
            (c.args["store"], ("connection",)),
        ):
            for name in names:
                patch.setattr(target, name, forbidden)
        seen = envelope_probe(patch, forbidden=True)
        yield
        assert seen == []
    assert (snapshot(c.owner), rows(c.args["store"])) == before


def test_status_reopens_revoked_history(status_case, monkeypatch):
    c = status_case
    first = c.handoff.submit(request=c.upload, raw_source_bytes=c.raw)
    c.owner.publish_authority(next_snapshot(key_grants=[]), expected_generation=1)
    c.owner = store(c.owner.root)
    c.access = reader(c.owner, clock=lambda: NOW)
    c.runtime = PackRuntime.load(**c.args)
    c.handoff = composition(c.runtime, c.access, c.intent)
    del c.raw  # Reference-only reopen, no authority/body argument to status.
    with status_only(c, monkeypatch):
        found = c.handoff.status(request=c.request)
    assert type(found) is cp.ResolvedStatusResult and found.schema_version == "1.1"
    assert found.reason == "workflow_known" and found.source_receipt == first.source_receipt
    assert not found.workflow.workflow_applied
    for name in ("workflow_record_id", "workflow_event_id", "stage", "state_version"):
        assert getattr(found.workflow, name) == getattr(first, name)
    assert cp.parse_untrusted_status_result(cp.canonical_status_result(found)) == found


def committed(c, outcome="accepted"):
    from test_lead_custody_recovery import historical
    from test_lead_custody_resume import resumed

    return historical(
        SimpleNamespace(**{**vars(c), "request": resumed(c.intent, c.upload)}), outcome
    )


def cleaned(c):
    content = SourceContent(c.owner, clock=lambda: NOW)
    content.retire_namespace(c.intent.scope.namespace_id)
    content.cleanup_retired(c.intent.scope.namespace_id, limit=1)
    assert c.access.observe_status(request=c.request).custody.receipt is None


@pytest.mark.parametrize("phase", ["missing", "prepared", "bound", "closed", "closed-bound"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_status_before_custody(setup, monkeypatch, phase, offset):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    intent, upload, _ = prepare(runtime, access, phase="bound" if "bound" in phase else phase)
    if phase.startswith("closed"):
        access.close_admission(managed_operation(intent, "settle"))
    request = status(intent, upload if "bound" in phase else None, 2147483647)
    sample = datetime.fromisoformat(RESERVATION) + timedelta(microseconds=offset)
    access._clock = lambda: sample
    c = SimpleNamespace(args=args, owner=owner, runtime=runtime, access=access)
    handoff = composition(runtime, access, intent)
    monkeypatch.setattr(runtime, "lookup_source_outcome", forbidden)
    with status_only(c, monkeypatch):
        found = handoff.status(request=request)
    if phase == "missing" or phase == "prepared" and offset >= 0:
        assert found.code == ("not_found" if phase == "missing" else "unknown")
        return
    assert found.observed_at == sample.isoformat(timespec="microseconds").replace("+00:00", "Z")
    expected = (
        ("fenced_empty", "not_received", "capture_cancelled")
        if phase.startswith("closed")
        else (
            ("prepared", "not_received", "ready")
            if phase == "prepared"
            else ("upload_possible", "unknown", "pending")
        )
    )
    assert (found.capture_phase, found.content_state, found.reason) == expected
    assert found.capture == request.payload.capture and found.workflow is None
    assert found.source_receipt is None and found.fence_generation == (
        2 if phase.startswith("closed") else 1
    )
    assert found.reservation_expires_at == (RESERVATION if phase == "prepared" else None)


@pytest.mark.parametrize("outcome", ["not_found", "accepted", "no_match"])
@pytest.mark.parametrize("lifecycle", ["none", "purged", "retired", "cleaned", "expired"])
def test_status_custody_table(status_case, monkeypatch, outcome, lifecycle):
    c = status_case
    prior = committed(c, outcome) if outcome != "not_found" else None
    content = SourceContent(c.owner, clock=lambda: NOW)
    if lifecycle == "purged":
        content.purge_message(c.intent.payload.source, cutoff=NOW)
    elif lifecycle == "retired":
        content.retire_namespace(c.intent.scope.namespace_id)
    elif lifecycle == "cleaned":
        cleaned(c)
    elif lifecycle == "expired":
        c.access._clock = lambda: datetime.fromisoformat(c.upload.payload.capture.recovery_deadline)
    with status_only(c, monkeypatch):
        found = c.handoff.status(request=c.request)
    if lifecycle == "cleaned" and outcome == "not_found":
        assert found.code == "unknown"
        return
    assert found.capture_phase == "custodied" and found.workflow.workflow_outcome == outcome
    assert found.content_state == ("retained" if lifecycle == "none" else "unavailable")
    assert found.unavailable_reason == (
        None if lifecycle == "none" else "retired" if lifecycle == "cleaned" else lifecycle
    )
    assert found.reason == (
        "workflow_known"
        if prior
        else "custody_confirmed"
        if lifecycle == "none"
        else "content_unavailable"
    )
    if prior:
        assert found.workflow == prior and found.source_receipt == prior.source_receipt


@pytest.mark.parametrize("body", ["complete", "truncated", "unknown", "unavailable"])
def test_status_body_metadata_is_not_body_authentication(setup, monkeypatch, body):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    value = envelope()
    data = value["payload"]["snapshot"]["body"]
    if body == "unavailable":
        value["payload"]["snapshot"]["body"] = dict(state=body, reason="source_gone")
    else:
        data.update(
            completeness=body,
            source_chars=None
            if body == "unknown"
            else data["stored_chars"] + int(body == "truncated"),
        )
    intent, upload, raw = prepare(runtime, access, value)
    handoff = composition(runtime, access, intent)
    handoff.submit(request=upload, raw_source_bytes=raw)
    with status_only(
        SimpleNamespace(args=args, owner=owner, runtime=runtime, access=access), monkeypatch
    ):
        found = handoff.status(request=status(intent, upload))
    assert found.reason == "workflow_known" and found.content_state == "retained"


@pytest.mark.parametrize("path,value", BINDINGS, ids=[p[-1] for p, _ in BINDINGS])
def test_status_request_pins(status_case, monkeypatch, path, value):
    c = status_case
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
    request = rewrite_request(c.request, path, value)
    if path in (
        ["scope", "host_id"],
        ["scope", "organization_id"],
        ["scope", "namespace_id"],
        ["scope", "route_digest"],
        ["enrolled_machine_id"],
    ):
        with pytest.raises(EventBindingError):
            c.handoff.status(request=request)
    else:
        assert c.handoff.status(request=request).code == "conflict"


@pytest.mark.parametrize("value", [None, False, "", 0, -1, 2147483648])
def test_status_invalid_hints_before_observation(status_case, monkeypatch, value):
    c = status_case
    monkeypatch.setattr(c.access, "observe_status", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.status(request=c.request.model_copy(update={"expected_fence_generation": value}))


@pytest.mark.parametrize("generation", [1, 2, 2147483647])
def test_status_canonical_copy_and_snapshot_order(status_case, monkeypatch, generation):
    c = status_case
    observe, lookup, snapshot_read = (
        c.access.observe_status,
        c.runtime.lookup_source_outcome,
        c.owner._read_snapshot,
    )
    active, calls, seen = [], [], []

    @contextmanager
    def source(**kw):
        with snapshot_read(**kw) as db:
            active.append(db)
            try:
                yield db
            finally:
                active.pop()

    def observed(**kw):
        seen.append(kw["request"])
        return observe(**kw)

    def looked(**kw):
        assert not active
        calls.append(kw)
        return lookup(**kw)

    monkeypatch.setattr(c.owner, "_read_snapshot", source)
    monkeypatch.setattr(c.access, "observe_status", observed)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", looked)
    request = c.request.model_copy(update={"expected_fence_generation": generation})
    with status_only(c, monkeypatch):
        found = c.handoff.status(request=request)
    assert found.fence_generation == 1 and seen == [request] and seen[0] is not request
    assert seen[0].scope is not request.scope
    assert calls == [
        dict(
            binding="inbox",
            event_id=c.intent.scope.event_id,
            expected_payload_digest=c.upload.payload.capture.payload_digest,
        )
    ]
    assert calls[0]["expected_payload_digest"] != c.upload.payload.capture.envelope_sha256


@pytest.mark.parametrize("kind", ["prepare", "upload", "resume", "settle", "copied"])
def test_status_wrong_operation(status_case, monkeypatch, kind):
    c = status_case
    request = (
        c.intent
        if kind == "prepare"
        else c.upload
        if kind == "upload"
        else c.request.model_copy(update={"operation": "upload"})
        if kind == "copied"
        else managed_operation(
            c.intent, kind, c.upload.payload.capture.model_dump() if kind == "resume" else None
        )
    )
    monkeypatch.setattr(c.access, "observe_status", forbidden)
    with pytest.raises(EventBindingError):
        c.handoff.status(request=request)


@pytest.mark.parametrize(
    "field,value",
    [
        ("host_id", OTHER),
        ("organization_id", OTHER),
        ("namespace_id", OTHER),
        ("event_id", OTHER),
        ("payload_digest", "0" * 64),
        ("recovery_deadline", "2026-10-18T13:00:01Z"),
        ("admission_id", OTHER),
    ],
)
def test_status_cleaned_historical_join(status_case, monkeypatch, field, value):
    c = status_case
    found = committed(c)
    cleaned(c)
    wrong = found.model_copy(
        update={"source_receipt": found.source_receipt.model_copy(update={field: value})}
    )
    SourceHandoffLookup.model_validate(wrong, by_name=True)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: wrong)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).code == "unknown"


@pytest.mark.parametrize(
    "field,value", [("admission_id", OTHER), ("accepted_at", "2026-10-18T12:30:00.250000Z")]
)
def test_status_full_receipt_equality(status_case, monkeypatch, field, value):
    c = status_case
    found = committed(c)
    c.access._clock = lambda: NOW + timedelta(microseconds=500000)
    wrong = found.model_copy(
        update={"source_receipt": found.source_receipt.model_copy(update={field: value})}
    )
    SourceHandoffLookup.model_validate(wrong, by_name=True)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: wrong)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).code == "unknown"


@pytest.mark.parametrize(
    "where,error",
    [
        ("source", SourceStoreBusy),
        ("source", SourceStoreUnavailable),
        ("source", SourceStoreUncertain),
        ("source", SourceStoreConflict),
        ("source", RuntimeError),
        ("workflow", EventConflict),
        ("workflow", RuntimeError),
        ("workflow", SourceHandoffUnknown),
        ("workflow", EventBindingError),
        ("workflow", EventInputError),
        ("workflow", PackVersionError),
        ("workflow", AutomateLicenseError),
    ],
)
def test_status_error_mapping(status_case, monkeypatch, caplog, where, error):
    c = status_case
    problem = (
        error("SYNTHETIC-PRIVATE")
        if error is RuntimeError
        else error("fixed refusal")
        if error in (PackVersionError, AutomateLicenseError)
        else error()
    )

    def broken(**kw):
        raise problem

    monkeypatch.setattr(
        c.access if where == "source" else c.runtime,
        "observe_status" if where == "source" else "lookup_source_outcome",
        broken,
    )
    with status_only(c, monkeypatch):
        if error in (EventBindingError, EventInputError, PackVersionError, AutomateLicenseError):
            with pytest.raises(error) as caught:
                c.handoff.status(request=c.request)
            assert caught.value is problem
        else:
            found = c.handoff.status(request=c.request)
            assert found.code == (
                "conflict" if error in (SourceStoreConflict, EventConflict) else "unknown"
            )
            assert "SYNTHETIC-PRIVATE" not in cp.canonical_status_result(found).decode()
    assert "SYNTHETIC-PRIVATE" not in caplog.text


@pytest.mark.parametrize(
    "kind", ["host", "deployment", "incarnation", "owner", "binding", "license", "actions", "pack"]
)
def test_status_runtime_pins(status_case, monkeypatch, kind):
    from test_lead_receipt_vocabulary import workflow
    from test_lead_runtime_results import signed_workflow

    from connect_automate.automate.host import AutomateHost

    c = status_case
    if kind in ("host", "deployment"):
        monkeypatch.setattr(c.owner, "host_id" if kind == "host" else "organization_id", OTHER)
    elif kind == "incarnation":
        monkeypatch.setattr(c.access, "_incarnation", OTHER)
    elif kind == "owner":
        monkeypatch.setattr(c.access, "_store", store(c.owner.root))
    elif kind == "binding":
        monkeypatch.setattr(c.runtime, "_event_bindings", {})
    elif kind == "license":
        monkeypatch.setattr(AutomateHost, "licensed", lambda self: False)
    else:
        args, value = dict(c.args), workflow()
        if kind == "actions":
            value["definitions"][0]["actions"] = [
                dict(action="notify.local", request=dict(body="synthetic"))
            ]
        signed_workflow(args, value, version=2 if kind == "pack" else 1)
        monkeypatch.setattr(c.runtime, "_pack", PackRuntime.load(**args)._pack)
    monkeypatch.setattr(c.access, "observe_status", forbidden)
    with pytest.raises(AutomateLicenseError if kind == "license" else EventBindingError):
        c.handoff.status(request=c.request)


@pytest.mark.parametrize(
    "kind",
    ["dict", "applied", "extra", "schema", "actions", "record", "version", "not-found-record"],
)
def test_status_closed_lookup(status_case, monkeypatch, kind):
    c = status_case
    found = (
        c.runtime.lookup_source_outcome(
            binding="inbox",
            event_id=c.intent.scope.event_id,
            expected_payload_digest=c.upload.payload.capture.payload_digest,
        )
        if kind == "not-found-record"
        else committed(c)
    )
    changes = {
        "applied": {"workflow_applied": True},
        "extra": {"source_applied": False},
        "schema": {"schema_name": "lead.source.handoff.result"},
        "actions": {"actions": [dict(action_id=OTHER, kind="notify.local", status="pending")]},
        "record": {"workflow_record_id": None},
        "version": {"state_version": 0},
        "not-found-record": {"workflow_record_id": OTHER},
    }
    wrong = (
        found.model_dump(by_alias=True)
        if kind == "dict"
        else found.model_copy(update=changes[kind])
    )
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", lambda **kw: wrong)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).code == "unknown"


@pytest.mark.parametrize(
    "field,value",
    [
        ("handoff_id", OTHER),
        ("scope", None),
        ("capture", None),
        ("ever_custodied", 1),
        ("ever_custodied", False),
        ("closed", 0),
    ],
)
def test_status_custody_value_is_revalidated(status_case, monkeypatch, field, value):
    c = status_case
    facts = c.access.observe_status(request=c.request)
    wrong = replace(facts, custody=replace(facts.custody, **{field: value}))
    monkeypatch.setattr(c.access, "observe_status", lambda **kw: wrong)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
    assert c.handoff.status(request=c.request).code == "unknown"


@pytest.mark.parametrize(
    "kind",
    [
        "duck",
        "custody-duck",
        "retired-type",
        "retired-disposition",
        "admission",
        "availability",
        "clock",
        "revision",
    ],
)
def test_status_malformed_observation(status_case, monkeypatch, kind):
    c = status_case
    value = c.access.observe_status(request=c.request)
    wrong = (
        SimpleNamespace(**vars(value))
        if kind == "duck"
        else replace(
            value,
            **{
                "custody-duck": {"custody": SimpleNamespace(**vars(value.custody))},
                "retired-type": {"namespace_retired": 1},
                "retired-disposition": {"namespace_retired": True},
                "admission": {"admission_id": OTHER},
                "availability": {"content_state": "unknown"},
                "clock": {"observed_at": "2026-10-18T12:30:00Z"},
                "revision": {"custody": replace(value.custody, state_revision=False)},
            }[kind],
        )
    )
    monkeypatch.setattr(c.access, "observe_status", lambda **kw: wrong)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).code == "unknown"


@pytest.mark.parametrize(
    "sample", [None, False, 0, "", NOW.replace(tzinfo=None), NOW - timedelta(microseconds=1)]
)
def test_status_bad_clock_is_unknown(status_case, monkeypatch, sample):
    c = status_case
    c.access._clock = lambda: sample
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).code == "unknown"


@pytest.mark.parametrize("mode", ["cap", "encoder", "minimal"])
def test_status_encoding_failure_is_closed(status_case, monkeypatch, mode):
    import connect_automate.lead_intake.custody_handoff as module

    c = status_case
    committed(c)
    encode = module.canonical_status_result
    calls = []

    def broken(value):
        calls.append(value.status)
        if value.status == "resolved" or mode == "minimal":
            raise RuntimeError("SYNTHETIC-PRIVATE")
        return encode(value)

    if mode == "cap":
        # Real byte-cap failure, not a fabricated truncated result.
        monkeypatch.setattr(cp, "MAX_RESULT_BYTES", 200)
    else:
        monkeypatch.setattr(module, "canonical_status_result", broken)
    with status_only(c, monkeypatch):
        if mode == "minimal":
            with pytest.raises(SourceHandoffUnknown) as caught:
                c.handoff.status(request=c.request)
            assert caught.value.args == ("lead source handoff outcome unknown",)
            assert caught.value.__context__ is None and caught.value.__cause__ is None
        else:
            found = c.handoff.status(request=c.request)
            assert found.code == "unknown" and len(encode(found)) <= 200
    if mode != "cap":
        assert calls == ["resolved", "unresolved"]


@pytest.mark.parametrize("kind", ["missing", "replaced", "corrupt", "lost-content"])
def test_status_missing_storage_is_not_missing_intent(status_case, kind):
    c = status_case
    if kind in ("missing", "replaced"):
        c.owner.root.rename(c.owner.root.with_name("old-source"))
        if kind == "replaced":
            c.owner.root.mkdir(mode=0o700)
            store(c.owner.root).initialize(trust())
    elif kind == "corrupt":
        with database(c.owner.path) as db:
            tamper(
                db,
                "handoff_progress",
                "UPDATE source_handoffs SET reservation_expires_at='invalid'",
            )
    else:
        with database(c.owner.path) as db:
            db.execute("DELETE FROM source_content")
    assert c.handoff.status(request=c.request).code == "unknown"


def test_status_expiry_is_not_clock_floor_or_deletion(status_case, monkeypatch):
    c = status_case
    committed(c)
    content = SourceContent(c.owner, clock=lambda: NOW + timedelta(minutes=20))
    content.read_content(c.access.observe_status(request=c.request).admission_id)
    assert c.handoff.status(request=c.request).code == "unknown"
    admin = SourceClockAdmin(c.owner)
    admin.reconcile(
        operation_id=str(uuid4()), expected_sequence=admin.read().sequence, corrected_at=NOW
    )
    with status_only(c, monkeypatch):
        c.access._clock = lambda: datetime.fromisoformat(c.upload.payload.capture.recovery_deadline)
        assert c.handoff.status(request=c.request).unavailable_reason == "expired"
        c.access._clock = lambda: NOW
        assert c.handoff.status(request=c.request).content_state == "retained"
    SourceContent(c.owner, clock=lambda: NOW).purge_message(c.intent.payload.source, cutoff=NOW)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).unavailable_reason == "purged"


def test_status_preserves_original_workflow_stage(setup, monkeypatch):
    from test_automate_events import event_workflow
    from test_lead_receipt_vocabulary import workflow
    from test_lead_runtime_results import signed_workflow

    args, _, _ = setup
    value = workflow()
    value["definitions"].append(event_workflow()["definitions"][1])
    signed_workflow(args, value)
    c = status_case.__wrapped__(setup)
    prior = committed(c)
    c.runtime.submit_decision(
        prior.workflow_record_id,
        decision="approve",
        operation_key="later",
        request={},
        expected_version=prior.state_version,
        now=NOW,
    )
    assert args["store"].get_record(prior.workflow_record_id).stage == "completed"
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=c.request).workflow == prior


def test_status_absent_capture_does_not_adopt_bound_identity(status_case, monkeypatch):
    c = status_case
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", forbidden)
    with status_only(c, monkeypatch):
        assert c.handoff.status(request=status(c.intent)).code == "conflict"


@pytest.mark.parametrize(
    "field",
    [
        "handoff_id",
        "scope",
        "capture",
        "ever_custodied",
        "closed",
        "admission_id",
        "namespace_retired",
        "receipt",
        "content_state",
        "unavailable_reason",
    ],
)
def test_status_uncustodied_checks_independently(setup, monkeypatch, field):
    args, owner, _ = setup
    runtime = PackRuntime.load(**args)
    access = reader(owner, clock=lambda: NOW)
    # The bound projection replaces content_state with "unknown". Use it to
    # prove invalid source content is rejected before that information is lost.
    bound = field == "content_state"
    intent, upload, raw = prepare(runtime, access, phase="bound" if bound else "prepared")
    request = status(intent, upload if bound else None)
    value = access.observe_status(request=request)
    changes = dict(
        handoff_id=OTHER,
        scope=intent.scope.model_copy(update={"event_id": OTHER}),
        capture=upload.payload.capture,
        ever_custodied=0,
        closed=0,
    )
    if field == "receipt":
        # Keep the original never-custodied observation; introduce only a fully
        # valid receipt obtained from the real owner after that observation.
        access.bind_upload(upload)
        changes["receipt"] = access.admit_bound(upload, raw).receipt
    observation_changes = dict(
        admission_id=OTHER,
        namespace_retired=0,
        content_state="retained",
        unavailable_reason="purged",
    )
    wrong = (
        replace(value, custody=replace(value.custody, **{field: changes[field]}))
        if field in changes
        else replace(value, **{field: observation_changes[field]})
    )
    monkeypatch.setattr(access, "observe_status", lambda **kw: wrong)
    monkeypatch.setattr(runtime, "lookup_source_outcome", forbidden)
    with status_only(
        SimpleNamespace(args=args, owner=owner, runtime=runtime, access=access), monkeypatch
    ):
        found = composition(runtime, access, intent).status(request=request)
    assert found.status == "unresolved" and found.code == "unknown"


def test_status_missing_receipt_requires_retirement(status_case, monkeypatch):
    c = status_case
    expected = committed(c)
    value = c.access.observe_status(request=c.request)
    assert value.custody.ever_custodied is True and value.namespace_retired is False
    assert (
        value.custody.receipt is not None
        and value.admission_id == expected.source_receipt.admission_id
    )
    wrong = replace(value, custody=replace(value.custody, receipt=None))
    lookup, calls = c.runtime.lookup_source_outcome, []

    def looked_up(**kwargs):
        result = lookup(**kwargs)
        calls.append(result)
        return result

    monkeypatch.setattr(c.access, "observe_status", lambda **kw: wrong)
    monkeypatch.setattr(c.runtime, "lookup_source_outcome", looked_up)
    with status_only(c, monkeypatch):
        found = c.handoff.status(request=c.request)
    assert calls == [expected]  # Known history must not repair inconsistent source facts.
    assert found.status == "unresolved" and found.code == "unknown"
