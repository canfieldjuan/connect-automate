"""Register-side ordering with real PostgreSQL and signed synthetic facts only."""

import hashlib
import multiprocessing
from datetime import timedelta
from uuid import uuid4

import pytest
from test_register_postgres import (
    _run_client,
    associate,
    command,
    consumption,
    evidence,
    instant,
    setup_path,
    uid,
    wait_for_lock,
)
from test_register_postgres import (
    cluster as cluster,
)
from test_register_postgres import (
    pytestmark as pytestmark,
)
from test_register_postgres import (
    reg as reg,
)


def begin(reg, *, revision=1, change=50, reason="SOURCE_UPDATED", record=11, **fields):
    return command(reg, "begin_change", record, revision=revision,
                   change_id=uid(change), reason=reason, **fields)


def finish(reg, *, revision=2, change=50, record=11, candidate_fields=None,
           completion_fields=None):
    from qualification.owner_authority.protocol import canonical
    with reg.admin() as db:
        now = db.execute("SELECT clock_timestamp()").fetchone()[0]
    candidate = evidence("ENROLLMENT", record, registration_ref=uid(21),
                         authority_expires_at=instant(now + timedelta(minutes=10)),
                         required_source_expires_at=None) | (candidate_fields or {})
    decision = reg.proof(candidate)
    proof = evidence("ENROLLMENT_COMPLETION", record, change_id=uid(change),
        pending_revision=revision, decision_proof_id=decision,
        decision_sha256=hashlib.sha256(canonical(candidate)).hexdigest(),
        registration_ref=candidate["registration_ref"], private_revision=1,
        private_sha256="f" * 64) | (completion_fields or {})
    return command(reg, "finish_change", record, reg.proof(proof), revision=revision,
                   change_id=uid(change), decision_id=decision)


def test_begin_finish_fences_association_and_preserves_history(reg):
    import psycopg
    setup_path(reg)
    start = reg.client("enrollment").apply(begin(reg))
    assert start["revision"] == 2
    a = associate(reg)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
        reg.client().apply(a)
    assert reg.snapshot() == before
    result = reg.client("enrollment").apply(finish(reg))
    assert result["revision"] == 3 and result["qualification_pass"] is False
    reg.client().apply(a)
    with reg.admin() as db:
        assert db.execute("SELECT enrollment_revision FROM "
                          "licensing_register.associations").fetchone()[0] == 3
        assert db.execute("SELECT state FROM licensing_register.enrollment_revisions "
                          "ORDER BY revision").fetchall() == [
                              ("CURRENT",), ("PENDING",), ("CURRENT",)]


@pytest.mark.parametrize("reason", ["SOURCE_UPDATED", "SOURCE_UNAVAILABLE", "AUTHORITY_WITHDRAWN",
                                    "legacy_withdrawal"])
def test_noncurrent_recovery_preserves_original_association_and_consumption(reg, reason):
    import psycopg
    setup_path(reg)
    reg.client().apply(associate(reg))
    reg.client().apply(consumption(reg))
    c = (command(reg, "withdraw_enrollment", 11, revision=1)
         if reason == "legacy_withdrawal" else begin(reg, reason=reason))
    reg.client("enrollment").apply(c)
    with reg.admin() as db:
        assert db.execute("SELECT proof,expires,source_expires FROM "
                          "licensing_register.enrollments").fetchone() == (None, None, None)
        assert str(db.execute("SELECT prior_proof FROM licensing_register.enrollments")
                   .fetchone()[0]) != "None"
    if reason != "SOURCE_UPDATED":
        before = reg.snapshot()
        with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
            reg.client("enrollment").apply(finish(reg))
        assert reg.snapshot() == before
        reg.client("enrollment").apply(begin(reg, revision=2, change=51))
    reg.client("enrollment").apply(finish(reg, revision=2 if reason == "SOURCE_UPDATED" else 3,
                                        change=50 if reason == "SOURCE_UPDATED" else 51))
    with reg.admin() as db:
        assert db.execute("SELECT enrollment_revision FROM "
                          "licensing_register.associations").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM licensing_register.consumptions").fetchone()[0] == 1


@pytest.mark.parametrize("field", ["record_id", "organization_id", "change_id", "pending_revision",
                                  "decision_proof_id", "decision_sha256", "registration_ref",
                                  "requested_change", "candidate_record", "candidate_organization"])
def test_completion_bindings_refuse_existing_mismatches(reg, field):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    other = evidence("ENROLLMENT", 41, registration_ref=uid(42),
                     authority_expires_at="2099-01-01T00:00:00Z", required_source_expires_at=None)
    other_proof = reg.proof(other)
    reg.client("enrollment").apply(command(reg, "enroll", 41, other_proof))
    reg.client("enrollment").apply(begin(reg, record=41, change=51))
    values = {"record_id": uid(41), "organization_id": uid(2), "change_id": uid(51),
              "pending_revision": 3, "decision_proof_id": other_proof,
              "decision_sha256": "0" * 64, "registration_ref": uid(42)}
    if field == "requested_change":
        bad = finish(reg, change=51)
    elif field.startswith("candidate_"):
        fields = ({"record_id": uid(41)} if field == "candidate_record"
                  else {"organization_id": uid(2)})
        bad = finish(reg, candidate_fields=fields)
    else:
        bad = finish(reg, completion_fields={field: values[field]})
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client("enrollment").apply(bad)
    assert reg.snapshot() == before
    assert reg.client("enrollment").apply(finish(reg))["result_kind"] == "RECORDED"


@pytest.mark.parametrize("other_org", [False, True])
def test_change_id_is_unique_across_enrollments_and_organizations(reg, other_org):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    if other_org:
        with reg.admin() as db:
            db.execute("UPDATE licensing_register.actors SET lane='ENROLLMENT' "
                       "WHERE login='actor_other'")
    role = "other" if other_org else "enrollment"
    proof = reg.proof(evidence("ENROLLMENT", 41, organization_id=uid(2 if other_org else 1),
        registration_ref=uid(42), authority_expires_at="2099-01-01T00:00:00Z",
        required_source_expires_at=None))
    reg.client(role).apply(command(reg, "enroll", 41, proof))
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client(role).apply(begin(reg, record=41))
    assert reg.snapshot() == before
    assert reg.client(role).apply(begin(reg, record=41, change=51))["result_kind"] == "RECORDED"


def test_replay_is_historical_and_newer_begin_or_withdrawal_fences_finish(reg):
    import psycopg
    setup_path(reg)
    b = begin(reg)
    reg.client("enrollment").apply(b)
    old = finish(reg)
    reg.client("enrollment").apply(begin(reg, revision=2, change=51))
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="REVISION_CONFLICT"):
        reg.client("enrollment").apply(old)
    assert reg.snapshot() == before
    current = finish(reg, revision=3, change=51)
    result = reg.client("enrollment").apply(current)
    reg.client("enrollment").apply(command(reg, "withdraw_enrollment", 11, revision=4))
    before = reg.snapshot()
    assert reg.client("enrollment").apply(current) == result | {"result_kind": "REPLAY"}
    assert reg.client("enrollment").apply(b)["result_kind"] == "REPLAY"
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client("enrollment").apply(current | {"decision_id": uid(99)})
    assert reg.snapshot() == before
    with reg.admin() as db:
        db.execute("UPDATE licensing_register.actors SET active=false "
                   "WHERE login='actor_enrollment'")
    with pytest.raises(psycopg.Error, match="UNAUTHORIZED"):
        reg.client("enrollment").apply(current)


@pytest.mark.parametrize("finish_command", [False, True])
def test_change_commands_role_missing_proof_restore_and_reply_loss(reg, finish_command):
    import psycopg

    from qualification.licensing_register.fixture import execute
    setup_path(reg)
    if finish_command:
        reg.client("enrollment").apply(begin(reg))
    c = finish(reg) if finish_command else begin(reg)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="UNAUTHORIZED"):
        reg.client().apply(c)
    if finish_command:
        with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
            reg.client("enrollment").apply(c | {"proof_id": c["decision_id"]})
        for field in ("proof_id", "decision_id"):
            with pytest.raises(psycopg.Error, match="SOURCE_UNAVAILABLE"):
                reg.client("enrollment").apply(c | {field: uid(99)})
    db = reg.client("enrollment").connect()
    execute(db, c)
    db.close()
    assert reg.snapshot() == before
    with reg.client("enrollment").connect() as db:
        result = execute(db, c)
    assert reg.client("enrollment").apply(c) == result | {"result_kind": "REPLAY"}
    reg.lock_restored()
    with pytest.raises(psycopg.Error, match="REGISTER_LOCKED"):
        reg.client("enrollment").apply(c)


@pytest.mark.parametrize("field", ["authority_expires_at", "required_source_expires_at"])
def test_expired_finish_keeps_pending(reg, field):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    bad = finish(reg, candidate_fields={field: "2000-01-01T00:00:00Z"})
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
        reg.client("enrollment").apply(bad)
    assert reg.snapshot() == before
    reg.client("enrollment").apply(finish(reg))


def compete(reg, first, second, first_role="enrollment", second_role="enrollment"):
    from qualification.licensing_register.fixture import execute
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_run_client, args=(reg.client(second_role)._args, second, child))
    try:
        with reg.client(first_role).connect() as db:
            result = execute(db, first)
            proc.start()
            child.close()
            assert parent.poll(10)
            wait_for_lock(reg, parent.recv())
        assert parent.poll(10)
        return result, parent.recv()
    finally:
        if proc.pid is not None:
            proc.join(10)
            if proc.is_alive():
                proc.terminate()
                proc.join(10)
        parent.close()
        child.close()


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("scenario", ["begin_association", "finish_withdraw", "begins", "finishes"])
def test_change_process_races_have_one_serial_order(reg, repeat, reverse, scenario):
    setup_path(reg)
    roles = ("enrollment", "enrollment")
    if scenario == "begin_association":
        pair = (begin(reg), associate(reg))
        roles = ("enrollment", "licensing")
    elif scenario == "begins":
        pair = (begin(reg), begin(reg, change=51))
    else:
        reg.client("enrollment").apply(begin(reg))
        f = finish(reg)
        pair = (f, command(reg, "withdraw_enrollment", 11, revision=2)
                if scenario == "finish_withdraw" else f | {"operation_id": str(uuid4())})
    if reverse:
        pair, roles = pair[::-1], roles[::-1]
    _, (status, response) = compete(reg, *pair, *roles)
    if scenario == "begin_association" and reverse:
        assert status == "OK"
    else:
        expected = ("AUTHORITY_NOT_CURRENT" if scenario == "begin_association"
                    else "REVISION_CONFLICT")
        assert status == "ERROR" and expected in response
    if scenario == "finish_withdraw" and not reverse:
        reg.client("enrollment").apply(command(reg, "withdraw_enrollment", 11, revision=3))
    with reg.admin() as db:
        state = db.execute("SELECT state FROM licensing_register.enrollments").fetchone()[0]
        assert state == ("WITHDRAWN" if scenario == "finish_withdraw" else
                         "CURRENT" if scenario == "finishes" else "PENDING")


@pytest.mark.parametrize("source", [False, True])
def test_finish_rechecks_real_clock_after_lock_wait(reg, source):
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    with reg.admin() as db:
        now = db.execute("SELECT clock_timestamp()").fetchone()[0]
        deadline = instant(now + timedelta(seconds=5))
    c = finish(reg, candidate_fields={"required_source_expires_at" if source else
                                     "authority_expires_at": deadline})
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_run_client, args=(reg.client("enrollment")._args, c, child))
    before = reg.snapshot()
    try:
        with reg.admin() as db:
            db.execute("SELECT * FROM licensing_register.control FOR UPDATE")
            proc.start()
            child.close()
            assert parent.poll(10)
            wait_for_lock(reg, parent.recv())
            db.execute("SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM "
                       "(%s::timestamptz-clock_timestamp()))) + 0.05)", (deadline,))
        assert parent.poll(10)
        status, result = parent.recv()
        assert status == "ERROR" and "AUTHORITY_NOT_CURRENT" in result
    finally:
        if proc.pid is not None:
            proc.join(10)
            if proc.is_alive():
                proc.terminate()
                proc.join(10)
        parent.close()
        child.close()
    assert reg.snapshot() == before


@pytest.mark.parametrize("finish_command,table,event", [
    (f, table, event) for f in (False, True) for table, event in
    [("enrollment_changes", "INSERT"), ("enrollment_revisions", "INSERT"),
     ("enrollment_heads", "UPDATE"), ("journal", "INSERT"), ("control", "UPDATE")]
    if not (f and table == "enrollment_changes")])
def test_fault_after_each_enrollment_write_rolls_back(reg, finish_command, table, event):
    import psycopg
    from psycopg import sql
    setup_path(reg)
    if finish_command:
        reg.client("enrollment").apply(begin(reg))
    c = finish(reg) if finish_command else begin(reg)
    with reg.admin() as db:
        db.execute("CREATE FUNCTION public.change_fault() RETURNS trigger LANGUAGE plpgsql "
                   "AS $$ BEGIN RAISE EXCEPTION 'INJECTED_CHANGE_FAILURE'; END $$")
        db.execute(sql.SQL("CREATE TRIGGER injected AFTER {} ON licensing_register.{} "
                           "FOR EACH ROW EXECUTE FUNCTION public.change_fault()").format(
                               sql.SQL(event), sql.Identifier(table)))
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="INJECTED_CHANGE_FAILURE"):
        reg.client("enrollment").apply(c)
    assert reg.snapshot() == before
    with reg.admin() as db:
        db.execute("CREATE OR REPLACE FUNCTION public.change_fault() RETURNS trigger "
                   "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
    assert reg.client("enrollment").apply(c)["result_kind"] == "RECORDED"


@pytest.mark.parametrize("mutation", [
    "DELETE FROM licensing_register.enrollment_changes",
    "UPDATE licensing_register.enrollment_changes SET start_revision=3",
    "DELETE FROM licensing_register.enrollment_revisions WHERE revision=1",
    "DELETE FROM licensing_register.enrollment_heads",
    "UPDATE licensing_register.proofs SET document=jsonb_set(document,'{private_revision}','2') "
    "WHERE kind='ENROLLMENT_COMPLETION'",
    "UPDATE licensing_register.proofs SET canonical_sha256=repeat('0',64) WHERE kind='ENROLLMENT'",
])
def test_retained_lineage_corruption_stops_replay_and_new_change(reg, mutation):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    c = finish(reg)
    reg.client("enrollment").apply(c)
    with reg.admin() as db:
        db.execute("SET LOCAL session_replication_role=replica")
        db.execute(mutation)
    before = reg.snapshot()
    for request in (c, begin(reg, revision=3, change=51)):
        with pytest.raises(psycopg.Error, match="HISTORY_CORRUPT"):
            reg.client("enrollment").apply(request)
        assert reg.snapshot() == before


@pytest.mark.parametrize("finish_command", [False, True])
def test_direct_sql_change_input_cannot_bypass_closed_branches(reg, finish_command):
    import psycopg
    setup_path(reg)
    if finish_command:
        reg.client("enrollment").apply(begin(reg))
    c = finish(reg) if finish_command else begin(reg)
    args = [c["command"], c["operation_id"], c["epoch"], c["record_id"], c["proof_id"],
            c["expected_revision"], c["change_id"], c.get("reason"), c.get("decision_id")]
    changes = [(5, 0), (5, -1), (5, None), (6, None)]
    changes += ([(4, None), (8, None), (7, "SOURCE_UPDATED")] if finish_command
                else [(4, uid(99)), (8, uid(99)), (7, None), (7, "INITIAL")])
    before = reg.snapshot()
    for index, value in changes:
        bad = args.copy()
        bad[index] = value
        with (
            pytest.raises(psycopg.Error, match="INPUT_INVALID"),
            reg.client("enrollment").connect() as db,
        ):
            db.execute("SELECT licensing_register.apply(%s,%s,%s,%s,%s,%s,%s,%s,%s)", bad)
        assert reg.snapshot() == before
    with (
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        reg.client("enrollment").connect() as db,
    ):
        db.execute("SELECT licensing_register.transition_enrollment('enroll',%s,%s,%s,"
                   "NULL,NULL,NULL,NULL,NULL)", (str(uuid4()), uid(11), uid(1)))
    assert reg.client("enrollment").apply(c)["result_kind"] == "RECORDED"


def test_completion_private_metadata_tampering_refuses_before_import(reg):
    from cryptography.exceptions import InvalidSignature
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    c = finish(reg)
    with reg.admin() as db:
        document, signature = db.execute("SELECT document,signature FROM licensing_register.proofs "
                                         "WHERE id=%s", (c["proof_id"],)).fetchone()
        count = db.execute("SELECT count(*) FROM licensing_register.proofs").fetchone()[0]
    for field, value in (("private_revision", 2), ("private_sha256", "0" * 64)):
        with pytest.raises(InvalidSignature):
            reg.import_proof(document | {field: value}, signature)
    with reg.admin() as db:
        assert db.execute("SELECT count(*) FROM licensing_register.proofs").fetchone()[0] == count
    reg.client("enrollment").apply(c)


def test_relational_state_branches_cannot_claim_incomplete_current(reg):
    import psycopg
    setup_path(reg)
    before = reg.snapshot()
    with pytest.raises(psycopg.errors.CheckViolation), reg.admin() as db:
        db.execute("UPDATE licensing_register.enrollment_revisions SET state='PENDING'")
    assert reg.snapshot() == before
    reg.client("enrollment").apply(begin(reg))
    before = reg.snapshot()
    with pytest.raises(psycopg.errors.CheckViolation), reg.admin() as db:
        db.execute("UPDATE licensing_register.enrollment_revisions "
                   "SET state='CURRENT' WHERE revision=2")
    assert reg.snapshot() == before


@pytest.mark.parametrize("field", ["proof", "prior_proof", "completion", "change_id"])
def test_retained_revision_links_cannot_cross_existing_enrollments(reg, field):
    import psycopg
    from psycopg import sql
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    reg.client("enrollment").apply(finish(reg))
    proof = reg.proof(evidence("ENROLLMENT", 41, registration_ref=uid(42),
        authority_expires_at="2099-01-01T00:00:00Z", required_source_expires_at=None))
    reg.client("enrollment").apply(command(reg, "enroll", 41, proof))
    reg.client("enrollment").apply(begin(reg, record=41, change=51))
    reg.client("enrollment").apply(finish(reg, record=41, change=51))
    with reg.admin() as db:
        other = db.execute(sql.SQL("SELECT {} FROM licensing_register.enrollments WHERE id=%s")
                           .format(sql.Identifier(field)), (uid(41),)).fetchone()[0]
    before = reg.snapshot()
    with pytest.raises(psycopg.errors.ForeignKeyViolation), reg.admin() as db:
        db.execute(sql.SQL("UPDATE licensing_register.enrollment_revisions SET {}=%s "
                           "WHERE id=%s AND revision=3").format(sql.Identifier(field)),
                   (other, uid(11)))
    assert reg.snapshot() == before


def test_completion_cannot_use_earlier_change_of_same_enrollment(reg):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    reg.client("enrollment").apply(begin(reg, revision=2, change=51))
    bad = finish(reg, revision=3, change=50)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client("enrollment").apply(bad)
    assert reg.snapshot() == before
    reg.client("enrollment").apply(finish(reg, revision=3, change=51))


@pytest.mark.parametrize("field", ["record_id", "organization_id"])
def test_candidate_scope_precedes_expiry(reg, field):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    bad = finish(reg, candidate_fields={field: uid(2 if field == "organization_id" else 41),
                                       "authority_expires_at": "2000-01-01T00:00:00Z"})
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client("enrollment").apply(bad)
    assert reg.snapshot() == before
    reg.client("enrollment").apply(finish(reg))


def test_wrong_kind_candidate_is_binding_refusal(reg):
    import psycopg

    from qualification.owner_authority.protocol import canonical
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg))
    c = finish(reg)
    with reg.admin() as db:
        candidate = db.execute("SELECT document FROM licensing_register.proofs WHERE id=%s",
                               (c["proof_id"],)).fetchone()[0]
    outer = candidate | {"proof_id": str(uuid4()), "decision_proof_id": c["proof_id"],
                         "decision_sha256": hashlib.sha256(canonical(candidate)).hexdigest()}
    bad = c | {"operation_id": str(uuid4()), "proof_id": reg.proof(outer),
               "decision_id": c["proof_id"]}
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client("enrollment").apply(bad)
    assert reg.snapshot() == before
    reg.client("enrollment").apply(c)


@pytest.mark.parametrize("reason", ["SOURCE_UNAVAILABLE", "AUTHORITY_WITHDRAWN"])
def test_other_noncurrent_heads_deny_association_until_evidenced_recovery(reg, reason):
    import psycopg
    setup_path(reg)
    reg.client("enrollment").apply(begin(reg, reason=reason))
    a = associate(reg)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
        reg.client().apply(a)
    assert reg.snapshot() == before
    reg.client("enrollment").apply(begin(reg, revision=2, change=51))
    reg.client("enrollment").apply(finish(reg, revision=3, change=51,
        candidate_fields={"required_source_expires_at": "2099-01-01T00:00:00Z"}))
    reg.client().apply(a)
    with reg.admin() as db:
        assert db.execute("SELECT enrollment_revision FROM "
                          "licensing_register.associations").fetchone()[0] == 4
