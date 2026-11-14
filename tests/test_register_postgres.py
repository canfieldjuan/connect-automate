"""Real disposable PostgreSQL, synthetic evidence only; opt in explicitly."""

import base64
import importlib
import multiprocessing
import os
import sys
import time
from datetime import UTC, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidSignature

sys.path.append(str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(os.environ.get("RUN_REGISTER_POSTGRES") != "1",
                                reason="dedicated offline PostgreSQL lane")


def uid(n):
    return f"{n:08x}-1111-4111-8111-111111111111"


def instant(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@pytest.fixture(scope="module")
def cluster(tmp_path_factory):
    f = importlib.import_module("qualification.licensing_register.fixture")
    with f.temporary_cluster(tmp_path_factory.getbasetemp()) as c:
        yield c


@pytest.fixture
def reg(cluster):
    return cluster.create(uid(1), uid(2))


def test_cluster_uses_pytest_retention(cluster, tmp_path_factory):
    assert cluster.root.is_relative_to(tmp_path_factory.getbasetemp())


def evidence(kind, record, **fields):
    return dict(version="offline-register-evidence/1", evidence_class="OFFLINE_CONFORMANCE",
                qualification_pass=False, proof_id=str(uuid4()), record_id=uid(record),
                organization_id=uid(1), kind=kind) | fields


def command(reg, kind, record, proof=None, revision=None, **changes):
    return dict(version="offline-register/1", command=kind, operation_id=str(uuid4()),
                epoch=reg.epoch, record_id=uid(record), proof_id=proof,
                expected_revision=revision) | changes


def setup_path(reg, *, lifetime=timedelta(minutes=10), source_lifetime=None):
    with reg.admin() as db:
        now = db.execute("SELECT clock_timestamp()").fetchone()[0]
    grant = reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    enrollment = reg.proof(evidence("ENROLLMENT", 11, registration_ref=uid(21),
        authority_expires_at=instant(now + lifetime),
        required_source_expires_at=(instant(now + source_lifetime)
                                   if source_lifetime is not None else None)))
    issuance = reg.proof(evidence("ISSUANCE", 12, grant_id=uid(10), envelope_sha256="a" * 64))
    reg.client().apply(command(reg, "grant", 10, grant))
    reg.client("enrollment").apply(command(reg, "enroll", 11, enrollment))
    reg.client().apply(command(reg, "issuance", 12, issuance))


def associate(reg, **fields):
    proof = reg.proof(evidence("ASSOCIATION", 13, **(dict(grant_id=uid(10),
        enrollment_id=uid(11), entitlement_id=uid(12), verification_ref=uid(22)) | fields)))
    return command(reg, "associate", 13, proof)


def consumption(reg, entitlement=12):
    # Reuse the real closed original-consumption binding model, with synthetic bytes.
    binding = dict(version="owner-bootstrap/1", operation_id=uid(15), installation_id=uid(16),
                   host_id=uid(17), organization_id=uid(1), claim_id=uid(14),
                   entitlement_id=uid(entitlement),
                   generation=1, claim_sha256="b" * 64, principal_commitment="c" * 64,
                   initialization_sha256="d" * 64,
                   installation_public_key=base64.urlsafe_b64encode(bytes(32)).decode().rstrip("="))
    p = reg.proof(evidence("CONSUMPTION", 13, binding=binding, receipt_sha256="e" * 64))
    return command(reg, "consume", 13, p)


def test_grant_to_consumption_is_atomic_and_replays(reg):
    setup_path(reg)
    c = associate(reg)
    first = reg.client().apply(c)
    assert first["evidence_class"] == "OFFLINE_CONFORMANCE"
    assert first["qualification_pass"] is False
    assert "approved" not in first
    before = reg.snapshot()
    assert reg.client().apply(c) == first | {"result_kind": "REPLAY"}
    assert reg.snapshot() == before
    consume = consumption(reg)
    result = reg.client().apply(consume)
    assert reg.client().apply(consume) == result | {"result_kind": "REPLAY"}
    with reg.admin() as db:
        row = db.execute("SELECT claim,consumed_operation,entitlement FROM "
                         "licensing_register.consumptions").fetchone()
        assert tuple(map(str, row)) == (uid(14), uid(15), uid(12))
        assert db.execute("SELECT count(*) FROM licensing_register.journal").fetchone()[0] == 5


@pytest.mark.parametrize("kind,record,role", [("grant", 10, "licensing"),
    ("enrollment", 11, "enrollment"), ("association", 13, "licensing")])
def test_withdrawal_preserves_history_and_replay_is_not_authority(reg, kind, record, role):
    setup_path(reg)
    c = associate(reg)
    reg.client().apply(c)
    reg.client().apply(consumption(reg))
    reg.client(role).apply(command(reg, "withdraw_" + kind, record, revision=1))
    before = reg.snapshot()
    assert reg.client().apply(c)["result_kind"] == "REPLAY"
    assert reg.snapshot() == before
    with reg.admin() as db:
        assert db.execute("SELECT count(*) FROM licensing_register.consumptions").fetchone()[0] == 1


@pytest.mark.parametrize("changed", ["operation_content", "proof_scope", "actor_scope",
                                     "entitlement", "grant", "enrollment"])
def test_conflicting_facts_leave_snapshot_unchanged(reg, changed):
    import psycopg
    setup_path(reg)
    c = associate(reg)
    reg.client().apply(c)
    role = "licensing"
    if changed == "operation_content":
        c = c | {"record_id": uid(99)}
    elif changed == "actor_scope":
        role = "other"
    elif changed == "proof_scope":
        proof = evidence("ASSOCIATION", 13, organization_id=uid(2), grant_id=uid(10),
                         enrollment_id=uid(11), entitlement_id=uid(12), verification_ref=uid(22))
        c = command(reg, "associate", 13, reg.proof(proof))
    else:
        c = associate(reg, **{changed + "_id": uid(99)})
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client(role).apply(c)
    assert reg.snapshot() == before


@pytest.mark.parametrize("mismatch", ["record", "kind", "consumed_entitlement", "issued_grant"])
def test_existing_mismatched_proof_refuses_with_valid_control(reg, mismatch):
    import psycopg
    setup_path(reg)
    # Both commercial sources and entitlements exist: an FK alone cannot protect the binding.
    grant = reg.proof(evidence("GRANT", 30, provenance_ref=uid(40), policy_revision=1))
    reg.client().apply(command(reg, "grant", 30, grant))
    issuance = reg.proof(evidence("ISSUANCE", 32, grant_id=uid(30), envelope_sha256="f" * 64))
    reg.client().apply(command(reg, "issuance", 32, issuance))
    if mismatch == "record":
        # An existing record's proof cannot authorize creating another record.
        bad = command(reg, "grant", 31, grant)
        good = command(reg, "grant", 31, reg.proof(evidence(
            "GRANT", 31, provenance_ref=uid(41), policy_revision=1)))
    elif mismatch == "kind":
        with reg.admin() as db:
            proof = str(db.execute("SELECT proof FROM licensing_register.enrollments "
                                   "WHERE id=%s", (uid(11),)).fetchone()[0])
        bad = command(reg, "grant", 11, proof)
        good = command(reg, "grant", 11, reg.proof(evidence(
            "GRANT", 11, provenance_ref=uid(41), policy_revision=1)))
    elif mismatch == "consumed_entitlement":
        reg.client().apply(associate(reg))
        bad = consumption(reg, entitlement=32)
        good = consumption(reg)
    else:
        bad = associate(reg, entitlement_id=uid(32))
        good = associate(reg, entitlement_id=uid(32), grant_id=uid(30))
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client().apply(bad)
    assert reg.snapshot() == before
    result = reg.client().apply(good)
    assert result["result_kind"] == "RECORDED"
    assert result["qualification_pass"] is False


@pytest.mark.parametrize("kind,record,role", [("grant", 10, "licensing"),
                                             ("enrollment", 11, "enrollment")])
def test_withdrawal_before_association_refuses(reg, kind, record, role):
    import psycopg
    setup_path(reg)
    c = associate(reg)
    reg.client(role).apply(command(reg, "withdraw_" + kind, record, revision=1))
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
        reg.client().apply(c)
    assert before == reg.snapshot()


def test_changed_signature_or_real_qualification_is_not_importable(reg):
    from pydantic import ValidationError
    p, sig = reg.sign(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    with pytest.raises(InvalidSignature):
        reg.import_proof(p | {"organization_id": uid(2)}, sig)
    with pytest.raises(ValidationError):
        reg.import_proof(p | {"qualification_pass": True}, sig)
    with reg.admin() as db:
        assert db.execute("SELECT count(*) FROM licensing_register.proofs").fetchone()[0] == 0


@pytest.mark.parametrize("statement", [
    "INSERT INTO licensing_register.control VALUES(false,null,false,0,null)",
    "UPDATE licensing_register.grants SET state='CURRENT'",
    "INSERT INTO licensing_register.proofs SELECT * FROM licensing_register.proofs",
    "SELECT * FROM licensing_register.proofs",
    "SELECT licensing_register.snapshot()",
    "SET ROLE register_owner",
])
def test_application_has_execute_only_access(reg, statement):
    import psycopg
    with reg.client().connect() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.execute(statement)


def test_session_identity_cannot_be_supplied_via_set_role_or_command(reg):
    import psycopg
    proof = reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    c = command(reg, "grant", 10, proof)
    with pytest.raises(psycopg.Error, match="UNAUTHORIZED"):
        reg.client("enrollment").apply(c)
    with reg.client("other").connect() as db:
        db.execute("SET ROLE register_licensing")
        from qualification.licensing_register.fixture import execute
        with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
            execute(db, c)


def test_revoked_actor_cannot_replay(reg):
    import psycopg
    proof = reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    c = command(reg, "grant", 10, proof)
    reg.client().apply(c)
    with reg.admin() as db:
        db.execute("UPDATE licensing_register.actors SET active=false "
                   "WHERE login='actor_licensing'")
    with pytest.raises(psycopg.Error, match="UNAUTHORIZED"):
        reg.client().apply(c)


def test_stale_revision_and_epoch_are_not_defaults(reg):
    import psycopg
    setup_path(reg)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="REVISION_CONFLICT"):
        reg.client().apply(command(reg, "withdraw_grant", 10, revision=2))
    with pytest.raises(psycopg.Error, match="REGISTER_LOCKED"):
        reg.client().apply(command(reg, "withdraw_grant", 10, revision=1, epoch=uid(77)))
    assert reg.snapshot() == before


@pytest.mark.parametrize("mutation", [
    "UPDATE licensing_register.grants SET state='WITHDRAWN'",
    "UPDATE licensing_register.proofs SET document=jsonb_set(document,'{policy_revision}','2')",
    "UPDATE licensing_register.journal SET result='{}'",
    "DELETE FROM licensing_register.journal",
    "UPDATE licensing_register.control SET sequence=0",
    "DELETE FROM licensing_register.control",
])
def test_corrupt_history_is_stop_even_on_replay(reg, mutation):
    import psycopg
    p = reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    c = command(reg, "grant", 10, p)
    reg.client().apply(c)
    with reg.admin() as db:
        db.execute(mutation)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="HISTORY_CORRUPT"):
        reg.client().apply(c)
    assert reg.snapshot() == before


def test_restore_locks_current_and_old_epoch_with_no_unlock(reg):
    import psycopg
    setup_path(reg)
    c = associate(reg)
    reg.lock_restored()
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="REGISTER_LOCKED"):
        reg.client().apply(c)
    with reg.admin() as db:
        epoch = str(db.execute("SELECT epoch FROM licensing_register.control").fetchone()[0])
    with pytest.raises(psycopg.Error, match="REGISTER_LOCKED"):
        reg.client().apply(c | {"epoch": epoch})
    assert reg.snapshot() == before


def test_rollback_and_lost_reply(reg):
    from qualification.licensing_register.fixture import execute
    p = reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    c = command(reg, "grant", 10, p)
    before = reg.snapshot()
    db = reg.client().connect()
    execute(db, c)
    db.close()  # Uncommitted connection loss must roll back the entire owner transaction.
    assert reg.snapshot() == before
    db = reg.client().connect()
    res = execute(db, c)
    db.commit()
    db.close()  # Caller loses the reply; next call must recover the exact committed result.
    assert reg.client().apply(c) == res | {"result_kind": "REPLAY"}


def _run_client(args, c, pipe):
    from qualification.licensing_register.fixture import Client
    try:
        client = Client(args, c["epoch"])
        with client.connect() as db:
            pipe.send(db.info.backend_pid)
            from qualification.licensing_register.fixture import execute
            result = execute(db, c)
        pipe.send(("OK", result))
    except Exception as exc:
        pipe.send(("ERROR", str(exc)))
    finally:
        pipe.close()


def wait_for_lock(reg, pid):
    deadline = time.monotonic() + 10
    with reg.admin() as db:
        while time.monotonic() < deadline:
            row = db.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",
                             (pid,)).fetchone()
            if row and row[0] == "Lock":
                return
            db.execute("SELECT pg_stat_clear_snapshot()")
            time.sleep(.01)
    raise AssertionError("second writer did not reach real PostgreSQL lock wait")


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("withdraw_first", [True, False])
def test_withdrawal_race_has_one_serial_order(reg, repeat, withdraw_first):
    from qualification.licensing_register.fixture import execute
    setup_path(reg)
    a = associate(reg)
    w = command(reg, "withdraw_grant", 10, revision=1)
    first, second = (w, a) if withdraw_first else (a, w)
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_run_client, args=(reg.client()._args, second, child))
    with reg.client().connect() as db:
        execute(db, first)
        proc.start()
        child.close()
        assert parent.poll(10)
        pid = parent.recv()
        wait_for_lock(reg, pid)
    assert parent.poll(10)
    status, result = parent.recv()
    proc.join(10)
    assert proc.exitcode == 0
    assert status == ("ERROR" if withdraw_first else "OK")
    if withdraw_first:
        assert "AUTHORITY_NOT_CURRENT" in result
    with reg.admin() as db:
        count = db.execute("SELECT count(*) FROM licensing_register.associations").fetchone()[0]
        assert count == (not withdraw_first)


@pytest.mark.parametrize("source", [True, False])
def test_db_clock_rechecked_after_lock_wait(reg, source):
    # Actual DB clock; no Python time override can make expired evidence current.
    setup_path(reg, lifetime=timedelta(seconds=5) if not source else timedelta(minutes=10),
               source_lifetime=timedelta(seconds=5) if source else None)
    c = associate(reg)
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_run_client, args=(reg.client()._args, c, child))
    with reg.admin() as db:
        db.execute("SELECT * FROM licensing_register.control FOR UPDATE")
        proc.start()
        child.close()
        assert parent.poll(10)
        wait_for_lock(reg, parent.recv())
        db.execute("SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM "
                   "(LEAST(expires,source_expires)-clock_timestamp()))) + 0.05) "
                   "FROM licensing_register.enrollments")
    assert parent.poll(10)
    status, result = parent.recv()
    proc.join(10)
    assert proc.exitcode == 0
    assert status == "ERROR" and "AUTHORITY_NOT_CURRENT" in result
    with reg.admin() as db:
        assert db.execute("SELECT count(*) FROM licensing_register.associations").fetchone()[0] == 0


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("conflict", [False, True])
def test_competing_associations_commit_once(reg, repeat, conflict):
    from qualification.licensing_register.fixture import execute
    setup_path(reg)
    first = associate(reg)
    second = first
    if conflict:
        proof = reg.proof(evidence("ASSOCIATION", 99, grant_id=uid(10),
            enrollment_id=uid(11), entitlement_id=uid(12), verification_ref=uid(22)))
        second = command(reg, "associate", 99, proof)
        if repeat % 2:
            first, second = second, first
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_run_client, args=(reg.client()._args, second, child))
    with reg.client().connect() as db:
        result = execute(db, first)
        proc.start()
        child.close()
        assert parent.poll(10)
        wait_for_lock(reg, parent.recv())
    assert parent.poll(10)
    status, reply = parent.recv()
    proc.join(10)
    assert proc.exitcode == 0
    if conflict:
        assert status == "ERROR" and "BINDING_CONFLICT" in reply
    else:
        assert status == "OK" and reply == result | {"result_kind": "REPLAY"}
    with reg.admin() as db:
        assert db.execute("SELECT count(*) FROM licensing_register.associations").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM licensing_register.journal").fetchone()[0] == 4


@pytest.mark.parametrize("table,event", [("grants", "INSERT"), ("journal", "INSERT"),
                                       ("control", "UPDATE")])
def test_failure_after_each_write_rolls_back_whole_command(reg, table, event):
    import psycopg
    from psycopg import sql
    p = reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1))
    c = command(reg, "grant", 10, p)
    # Fixture-admin fault injection; no application hook or privilege is added.
    with reg.admin() as db:
        db.execute("CREATE FUNCTION public.inject_fault() RETURNS trigger LANGUAGE plpgsql "
                   "AS $$ BEGIN RAISE EXCEPTION 'INJECTED_WRITE_FAILURE'; END $$")
        db.execute(sql.SQL("CREATE TRIGGER injected AFTER {} ON licensing_register.{} "
                           "FOR EACH ROW EXECUTE FUNCTION public.inject_fault()").format(
                               sql.SQL(event), sql.Identifier(table)))
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="INJECTED_WRITE_FAILURE"):
        reg.client().apply(c)
    assert reg.snapshot() == before
    # Remove only the injected behavior, retaining the trigger/function for inspection.
    with reg.admin() as db:
        db.execute("CREATE OR REPLACE FUNCTION public.inject_fault() RETURNS trigger "
                   "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
    assert reg.client().apply(c)["result_kind"] == "RECORDED"


@pytest.mark.parametrize("mutation", [
    "DELETE FROM licensing_register.consumptions",
    "UPDATE licensing_register.consumptions SET consumed_operation="
    "'00000099-1111-4111-8111-111111111111'",
])
def test_missing_or_rekeyed_original_consumption_is_corruption(reg, mutation):
    import psycopg
    setup_path(reg)
    reg.client().apply(associate(reg))
    c = consumption(reg)
    reg.client().apply(c)
    with reg.admin() as db:
        db.execute(mutation)
    before = reg.snapshot()
    for request in (c, command(reg, "withdraw_grant", 10, revision=1)):
        with pytest.raises(psycopg.Error, match="HISTORY_CORRUPT"):
            reg.client().apply(request)
        assert reg.snapshot() == before


@pytest.mark.parametrize("expected", [None, 0, -1, True, False, "", "1", 2**63])
def test_raw_sql_cannot_bypass_revision_boundary(reg, expected):
    import psycopg
    # Text "1" is a valid SQL bigint literal; a SQL caller has already selected its type.
    # It must still fail the stored-head check on this empty fixture.
    before = reg.snapshot()
    with reg.client().connect() as db, pytest.raises(psycopg.Error):
        db.execute("SELECT licensing_register.apply('withdraw_grant',%s,%s,%s,NULL,%s)",
                   (str(uuid4()), reg.epoch, uid(10), expected))
    assert reg.snapshot() == before
