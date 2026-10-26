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
