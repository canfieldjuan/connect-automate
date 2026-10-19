"""Real SQLite read snapshots; all records and paths are synthetic."""

import multiprocessing
import sqlite3
from datetime import UTC, datetime

import pytest

from connect_automate.automate.store import WorkflowStore, WorkflowStoreError

NOW = datetime(2026, 1, 2, tzinfo=UTC)
STAGES = frozenset({"received", "reviewed"})


def initialized(tmp_path, name="workflow.db"):
    store = WorkflowStore(tmp_path / name)
    store.initialize()
    record = store.create_record("read-proof", "received", now=NOW, allowed_stages=STAGES)
    return store, record


@pytest.mark.parametrize("parent_exists", [True, False])
def test_missing_read_store_is_not_created(tmp_path, parent_exists):
    parent = tmp_path if parent_exists else tmp_path / "missing-parent"
    path = parent / "missing.db"
    with pytest.raises(WorkflowStoreError), WorkflowStore(path).read_connection():
        pytest.fail("missing store yielded a connection")
    assert not path.exists()
    assert not list(tmp_path.iterdir())


def test_read_rows_and_empty_result_and_close(tmp_path):
    store, record = initialized(tmp_path)
    with store.read_connection() as db:
        row = db.execute("SELECT * FROM workflow_records").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row["record_id"] == record.record_id
        assert row["stage"] == "received"
        assert (
            db.execute("SELECT * FROM workflow_records WHERE record_id=?", ("missing",)).fetchone()
            is None
        )
        assert db.in_transaction
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


def test_read_allows_bound_joins_functions_and_recursive_select(tmp_path):
    store, record = initialized(tmp_path)
    with store.read_connection() as db:
        row = db.execute(
            "SELECT r.record_id, count(e.event_id) AS events, upper(r.stage) AS stage "
            "FROM workflow_records r JOIN workflow_events e ON e.record_id=r.record_id "
            "WHERE r.record_id=? GROUP BY r.record_id",
            (record.record_id,),
        ).fetchone()
        assert (row["record_id"], row["events"], row["stage"]) == (
            record.record_id,
            1,
            "RECEIVED",
        )
        assert (
            db.execute(
                "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<3) "
                "SELECT sum(x) FROM n"
            ).fetchone()[0]
            == 6
        )


@pytest.mark.parametrize("kind", ["empty", "unrelated", "corrupt", "weakened", "partial"])
def test_read_refuses_invalid_store_without_repair(tmp_path, kind):
    path = tmp_path / "workflow.db"
    if kind == "corrupt":
        path.write_bytes(b"synthetic invalid database")
    elif kind == "empty":
        path.touch()
    elif kind == "unrelated":
        db = sqlite3.connect(path)
        try:
            db.execute("CREATE TABLE unrelated (value TEXT)")
            db.commit()
        finally:
            db.close()
    else:
        store, _ = initialized(tmp_path)
        with store.connection() as db:
            db.execute("DROP TRIGGER workflow_receipts_no_update")
            if kind == "weakened":
                db.execute(
                    "CREATE TRIGGER workflow_receipts_no_update BEFORE UPDATE ON "
                    "workflow_event_receipts BEGIN SELECT 1; END"
                )
    before = path.read_bytes()
    with pytest.raises(WorkflowStoreError), WorkflowStore(path).read_connection():
        pytest.fail("invalid store yielded a connection")
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE workflow_records SET stage='reviewed'",
        "DELETE FROM workflow_records",
        "CREATE TABLE new_table (value TEXT)",
        "CREATE TEMP TABLE temp_table (value TEXT)",
        "PRAGMA user_version=123",
        "PRAGMA query_only=OFF",
        "COMMIT",
        "ROLLBACK",
        "END",
        "SAVEPOINT escape",
    ],
    ids=[
        "update",
        "delete",
        "ddl",
        "temp-ddl",
        "pragma",
        "disable",
        "commit",
        "rollback",
        "end",
        "savepoint",
    ],
)
def test_read_refuses_mutation_and_snapshot_escape(tmp_path, sql):
    store, record = initialized(tmp_path)
    with pytest.raises(WorkflowStoreError), store.read_connection() as db:
        db.execute(sql)
    assert store.get_record(record.record_id).stage == "received"
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 0
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='new_table'").fetchone() is None


def test_read_cannot_attach_or_create_another_database(tmp_path):
    store, _ = initialized(tmp_path)
    other = tmp_path / "not-created.db"
    with pytest.raises(WorkflowStoreError), store.read_connection() as db:
        db.execute("ATTACH DATABASE ? AS other", (str(other),))
    assert not other.exists()


def test_relative_path_and_uri_metacharacters_are_literal(tmp_path, monkeypatch):
    store, record = initialized(tmp_path, "literal # mode=rw % café.db")
    monkeypatch.chdir(tmp_path)
    relative = WorkflowStore(store.path.relative_to(tmp_path))
    with relative.read_connection() as db:
        assert (
            db.execute("SELECT record_id FROM workflow_records").fetchone()[0] == record.record_id
        )


def _advance_record(path, record_id, result):
    try:
        WorkflowStore(path).transition(
            record_id,
            "reviewed",
            operation_key="review",
            operation_name="review",
            request={},
            expected_version=1,
            now=NOW,
            allowed_stages=STAGES,
        )
        result.put("committed")
    except Exception as error:
        result.put(type(error).__name__)


@pytest.mark.parametrize("read_before_writer", [False, True])
def test_snapshot_is_pinned_before_yield_and_writer_can_commit(tmp_path, read_before_writer):
    store, record = initialized(tmp_path)
    context = multiprocessing.get_context("spawn")
    result = context.Queue()
    writer = context.Process(target=_advance_record, args=(store.path, record.record_id, result))
    try:
        with store.read_connection() as db:
            if read_before_writer:
                assert db.execute("SELECT stage FROM workflow_records").fetchone()[0] == "received"
            writer.start()
            assert result.get(timeout=30) == "committed"
            writer.join(timeout=30)
            assert writer.exitcode == 0
            # The writer really committed while this reader's snapshot stayed old.
            assert store.get_record(record.record_id).stage == "reviewed"
            assert db.execute("SELECT stage FROM workflow_records").fetchone()[0] == "received"
        with store.read_connection() as reopened:
            assert (
                reopened.execute("SELECT stage FROM workflow_records").fetchone()[0] == "reviewed"
            )
    finally:
        if writer.is_alive():
            writer.terminate()
            writer.join(timeout=30)
        result.close()
        result.join_thread()


def test_live_wal_rows_are_visible(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    # Keep a connection open so the committed record remains in WAL, not a clean
    # database-only snapshot. immutable=1 would silently lose this commit.
    with store.connection() as keeper:
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        keeper.execute("BEGIN")
        assert keeper.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 0
        record = store.create_record("wal-proof", "received", now=NOW, allowed_stages=STAGES)
        assert store.path.with_name(store.path.name + "-wal").stat().st_size > 0
        with store.read_connection() as db:
            ids = [row[0] for row in db.execute("SELECT record_id FROM workflow_records")]
            assert ids == [record.record_id]


def test_sql_errors_hide_query_and_connection_is_closed(tmp_path):
    store, _ = initialized(tmp_path)
    with pytest.raises(WorkflowStoreError) as error, store.read_connection() as db:
        db.execute("SELECT * FROM private_synthetic_secret")
    assert "private_synthetic_secret" not in str(error.value)
    assert str(tmp_path) not in str(error.value)
    assert error.value.__context__ is None
    assert error.value.__cause__ is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


def test_caller_exception_closes_connection_without_swallowing_it(tmp_path):
    store, _ = initialized(tmp_path)
    problem = RuntimeError("synthetic caller failure")
    with pytest.raises(RuntimeError) as error, store.read_connection() as db:
        raise problem
    assert error.value is problem
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


def test_setup_failure_closes_connection(tmp_path, monkeypatch):
    from connect_automate.automate import store as module

    store, _ = initialized(tmp_path)
    # Warm the existing in-memory schema cache before instrumenting file opens.
    module._expected_event_schema()
    with store.connection() as db:
        db.execute("DROP TRIGGER workflow_receipts_no_update")
    original = sqlite3.connect
    opened = []

    def capture(*args, **kwargs):
        connection = original(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", capture)
    with pytest.raises(WorkflowStoreError), store.read_connection():
        pytest.fail("weakened schema yielded")
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
