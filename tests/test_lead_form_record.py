"""Offline synthetic parser and private record owner checks."""

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier, Event
from uuid import uuid4

import pytest
from test_lead_form_source import FORM_BYTES, form_envelope
from test_lead_source_auth import NOW, OTHER, encode, key, resign, trust, trust_data
from test_lead_source_store import database
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake import (
    SourceAuthenticationError,
    SourceStoreUnavailable,
    SourceTrustSnapshot,
    authenticate_source,
    parse_untrusted_source,
)


def facts(value=None, *, workflow_outcome="accepted", actions=(), signer=None):
    """Synthetic receipt projection for this owner-level slice."""
    from connect_automate.lead_intake.results import SourceHandoffResult

    value = form_envelope() if value is None else value
    raw = resign(value, signer)
    authority = trust_data(value)
    if signer is not None:
        authority["key_grants"][0]["public_key"] = signer.public_key().public_bytes_raw()
    verified = authenticate_source(
        raw, trust=SourceTrustSnapshot.model_validate(authority), now=NOW
    )
    payload = verified.source.payload
    accepted = workflow_outcome == "accepted"
    result = SourceHandoffResult.model_validate(
        dict(
            schema="lead.source.handoff.result",
            schema_version="2.0",
            source_receipt=dict(
                admission_id=str(uuid4()),
                host_id=verified.host_id,
                organization_id=verified.organization_id,
                namespace_id=verified.namespace_id,
                event_id=payload.event_id,
                payload_digest=verified.payload_digest,
                accepted_at=NOW.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                recovery_deadline=payload.retention.recovery_deadline,
            ),
            source_applied=True,
            workflow_outcome=workflow_outcome,
            workflow_applied=accepted,
            workflow_record_id=str(uuid4()) if accepted else None,
            workflow_event_id=str(uuid4()) if accepted else None,
            stage="New" if accepted else None,
            state_version=1 if accepted else None,
            actions=list(actions),
        )
    )
    return raw, result


def store(root, *, organization_id=None, owner_id=OTHER):
    from connect_automate.lead_intake.form_record import _LeadStore

    authority = trust()
    return _LeadStore(
        root / "leads.sqlite3",
        private_root=root,
        host_id=authority.host_id,
        organization_id=organization_id or authority.organization_id,
        owner_id=owner_id,
    )


def test_synthetic_form_writes_one_retrievable_private_record(private_root):
    writer = store(private_root)
    writer.initialize()
    raw, workflow = facts()
    reference = writer.commit(authorize=lambda: (raw, workflow))

    record = store(private_root).read(reference.lead_id)
    assert record.reference == reference
    assert record.source_receipt == workflow.source_receipt
    assert record.fields.model_dump() == {
        "name": "Zoë",
        "email": "synthetic@example.test",
        "message": "Hello 😀\r\n  Name: data\r\n",
    }
    assert record.review_state == "NEEDS_REVIEW"
    stages = writer.default_stages()
    assert [stage.label for stage in stages] == ["New", "In progress", "Closed"]
    assert record.stage_id == stages[0].stage_id
    assert record.stage_set_id == stages[0].stage_set_id
    assert (
        record.binding.part_sha256
        == form_envelope(FORM_BYTES)["payload"]["snapshot"]["part"]["sha256"]
    )


@pytest.mark.parametrize(
    ("body", "name", "email", "message"),
    [
        (b"Name:\nEmail:\nMessage:", "", "", ""),
        (
            b"Email: for review\nName:  A\nMessage:  X \nEmail: body",
            " A",
            "for review",
            " X \nEmail: body",
        ),
        (b"Name: A\r\nEmail: E\nMessage:\n  line\n", "A", "E", "\n  line\n"),
    ],
)
def test_line_structure_preserves_present_blanks_and_message(body, name, email, message):
    from connect_automate.lead_intake.form import parse_synthetic_form

    form = parse_untrusted_source(encode(form_envelope(body))).payload.snapshot
    assert parse_synthetic_form(form).model_dump() == {
        "name": name,
        "email": email,
        "message": message,
    }


@pytest.fixture
def writer(private_root):
    instance = store(private_root)
    instance.initialize()
    return instance


def dump(writer):
    with database(writer.path) as db:
        return tuple(db.iterdump())


@pytest.mark.parametrize(
    "body",
    [
        b"Name: A\nName: B\nMessage: body",
        b"Email: E\nEmail: F\nMessage: body",
        b"Name: A\nOther: E\nMessage: body",
        b"Name\nEmail: E\nMessage: body",
        b"Name: A\nEmail",
        b"Name: A\rZ\nEmail: E\nMessage: body",
        b"Name: A\nEmail: E",
        b"Name: A\nEmail: E\n",
        b"Name: A\nEmail: E\nMessage",
        b"Name: A\nEmail: E\nOther: body",
        b"Name: A\nEmail: E\n\nMessage: body",
        b"Name: A\nMessage: body",
        b"Email: E\nMessage: body",
        b"Name: A\nEmail: E\nExtra: X\nMessage: body",
    ],
)
def test_malformed_form_refused_without_record(writer, body):
    from connect_automate.lead_intake.form_record import LeadRecordRefused

    authorized = facts(form_envelope(body))
    before = dump(writer)
    with pytest.raises(LeadRecordRefused) as caught:
        writer.commit(authorize=lambda: authorized)
    assert caught.value.__context__ is None
    assert dump(writer) == before


def test_exact_and_changed_delivery_replay_keep_first_receipt(writer):
    first = facts()
    reference = writer.commit(authorize=lambda: first)
    original = writer.read(reference.lead_id)
    before = dump(writer)
    assert writer.commit(authorize=lambda: first) == reference

    changed = form_envelope()
    changed["payload"]["event_id"] = OTHER
    changed["payload"]["watcher_event_id"] = "d" * 64
    changed["authorization"]["key_id"] = OTHER
    rotated = facts(changed, signer=key(bytes(range(32))))
    assert rotated[1].source_receipt != original.source_receipt
    assert writer.commit(authorize=lambda: rotated) == reference
    assert writer.read(reference.lead_id) == original
    assert dump(writer) == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("namespace_id", OTHER),
        ("provider", "other-synthetic-provider"),
        ("account_id", "other-synthetic-account"),
        ("mailbox_identity_key", "1" * 64),
        ("message_id", "different-physical-message"),
    ],
)
def test_each_physical_source_component_participates_in_uniqueness(writer, field, value):
    original = facts()
    first = writer.commit(authorize=lambda: original)
    changed = form_envelope()
    changed["payload"]["source"][field] = value
    independent = facts(changed)
    second = writer.commit(authorize=lambda: independent)
    assert first != second
    assert writer.read(first.lead_id).fields == writer.read(second.lead_id).fields


def test_storage_enforces_physical_source_uniqueness(writer):
    authorized = facts()
    reference = writer.commit(authorize=lambda: authorized)
    before = dump(writer)
    record = writer.read(reference.lead_id).model_dump()
    record["reference"]["lead_id"] = str(uuid4())
    with (
        database(writer.path) as db,
        pytest.raises(
            sqlite3.IntegrityError, match="UNIQUE constraint failed: leads.organization_id"
        ),
    ):
        db.execute("INSERT INTO leads (record) VALUES (?)", (json.dumps(record),))
    assert dump(writer) == before


@pytest.mark.parametrize("change", ["part", "content"])
def test_conflicting_binding_preserves_original(writer, change):
    from connect_automate.lead_intake.form_record import LeadRecordConflict

    first = facts()
    writer.commit(authorize=lambda: first)
    before = dump(writer)
    value = form_envelope(FORM_BYTES + b"changed" if change == "content" else FORM_BYTES)
    if change == "part":
        value["payload"]["snapshot"]["part"]["part_id"] = "2"
    conflict = facts(value)
    with pytest.raises(LeadRecordConflict):
        writer.commit(authorize=lambda: conflict)
    assert dump(writer) == before


@pytest.mark.parametrize(
    "field,changed",
    [
        ("host_id", OTHER),
        ("organization_id", OTHER),
        ("namespace_id", OTHER),
        ("event_id", OTHER),
        ("payload_digest", "d" * 64),
        ("recovery_deadline", "2026-10-18T13:30:00Z"),
    ],
)
def test_mismatched_workflow_receipt_refused(writer, field, changed):
    from connect_automate.lead_intake.form_record import LeadRecordRefused

    raw, workflow = facts()
    receipt = workflow.source_receipt.model_copy(update={field: changed})
    workflow = workflow.model_copy(update={"source_receipt": receipt})
    before = dump(writer)
    with pytest.raises(LeadRecordRefused):
        writer.commit(authorize=lambda: (raw, workflow))
    assert dump(writer) == before


@pytest.mark.parametrize("change", ["legacy", "no_match", "actions", "source_host", "source_org"])
def test_ineligible_inputs_refused(writer, change):
    from test_lead_source_auth import envelope

    from connect_automate.lead_intake.form_record import LeadRecordRefused
    from connect_automate.lead_intake.source import payload_digest

    value = form_envelope()
    if change == "legacy":
        value = envelope()
    actions = ()
    if change == "actions":
        actions = (dict(action_id=OTHER, kind="notify.local", status="pending"),)
    raw, workflow = facts(
        value,
        workflow_outcome="no_match" if change == "no_match" else "accepted",
        actions=actions,
    )
    # Isolate the source-side scope check from the receipt copy and digest.
    if change in ("source_host", "source_org"):
        if change == "source_host":
            value["authorization"]["host_id"] = OTHER
        else:
            value["payload"]["organization_id"] = OTHER
        raw = resign(value)
        receipt = workflow.source_receipt.model_copy(
            update={"payload_digest": payload_digest(parse_untrusted_source(raw))}
        )
        workflow = workflow.model_copy(update={"source_receipt": receipt})
    before = dump(writer)
    with pytest.raises(LeadRecordRefused):
        writer.commit(authorize=lambda: (raw, workflow))
    assert dump(writer) == before


def test_scope_is_bound_and_defaults_survive_reopen(writer, private_root):
    before = dump(writer)
    stages = writer.default_stages()
    writer.initialize()
    assert store(private_root).default_stages() == stages
    assert dump(writer) == before
    for changes in ({"organization_id": OTHER}, {"owner_id": str(uuid4())}):
        foreign = store(private_root, **changes)
        with pytest.raises(SourceStoreUnavailable):
            foreign.default_stages()
    assert dump(writer) == before


def test_foreign_database_refused_without_writes(private_root):
    writer = store(private_root)
    with database(writer.path) as db:
        db.execute("CREATE TABLE unrelated (id TEXT)")
    if os.name != "nt":
        writer.path.chmod(0o600)
    before = dump(writer)
    with pytest.raises(SourceStoreUnavailable):
        writer.initialize()
    assert dump(writer) == before


@pytest.mark.parametrize("order", ["same-binding", "original-first", "changed-first"])
def test_independent_writers_serialize_on_one_physical_source(writer, private_root, order):
    from connect_automate.lead_intake.form_record import LeadRecordConflict

    original = facts()
    changed = facts(form_envelope(FORM_BYTES + b" competing"))
    first, second = (changed, original) if order == "changed-first" else (original, changed)
    if order == "same-binding":
        second = facts()
    entrant = Barrier(2, timeout=4)
    ready = Event()
    release = Event()

    def first_check():
        ready.set()
        assert release.wait(4)
        return first

    def run_second():
        entrant.wait()
        return store(private_root).commit(authorize=lambda: second)

    with ThreadPoolExecutor(2) as threads:
        first_write = threads.submit(writer.commit, authorize=first_check)
        try:
            assert ready.wait(4)
            second_write = threads.submit(run_second)
            entrant.wait()
        finally:
            release.set()
        ref = first_write.result(timeout=5)
        if order == "same-binding":
            assert second_write.result(timeout=5) == ref
        else:
            with pytest.raises(LeadRecordConflict):
                second_write.result(timeout=5)
    assert writer.read(ref.lead_id).source_receipt == first[1].source_receipt
    with database(writer.path) as db:
        assert db.execute("SELECT count(*) FROM leads").fetchone()[0] == 1


@pytest.mark.parametrize("already_committed", [False, True])
def test_authority_callback_runs_under_writer_lock_on_every_attempt(writer, already_committed):
    from connect_automate.lead_intake.form_record import LeadRecordRefused

    incoming = facts()
    if already_committed:
        writer.commit(authorize=lambda: incoming)
    before = dump(writer)

    def revoked():
        with (
            closing(sqlite3.connect(writer.path, timeout=0)) as competing,
            pytest.raises(sqlite3.OperationalError, match="database is locked"),
        ):
            competing.execute("BEGIN IMMEDIATE")
        raise SourceAuthenticationError()

    with pytest.raises(SourceAuthenticationError):
        writer.commit(authorize=revoked)
    assert dump(writer) == before

    def no_match():
        return facts(workflow_outcome="no_match")

    with pytest.raises(LeadRecordRefused):
        writer.commit(authorize=no_match)
    assert dump(writer) == before


def test_entire_opaque_source_key_is_compared(writer):
    left = form_envelope()
    right = form_envelope()
    left["payload"]["source"]["message_id"] = "é\x00left"
    right["payload"]["source"]["message_id"] = "é\x00right"
    first = writer.commit(authorize=lambda: facts(left))
    second = writer.commit(authorize=lambda: facts(right))
    assert first != second
    assert writer.commit(authorize=lambda: facts(left)) == first
    assert writer.commit(authorize=lambda: facts(right)) == second


def test_missing_initial_stage_refuses_instead_of_using_the_next_stage(writer):
    authorized = facts()
    with database(writer.path) as db:
        db.execute("DELETE FROM lead_stages WHERE position=0")
    before = dump(writer)
    with pytest.raises(SourceStoreUnavailable) as caught:
        writer.commit(authorize=lambda: authorized)
    assert caught.value.__context__ is None
    assert dump(writer) == before


def test_empty_store_requires_initialization(private_root):
    writer = store(private_root)
    writer._create()

    def unexpected_authorize():
        pytest.fail("uninitialized lead storage reached the authorization callback")

    with pytest.raises(SourceStoreUnavailable):
        writer.commit(authorize=unexpected_authorize)
    with pytest.raises(SourceStoreUnavailable):
        writer.default_stages()


def test_missing_scope_is_unavailable(writer):
    with database(writer.path) as db:
        db.execute("DELETE FROM lead_scope")
    with pytest.raises(SourceStoreUnavailable) as caught:
        writer.default_stages()
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("section", "field", "changed"),
    [
        (None, "fields_version", "2.0"),
        (None, "review_state", "APPROVED"),
        ("binding", "template_id", "unexpected"),
        ("binding", "part_id", ""),
        ("binding", "part_sha256", "bad"),
        ("fields", "name", 1),
        ("fields", "email", False),
        ("fields", "message", None),
        ("fields", "unknown", "private fixture"),
        ("reference", "lead_id", None),
    ],
)
def test_corrupt_record_fields_fail_closed(writer, section, field, changed):
    reference = writer.commit(authorize=facts)
    record = writer.read(reference.lead_id).model_dump()
    target = record if section is None else record[section]
    target[field] = changed
    raw = json.dumps(record)
    with database(writer.path) as db:
        if field == "lead_id":
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                db.execute("UPDATE leads SET record=?", (raw,))
            return
        db.execute("UPDATE leads SET record=?", (raw,))
    with pytest.raises(SourceStoreUnavailable) as caught:
        writer.read(reference.lead_id)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("key", ["stage_set_id", "stage_id", "reference.organization_id"])
def test_storage_enforces_scoped_stage_assignment(writer, key):
    reference = writer.commit(authorize=facts)
    record = writer.read(reference.lead_id).model_dump()
    if key == "reference.organization_id":
        record["reference"]["organization_id"] = str(uuid4())
    else:
        record[key] = str(uuid4())
    with (
        database(writer.path) as db,
        pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"),
    ):
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("UPDATE leads SET record=?", (json.dumps(record),))


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
def test_private_lead_writer_refuses_broad_root(private_root):
    writer = store(private_root)
    private_root.chmod(0o755)
    with pytest.raises(SourceStoreUnavailable):
        writer.initialize()
    assert not writer.path.exists()


@pytest.mark.parametrize("kind", ["template", "charset", "digest"])
def test_template_parser_revalidates_copied_snapshot(kind):
    from connect_automate.lead_intake.form import FormInputError, parse_synthetic_form

    snapshot = parse_untrusted_source(encode(form_envelope())).payload.snapshot
    if kind == "template":
        snapshot = snapshot.model_copy(update={"template_id": "another-template"})
    else:
        update = {"charset": "ascii"} if kind == "charset" else {"sha256": "0" * 64}
        snapshot = snapshot.model_copy(update={"part": snapshot.part.model_copy(update=update)})
    with pytest.raises(FormInputError):
        parse_synthetic_form(snapshot)


def test_lead_store_path_is_scoped_before_any_effect(private_root):
    from pathlib import Path

    from connect_automate.lead_intake.form_record import _LeadStore
    from connect_automate.lead_intake.source_store import SourceStoreInputError

    settings = dict(host_id=OTHER, organization_id=OTHER, owner_id=OTHER)
    cases = [
        (Path("private/leads.sqlite3"), Path("private")),
        (private_root.parent / "outside.sqlite3", private_root),
        (private_root / ".." / "outside.sqlite3", private_root / ".."),
    ]
    for path, root in cases:
        with pytest.raises(SourceStoreInputError):
            _LeadStore(path, private_root=root, **settings)


def test_lead_store_failure_after_insert_rolls_back(writer, monkeypatch):
    authorized = facts()
    before = dump(writer)
    original_check = writer._paths

    checks = 0

    def unavailable_at_commit(*args, **kwargs):
        nonlocal checks
        checks += 1
        if checks == 3:
            raise SourceStoreUnavailable()
        return original_check(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(writer, "_paths", unavailable_at_commit)
        with pytest.raises(SourceStoreUnavailable):
            writer.commit(authorize=lambda: authorized)
    assert dump(writer) == before
    assert writer.read(writer.commit(authorize=lambda: authorized).lead_id).source_receipt == (
        authorized[1].source_receipt
    )


def test_commit_acknowledgement_loss_returns_the_existing_lead(writer, monkeypatch):
    from connect_automate.lead_intake.source_store import SourceStoreUncertain

    authorized = facts()
    connect = sqlite3.connect

    class LostAcknowledgement(sqlite3.Connection):
        def commit(self):
            super().commit()
            raise sqlite3.OperationalError("synthetic lost acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(
            sqlite3,
            "connect",
            lambda *args, **kwargs: connect(*args, **kwargs, factory=LostAcknowledgement),
        )
        with pytest.raises(SourceStoreUncertain) as caught:
            writer.commit(authorize=lambda: authorized)
    assert caught.value.__context__ is None
    before = dump(writer)
    reference = writer.commit(authorize=lambda: authorized)
    assert writer.read(reference.lead_id).source_receipt == authorized[1].source_receipt
    assert dump(writer) == before
