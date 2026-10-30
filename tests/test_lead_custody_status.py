"""R3.5 first slice: precise values and source-owned, read-only observations."""

import sqlite3
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
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
from test_lead_source_admission import tamper
from test_lead_source_auth import NOW, OTHER, envelope, resign, trust
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake import custody_protocol as cp
from connect_automate.lead_intake.content import SourceContent
from connect_automate.lead_intake.source_store import (
    SourceClockAdmin,
    SourceStoreConflict,
    SourceStoreInputError,
    SourceStoreUnavailable,
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
    expected = SourceStoreUnavailable if kind == "missing" else SourceStoreConflict
    with pytest.raises(expected):
        access.observe_status(request=status(prepared, upload))
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
