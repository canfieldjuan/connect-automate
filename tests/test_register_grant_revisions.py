"""Retained synthetic grant decisions and historical issuance on real PostgreSQL."""

import pytest
from test_register_postgres import cluster as cluster
from test_register_postgres import command, evidence, setup_path, uid
from test_register_postgres import pytestmark as pytestmark
from test_register_postgres import reg as reg


def revise(reg, revision=1, **fields):
    p = (
        evidence(
            "GRANT_REVISION",
            10,
            expected_revision=revision,
            provenance_ref=uid(20),
            policy_revision=1,
        )
        | fields
    )
    return command(reg, "revise_grant", 10, reg.proof(p), revision=revision)


def test_revision_lifecycle_retains_history(reg):
    setup_path(reg)
    reg.client().apply(revise(reg))
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=2))
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=3))
    reg.client().apply(revise(reg, 4))
    with reg.admin() as db:
        assert db.execute(
            "SELECT revision,state,decision_revision FROM "
            "licensing_register.grant_revisions ORDER BY revision"
        ).fetchall() == [
            (1, "CURRENT", 1),
            (2, "CURRENT", 2),
            (3, "WITHDRAWN", 2),
            (4, "WITHDRAWN", 2),
            (5, "CURRENT", 5),
        ]
        assert db.execute("SELECT revision,state FROM licensing_register.grants").fetchone() == (
            5,
            "CURRENT",
        )


def test_issuance_revision_cannot_default():
    from pydantic import ValidationError

    from qualification.licensing_register.protocol import EVIDENCE

    p = evidence("ISSUANCE", 12, grant_id=uid(10), envelope_sha256="a" * 64)
    with pytest.raises(ValidationError, match="grant_revision"):
        EVIDENCE.validate_python(p)


def issuance(reg, record=40, revision=1, **fields):
    p = (
        evidence(
            "ISSUANCE", record, grant_id=uid(10), grant_revision=revision, envelope_sha256="a" * 64
        )
        | fields
    )
    return command(reg, "issuance", record, reg.proof(p))


def assert_refuses(reg, request, error, role="licensing"):
    import psycopg

    before = reg.snapshot()
    with pytest.raises(psycopg.Error, match=error):
        reg.client(role).apply(request)
    assert reg.snapshot() == before


def rows(reg, table):
    from psycopg import sql

    with reg.admin() as db:
        return db.execute(
            sql.SQL("SELECT * FROM licensing_register.{} ORDER BY 1").format(sql.Identifier(table))
        ).fetchall()


def test_historical_issuance_restoration_and_original_consumption(reg):
    from test_register_association_correction import correct
    from test_register_postgres import associate, consumption

    setup_path(reg)
    reg.client().apply(associate(reg))
    reg.client().apply(consumption(reg))
    original = rows(reg, "consumptions"), rows(reg, "issuances")
    reg.client().apply(revise(reg))
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=2))
    # The envelope was attested under decision 1; its recording may arrive late.
    delayed = issuance(reg)
    reg.client().apply(delayed)
    assert_refuses(reg, issuance(reg, record=41, revision=3), "AUTHORITY_NOT_CURRENT")
    assert_refuses(reg, correct(reg, proof_fields={"grant_revision": 3}), "AUTHORITY_NOT_CURRENT")
    reg.client().apply(revise(reg, 3))
    reg.client().apply(correct(reg, proof_fields={"grant_revision": 4}))
    reg.client().apply(issuance(reg, record=42, revision=2))
    reg.client().apply(issuance(reg, record=43, revision=4))
    with reg.admin() as db:
        assert db.execute(
            "SELECT grant_revision FROM licensing_register.associations"
        ).fetchone() == (4,)
        assert db.execute(
            "SELECT grant_revision FROM licensing_register.issuances ORDER BY id"
        ).fetchall() == [(1,), (1,), (2,), (4,)]
    assert rows(reg, "consumptions") == original[0]
    assert rows(reg, "issuances")[0] == original[1][0]
    before = reg.snapshot()
    assert reg.client().apply(delayed)["result_kind"] == "REPLAY"
    assert reg.snapshot() == before


def test_new_association_uses_current_grant_but_keeps_historical_issuance(reg):
    from test_register_postgres import associate

    setup_path(reg)
    a = associate(reg)
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=1))
    assert_refuses(reg, a, "AUTHORITY_NOT_CURRENT")
    reg.client().apply(revise(reg, 2))
    reg.client().apply(a)
    with reg.admin() as db:
        assert db.execute(
            "SELECT grant_revision FROM licensing_register.associations"
        ).fetchone() == (3,)
        assert db.execute("SELECT grant_revision FROM licensing_register.issuances").fetchone() == (
            1,
        )


@pytest.mark.parametrize("field", ["record_id", "organization_id", "expected_revision", "kind"])
def test_revision_wrong_existing_binding_and_kind(reg, field):
    setup_path(reg)
    p = reg.proof(evidence("GRANT", 30, provenance_ref=uid(20), policy_revision=1))
    reg.client().apply(command(reg, "grant", 30, p))
    fields = {"record_id": uid(30), "organization_id": uid(2), "expected_revision": 2}
    bad = (
        revise(reg, **{field: fields[field]})
        if field != "kind"
        else command(
            reg,
            "revise_grant",
            10,
            reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1)),
            revision=1,
        )
    )
    assert_refuses(reg, bad, "BINDING_CONFLICT")
    assert reg.client().apply(revise(reg))["revision"] == 2


@pytest.mark.parametrize("field", ["grant_id", "organization_id", "record_id", "grant_revision"])
def test_issuance_wrong_binding(reg, field):
    setup_path(reg)
    p = reg.proof(
        evidence("GRANT", 30, organization_id=uid(2), provenance_ref=uid(20), policy_revision=1)
    )
    reg.client("other").apply(command(reg, "grant", 30, p))
    values = {
        "grant_id": uid(30),
        "organization_id": uid(2),
        "record_id": uid(12),
        "grant_revision": 99,
    }
    assert_refuses(reg, issuance(reg, **{field: values[field]}), "BINDING_CONFLICT")
    assert reg.client().apply(issuance(reg))["result_kind"] == "RECORDED"


def test_replay_stale_proof_and_recreation_do_not_restore(reg):
    from uuid import uuid4

    setup_path(reg)
    with reg.admin() as db:
        proof = str(db.execute("SELECT proof FROM licensing_register.grants").fetchone()[0])
    initial = command(reg, "grant", 10, proof)
    c = revise(reg)
    result = reg.client().apply(c)
    w = command(reg, "withdraw_grant", 10, revision=2)
    reg.client().apply(w)
    for old in (c, w):
        before = reg.snapshot()
        assert reg.client().apply(old)["result_kind"] == "REPLAY"
        assert reg.snapshot() == before
    for bad, error in (
        (c | {"operation_id": str(uuid4())}, "REVISION_CONFLICT"),
        (c | {"operation_id": str(uuid4()), "expected_revision": 3}, "BINDING_CONFLICT"),
        (c | {"expected_revision": 3}, "BINDING_CONFLICT"),
        (initial, "BINDING_CONFLICT"),
    ):
        assert_refuses(reg, bad, error)
    reg.client().apply(revise(reg, 3))
    assert reg.client().apply(c) == result | {"result_kind": "REPLAY"}
    with reg.admin() as db:
        db.execute(
            "UPDATE licensing_register.actors SET active=false WHERE login='actor_licensing'"
        )
    assert_refuses(reg, c, "UNAUTHORIZED")


def test_withdrawal_and_consumption_remain_available_with_noncurrent_support(reg):
    from test_register_postgres import associate, consumption

    setup_path(reg)
    reg.client().apply(associate(reg))
    reg.client("enrollment").apply(command(reg, "withdraw_enrollment", 11, revision=1))
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=1))
    reg.client().apply(command(reg, "withdraw_association", 13, revision=1))
    reg.client().apply(consumption(reg))
    original = rows(reg, "consumptions"), rows(reg, "association_revisions")
    reg.client().apply(revise(reg, 2))
    assert (rows(reg, "consumptions"), rows(reg, "association_revisions")) == original


@pytest.mark.parametrize("kind", ["revise_grant", "withdraw_grant", "issuance"])
def test_commit_loss_scope_and_restore(reg, kind):
    from qualification.licensing_register.fixture import execute

    setup_path(reg)
    c = (
        revise(reg)
        if kind == "revise_grant"
        else issuance(reg)
        if kind == "issuance"
        else command(reg, kind, 10, revision=1)
    )
    assert_refuses(reg, c, "UNAUTHORIZED", "enrollment")
    assert_refuses(
        reg, c, "REVISION_CONFLICT" if kind == "withdraw_grant" else "BINDING_CONFLICT", "other"
    )
    if kind != "withdraw_grant":
        assert_refuses(reg, c | {"proof_id": uid(99)}, "SOURCE_UNAVAILABLE")
    before = reg.snapshot()
    db = reg.client().connect()
    execute(db, c)
    db.close()
    assert reg.snapshot() == before
    with reg.client().connect() as db:
        result = execute(db, c)
    assert reg.client().apply(c) == result | {"result_kind": "REPLAY"}
    reg.lock_restored()
    assert_refuses(reg, c, "REGISTER_LOCKED")
    with reg.admin() as db:
        epoch = str(db.execute("SELECT epoch FROM licensing_register.control").fetchone()[0])
    assert_refuses(reg, c | {"epoch": epoch}, "REGISTER_LOCKED")


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "scenario",
    [
        "revise",
        "withdraw",
        "issuance_revise",
        "issuance_withdraw",
        "associate_revise",
        "associate_withdraw",
        "correct_revise",
        "correct_withdraw",
    ],
)
def test_grant_races_have_one_serial_order(reg, repeat, reverse, scenario):
    from test_register_association_correction import correct
    from test_register_enrollment_change import compete
    from test_register_postgres import associate

    setup_path(reg)
    if scenario.startswith("correct"):
        reg.client().apply(associate(reg))
    grant = (
        command(reg, "withdraw_grant", 10, revision=1)
        if scenario.endswith("withdraw")
        else revise(reg)
    )
    other = (
        revise(reg)
        if scenario in ("revise", "withdraw")
        else issuance(reg)
        if scenario.startswith("issuance")
        else correct(reg)
        if scenario.startswith("correct")
        else associate(reg)
    )
    pair = (other, grant) if reverse else (grant, other)
    _, (status, result) = compete(reg, *pair, "licensing", "licensing")
    conflict = scenario in ("revise", "withdraw") or (
        not reverse and (scenario.startswith("correct") or scenario == "associate_withdraw")
    )
    assert status == ("ERROR" if conflict else "OK")
    if conflict:
        assert (
            "AUTHORITY_NOT_CURRENT" if scenario == "associate_withdraw" else "REVISION_CONFLICT"
        ) in result
    with reg.admin() as db:
        assert db.execute("SELECT revision FROM licensing_register.grants").fetchone() == (2,)
        assert db.execute("SELECT count(*) FROM licensing_register.grant_revisions").fetchone() == (
            2,
        )
        if scenario.startswith("issuance"):
            assert db.execute(
                "SELECT grant_revision FROM licensing_register.issuances ORDER BY id"
            ).fetchall() == [(1,), (1,)]
        elif scenario.startswith("associate"):
            expected = (
                [] if scenario == "associate_withdraw" and not reverse else [(1 if reverse else 2,)]
            )
            assert (
                db.execute("SELECT grant_revision FROM licensing_register.associations").fetchall()
                == expected
            )
        elif scenario.startswith("correct"):
            assert db.execute(
                "SELECT revision,grant_revision FROM licensing_register.associations"
            ).fetchone() == (2 if reverse else 1, 1)


@pytest.mark.parametrize(
    "kind,table,event",
    [
        (kind, table, event)
        for kind in ("grant", "revise_grant", "withdraw_grant", "issuance")
        for table, event in (
            (
                [("issuances", "INSERT")]
                if kind == "issuance"
                else [
                    ("grant_revisions", "INSERT"),
                    ("grant_heads", "INSERT" if kind == "grant" else "UPDATE"),
                ]
            )
            + [("journal", "INSERT"), ("control", "UPDATE")]
        )
    ],
)
def test_grant_write_faults_roll_back_every_stage(reg, kind, table, event):
    from psycopg import sql

    if kind != "grant":
        setup_path(reg)
    c = (
        command(
            reg,
            "grant",
            10,
            reg.proof(evidence("GRANT", 10, provenance_ref=uid(20), policy_revision=1)),
        )
        if kind == "grant"
        else revise(reg)
        if kind == "revise_grant"
        else issuance(reg)
        if kind == "issuance"
        else command(reg, kind, 10, revision=1)
    )
    with reg.admin() as db:
        db.execute(
            "CREATE FUNCTION public.grant_fault() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN RAISE EXCEPTION 'INJECTED_GRANT_FAILURE'; END $$"
        )
        db.execute(
            sql.SQL(
                "CREATE TRIGGER injected AFTER {} ON licensing_register.{} "
                "FOR EACH ROW EXECUTE FUNCTION public.grant_fault()"
            ).format(sql.SQL(event), sql.Identifier(table))
        )
    assert_refuses(reg, c, "INJECTED_GRANT_FAILURE")
    with reg.admin() as db:
        db.execute(
            "CREATE OR REPLACE FUNCTION public.grant_fault() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN RETURN NEW; END $$"
        )
    assert reg.client().apply(c)["result_kind"] == "RECORDED"


@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM licensing_register.grant_heads",
        "DELETE FROM licensing_register.grant_revisions WHERE revision=1",
        "UPDATE licensing_register.grant_revisions SET decision_revision=1 WHERE revision=3",
        "DELETE FROM licensing_register.proofs WHERE kind='GRANT'",
        "UPDATE licensing_register.proofs SET document=jsonb_set(document,'{policy_revision}','2') "
        "WHERE kind='GRANT_REVISION'",
        "DELETE FROM licensing_register.issuances",
        "UPDATE licensing_register.issuances SET grant_revision=2",
        "DELETE FROM licensing_register.consumptions",
        "UPDATE licensing_register.consumptions "
        "SET consumed_operation='00000099-1111-4111-8111-111111111111'",
    ],
)
def test_old_grant_and_issuance_corruption_is_stop(reg, mutation):
    from test_register_postgres import associate, consumption

    setup_path(reg)
    reg.client().apply(associate(reg))
    reg.client().apply(consumption(reg))
    c = revise(reg)
    reg.client().apply(c)
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=2))
    with reg.admin() as db:
        db.execute("SET LOCAL session_replication_role=replica")
        db.execute(mutation)
    for request in (c, revise(reg, 3), issuance(reg)):
        assert_refuses(reg, request, "HISTORY_CORRUPT")


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("UPDATE licensing_register.grant_heads SET revision=99", "ForeignKeyViolation"),
        ("DELETE FROM licensing_register.grant_revisions WHERE revision=1", "ForeignKeyViolation"),
        ("UPDATE licensing_register.grant_heads SET original_revision=2", "CheckViolation"),
        (
            "UPDATE licensing_register.grant_revisions SET decision_revision=1 WHERE revision=2",
            "CheckViolation",
        ),
        (
            "UPDATE licensing_register.grant_revisions SET decision_revision=3 WHERE revision=4",
            "ForeignKeyViolation",
        ),
        (
            "UPDATE licensing_register.grant_revisions SET state='WITHDRAWN' WHERE revision=2",
            "CheckViolation",
        ),
        (
            "UPDATE licensing_register.grant_revisions "
            "SET decision_state='WITHDRAWN' WHERE revision=4",
            "CheckViolation",
        ),
        ("UPDATE licensing_register.issuances SET grant_revision=3", "ForeignKeyViolation"),
        ("UPDATE licensing_register.issuances SET grant_state='WITHDRAWN'", "CheckViolation"),
        (
            "UPDATE licensing_register.association_revisions SET grant_revision=3",
            "ForeignKeyViolation",
        ),
        (
            "UPDATE licensing_register.association_revisions SET decision_state='WITHDRAWN'",
            "CheckViolation",
        ),
    ],
)
def test_grant_relational_constraints(reg, mutation, error):
    import psycopg
    from test_register_postgres import associate

    setup_path(reg)
    reg.client().apply(associate(reg))
    reg.client().apply(revise(reg))
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=2))
    reg.client().apply(command(reg, "withdraw_grant", 10, revision=3))
    before = reg.snapshot()
    with pytest.raises(getattr(psycopg.errors, error)), reg.admin() as db:
        db.execute(mutation)
    assert reg.snapshot() == before


def test_direct_sql_revision_shapes_and_owner_access(reg):
    import psycopg

    setup_path(reg)
    c = revise(reg)
    args = [
        c["command"],
        c["operation_id"],
        c["epoch"],
        c["record_id"],
        c["proof_id"],
        1,
        None,
        None,
        None,
    ]
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
        before = reg.snapshot()
        with pytest.raises(psycopg.Error, match="INPUT_INVALID"), reg.client().connect() as db:
            db.execute("SELECT licensing_register.apply(%s,%s,%s,%s,%s,%s,%s,%s,%s)", bad)
        assert reg.snapshot() == before
    for statement in ("SELECT licensing_register.transition_grant('revise_grant',%s,%s,NULL,1)",):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), reg.client().connect() as db:
            db.execute(statement, (uid(10), uid(1)))
    for table in ("grant_heads", "grant_revisions", "grants", "issuances"):
        from psycopg import sql

        with pytest.raises(psycopg.errors.InsufficientPrivilege), reg.client().connect() as db:
            db.execute(sql.SQL("SELECT * FROM licensing_register.{}").format(sql.Identifier(table)))
    reg.client().apply(c)


@pytest.mark.parametrize("kind", ["revise_grant", "withdraw_grant"])
def test_revision_storage_maximum_cannot_wrap(reg, kind):
    import psycopg

    setup_path(reg)
    # Admin seeds the storage boundary; call the arithmetic owner directly, without
    # fabricating quadrillions of journal entries or weakening its history admission.
    with reg.admin() as db:
        db.execute(
            "INSERT INTO licensing_register.grant_revisions "
            "SELECT id,organization,9223372036854775807,state,'RECORD_CORRECTION',proof,"
            "9223372036854775807,decision_state FROM licensing_register.grant_revisions"
        )
        db.execute("UPDATE licensing_register.grant_heads SET revision=9223372036854775807")
    before = reg.snapshot()
    with pytest.raises(psycopg.errors.NumericValueOutOfRange), reg.admin() as db:
        db.execute(
            "SELECT licensing_register.transition_grant(%s,%s,%s,NULL,9223372036854775807)",
            (kind, uid(10), uid(1)),
        )
    assert reg.snapshot() == before


def test_missing_grant_head_cannot_be_recreated_by_revision(reg):
    assert_refuses(reg, revise(reg), "REVISION_CONFLICT")


@pytest.mark.parametrize(
    "kind,field", [("GRANT_REVISION", "expected_revision"), ("ISSUANCE", "grant_revision")]
)
def test_bound_revision_cannot_be_changed_after_signing(reg, kind, field):
    from cryptography.exceptions import InvalidSignature

    p = (
        evidence(kind, 10, expected_revision=1, provenance_ref=uid(20), policy_revision=1)
        if kind == "GRANT_REVISION"
        else evidence(kind, 40, grant_id=uid(10), grant_revision=1, envelope_sha256="a" * 64)
    )
    signed, signature = reg.sign(p)
    before = reg.snapshot()
    with pytest.raises(InvalidSignature):
        reg.import_proof(signed | {field: 2}, signature)
    assert reg.snapshot() == before
    with reg.admin() as db:
        assert db.execute("SELECT count(*) FROM licensing_register.proofs").fetchone() == (0,)


def test_issuance_cannot_relabel_existing_entitlement_or_envelope(reg):
    setup_path(reg)
    before = rows(reg, "issuances")
    assert_refuses(reg, issuance(reg, record=12, envelope_sha256="b" * 64), "BINDING_CONFLICT")
    assert rows(reg, "issuances") == before
    reg.client().apply(issuance(reg, record=40, envelope_sha256="b" * 64))
