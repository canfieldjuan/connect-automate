"""Offline association transitions over real PostgreSQL and synthetic proofs."""

from uuid import UUID, uuid4

import pytest
from test_register_enrollment_change import begin, compete, finish
from test_register_postgres import associate, command, consumption, evidence, setup_path, uid
from test_register_postgres import cluster as cluster
from test_register_postgres import pytestmark as pytestmark
from test_register_postgres import reg as reg


def correct(reg, *, revision=1, proof_fields=None, **fields):
    proof = evidence(
        "ASSOCIATION_CORRECTION",
        13,
        expected_revision=revision,
        grant_id=uid(10),
        grant_revision=1,
        enrollment_id=uid(11),
        enrollment_revision=1,
        entitlement_id=uid(12),
        verification_ref=uid(22),
    ) | (proof_fields or {})
    return command(reg, "correct_association", 13, reg.proof(proof), revision=revision, **fields)


def setup_association(reg, *, consumed=False):
    setup_path(reg)
    reg.client().apply(associate(reg))
    if consumed:
        reg.client().apply(consumption(reg))


def consumed_rows(reg):
    with reg.admin() as db:
        return db.execute("SELECT * FROM licensing_register.consumptions ORDER BY id").fetchall()


def test_correction_retains_decisions_and_original_consumption(reg):
    setup_association(reg, consumed=True)
    original = consumed_rows(reg)
    reg.client("enrollment").apply(begin(reg))
    reg.client("enrollment").apply(finish(reg))
    c = correct(reg, proof_fields={"enrollment_revision": 3})
    result = reg.client().apply(c)
    assert result["revision"] == 2 and result["qualification_pass"] is False
    assert consumed_rows(reg) == original
    with reg.admin() as db:
        assert db.execute(
            "SELECT revision,enrollment_revision FROM "
            "licensing_register.association_revisions ORDER BY revision"
        ).fetchall() == [(1, 1), (2, 3)]
    before = reg.snapshot()
    assert reg.client().apply(c) == result | {"result_kind": "REPLAY"}
    assert reg.snapshot() == before


def new_enrollment(reg, record=41, organization=1):
    p = reg.proof(
        evidence(
            "ENROLLMENT",
            record,
            organization_id=uid(organization),
            registration_ref=uid(42),
            authority_expires_at="2099-01-01T00:00:00Z",
            required_source_expires_at=None,
        )
    )
    if organization == 1:
        reg.client("enrollment").apply(command(reg, "enroll", record, p))
    else:
        with reg.admin() as db:
            db.execute(
                "UPDATE licensing_register.actors SET lane='ENROLLMENT' WHERE login='actor_other'"
            )
        reg.client("other").apply(command(reg, "enroll", record, p))


@pytest.mark.parametrize("other_enrollment", [False, True])
@pytest.mark.parametrize("withdrawn", [False, True])
def test_correction_can_restore_or_keep_same_support_and_verification(
    reg, other_enrollment, withdrawn
):
    setup_association(reg, consumed=True)
    original = consumed_rows(reg)
    if other_enrollment:
        new_enrollment(reg)
    if withdrawn:
        reg.client().apply(command(reg, "withdraw_association", 13, revision=1))
    rev = 2 if withdrawn else 1
    result = reg.client().apply(
        correct(
            reg, revision=rev, proof_fields={"enrollment_id": uid(41 if other_enrollment else 11)}
        )
    )
    assert result["revision"] == rev + 1
    assert consumed_rows(reg) == original
    with reg.admin() as db:
        assert db.execute(
            "SELECT state,decision_revision,enrollment FROM licensing_register.associations"
        ).fetchone() == ("CURRENT", rev + 1, UUID(uid(41 if other_enrollment else 11)))


@pytest.mark.parametrize("support", ["grant", "enrollment", "expired"])
def test_withdrawal_and_historical_consume_do_not_require_current_support(reg, support):
    setup_association(reg)
    c = consumption(reg)
    if support == "expired":
        # The controlled clock isolates withdrawal's exemption; real elapsed expiry is tested below.
        freeze_association_clock(reg, "2100-01-01T00:00:00Z")
    else:
        reg.client("enrollment" if support == "enrollment" else "licensing").apply(
            command(reg, "withdraw_" + support, 11 if support == "enrollment" else 10, revision=1)
        )
    reg.client().apply(command(reg, "withdraw_association", 13, revision=1))
    reg.client().apply(command(reg, "withdraw_association", 13, revision=2))
    reg.client().apply(c)
    with reg.admin() as db:
        assert db.execute(
            "SELECT state,decision_revision,proof,grant_id,enrollment FROM "
            "licensing_register.associations"
        ).fetchone() == ("WITHDRAWN", 1, None, None, None)
    assert len(consumed_rows(reg)) == 1


@pytest.mark.parametrize(
    "field",
    [
        "record_id",
        "organization_id",
        "expected_revision",
        "entitlement_id",
        "grant_id",
        "enrollment_id",
        "grant_revision",
        "enrollment_revision",
    ],
)
def test_correction_existing_wrong_bindings(reg, field):
    import psycopg

    setup_association(reg)
    new_enrollment(reg, organization=2)
    gp = reg.proof(evidence("GRANT", 31, provenance_ref=uid(32), policy_revision=1))
    reg.client().apply(command(reg, "grant", 31, gp))
    ip = reg.proof(evidence("ISSUANCE", 43, grant_id=uid(10), envelope_sha256="a" * 64))
    reg.client().apply(command(reg, "issuance", 43, ip))
    ap = reg.proof(
        evidence(
            "ASSOCIATION",
            44,
            grant_id=uid(10),
            enrollment_id=uid(11),
            entitlement_id=uid(43),
            verification_ref=uid(22),
        )
    )
    reg.client().apply(command(reg, "associate", 44, ap))
    values = {
        "record_id": uid(44),
        "organization_id": uid(2),
        "expected_revision": 2,
        "entitlement_id": uid(43),
        "grant_id": uid(31),
        "enrollment_id": uid(41),
        "grant_revision": 2,
        "enrollment_revision": 2,
    }
    bad = correct(reg, proof_fields={field: values[field]})
    before = reg.snapshot()
    error = (
        "REVISION_CONFLICT"
        if field in ("grant_revision", "enrollment_revision")
        else "BINDING_CONFLICT"
    )
    with pytest.raises(psycopg.Error, match=error):
        reg.client().apply(bad)
    assert reg.snapshot() == before
    reg.client().apply(correct(reg))


@pytest.mark.parametrize("support", ["grant", "PENDING", "UNAVAILABLE", "WITHDRAWN"])
def test_current_state_required_even_with_matching_support_revisions(reg, support):
    import psycopg

    setup_association(reg)
    if support == "grant":
        reg.client().apply(command(reg, "withdraw_grant", 10, revision=1))
        fields = {"grant_revision": 2}
    else:
        reason = {
            "PENDING": "SOURCE_UPDATED",
            "UNAVAILABLE": "SOURCE_UNAVAILABLE",
            "WITHDRAWN": "AUTHORITY_WITHDRAWN",
        }[support]
        reg.client("enrollment").apply(begin(reg, reason=reason))
        fields = {"enrollment_revision": 2}
    c = correct(reg, proof_fields=fields)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
        reg.client().apply(c)
    assert reg.snapshot() == before


def test_replay_stale_proof_and_initial_creation_never_reactivate(reg):
    import psycopg

    setup_path(reg)
    initial = associate(reg)
    reg.client().apply(initial)
    c = correct(reg)
    result = reg.client().apply(c)
    withdrawal = command(reg, "withdraw_association", 13, revision=2)
    reg.client().apply(withdrawal)
    before = reg.snapshot()
    for old in (initial, c, withdrawal):
        assert reg.client().apply(old)["result_kind"] == "REPLAY"
    for bad, error in (
        (c | {"operation_id": str(uuid4())}, "REVISION_CONFLICT"),
        (c | {"operation_id": str(uuid4()), "expected_revision": 3}, "BINDING_CONFLICT"),
        (c | {"expected_revision": 3}, "BINDING_CONFLICT"),
        (initial | {"operation_id": str(uuid4())}, "BINDING_CONFLICT"),
    ):
        with pytest.raises(psycopg.Error, match=error):
            reg.client().apply(bad)
        assert reg.snapshot() == before
    reg.client().apply(correct(reg, revision=3))
    assert reg.client().apply(c) == result | {"result_kind": "REPLAY"}
    with reg.admin() as db:
        db.execute(
            "UPDATE licensing_register.actors SET active=false WHERE login='actor_licensing'"
        )
    with pytest.raises(psycopg.Error, match="UNAUTHORIZED"):
        reg.client().apply(c)


def test_correction_permission_proof_missing_commit_loss_and_restore(reg):
    import psycopg

    from qualification.licensing_register.fixture import execute

    setup_association(reg)
    c = correct(reg)
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="UNAUTHORIZED"):
        reg.client("enrollment").apply(c)
    with pytest.raises(psycopg.Error, match="SOURCE_UNAVAILABLE"):
        reg.client().apply(c | {"proof_id": uid(99)})
    with pytest.raises(psycopg.Error, match="BINDING_CONFLICT"):
        reg.client().apply(c | {"proof_id": associate(reg)["proof_id"]})
    db = reg.client().connect()
    execute(db, c)
    db.close()
    assert reg.snapshot() == before
    with reg.client().connect() as db:
        recorded = execute(db, c)
    assert reg.client().apply(c) == recorded | {"result_kind": "REPLAY"}
    reg.lock_restored()
    for request in (c, correct(reg, revision=2)):
        with pytest.raises(psycopg.Error, match="REGISTER_LOCKED"):
            reg.client().apply(request)


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "scenario",
    [
        "correction",
        "withdrawal",
        "enrollment_begin",
        "enrollment_withdrawal",
        "grant_withdrawal",
        "consumption",
    ],
)
def test_correction_races_have_one_serial_order(reg, repeat, reverse, scenario):
    setup_association(reg)
    c = correct(reg)
    other = {
        "correction": lambda: correct(reg),
        "withdrawal": lambda: command(reg, "withdraw_association", 13, revision=1),
        "enrollment_begin": lambda: begin(reg),
        "enrollment_withdrawal": lambda: command(reg, "withdraw_enrollment", 11, revision=1),
        "grant_withdrawal": lambda: command(reg, "withdraw_grant", 10, revision=1),
        "consumption": lambda: consumption(reg),
    }[scenario]()
    pair = (c, other)
    roles = ("licensing", "enrollment" if scenario.startswith("enrollment") else "licensing")
    if reverse:
        pair, roles = pair[::-1], roles[::-1]
    _, (status, response) = compete(reg, *pair, *roles)
    conflict = scenario in ("correction", "withdrawal") or (reverse and scenario != "consumption")
    assert status == ("ERROR" if conflict else "OK")
    if conflict:
        assert "REVISION_CONFLICT" in response
    if scenario == "withdrawal" and not reverse:
        reg.client().apply(command(reg, "withdraw_association", 13, revision=2))
    if scenario == "consumption":
        assert len(consumed_rows(reg)) == 1
    with reg.admin() as db:
        row = db.execute("SELECT state,revision FROM licensing_register.associations").fetchone()
        assert row == (
            ("WITHDRAWN", 2 if reverse else 3)
            if scenario == "withdrawal"
            else ("CURRENT", 1 if reverse and conflict and scenario != "correction" else 2)
        )


@pytest.mark.parametrize(
    "kind,table,event",
    [
        (kind, table, event)
        for kind in ("associate", "correct_association", "withdraw_association")
        for table, event in [
            ("association_revisions", "INSERT"),
            ("association_heads", "INSERT" if kind == "associate" else "UPDATE"),
            ("journal", "INSERT"),
            ("control", "UPDATE"),
        ]
    ],
)
def test_association_write_faults_roll_back_every_stage(reg, kind, table, event):
    import psycopg
    from psycopg import sql

    setup_path(reg)
    if kind != "associate":
        reg.client().apply(associate(reg))
    c = (
        associate(reg)
        if kind == "associate"
        else correct(reg)
        if kind == "correct_association"
        else command(reg, kind, 13, revision=1)
    )
    with reg.admin() as db:
        db.execute(
            "CREATE FUNCTION public.association_fault() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN RAISE EXCEPTION 'INJECTED_ASSOCIATION_FAILURE'; END $$"
        )
        db.execute(
            sql.SQL(
                "CREATE TRIGGER injected AFTER {} ON licensing_register.{} "
                "FOR EACH ROW EXECUTE FUNCTION public.association_fault()"
            ).format(sql.SQL(event), sql.Identifier(table))
        )
    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match="INJECTED_ASSOCIATION_FAILURE"):
        reg.client().apply(c)
    assert reg.snapshot() == before
    with reg.admin() as db:
        db.execute(
            "CREATE OR REPLACE FUNCTION public.association_fault() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"
        )
    assert reg.client().apply(c)["result_kind"] == "RECORDED"


@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM licensing_register.association_heads",
        "DELETE FROM licensing_register.association_revisions WHERE revision=1",
        "UPDATE licensing_register.association_revisions SET decision_revision=1 WHERE revision=3",
        "DELETE FROM licensing_register.proofs WHERE kind='ASSOCIATION'",
        "UPDATE licensing_register.proofs SET document=jsonb_set(document,'{verification_ref}',"
        "'\"00000099-1111-4111-8111-111111111111\"') WHERE kind='ASSOCIATION_CORRECTION'",
        "DELETE FROM licensing_register.consumptions",
        "UPDATE licensing_register.consumptions "
        "SET consumed_operation='00000099-1111-4111-8111-111111111111'",
    ],
)
def test_retained_association_corruption_stops_replay_and_correction(reg, mutation):
    import psycopg

    setup_association(reg, consumed=True)
    c = correct(reg)
    reg.client().apply(c)
    reg.client().apply(command(reg, "withdraw_association", 13, revision=2))
    with reg.admin() as db:
        db.execute("SET LOCAL session_replication_role=replica")
        db.execute(mutation)
    before = reg.snapshot()
    for request in (c, correct(reg, revision=3)):
        with pytest.raises(psycopg.Error, match="HISTORY_CORRUPT"):
            reg.client().apply(request)
        assert reg.snapshot() == before


def test_direct_sql_correction_input_and_helper_privileges(reg):
    import psycopg

    setup_association(reg)
    c = correct(reg)
    args = [
        c["command"],
        c["operation_id"],
        c["epoch"],
        c["record_id"],
        c["proof_id"],
        c["expected_revision"],
        None,
        None,
        None,
    ]
    before = reg.snapshot()
    for index, value in (
        (4, None),
        (5, None),
        (5, 0),
        (5, -1),
        (6, uid(99)),
        (7, "SOURCE_UPDATED"),
        (8, uid(99)),
    ):
        bad = args.copy()
        bad[index] = value
        with pytest.raises(psycopg.Error, match="INPUT_INVALID"), reg.client().connect() as db:
            db.execute("SELECT licensing_register.apply(%s,%s,%s,%s,%s,%s,%s,%s,%s)", bad)
        assert reg.snapshot() == before
    with pytest.raises(psycopg.errors.InsufficientPrivilege), reg.client().connect() as db:
        db.execute(
            "SELECT licensing_register.transition_association('correct_association',%s,%s,NULL,1)",
            (uid(13), uid(1)),
        )
    reg.client().apply(c)


def freeze_association_clock(reg, instant):
    """Fixture-admin clock only, to exercise exact equality in PostgreSQL, not sleep timing."""
    from psycopg import sql

    with reg.admin() as db:
        definition = db.execute(
            "SELECT pg_get_functiondef('licensing_register.transition_association("
            "licensing_register.command_kind,licensing_register.uid,licensing_register.uid,"
            "licensing_register.proofs,bigint)'::regprocedure)"
        ).fetchone()[0]
        assert definition.count("clock_timestamp()") == 1
        literal = sql.Literal(instant).as_string(db) + "::timestamptz"
        db.execute(definition.replace("clock_timestamp()", literal))


@pytest.mark.parametrize("source", [False, True])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_correction_expiry_exact_boundary(reg, source, offset):
    from datetime import timedelta

    import psycopg

    setup_path(
        reg,
        lifetime=timedelta(minutes=20 if source else 10),
        source_lifetime=timedelta(minutes=10) if source else None,
    )
    reg.client().apply(associate(reg))
    c = correct(reg)
    with reg.admin() as db:
        deadline = db.execute(
            "SELECT source_expires,expires FROM licensing_register.enrollments"
        ).fetchone()
    freeze_association_clock(
        reg, (deadline[0 if source else 1] + timedelta(microseconds=offset)).isoformat()
    )
    before = reg.snapshot()
    if offset < 0:
        reg.client().apply(c)
    else:
        with pytest.raises(psycopg.Error, match="AUTHORITY_NOT_CURRENT"):
            reg.client().apply(c)
        assert reg.snapshot() == before


@pytest.mark.parametrize("source", [False, True])
def test_correction_uses_real_clock_after_lock_wait(reg, source):
    import multiprocessing
    from datetime import timedelta

    from test_register_postgres import _run_client, wait_for_lock

    setup_path(
        reg,
        lifetime=timedelta(seconds=30 if source else 5),
        source_lifetime=timedelta(seconds=5) if source else None,
    )
    reg.client().apply(associate(reg))
    c = correct(reg)
    before = reg.snapshot()
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    proc = ctx.Process(target=_run_client, args=(reg.client()._args, c, child))
    try:
        with reg.admin() as db:
            db.execute("SELECT * FROM licensing_register.control FOR UPDATE")
            proc.start()
            child.close()
            assert parent.poll(10)
            wait_for_lock(reg, parent.recv())
            db.execute(
                "SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM "
                "(LEAST(expires,source_expires)-clock_timestamp()))) + 0.05) "
                "FROM licensing_register.enrollments"
            )
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


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("UPDATE licensing_register.association_heads SET revision=99", "ForeignKeyViolation"),
        (
            "DELETE FROM licensing_register.association_revisions WHERE revision=1",
            "ForeignKeyViolation",
        ),
        ("UPDATE licensing_register.association_heads SET original_revision=2", "CheckViolation"),
        (
            "UPDATE licensing_register.association_revisions "
            "SET decision_revision=1 WHERE revision=2",
            "CheckViolation",
        ),
        (
            "UPDATE licensing_register.association_revisions "
            "SET decision_revision=3 WHERE revision=4",
            "ForeignKeyViolation",
        ),
        (
            "UPDATE licensing_register.association_revisions "
            "SET state='WITHDRAWN' WHERE revision=2",
            "CheckViolation",
        ),
        (
            "UPDATE licensing_register.association_revisions "
            "SET decision_state='WITHDRAWN' WHERE revision=4",
            "CheckViolation",
        ),
    ],
)
def test_retained_association_structure_enforced_by_database(reg, mutation, error):
    import psycopg

    setup_association(reg, consumed=True)
    reg.client().apply(correct(reg))
    reg.client().apply(command(reg, "withdraw_association", 13, revision=2))
    reg.client().apply(command(reg, "withdraw_association", 13, revision=3))
    before = reg.snapshot()
    with pytest.raises(getattr(psycopg.errors, error)), reg.admin() as db:
        db.execute(mutation)
    assert reg.snapshot() == before


@pytest.mark.parametrize("field", ["proof", "enrollment"])
def test_retained_association_links_reject_existing_foreign_scope(reg, field):
    import psycopg
    from psycopg import sql

    setup_association(reg)
    new_enrollment(reg, organization=2)
    foreign = correct(reg, proof_fields={"record_id": uid(44)})["proof_id"]
    reg.client().apply(correct(reg))
    before = reg.snapshot()
    with pytest.raises(psycopg.errors.ForeignKeyViolation), reg.admin() as db:
        db.execute(
            sql.SQL(
                "UPDATE licensing_register.association_revisions SET {}=%s WHERE revision=2"
            ).format(sql.Identifier(field)),
            (foreign if field == "proof" else uid(41),),
        )
    assert reg.snapshot() == before


def test_cluster_flushes_committed_writes_before_shutdown_wait(tmp_path_factory, monkeypatch):
    from qualification.licensing_register import fixture

    observed = []
    run = fixture.subprocess.run
    with fixture.temporary_cluster(tmp_path_factory.getbasetemp()) as owned:
        with owned.admin("postgres") as db:
            db.execute("CREATE TABLE shutdown_proof AS SELECT generate_series(1,1000) AS n")
        with owned.admin("postgres") as db:
            committed_lsn = db.execute("SELECT pg_current_wal_insert_lsn()").fetchone()[0]

        def observe_stop(args, **kwargs):
            if args[-1] == "stop" and str(owned.root / "data") in args:
                with owned.admin("postgres") as db:
                    observed.append(
                        db.execute(
                            "SELECT checkpoint_lsn >= %s::pg_lsn FROM pg_control_checkpoint()",
                            (committed_lsn,),
                        ).fetchone()[0]
                    )
            return run(args, **kwargs)

        monkeypatch.setattr(fixture.subprocess, "run", observe_stop)
    assert observed == [True]


def test_checkpoint_failure_still_stops_owned_cluster(tmp_path_factory, monkeypatch):
    from qualification.licensing_register import fixture

    def unavailable(*args, **kwargs):
        raise RuntimeError("INJECTED_CHECKPOINT_CONNECTION_FAILURE")

    with (
        pytest.raises(RuntimeError, match="INJECTED_CHECKPOINT_CONNECTION_FAILURE"),
        fixture.temporary_cluster(tmp_path_factory.getbasetemp()) as owned,
    ):
        monkeypatch.setattr(owned, "admin", unavailable)
    assert not owned.started
    assert not (owned.root / "data" / "postmaster.pid").exists()
