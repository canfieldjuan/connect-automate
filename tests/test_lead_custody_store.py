"""R2 migration and metadata-only observation, with synthetic source evidence."""

import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from test_lead_custody_protocol import capture, request
from test_lead_source_admission import tamper
from test_lead_source_auth import NOW, OTHER, encode, envelope, resign, trust
from test_lead_source_store import database, next_snapshot, store
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake.admission import SourceAdmission, SourceReceipt
from connect_automate.lead_intake.content import SourceContent
from connect_automate.lead_intake.custody_protocol import (
    CaptureReference,
    ScopeReference,
    canonical_request,
    parse_untrusted_request,
)
from connect_automate.lead_intake.custody_store import SourceCustodyStore
from connect_automate.lead_intake.source import (
    SourceIdentity,
    canonical_source,
    parse_untrusted_source,
    payload_digest,
)
from connect_automate.lead_intake.source_store import (
    SourceStoreConflict,
    SourceStoreInputError,
    SourceStoreUnavailable,
    _encode,
    _handoff_state,
    _stored_request,
)

V4 = Path(__file__).parent / "fixtures" / "lead_source_admission" / "v4-source-schema.sql"


def legacy(root):
    owner = store(root)
    owner._create()
    with database(owner.path) as db:
        db.executescript(V4.read_text(encoding="utf-8"))
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            "INSERT INTO deployment VALUES (1, ?, ?)", (owner.host_id, owner.organization_id)
        )
        raw = _encode(trust())
        db.execute(
            "INSERT INTO authority_history VALUES (1, ?, ?)",
            (raw, hashlib.sha256(raw.encode()).hexdigest()),
        )
    return owner


def snapshot(owner):
    with database(owner.path) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: db.execute(f'SELECT * FROM "{t}"').fetchall() for t in sorted(tables)}


def test_explicit_v4_migration_preserves_rows(private_root):
    owner = legacy(private_root)
    before = snapshot(owner)
    result = owner.migrate()
    assert result.applied is True
    after = snapshot(owner)
    assert {name: after[name] for name in before} == before
    assert owner.migrate().applied is False
    assert owner.read_incarnation() == result.incarnation


def test_new_initialization_has_incarnation(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    with database(owner.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
    first = owner.read_incarnation()
    assert store(private_root).read_incarnation() == first


def seed_legacy(owner, *, purged=False, value=None):
    value = value or envelope()
    parsed = parse_untrusted_source(encode(value))
    raw = canonical_source(parsed)
    payload = parsed.payload
    receipt = SourceReceipt.model_validate(
        dict(
            schema="lead.source.receipt",
            schema_version="1.0",
            admission_id=str(uuid4()),
            host_id=owner.host_id,
            organization_id=owner.organization_id,
            namespace_id=payload.source.namespace_id,
            event_id=payload.event_id,
            payload_digest=payload_digest(parsed),
            accepted_at="2026-10-18T12:30:00.000000Z",
            key_id=parsed.authorization.key_id,
            trust_generation=1,
            policy_id=payload.retention.policy_id,
            policy_version=payload.retention.policy_version,
            recovery_deadline=payload.retention.recovery_deadline,
        )
    )
    with database(owner.path) as db:
        db.execute(
            "INSERT INTO source_receipts VALUES (?, ?, ?, ?, ?, ?)",
            (
                receipt.admission_id,
                receipt.organization_id,
                receipt.namespace_id,
                receipt.event_id,
                encode(receipt.model_dump(by_alias=True)).decode(),
                hashlib.sha256(raw).hexdigest(),
            ),
        )
        db.execute(
            "INSERT INTO source_custody VALUES (?, ?, ?, ?)",
            (
                receipt.admission_id,
                encode(payload.source.model_dump()).decode(),
                payload.snapshot.captured_at,
                "purged" if purged else "retained",
            ),
        )
        if not purged:
            db.execute("INSERT INTO source_content VALUES (?, ?)", (receipt.admission_id, raw))
        db.execute(
            "INSERT INTO authority_clock_history VALUES (1,'sample',NULL,?,1,NULL)",
            (receipt.accepted_at,),
        )
    return receipt, raw


def reader(owner, **changes):
    options = dict(
        expected_incarnation=owner.read_incarnation(),
        max_handoffs=10,
        max_mutation_records=30,
        max_reservation_seconds=3600,
    )
    options.update(changes)
    return SourceCustodyStore(owner, **options)


def lookup(access, value=None, **changes):
    parsed = parse_untrusted_source(encode(value or envelope()))
    args = dict(
        identity=parsed.payload.source,
        event_id=parsed.payload.event_id,
        payload_digest=payload_digest(parsed),
        envelope_sha256=hashlib.sha256(canonical_source(parsed)).hexdigest(),
    )
    args.update(changes)
    return access.lookup_receipt(**args)


def seeded(root):
    owner = store(root)
    owner.initialize(trust())
    receipt = SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope())).receipt
    return owner, receipt


def managed(root, phase="prepared", closed=False):
    """Synthetic final rows only; intentionally no operational register API."""
    owner = store(root)
    owner.initialize(trust())
    value = envelope()
    payload = value["payload"]
    data = request(value=value)
    data.update(handoff_id=str(uuid4()), control_id=str(uuid4()), job_id=str(uuid4()))
    data["scope"].update(
        host_id=owner.host_id,
        organization_id=owner.organization_id,
        namespace_id=payload["source"]["namespace_id"],
        event_id=payload["event_id"],
    )
    data["payload"].update(
        rule_id=payload["trigger"]["rule_id"],
        rule_version=payload["trigger"]["rule_version"],
        policy_id=payload["retention"]["policy_id"],
        policy_version=payload["retention"]["policy_version"],
    )
    prepared = parse_untrusted_request(encode(data))
    intent = canonical_request(prepared).decode()
    cap = capture(value) if phase != "prepared" else None
    receipt = (
        SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(value)).receipt
        if phase == "custodied"
        else None
    )
    revision = 1 + int(cap is not None) + int(receipt is not None) + int(closed)
    incarnation = owner.read_incarnation()
    with database(owner.path) as db:
        s = prepared.scope
        db.execute(
            "INSERT INTO source_handoffs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                prepared.handoff_id,
                incarnation,
                s.host_id,
                s.organization_id,
                s.namespace_id,
                s.event_id,
                s.route_digest,
                prepared.enrolled_machine_id,
                intent,
                hashlib.sha256(intent.encode()).hexdigest(),
                "2026-10-18T13:00:00Z",
                encode(cap).decode() if cap else None,
                2 if closed else 1,
                revision,
                int(closed),
                receipt.admission_id if receipt else None,
                int(receipt is not None),
            ),
        )
        db.execute(
            "INSERT INTO source_handoff_operations VALUES (?,?,?,?,?,?,?,?)",
            (
                prepared.control_id,
                prepared.job_id,
                prepared.handoff_id,
                "prepare",
                intent,
                hashlib.sha256(intent.encode()).hexdigest(),
                "prepared",
                1,
            ),
        )
        if cap is not None:
            upload = prepared.model_dump()
            upload.update(
                operation="upload",
                expected_fence_generation=1,
                control_id=str(uuid4()),
                job_id=str(uuid4()),
                payload={"capture": cap},
            )
            raw = canonical_request(parse_untrusted_request(encode(upload))).decode()
            db.execute(
                "INSERT INTO source_handoff_operations VALUES (?,?,?,?,?,?,?,?)",
                (
                    upload["control_id"],
                    upload["job_id"],
                    prepared.handoff_id,
                    "upload",
                    raw,
                    hashlib.sha256(raw.encode()).hexdigest(),
                    "admitted" if receipt else "bound",
                    3 if receipt else 2,
                ),
            )
    return owner, prepared, cap, receipt


def observe(access, prepared, cap=None, **changes):
    args = dict(
        handoff_id=prepared.handoff_id,
        scope=prepared.scope,
        enrolled_machine_id=prepared.enrolled_machine_id,
        capture=CaptureReference.model_validate(cap) if cap else None,
    )
    args.update(changes)
    return access.observe(**args)


@pytest.mark.parametrize("purged", [False, True])
def test_populated_migration_keeps_every_old_row(private_root, purged):
    owner = legacy(private_root)
    receipt, _ = seed_legacy(owner, purged=purged)
    before = snapshot(owner)
    assert owner.migrate().applied
    after = snapshot(owner)
    assert {name: after[name] for name in before} == before
    assert lookup(reader(owner)).receipt == receipt
    assert lookup(reader(owner)).state == ("purged" if purged else "retained")


@pytest.mark.parametrize("operation", ["initialize", "authority", "incarnation", "lookup"])
def test_ordinary_calls_never_migrate(private_root, operation):
    owner = legacy(private_root)
    before = snapshot(owner)
    access = SourceCustodyStore(
        owner,
        expected_incarnation=OTHER,
        max_handoffs=1,
        max_mutation_records=3,
        max_reservation_seconds=1,
    )
    calls = dict(
        initialize=lambda: owner.initialize(trust()),
        authority=owner.read_authority,
        incarnation=owner.read_incarnation,
        lookup=lambda: lookup(access),
    )
    with pytest.raises(SourceStoreUnavailable):
        calls[operation]()
    assert snapshot(owner) == before
    with database(owner.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4


@pytest.mark.parametrize("damage", ["older", "future", "extra", "missing", "foreign", "empty"])
def test_migration_exact_preflight_no_changes(private_root, damage):
    owner = legacy(private_root)
    with database(owner.path) as db:
        if damage in ("older", "future", "empty"):
            db.execute(f"PRAGMA user_version={dict(older=3, future=6, empty=0)[damage]}")
        elif damage == "extra":
            db.execute("CREATE TABLE impostor (id TEXT)")
        elif damage == "missing":
            db.execute("DROP TRIGGER history_no_update")
        elif damage == "foreign":
            tamper(db, "deployment_no_update", "UPDATE deployment SET host_id=?", (OTHER,))
    before = snapshot(owner)
    with pytest.raises(SourceStoreUnavailable):
        owner.migrate()
    assert snapshot(owner) == before


@pytest.mark.parametrize("damage", ["body", "missing-body", "orphan", "clock", "lifecycle"])
def test_migration_validates_existing_rows_before_ddl(private_root, damage):
    owner = legacy(private_root)
    receipt, raw = seed_legacy(owner)
    with database(owner.path) as db:
        if damage == "body":
            tamper(db, "content_no_update", "UPDATE source_content SET envelope=?", (b"wrong",))
        elif damage == "missing-body":
            db.execute("DELETE FROM source_content")
        elif damage == "orphan":
            db.execute("INSERT INTO source_content VALUES (?,?)", (OTHER, raw))
        elif damage == "clock":
            tamper(db, "clock_no_update", "UPDATE authority_clock_history SET new_floor='bad'")
        else:
            db.execute("INSERT INTO source_retired VALUES (?,?)", (receipt.namespace_id, "bad"))
    before = snapshot(owner)
    with pytest.raises(SourceStoreUnavailable) as error:
        owner.migrate()
    assert error.value.__cause__ is None and error.value.__context__ is None
    assert snapshot(owner) == before


@pytest.mark.parametrize("phase", ["prepared", "bound", "custodied"])
@pytest.mark.parametrize("closed", [False, True])
def test_observe_source_facts_without_wire_or_body(private_root, phase, closed):
    owner, prepared, cap, receipt = managed(private_root, phase, closed)
    before = snapshot(owner)
    facts = observe(reader(owner), prepared, cap)
    assert facts.handoff_id == prepared.handoff_id
    assert facts.closed is closed and facts.fence_generation == (2 if closed else 1)
    assert facts.receipt == receipt
    assert facts.ever_custodied is (receipt is not None)
    assert facts.content_state == ("retained" if receipt else "not_received")
    assert snapshot(owner) == before
    assert not hasattr(facts, "workflow") and not hasattr(facts, "observed_at")


def test_query_only_does_not_read_authenticate_or_expire_body(private_root, monkeypatch):
    owner, receipt = seeded(private_root)
    access = reader(owner)
    authority = next_snapshot(key_grants=[])
    owner.publish_authority(authority, expected_generation=1)
    before = snapshot(owner)

    def forbidden(*args, **kwargs):
        pytest.fail("metadata observation invoked a mutation/body/authentication owner")

    from connect_automate.lead_intake import admission, source_store

    monkeypatch.setattr(admission, "authenticate_source", forbidden)
    monkeypatch.setattr(source_store.SourceStore, "_transaction", forbidden)
    monkeypatch.setattr(source_store.SourceStore, "_check_clock", forbidden)
    assert lookup(access).receipt == receipt
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT envelope FROM source_content",
        "UPDATE source_content SET envelope=x'00'",
        "PRAGMA query_only=OFF",
        "COMMIT",
        "BEGIN IMMEDIATE",
        "CREATE TABLE forbidden (x)",
        "ATTACH ':memory:' AS forbidden",
    ],
    ids=["body", "write", "pragma", "commit", "begin", "ddl", "attach"],
)
def test_snapshot_denies_body_and_mutation(private_root, sql):
    owner, _ = seeded(private_root)
    before = snapshot(owner)
    with pytest.raises(SourceStoreUnavailable) as error, owner._read_snapshot() as db:
        db.execute(sql)
    assert error.value.__cause__ is None and error.value.__context__ is None
    assert snapshot(owner) == before


def test_live_wal_snapshot_spans_concurrent_commit(private_root):
    owner, prepared, _, _ = managed(private_root)
    with owner._read_snapshot() as db:
        before = owner._handoff_metadata(db, prepared.handoff_id)[0]
        with database(owner.path) as writer:
            writer.execute("UPDATE source_handoffs SET closed=1,generation=2,revision=2")
        assert owner._handoff_metadata(db, prepared.handoff_id)[0] == before
    assert observe(reader(owner), prepared).closed is True


def test_purge_and_retired_cleanup_keep_historical_unknown(private_root):
    owner, prepared, cap, receipt = managed(private_root, "custodied", True)
    access = reader(owner)
    content = SourceContent(owner, clock=lambda: NOW)
    content.purge_message(prepared.payload.source, cutoff=NOW)
    assert observe(access, prepared, cap).content_state == "purged"
    content.retire_namespace(prepared.scope.namespace_id)
    content.cleanup_retired(prepared.scope.namespace_id, limit=1)
    facts = observe(access, prepared, cap)
    assert facts.ever_custodied is True and facts.closed is True
    assert facts.receipt is None and facts.content_state == "unknown"
    assert receipt is not None


def test_retained_missing_body_is_not_invented_purge(private_root):
    owner, prepared, cap, _ = managed(private_root, "custodied")
    with database(owner.path) as db:
        db.execute("DELETE FROM source_content")
    with pytest.raises(SourceStoreUnavailable):
        observe(reader(owner), prepared, cap)


def test_blob_corruption_is_not_claimed_detected_by_metadata(private_root):
    owner, receipt = seeded(private_root)
    with database(owner.path) as db:
        tamper(db, "content_no_update", "UPDATE source_content SET envelope=?", (b"bad",))
    assert lookup(reader(owner)).receipt == receipt
    with pytest.raises(SourceStoreUnavailable):
        SourceContent(owner, clock=lambda: NOW).read_content(receipt.admission_id)


@pytest.mark.parametrize(
    "field",
    [
        "host_id",
        "organization_id",
        "namespace_id",
        "event_id",
        "route_digest",
        "machine",
        "capture",
        "handoff",
    ],
)
def test_observation_mixed_references_refuse_or_not_found(private_root, field):
    owner, prepared, cap, _ = managed(private_root, "bound")
    changes = {}
    if field == "machine":
        changes["enrolled_machine_id"] = str(uuid4())
    elif field == "capture":
        changes["capture"] = CaptureReference.model_validate(dict(cap, payload_digest="0" * 64))
    elif field == "handoff":
        assert observe(reader(owner), prepared, handoff_id=str(uuid4())) is None
        return
    else:
        data = prepared.scope.model_dump()
        data[field] = "0" * 64 if field == "route_digest" else str(uuid4())
        changes["scope"] = ScopeReference.model_validate(data)
    with pytest.raises(SourceStoreConflict):
        observe(reader(owner), prepared, **changes)


@pytest.mark.parametrize("field", ["payload_digest", "envelope_sha256", "identity"])
def test_legacy_lookup_compares_exact_pair_and_identity(private_root, field):
    owner, _ = seeded(private_root)
    value = "0" * 64
    if field == "identity":
        data = envelope()["payload"]["source"]
        data["account_id"] = "other"
        value = SourceIdentity.model_validate(data)
    with pytest.raises(SourceStoreConflict):
        lookup(reader(owner), **{field: value})


@pytest.mark.parametrize(
    "field", ["max_handoffs", "max_mutation_records", "max_reservation_seconds"]
)
@pytest.mark.parametrize("value", [0, False, "", None, -1, 2147483648, 1.5])
def test_constructor_has_no_unbounded_default(private_root, field, value):
    owner, _ = seeded(private_root)
    with pytest.raises(SourceStoreInputError):
        reader(owner, **{field: value})


@pytest.mark.parametrize("value", [1, 2147483647])
def test_constructor_accepts_closed_positive_boundaries(private_root, value):
    owner, _ = seeded(private_root)
    assert (
        lookup(
            reader(
                owner, max_handoffs=value, max_mutation_records=value, max_reservation_seconds=value
            )
        )
        is not None
    )


def test_old_binding_refuses_new_incarnation(private_root):
    owner, _ = seeded(private_root)
    old = owner.read_incarnation()
    with database(owner.path) as db:
        tamper(
            db,
            "incarnation_no_update",
            "UPDATE source_store_identity SET incarnation=?",
            (str(uuid4()),),
        )
    with pytest.raises(SourceStoreConflict):
        lookup(reader(owner, expected_incarnation=old))


def test_new_database_at_same_path_refuses_old_binding(private_root):
    owner, _ = seeded(private_root)
    access = reader(owner)
    owner.path.rename(private_root / "preserved.sqlite3")
    owner.initialize(trust())
    with pytest.raises(SourceStoreConflict):
        lookup(access)


def test_unavailable_body_migration_keeps_original_envelope(private_root):
    owner = legacy(private_root)
    value = envelope()
    value["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": "source_gone"}
    value = json.loads(resign(value))
    receipt, raw = seed_legacy(owner, value=value)
    owner.migrate()
    assert lookup(reader(owner), value).receipt == receipt
    assert SourceContent(owner, clock=lambda: NOW).read_content(receipt.admission_id) == raw


@pytest.mark.parametrize("missing", [False, True])
def test_migration_never_bootstraps_empty_or_missing_file(private_root, missing):
    owner = store(private_root)
    if not missing:
        owner._create()
    with pytest.raises(SourceStoreUnavailable):
        owner.migrate()
    assert owner.path.exists() is not missing
    if not missing:
        assert owner.path.read_bytes() == b""


def test_version_check_is_independent_of_exact_object_check(private_root):
    owner, _ = seeded(private_root)
    with database(owner.path) as db:
        db.execute("PRAGMA user_version=6")
    with pytest.raises(SourceStoreUnavailable):
        owner.migrate()


def assert_storage_refusal(call):
    failure = None
    try:
        call()
    except Exception as error:
        failure = error
    assert type(failure) is SourceStoreUnavailable, "corrupt metadata did not fail closed"
    assert str(failure) == "lead source store unavailable"
    assert failure.__cause__ is None and failure.__context__ is None


def inspect_handoff(owner, prepared):
    with owner._read_snapshot() as db:
        return owner._handoff_metadata(db, prepared.handoff_id)


@pytest.mark.parametrize(
    "field",
    [
        "host_id",
        "organization_id",
        "namespace_id",
        "event_id",
        "route_digest",
        "enrolled_machine_id",
        "incarnation",
        "intent_sha256",
        "reservation_expires_at",
    ],
)
def test_each_handoff_index_is_compared_with_canonical_owner(private_root, field):
    owner, prepared, _, _ = managed(private_root)
    changed = "0" * 64 if field in ("route_digest", "intent_sha256") else str(uuid4())
    if field == "reservation_expires_at":
        changed = "not-a-time"
    with database(owner.path) as db:
        tamper(db, "handoff_progress", f"UPDATE source_handoffs SET {field}=?", (changed,))
    assert_storage_refusal(lambda: inspect_handoff(owner, prepared))


@pytest.mark.parametrize(
    "case",
    [
        "intent-kind",
        "intent-canonical",
        "capture-canonical",
        "capture-deadline",
        "generation",
        "revision-max",
        "revision-progress",
        "capture-link",
        "missing-prepare",
        "missing-upload",
        "unowned-receipt",
        "receipt-link",
        "erased-live",
    ],
)
def test_handoff_metadata_guards(private_root, case):
    owner, prepared, cap, receipt = managed(private_root, "custodied", True)
    with database(owner.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        if case.startswith("intent-"):
            value = prepared.model_dump()
            if case == "intent-kind":
                value.update(
                    operation="status", expected_fence_generation=2, payload={"capture": cap}
                )
            raw = (
                json.dumps(value, indent=2)
                if case == "intent-canonical"
                else encode(value).decode()
            )
            tamper(
                db,
                "handoff_progress",
                "UPDATE source_handoffs SET intent=?,intent_sha256=?",
                (raw, hashlib.sha256(raw.encode()).hexdigest()),
            )
        elif case == "capture-canonical":
            tamper(
                db,
                "handoff_progress",
                "UPDATE source_handoffs SET capture=?",
                (json.dumps(cap, indent=2),),
            )
        elif case == "capture-deadline":
            tamper(
                db,
                "handoff_progress",
                "UPDATE source_handoffs SET reservation_expires_at=?",
                (cap["captured_at"],),
            )
        elif case in ("generation", "revision-max", "revision-progress", "capture-link"):
            sql = {
                "generation": "generation=1",
                "revision-max": "revision=2147483648",
                "revision-progress": "revision=2",
                "capture-link": "capture=NULL",
            }[case]
            tamper(db, "handoff_progress", "UPDATE source_handoffs SET " + sql)
        elif case.startswith("missing-"):
            kind = case.removeprefix("missing-")
            tamper(
                db,
                "operation_no_delete",
                "DELETE FROM source_handoff_operations WHERE kind=?",
                (kind,),
            )
        elif case == "receipt-link":
            tamper(db, "handoff_progress", "UPDATE source_handoffs SET admission_id=?", (OTHER,))
        elif case == "unowned-receipt":
            tamper(
                db,
                "handoff_progress",
                "UPDATE source_handoffs SET admission_id=NULL,ever_custodied=0",
            )
            tamper(
                db,
                "operation_progress",
                "UPDATE source_handoff_operations SET phase='bound' WHERE kind='upload'",
            )
        elif case == "erased-live":
            tamper(db, "receipt_no_delete", "DELETE FROM source_receipts")
            tamper(db, "custody_no_delete", "DELETE FROM source_custody")
            db.execute("DELETE FROM source_content")
    assert receipt is not None
    assert_storage_refusal(lambda: inspect_handoff(owner, prepared))


@pytest.mark.parametrize(
    "case",
    [
        "hash",
        "canonical",
        "control",
        "job",
        "kind",
        "scope",
        "machine",
        "handoff",
        "revision-low",
        "revision-high",
        "prepare-fingerprint",
        "prepare-phase",
        "prepare-revision",
        "upload-capture",
        "upload-generation",
        "upload-phase",
        "upload-revision",
    ],
)
def test_each_operation_guard_has_its_own_corruption(private_root, case):
    owner, prepared, cap, _ = managed(private_root, "custodied", True)
    kind = "prepare" if case.startswith("prepare-") else "upload"
    with database(owner.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        row = db.execute(
            "SELECT request FROM source_handoff_operations WHERE kind=?", (kind,)
        ).fetchone()
        value = json.loads(row[0])
        if case == "hash":
            field, changed = "request_sha256", "0" * 64
        elif case == "canonical":
            field, changed = "request", json.dumps(value, indent=2)
        elif case in ("control", "job"):
            field, changed = case + "_id", str(uuid4())
        elif case == "kind":
            field, changed = "kind", "status"
        elif case == "revision-low":
            field, changed = "revision", 0
        elif case == "revision-high":
            field, changed = "revision", 5
        elif case.endswith("-phase"):
            field, changed = "phase", "bound" if kind == "upload" else "closed"
        elif case.endswith("-revision"):
            field, changed = "revision", 2
        else:
            field = "request"
            if case == "scope":
                value["scope"]["event_id"] = str(uuid4())
            elif case == "machine":
                value["enrolled_machine_id"] = str(uuid4())
            elif case == "handoff":
                value["handoff_id"] = str(uuid4())
            elif case == "prepare-fingerprint":
                value["proof_reference"] = str(uuid4())
            elif case == "upload-capture":
                value["payload"]["capture"]["snapshot_id"] = str(uuid4())
            elif case == "upload-generation":
                value["expected_fence_generation"] = 2
            changed = encode(value).decode()
        tamper(
            db,
            "operation_progress",
            f"UPDATE source_handoff_operations SET {field}=? WHERE kind=?",
            (changed, kind),
        )
        if field == "request":
            tamper(
                db,
                "operation_progress",
                "UPDATE source_handoff_operations SET request_sha256=? WHERE kind=?",
                (hashlib.sha256(changed.encode()).hexdigest(), kind),
            )
    assert_storage_refusal(lambda: inspect_handoff(owner, prepared))


@pytest.mark.parametrize(
    "field",
    [
        "envelope_sha256",
        "payload_digest",
        "identity",
        "captured_at",
        "recovery_deadline",
        "policy_id",
        "policy_version",
    ],
)
def test_receipt_link_checks_are_independent(private_root, field):
    owner, prepared, cap, receipt = managed(private_root, "custodied", True)
    with database(owner.path) as db:
        if field == "envelope_sha256":
            tamper(
                db, "receipt_no_update", "UPDATE source_receipts SET envelope_sha256=?", ("0" * 64,)
            )
        elif field == "identity":
            data = prepared.payload.source.model_dump()
            data["message_id"] = "other"
            tamper(
                db,
                "custody_identity_no_update",
                "UPDATE source_custody SET identity=?",
                (encode(data).decode(),),
            )
        elif field == "captured_at":
            tamper(
                db,
                "custody_identity_no_update",
                "UPDATE source_custody SET captured_at='2026-10-18T12:00:01Z'",
            )
        else:
            data = receipt.model_dump(by_alias=True)
            data[field] = {
                "payload_digest": "0" * 64,
                "recovery_deadline": "2026-10-18T13:30:00Z",
                "policy_id": OTHER,
                "policy_version": 2,
            }[field]
            tamper(
                db,
                "receipt_no_update",
                "UPDATE source_receipts SET receipt=?",
                (encode(data).decode(),),
            )
    assert_storage_refusal(lambda: inspect_handoff(owner, prepared))


def test_snapshot_body_prohibition_also_applies_to_expressions(private_root):
    owner, _ = seeded(private_root)
    with pytest.raises(SourceStoreUnavailable), owner._read_snapshot() as db:
        db.execute("SELECT length(envelope) FROM source_content").fetchall()


def test_snapshot_attach_cannot_create_file(private_root):
    owner, _ = seeded(private_root)
    target = private_root / "side-effect.sqlite3"
    with pytest.raises(SourceStoreUnavailable), owner._read_snapshot() as db:
        db.execute("ATTACH ? AS forbidden", (str(target),))
    assert not target.exists()


@pytest.mark.parametrize("target", ["scope", "capture", "identity", "incarnation"])
def test_copied_or_missing_inputs_cannot_bypass_validation(private_root, target):
    owner, prepared, cap, _ = managed(private_root, "bound")
    access = reader(owner)
    with pytest.raises(SourceStoreInputError) as error:
        if target == "scope":
            observe(access, prepared, scope=prepared.scope.model_copy(update={"event_id": False}))
        elif target == "capture":
            observe(
                access,
                prepared,
                capture=CaptureReference.model_validate(cap).model_copy(
                    update={"artifact_size": False}
                ),
            )
        elif target == "identity":
            lookup(access, identity=prepared.payload.source.model_copy(update={"message_id": ""}))
        else:
            reader(owner, expected_incarnation=None)
    assert error.value.__cause__ is None and error.value.__context__ is None


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE source_store_identity SET incarnation='other'",
        "DELETE FROM source_store_identity",
        "DELETE FROM source_handoffs",
        "UPDATE source_handoffs SET closed=0,generation=1,revision=5",
        "UPDATE source_handoffs SET capture=NULL,revision=5",
        "UPDATE source_handoffs SET admission_id=NULL,ever_custodied=0,revision=5",
        "UPDATE source_handoffs SET revision=4",
        "DELETE FROM source_handoff_operations",
        "UPDATE source_handoff_operations SET job_id='other'",
        "UPDATE source_handoff_operations SET phase='bound' WHERE kind='upload'",
    ],
    ids=[
        "inc-edit",
        "inc-delete",
        "handoff-delete",
        "reopen",
        "capture-clear",
        "receipt-clear",
        "revision",
        "op-delete",
        "job-edit",
        "phase-regress",
    ],
)
def test_storage_history_is_irreversible(private_root, sql):
    owner, _, _, _ = managed(private_root, "custodied", True)
    before = snapshot(owner)
    with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)
    assert snapshot(owner) == before


@pytest.mark.parametrize("case", ["missing", "invalid"])
def test_incarnation_corruption_is_unavailable(private_root, case):
    owner, _ = seeded(private_root)
    with database(owner.path) as db:
        if case == "missing":
            tamper(db, "incarnation_no_delete", "DELETE FROM source_store_identity")
        else:
            tamper(
                db, "incarnation_no_update", "UPDATE source_store_identity SET incarnation='bad'"
            )
    assert_storage_refusal(owner.read_incarnation)


@pytest.mark.parametrize(
    "case",
    [
        "receipt-canonical",
        "receipt-index",
        "custody-missing",
        "identity-canonical",
        "identity-namespace",
        "capture-future",
        "hash-invalid",
        "purged-with-blob",
        "history-missing",
    ],
)
def test_shared_receipt_metadata_guards_without_body(private_root, case):
    owner, receipt = seeded(private_root)
    with database(owner.path) as db:
        if case == "receipt-canonical":
            tamper(
                db,
                "receipt_no_update",
                "UPDATE source_receipts SET receipt=?",
                (json.dumps(receipt.model_dump(by_alias=True), indent=2),),
            )
        elif case == "receipt-index":
            value = receipt.model_dump(by_alias=True)
            value["event_id"] = str(uuid4())
            tamper(
                db,
                "receipt_no_update",
                "UPDATE source_receipts SET receipt=?",
                (encode(value).decode(),),
            )
        elif case == "custody-missing":
            tamper(db, "custody_no_delete", "DELETE FROM source_custody")
        elif case.startswith("identity-"):
            value = envelope()["payload"]["source"]
            if case == "identity-namespace":
                value["namespace_id"] = str(uuid4())
            raw = (
                json.dumps(value, indent=2)
                if case == "identity-canonical"
                else encode(value).decode()
            )
            tamper(db, "custody_identity_no_update", "UPDATE source_custody SET identity=?", (raw,))
        elif case == "capture-future":
            tamper(
                db,
                "custody_identity_no_update",
                "UPDATE source_custody SET captured_at='2026-10-18T12:59:00Z'",
            )
        elif case == "hash-invalid":
            tamper(db, "receipt_no_update", "UPDATE source_receipts SET envelope_sha256='invalid'")
        elif case == "purged-with-blob":
            db.execute("UPDATE source_custody SET state='purged'")
        else:
            value = receipt.model_dump(by_alias=True)
            value["trust_generation"] = 2
            tamper(
                db,
                "receipt_no_update",
                "UPDATE source_receipts SET receipt=?",
                (encode(value).decode(),),
            )
    # Construct with the known identity: corrupt per-receipt metadata does not
    # invalidate explicit installation identity discovery.
    access = reader(owner)
    assert_storage_refusal(lambda: lookup(access))


def test_snapshot_sets_query_only_and_native_readonly(private_root):
    owner, _ = seeded(private_root)
    with owner._read_snapshot() as db:
        # Remove one layer deliberately to probe the independent native layer.
        db.set_authorizer(None)
        assert db.execute("PRAGMA query_only").fetchone()[0] == 1
        db.execute("PRAGMA query_only=OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("UPDATE source_custody SET state='purged'")


def test_valid_v5_migration_noop_revalidates_managed_rows(private_root):
    owner, prepared, cap, _ = managed(private_root, "custodied")
    before = snapshot(owner)
    assert owner.migrate().applied is False
    assert snapshot(owner) == before
    with database(owner.path) as db:
        tamper(db, "handoff_progress", "UPDATE source_handoffs SET intent_sha256=?", ("0" * 64,))
    assert_storage_refusal(owner.migrate)


@pytest.mark.parametrize("case", ["open", "phase", "generation", "capture", "valid"])
def test_settlement_observation_guards(private_root, case):
    owner, prepared, cap, _ = managed(private_root, "custodied", case != "open")
    data = prepared.model_dump()
    data.update(
        operation="settle",
        control_id=str(uuid4()),
        job_id=str(uuid4()),
        expected_fence_generation=3 if case == "generation" else 1,
        payload={"capture": None},
    )
    if case == "capture":
        data["payload"]["capture"] = dict(cap, snapshot_id=str(uuid4()))
    raw = canonical_request(parse_untrusted_request(encode(data))).decode()
    with database(owner.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute(
            "INSERT INTO source_handoff_operations VALUES (?,?,?,?,?,?,?,?)",
            (
                data["control_id"],
                data["job_id"],
                prepared.handoff_id,
                "settle",
                raw,
                hashlib.sha256(raw.encode()).hexdigest(),
                "bound" if case == "phase" else "closed",
                3,
            ),
        )
    if case == "valid":
        assert observe(reader(owner), prepared).closed is True
    else:
        assert_storage_refusal(lambda: inspect_handoff(owner, prepared))


def test_handoff_binding_refuses_wrong_host_even_if_columns_agree(private_root):
    owner, prepared, _, _ = managed(private_root)
    data = prepared.model_dump()
    data["scope"]["host_id"] = str(uuid4())
    raw = canonical_request(parse_untrusted_request(encode(data))).decode()
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with database(owner.path) as db:
        tamper(
            db,
            "handoff_progress",
            "UPDATE source_handoffs SET host_id=?,intent=?,intent_sha256=?",
            (data["scope"]["host_id"], raw, digest),
        )
        tamper(
            db,
            "operation_progress",
            "UPDATE source_handoff_operations SET request=?,request_sha256=?",
            (raw, digest),
        )
    assert_storage_refusal(lambda: inspect_handoff(owner, prepared))


def test_migration_integrity_check_is_independent(private_root):
    owner = legacy(private_root)
    with database(owner.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        tamper(db, "deployment_no_update", "UPDATE deployment SET singleton=2")
    before = snapshot(owner)
    assert_storage_refusal(owner.migrate)
    assert snapshot(owner) == before


def test_snapshot_requires_existing_wal_mode(private_root):
    owner, _ = seeded(private_root)
    access = reader(owner)
    with database(owner.path) as db:
        assert db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    before = owner.path.read_bytes()
    assert_storage_refusal(lambda: lookup(access))
    assert owner.path.read_bytes() == before


@pytest.mark.parametrize("case", ["kind", "operation", "canonical", "digest"])
def test_stored_request_owner_has_independent_guards(case):
    value = request("status" if case in ("kind", "operation") else "prepare")
    raw = json.dumps(value, indent=2) if case == "canonical" else encode(value).decode()
    digest = "0" * 64 if case == "digest" else hashlib.sha256(raw.encode()).hexdigest()
    kind = "status" if case == "kind" else "prepare"
    assert_storage_refusal(lambda: _stored_request(raw, digest, kind))


@pytest.mark.parametrize("kind", ["prepare", "upload", "settle"])
def test_stored_request_owner_positive_boundary(kind):
    raw = encode(request(kind)).decode()
    assert _stored_request(raw, hashlib.sha256(raw.encode()).hexdigest(), kind).operation == kind


@pytest.mark.parametrize(
    "case", ["closed", "ever", "generation", "upper", "link", "capture", "floor"]
)
def test_handoff_state_owner_each_clause(case):
    cap = CaptureReference.model_validate(capture())
    args = dict(capture=cap, generation=2, revision=4, closed=1, admission=OTHER, ever=1)
    changes = {
        "closed": dict(closed=2, generation=3, revision=5),
        "ever": dict(ever=2, revision=5),
        "generation": dict(generation=1),
        "upper": dict(revision=2147483648),
        "link": dict(ever=0),
        "capture": dict(capture=None),
        "floor": dict(revision=3),
    }
    args.update(changes[case])
    assert_storage_refusal(lambda: _handoff_state(**args))


@pytest.mark.parametrize("revision", [4, 2147483647])
def test_handoff_state_owner_positive_boundaries(revision):
    assert (
        _handoff_state(CaptureReference.model_validate(capture()), 2, revision, 1, OTHER, 1) is None
    )


def test_missing_custody_fails_at_metadata_owner(private_root):
    owner, _ = seeded(private_root)
    with database(owner.path) as db:
        row = db.execute("SELECT * FROM source_receipts").fetchone()
        tamper(db, "custody_no_delete", "DELETE FROM source_custody")
        assert_storage_refusal(lambda: owner._receipt_metadata(db, row))


def test_receipt_deployment_guard_is_not_masked_by_indexes(private_root):
    owner, receipt = seeded(private_root)
    value = receipt.model_dump(by_alias=True)
    value["host_id"] = str(uuid4())
    with database(owner.path) as db:
        tamper(
            db,
            "receipt_no_update",
            "UPDATE source_receipts SET receipt=?",
            (encode(value).decode(),),
        )
    assert_storage_refusal(lambda: lookup(reader(owner)))


def test_custody_state_guard_without_retained_content(private_root):
    owner, _ = seeded(private_root)
    with database(owner.path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute("DELETE FROM source_content")
        db.execute("UPDATE source_custody SET state='invalid'")
    assert_storage_refusal(lambda: lookup(reader(owner)))


def test_foreign_scope_cannot_observe_missing_handoff(private_root):
    owner, prepared, _, _ = managed(private_root)
    bad = prepared.scope.model_copy(update={"host_id": str(uuid4())})
    with pytest.raises(SourceStoreConflict):
        observe(reader(owner), prepared, handoff_id=str(uuid4()), scope=bad)


@pytest.mark.parametrize("invalid", [None, False, object()])
def test_constructor_refuses_nonowner(invalid):
    with pytest.raises(SourceStoreInputError):
        SourceCustodyStore(
            invalid,
            expected_incarnation=OTHER,
            max_handoffs=1,
            max_mutation_records=3,
            max_reservation_seconds=1,
        )


def test_reader_does_not_acquire_writer(private_root):
    owner, receipt = seeded(private_root)
    access = reader(owner)
    with database(owner.path) as writer:
        writer.execute("BEGIN IMMEDIATE")
        assert lookup(access).receipt == receipt


def test_observer_rejects_hardlinked_store(private_root):
    import os

    owner, _ = seeded(private_root)
    access = reader(owner)
    os.link(owner.path, private_root / "alias.sqlite3")
    assert_storage_refusal(lambda: lookup(access))


@pytest.mark.parametrize("field", ["payload_digest", "envelope_sha256"])
@pytest.mark.parametrize("container", [bytes, bytearray])
def test_lookup_digest_references_are_strict_text(private_root, field, container):
    owner, _ = seeded(private_root)
    parsed = parse_untrusted_source(encode(envelope()))
    digest = (
        payload_digest(parsed)
        if field == "payload_digest"
        else hashlib.sha256(canonical_source(parsed)).hexdigest()
    )
    with pytest.raises(SourceStoreInputError):
        lookup(reader(owner), **{field: container(digest.encode())})


@pytest.mark.parametrize(
    "field",
    [
        "handoff_id",
        "incarnation",
        "host_id",
        "organization_id",
        "namespace_id",
        "event_id",
        "route_digest",
        "enrolled_machine_id",
        "intent",
        "intent_sha256",
        "reservation_expires_at",
        "capture",
        "admission_id",
    ],
)
def test_handoff_each_immutable_column(private_root, field):
    owner, _, _, _ = managed(private_root, "custodied", True)
    before = snapshot(owner)
    with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(f"UPDATE source_handoffs SET {field}=?,revision=5", (str(uuid4()),))
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "field", ["control_id", "job_id", "handoff_id", "request", "request_sha256"]
)
def test_operation_identity_immutable_during_forward_progress(private_root, field):
    owner, _, _, _ = managed(private_root, "bound")
    with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            f"UPDATE source_handoff_operations SET {field}=?,phase='admitted',revision=3 "
            "WHERE kind='upload'",
            (str(uuid4()),),
        )


@pytest.mark.parametrize("collision", ["control", "job", "slot"])
def test_operation_unique_identity_and_reserved_slot(private_root, collision):
    owner, prepared, cap, _ = managed(private_root, "bound", True)
    value = prepared.model_dump()
    value.update(
        operation="upload" if collision == "slot" else "settle",
        expected_fence_generation=1,
        control_id=str(uuid4()),
        job_id=str(uuid4()),
        payload={"capture": cap},
    )
    if collision == "control":
        value["control_id"] = prepared.control_id
    if collision == "job":
        value["job_id"] = prepared.job_id
    raw = canonical_request(parse_untrusted_request(encode(value))).decode()
    with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO source_handoff_operations VALUES (?,?,?,?,?,?,?,?)",
            (
                value["control_id"],
                value["job_id"],
                prepared.handoff_id,
                value["operation"],
                raw,
                hashlib.sha256(raw.encode()).hexdigest(),
                "bound" if collision == "slot" else "closed",
                3,
            ),
        )


def test_same_event_cannot_have_second_reservation(private_root):
    owner, prepared, _, _ = managed(private_root)
    value = prepared.model_dump()
    value.update(handoff_id=str(uuid4()), control_id=str(uuid4()), job_id=str(uuid4()))
    raw = canonical_request(parse_untrusted_request(encode(value))).decode()
    with database(owner.path) as db, pytest.raises(sqlite3.IntegrityError):
        row = list(db.execute("SELECT * FROM source_handoffs").fetchone())
        row[0], row[8], row[9] = value["handoff_id"], raw, hashlib.sha256(raw.encode()).hexdigest()
        db.execute("INSERT INTO source_handoffs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)


# Managed operations use the real owners; the earlier SQL fixtures remain only
# for independent metadata/corruption tests.
RESERVATION = "2026-10-18T12:45:00Z"


def managed_request(value=None):
    value = envelope() if value is None else value
    p = value["payload"]
    data = request(value=value)
    data.update(handoff_id=str(uuid4()), control_id=str(uuid4()), job_id=str(uuid4()))
    data["scope"].update(
        host_id=value["authorization"]["host_id"],
        organization_id=p["organization_id"],
        namespace_id=p["source"]["namespace_id"],
        event_id=p["event_id"],
    )
    data["payload"].update(
        rule_id=p["trigger"]["rule_id"],
        rule_version=p["trigger"]["rule_version"],
        policy_id=p["retention"]["policy_id"],
        policy_version=p["retention"]["policy_version"],
    )
    return parse_untrusted_request(encode(data))


def managed_operation(prepared, kind, cap=None, generation=1):
    data = prepared.model_dump()
    data.update(
        operation=kind,
        expected_fence_generation=generation,
        control_id=str(uuid4()),
        job_id=str(uuid4()),
        payload={"capture": cap},
    )
    return parse_untrusted_request(encode(data))


def managed_setup(root, value=None, **options):
    owner = store(root)
    owner.initialize(trust())
    access = reader(owner, clock=lambda: NOW, **options)
    prepared = managed_request(value)
    return owner, access, prepared


def test_managed_admission_close_and_revalidation(private_root):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    first = access.register_intent(prepared, reservation_expires_at=RESERVATION)
    assert (first.fence_generation, first.state_revision, first.ever_custodied) == (1, 1, False)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    bound = access.bind_upload(upload)
    assert (bound.state_revision, bound.capture) == (2, upload.payload.capture)
    raw = canonical_source(parse_untrusted_source(encode(envelope())))
    admitted = access.admit_bound(upload, raw)
    assert admitted.applied is True
    assert access.admit_bound(upload, raw).receipt == admitted.receipt
    settled = managed_operation(prepared, "settle", capture(envelope()))
    closed = access.close_admission(settled)
    assert (closed.closed, closed.fence_generation, closed.state_revision) == (True, 2, 4)
    assert closed.receipt == admitted.receipt
    assert access.close_admission(settled) == closed
    with pytest.raises(SourceAuthenticationError):
        access.admit_bound(upload, raw)
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW).admit_source(raw)
    resume = managed_operation(prepared, "resume", capture(envelope()), 2)
    before = snapshot(owner)
    resumed = access.revalidate_existing(resume, raw, admission_id=admitted.receipt.admission_id)
    assert resumed.receipt == admitted.receipt and resumed.applied is False
    assert snapshot(owner) == before


def rewrite_request(value, path, changed):
    data = value.model_dump()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = changed
    return parse_untrusted_request(encode(data))


def upload_setup(root, *, admit=False, value=None, **options):
    owner, access, prepared = managed_setup(root, value, **options)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    value = envelope() if value is None else value
    upload = managed_operation(prepared, "upload", capture(value))
    access.bind_upload(upload)
    raw = canonical_source(parse_untrusted_source(encode(value)))
    result = access.admit_bound(upload, raw) if admit else None
    return owner, access, prepared, upload, raw, result


@pytest.mark.parametrize("phase", ["prepared", "bound", "admitted", "closed"])
def test_managed_legacy_refusal_all_phases(private_root, phase):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    raw = encode(envelope())
    if phase != "prepared":
        upload = managed_operation(prepared, "upload", capture(envelope()))
        access.bind_upload(upload)
        if phase in ("admitted", "closed"):
            access.admit_bound(upload, raw)
        if phase == "closed":
            access.close_admission(managed_operation(prepared, "settle"))
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        SourceAdmission(owner, clock=lambda: NOW).admit_source(raw)
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["prepare", "upload", "settle"])
@pytest.mark.parametrize(
    "field", ["control_id", "job_id", "proof_reference", "enrolled_machine_id", "handoff_id"]
)
def test_managed_operation_fingerprint_rejects_changed_field(private_root, kind, field):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root)
    operation = prepared if kind == "prepare" else upload
    if kind == "settle":
        operation = managed_operation(prepared, "settle")
        access.close_admission(operation)
    altered = rewrite_request(operation, [field], str(uuid4()))
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        if kind == "prepare":
            access.register_intent(altered, reservation_expires_at=RESERVATION)
        elif kind == "upload":
            access.bind_upload(altered)
        else:
            access.close_admission(altered)
    assert snapshot(owner) == before


@pytest.mark.parametrize("phase", ["prepare", "bind", "admit", "close", "resume"])
def test_managed_incarnation_refuses_every_mutation(private_root, phase):
    owner, access, prepared, upload, raw, result = upload_setup(private_root, admit=True)
    wrong = reader(owner, expected_incarnation=str(uuid4()), clock=lambda: NOW)
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        if phase == "prepare":
            wrong.register_intent(prepared, reservation_expires_at=RESERVATION)
        elif phase == "bind":
            wrong.bind_upload(upload)
        elif phase == "admit":
            wrong.admit_bound(upload, raw)
        elif phase == "close":
            wrong.close_admission(managed_operation(prepared, "settle"))
        else:
            wrong.revalidate_existing(
                managed_operation(prepared, "resume", capture(envelope())),
                raw,
                admission_id=result.receipt.admission_id,
            )
    assert snapshot(owner) == before


@pytest.mark.parametrize("case", ["handoffs", "operations", "no-slot"])
def test_managed_capacity_reserves_settlement_and_preserves_retries(private_root, case):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    options = (
        dict(max_handoffs=1)
        if case == "handoffs"
        else dict(max_mutation_records=2 if case == "no-slot" else 3)
    )
    owner, access, prepared = managed_setup(private_root, **options)
    if case == "no-slot":
        before = snapshot(owner)
        with pytest.raises(SourceStoreConflict):
            access.register_intent(prepared, reservation_expires_at=RESERVATION)
        assert snapshot(owner) == before
        return
    first = access.register_intent(prepared, reservation_expires_at=RESERVATION)
    assert access.register_intent(prepared, reservation_expires_at=RESERVATION) == first
    other = envelope()
    other["payload"]["event_id"] = str(uuid4())
    resign(other)
    with pytest.raises(SourceStoreConflict):
        access.register_intent(managed_request(other), reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    access.bind_upload(upload)
    receipt = access.admit_bound(upload, encode(envelope())).receipt
    close = managed_operation(prepared, "settle")
    closed = access.close_admission(close)
    assert access.close_admission(close) == closed
    assert closed.receipt == receipt
    with pytest.raises(SourceAuthenticationError):
        access.bind_upload(upload)
    resume = managed_operation(prepared, "resume", capture(envelope()), 2)
    assert (
        access.revalidate_existing(
            resume, encode(envelope()), admission_id=receipt.admission_id
        ).receipt
        == receipt
    )
    with database(owner.path) as db:
        assert db.execute("SELECT count(*) FROM source_handoff_operations").fetchone()[0] == 3


def test_managed_legacy_receipt_cannot_be_adopted(private_root):
    owner, access, prepared = managed_setup(private_root)
    SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope()))
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "field,changed",
    [
        ("envelope_sha256", "0" * 64),
        ("payload_digest", "0" * 64),
        ("snapshot_id", OTHER),
        ("captured_at", "2026-10-18T12:00:01Z"),
        ("recovery_deadline", "2026-10-18T13:00:01Z"),
        ("artifact_size", 1),
    ],
)
def test_managed_capture_binding_fields_independent(private_root, field, changed):
    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    cap = capture(envelope())
    assert cap[field] != changed
    cap[field] = changed
    upload = managed_operation(prepared, "upload", cap)
    access.bind_upload(upload)
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        access.admit_bound(upload, encode(envelope()))
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "path,changed",
    [
        (["payload", "source", "message_id"], "different-message"),
        (["payload", "watcher_event_id"], "0" * 64),
        (["payload", "rule_id"], OTHER),
        (["payload", "rule_version"], 2),
    ],
)
def test_managed_intent_binding_fields_independent(private_root, path, changed):
    owner, access, prepared = managed_setup(private_root)
    assert prepared.model_dump()["payload"][path[-1]] != changed if len(path) == 2 else True
    prepared = rewrite_request(prepared, path, changed)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    access.bind_upload(upload)
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        access.admit_bound(upload, encode(envelope()))
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["bind", "admit"])
@pytest.mark.parametrize("when", ["first", "final"])
def test_managed_reservation_expiry_rolls_back(private_root, kind, when):
    from datetime import datetime

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    if kind == "admit":
        access.bind_upload(upload)
    samples = iter(
        [NOW, datetime.fromisoformat(RESERVATION)]
        if when == "final"
        else [datetime.fromisoformat(RESERVATION)]
    )
    late = reader(owner, clock=lambda: next(samples))
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        late.bind_upload(upload) if kind == "bind" else late.admit_bound(upload, encode(envelope()))
    assert snapshot(owner) == before


def test_managed_closed_empty_never_admits_and_unknown_never_closes(private_root):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    close = managed_operation(prepared, "settle")
    with pytest.raises(SourceAuthenticationError):
        access.close_admission(close)
    assert observe(access, prepared) is None
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    closed = access.close_admission(close)
    assert closed.closed and not closed.ever_custodied and closed.receipt is None
    with pytest.raises(SourceAuthenticationError):
        access.bind_upload(managed_operation(prepared, "upload", capture(envelope())))
    assert snapshot(owner)["source_content"] == []


def test_managed_revalidation_after_reservation_expiry_and_revoke(private_root):
    from datetime import timedelta

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared, upload, raw, admitted = upload_setup(private_root, admit=True)
    later = reader(owner, clock=lambda: NOW + timedelta(minutes=16))
    with pytest.raises(SourceAuthenticationError):
        later.admit_bound(upload, raw)
    resume = managed_operation(prepared, "resume", capture(envelope()))
    assert (
        later.revalidate_existing(resume, raw, admission_id=admitted.receipt.admission_id).applied
        is False
    )
    grants = trust().model_dump()["key_grants"]
    grants[0]["status"] = "revoked"
    owner.publish_authority(next_snapshot(key_grants=grants), expected_generation=1)
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        later.revalidate_existing(resume, raw, admission_id=admitted.receipt.admission_id)
    assert snapshot(owner) == before
    assert observe(access, prepared).receipt == admitted.receipt


@pytest.mark.parametrize("raw_kind", ["formatted", "copied", "signature"])
def test_managed_requires_exact_raw_authenticated_artifact(private_root, raw_kind):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared, upload, raw, _ = upload_setup(private_root)
    if raw_kind == "formatted":
        raw = json.dumps(envelope(), indent=2).encode()
        expected = SourceStoreConflict
    elif raw_kind == "copied":
        raw = parse_untrusted_source(raw)
        expected = SourceAuthenticationError
    else:
        value = envelope()
        value["authorization"]["signature"] = "A" * 86
        raw = encode(value)
        expected = SourceAuthenticationError
    before = snapshot(owner)
    with pytest.raises(expected) as failure:
        access.admit_bound(upload, raw)
    assert failure.value.__cause__ is None and failure.value.__context__ is None
    assert snapshot(owner) == before


@pytest.mark.parametrize("phase", ["prepared", "bound", "admitted"])
@pytest.mark.parametrize("lifecycle", ["purge", "retire"])
def test_managed_lifecycle_closes_only_known_captures(private_root, phase, lifecycle):
    from datetime import datetime

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    if phase != "prepared":
        access.bind_upload(upload)
        if phase == "admitted":
            access.admit_bound(upload, encode(envelope()))
    content = SourceContent(owner, clock=lambda: NOW)
    if lifecycle == "purge":
        content.purge_message(
            prepared.payload.source,
            cutoff=datetime.fromisoformat(upload.payload.capture.captured_at),
        )
    else:
        content.retire_namespace(prepared.scope.namespace_id)
    facts = observe(access, prepared)
    assert facts.closed is (lifecycle == "retire" or phase != "prepared")
    with pytest.raises(SourceAuthenticationError):
        access.bind_upload(upload)
    if facts.closed:
        old_settle = managed_operation(prepared, "settle")
        with pytest.raises(SourceAuthenticationError):
            access.close_admission(old_settle)
        current = managed_operation(prepared, "settle", generation=2)
        assert access.close_admission(current) == facts
        assert access.close_admission(current) == facts
    if lifecycle == "retire" and phase == "admitted":
        content.cleanup_retired(prepared.scope.namespace_id, limit=100)
        gone = observe(access, prepared)
        assert gone.closed and gone.ever_custodied and gone.receipt is None
        assert gone.content_state == "unknown"


@pytest.mark.parametrize("bound", [False, True])
def test_managed_late_purge_preserves_newer_capture(private_root, bound):
    from datetime import datetime, timedelta

    value = envelope()
    value["payload"]["snapshot"]["captured_at"] = "2026-10-18T12:00:01Z"
    value["payload"]["occurred_at"] = "2026-10-18T12:00:01Z"
    resign(value)
    owner, access, prepared = managed_setup(private_root, value)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(value))
    if bound:
        access.bind_upload(upload)
    SourceContent(owner, clock=lambda: NOW).purge_message(
        prepared.payload.source,
        cutoff=datetime.fromisoformat(upload.payload.capture.captured_at) - timedelta(seconds=1),
    )
    assert not observe(access, prepared).closed
    access.bind_upload(upload)
    assert access.admit_bound(upload, encode(value)).applied


def test_managed_expired_content_closes_and_preserves_receipt(private_root):
    from datetime import datetime

    from connect_automate.lead_intake.content import SourceContentUnavailable

    owner, access, prepared, upload, raw, admitted = upload_setup(private_root, admit=True)
    content = SourceContent(
        owner, clock=lambda: datetime.fromisoformat(upload.payload.capture.recovery_deadline)
    )
    with pytest.raises(SourceContentUnavailable):
        content.read_content(admitted.receipt.admission_id)
    facts = observe(access, prepared)
    assert facts.closed and facts.ever_custodied and facts.receipt == admitted.receipt
    assert facts.content_state == "purged"


@pytest.mark.parametrize("kind", ["prepare", "upload", "settle", "resume"])
@pytest.mark.parametrize("bad", [None, False, "", 0])
def test_managed_copied_requests_reparsed(private_root, kind, bad):
    owner, access, prepared, upload, raw, admitted = upload_setup(private_root, admit=True)
    operation = (
        prepared if kind == "prepare" else managed_operation(prepared, kind, capture(envelope()))
    )
    forged = operation.model_copy(update={"proof_reference": bad})
    before = snapshot(owner)
    with pytest.raises(SourceStoreInputError) as failure:
        if kind == "prepare":
            access.register_intent(forged, reservation_expires_at=RESERVATION)
        elif kind == "upload":
            access.admit_bound(forged, raw)
        elif kind == "settle":
            access.close_admission(forged)
        else:
            access.revalidate_existing(forged, raw, admission_id=admitted.receipt.admission_id)
    assert failure.value.__cause__ is None and failure.value.__context__ is None
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["prepare", "bind", "admit", "close", "resume"])
def test_managed_without_clock_never_mutates(private_root, kind):
    owner, _, prepared, upload, raw, admitted = upload_setup(private_root, admit=True)
    access = reader(owner)
    before = snapshot(owner)
    with pytest.raises(SourceStoreInputError):
        if kind == "prepare":
            access.register_intent(prepared, reservation_expires_at=RESERVATION)
        elif kind == "bind":
            access.bind_upload(upload)
        elif kind == "admit":
            access.admit_bound(upload, raw)
        elif kind == "close":
            access.close_admission(managed_operation(prepared, "settle"))
        else:
            access.revalidate_existing(
                managed_operation(prepared, "resume", capture(envelope())),
                raw,
                admission_id=admitted.receipt.admission_id,
            )
    assert snapshot(owner) == before


@pytest.mark.parametrize(
    "seconds,allowed", [(-1, False), (0, False), (1, True), (3600, True), (3601, False)]
)
def test_managed_reservation_bounds(private_root, seconds, allowed):
    from datetime import timedelta

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    deadline = (
        (NOW + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    before = snapshot(owner)
    if allowed:
        first = access.register_intent(prepared, reservation_expires_at=deadline)
        assert first.state_revision == 1
        later = reader(owner, clock=lambda: NOW + timedelta(hours=2))
        assert later.register_intent(prepared, reservation_expires_at=deadline) == first
        assert later.close_admission(managed_operation(prepared, "settle")).closed
    else:
        with pytest.raises(SourceAuthenticationError):
            access.register_intent(prepared, reservation_expires_at=deadline)
        assert snapshot(owner) == before


def test_managed_reservation_deadline_cannot_change(private_root):
    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        access.register_intent(prepared, reservation_expires_at="2026-10-18T12:45:01Z")
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["bind", "admit", "close", "purge", "retire"])
def test_managed_revision_overflow_before_effects(private_root, kind):
    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    if kind != "bind":
        access.bind_upload(upload)
    with database(owner.path) as db:
        db.execute("UPDATE source_handoffs SET revision=2147483647")
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        if kind == "bind":
            access.bind_upload(upload)
        elif kind == "admit":
            access.admit_bound(upload, encode(envelope()))
        elif kind == "close":
            access.close_admission(managed_operation(prepared, "settle"))
        elif kind == "purge":
            SourceContent(owner, clock=lambda: NOW).purge_message(
                prepared.payload.source, cutoff=NOW
            )
        else:
            SourceContent(owner, clock=lambda: NOW).retire_namespace(prepared.scope.namespace_id)
    assert snapshot(owner) == before


@pytest.mark.parametrize("which", ["policy_id", "policy_version"])
def test_managed_binding_checks_current_policy(private_root, which):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    prepared = rewrite_request(prepared, ["payload", which], OTHER if which == "policy_id" else 2)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        access.bind_upload(managed_operation(prepared, "upload", capture(envelope())))
    assert snapshot(owner) == before


def test_managed_near_calendar_end_reservation(private_root):
    from datetime import UTC, datetime

    owner, _, prepared = managed_setup(private_root)
    access = reader(owner, clock=lambda: datetime(9999, 12, 31, 23, 59, 58, tzinfo=UTC))
    result = access.register_intent(prepared, reservation_expires_at="9999-12-31T23:59:59Z")
    assert result.state_revision == 1


@pytest.mark.parametrize("state", ["unavailable", "complete", "truncated", "unknown"])
def test_managed_source_body_states(private_root, state):
    value = envelope()
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": "source_gone"}
    else:
        body = value["payload"]["snapshot"]["body"]
        body["completeness"] = state
        if state == "truncated":
            body["source_chars"] = body["stored_chars"] + 1
        elif state == "unknown":
            body["source_chars"] = None
    resign(value)
    owner, access, prepared, upload, raw, result = upload_setup(
        private_root, admit=True, value=value
    )
    assert result.applied
    reopened = reader(store(private_root), clock=lambda: NOW)
    assert reopened.admit_bound(upload, raw).receipt == result.receipt
    assert SourceContent(owner, clock=lambda: NOW).read_content(result.receipt.admission_id) == raw


@pytest.mark.parametrize(
    "field,changed",
    [
        ("envelope_sha256", "0" * 64),
        ("payload_digest", "0" * 64),
        ("snapshot_id", OTHER),
        ("captured_at", "2026-10-18T12:00:01Z"),
        ("recovery_deadline", "2026-10-18T13:00:01Z"),
        ("artifact_size", 1),
    ],
)
def test_managed_capture_guard_isolated(private_root, field, changed):
    """Do not let receipt metadata validation mask a missing ingress comparison."""
    from connect_automate.lead_intake.auth import authenticate_source

    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    cap = capture(envelope())
    cap[field] = changed
    upload = managed_operation(prepared, "upload", cap)
    access.bind_upload(upload)
    raw = encode(envelope())
    verified = authenticate_source(raw, trust=trust(), now=NOW)
    with owner._transaction() as db, pytest.raises(SourceStoreConflict):
        owner._managed_admission_state(db, upload, raw, verified, None)


def test_managed_canonical_guard_isolated(private_root):
    from connect_automate.lead_intake.auth import authenticate_source

    owner, access, prepared = managed_setup(private_root)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    raw = json.dumps(envelope(), indent=2).encode()
    cap = capture(envelope())
    cap.update(envelope_sha256=hashlib.sha256(raw).hexdigest(), artifact_size=len(raw))
    upload = managed_operation(prepared, "upload", cap)
    access.bind_upload(upload)
    with owner._transaction() as db, pytest.raises(SourceStoreConflict):
        owner._managed_admission_state(
            db, upload, raw, authenticate_source(raw, trust=trust(), now=NOW), None
        )


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "watcher_event_id",
        "rule_id",
        "rule_version",
        "policy_id",
        "policy_version",
        "event_id",
    ],
)
def test_managed_intent_guard_isolated(private_root, field):
    from connect_automate.lead_intake.auth import authenticate_source

    owner, access, prepared = managed_setup(private_root)
    if field == "source":
        prepared = rewrite_request(prepared, ["payload", "source", "message_id"], "another-message")
    elif field == "event_id":
        prepared = rewrite_request(prepared, ["scope", field], OTHER)
    else:
        prepared = rewrite_request(
            prepared,
            ["payload", field],
            "0" * 64 if field == "watcher_event_id" else 2 if field.endswith("version") else OTHER,
        )
    if field.startswith("policy"):
        policies = list(trust().model_dump()["retention_policies"])
        policies.append(
            dict(
                policy_id=prepared.payload.policy_id,
                policy_version=prepared.payload.policy_version,
                max_recovery_seconds=3600,
            )
        )
        owner.publish_authority(next_snapshot(retention_policies=policies), expected_generation=1)
    access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    access.bind_upload(upload)
    raw = encode(envelope())
    with owner._transaction() as db:
        verified = authenticate_source(raw, trust=owner._authority(db)[0], now=NOW)
        with pytest.raises(SourceStoreConflict):
            owner._managed_admission_state(db, upload, raw, verified, None)


@pytest.mark.parametrize(
    "case", ["generation", "admission", "purged", "expired", "changed-envelope"]
)
def test_managed_revalidation_refuses_changed_or_unavailable(private_root, case):
    from datetime import datetime

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared, upload, raw, result = upload_setup(private_root, admit=True)
    resume = managed_operation(
        prepared, "resume", capture(envelope()), 2 if case == "generation" else 1
    )
    admission_id = str(uuid4()) if case == "admission" else result.receipt.admission_id
    if case == "purged":
        SourceContent(owner, clock=lambda: NOW).purge_message(prepared.payload.source, cutoff=NOW)
        resume = managed_operation(prepared, "resume", capture(envelope()), 2)
    if case == "expired":
        access = reader(
            owner, clock=lambda: datetime.fromisoformat(upload.payload.capture.recovery_deadline)
        )
    if case == "changed-envelope":
        value = envelope()
        value["payload"]["snapshot"]["body"]["text"] = "other"
        value["payload"]["snapshot"]["body"]["stored_chars"] = 5
        value["payload"]["snapshot"]["body"]["source_chars"] = 5
        value["payload"]["snapshot"]["body"]["sha256"] = hashlib.sha256(b"other").hexdigest()
        resign(value)
        raw = encode(value)
        from connect_automate.lead_intake.auth import authenticate_source

        authenticate_source(raw, trust=trust(), now=NOW)
    before = snapshot(owner)
    with pytest.raises((SourceAuthenticationError, SourceStoreConflict)):
        access.revalidate_existing(resume, raw, admission_id=admission_id)
    assert snapshot(owner) == before


def test_managed_multiple_events_one_message_purge_is_cutoff_wide(private_root):
    from datetime import datetime

    owner, access, prepared = managed_setup(private_root)
    intents = []
    for stamp in ["2026-10-18T12:00:00Z", "2026-10-18T12:00:01Z", "2026-10-18T12:00:02Z"]:
        value = envelope()
        value["payload"]["event_id"] = str(uuid4())
        value["payload"]["snapshot"]["captured_at"] = value["payload"]["occurred_at"] = stamp
        resign(value)
        intent = managed_request(value)
        access.register_intent(intent, reservation_expires_at=RESERVATION)
        upload = managed_operation(intent, "upload", capture(value))
        access.bind_upload(upload)
        access.admit_bound(upload, encode(value))
        intents.append(intent)
    SourceContent(owner, clock=lambda: NOW).purge_message(
        prepared.payload.source, cutoff=datetime.fromisoformat("2026-10-18T12:00:01Z")
    )
    facts = [observe(access, intent) for intent in intents]
    assert [f.closed for f in facts] == [True, True, False]
    assert [f.content_state for f in facts] == ["purged", "purged", "retained"]
    assert len(snapshot(owner)["source_receipts"]) == 3


@pytest.mark.parametrize(
    "closed,expected,allowed", [(False, 1, True), (False, 2, False), (True, 2, False)]
)
def test_managed_open_fence_owner(private_root, closed, expected, allowed):
    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared, upload, raw, _ = upload_setup(private_root)
    if closed:
        access.close_admission(managed_operation(prepared, "settle"))
    facts = observe(access, prepared)
    candidate = managed_operation(prepared, "upload", capture(envelope()), expected)
    if allowed:
        assert owner._open_custody(facts, candidate) is None
    else:
        with pytest.raises(SourceAuthenticationError):
            owner._open_custody(facts, candidate)


@pytest.mark.parametrize("case", ["generation", "admission", "purged"])
def test_managed_revalidate_guard_isolated(private_root, case):
    from connect_automate.lead_intake.auth import SourceAuthenticationError, authenticate_source

    owner, access, prepared, upload, raw, result = upload_setup(private_root, admit=True)
    generation = 2 if case == "generation" else 1
    if case == "purged":
        SourceContent(owner, clock=lambda: NOW).purge_message(prepared.payload.source, cutoff=NOW)
        generation = 2
    resume = managed_operation(prepared, "resume", capture(envelope()), generation)
    ident = str(uuid4()) if case == "admission" else result.receipt.admission_id
    with owner._transaction() as db, pytest.raises(SourceAuthenticationError):
        owner._managed_admission_state(
            db, resume, raw, authenticate_source(raw, trust=trust(), now=NOW), ident
        )


@pytest.mark.parametrize("kind", ["prepare", "bind", "admit", "close"])
def test_managed_clock_regression_final_sample(private_root, kind):
    from datetime import timedelta

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    if kind != "prepare":
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
    upload = managed_operation(prepared, "upload", capture(envelope()))
    if kind == "admit":
        access.bind_upload(upload)
    samples = iter([NOW + timedelta(seconds=2), NOW + timedelta(seconds=1)])
    access = reader(owner, clock=lambda: next(samples))
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        if kind == "prepare":
            access.register_intent(prepared, reservation_expires_at=RESERVATION)
        elif kind == "bind":
            access.bind_upload(upload)
        elif kind == "admit":
            access.admit_bound(upload, encode(envelope()))
        else:
            access.close_admission(managed_operation(prepared, "settle"))
    assert snapshot(owner) == before


@pytest.mark.parametrize("case", ["future", "deadline", "recovery", "policy"])
def test_managed_capture_eligibility_owner(private_root, case):
    from datetime import datetime, timedelta

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, access, prepared = managed_setup(private_root)
    cap = CaptureReference.model_validate(capture(envelope()))
    deadline = datetime.fromisoformat(RESERVATION)
    now = NOW
    if case == "future":
        now = datetime.fromisoformat(cap.captured_at) - timedelta(seconds=1)
    elif case == "deadline":
        deadline = now
    elif case == "recovery":
        now = datetime.fromisoformat(cap.recovery_deadline)
        deadline = now + timedelta(seconds=1)
    else:
        prepared = rewrite_request(prepared, ["payload", "policy_version"], 2)
    with owner._transaction() as db, pytest.raises(SourceAuthenticationError):
        owner._capture_eligible(db, prepared, cap, deadline, now)


@pytest.mark.parametrize("which", ["control_id", "job_id"])
def test_managed_global_operation_collision_owner(private_root, which):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root)
    other = envelope()
    other["payload"]["event_id"] = str(uuid4())
    resign(other)
    candidate = managed_request(other)
    candidate = rewrite_request(candidate, [which], getattr(upload, which))
    with owner._transaction() as db, pytest.raises(SourceStoreConflict):
        owner._custody_operation(db, candidate)


def test_managed_other_event_same_handoff_refused(private_root):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root)
    other = rewrite_request(prepared, ["scope", "event_id"], str(uuid4()))
    before = snapshot(owner)
    with pytest.raises(SourceStoreConflict):
        access.register_intent(other, reservation_expires_at=RESERVATION)
    assert snapshot(owner) == before


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_managed_deployment_scope_owner(private_root, field):
    owner, _, prepared = managed_setup(private_root)
    wrong = rewrite_request(prepared, ["scope", field], str(uuid4()))
    with owner._transaction() as db, pytest.raises(SourceStoreConflict):
        owner._custody_request_state(db, wrong)


def test_managed_revision_owner_ceiling(private_root):
    from dataclasses import replace

    owner, access, prepared = managed_setup(private_root)
    facts = access.register_intent(prepared, reservation_expires_at=RESERVATION)
    assert owner._next_custody_revision(replace(facts, state_revision=2147483646)) == 2147483647
    with pytest.raises(SourceStoreConflict):
        owner._next_custody_revision(replace(facts, state_revision=2147483647))


def test_managed_operation_fingerprint_owner(private_root):
    owner, access, prepared, upload, raw, _ = upload_setup(private_root)
    changed = rewrite_request(upload, ["proof_reference"], str(uuid4()))
    with owner._transaction() as db, pytest.raises(SourceStoreConflict):
        owner._custody_operation(db, changed)


def test_managed_prepare_expiry_at_final_sample(private_root):
    from datetime import datetime

    from connect_automate.lead_intake.auth import SourceAuthenticationError

    owner, _, prepared = managed_setup(private_root)
    samples = iter([NOW, datetime.fromisoformat(RESERVATION)])
    access = reader(owner, clock=lambda: next(samples))
    before = snapshot(owner)
    with pytest.raises(SourceAuthenticationError):
        access.register_intent(prepared, reservation_expires_at=RESERVATION)
    assert snapshot(owner) == before
