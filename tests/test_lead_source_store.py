"""Authority-store proofs using synthetic grants and native SQLite processes."""

from contextlib import contextmanager

import pytest
from test_lead_source_auth import trust

from connect_automate.lead_intake.source_store import SourceStore


def trigger_statement(name):
    from connect_automate.lead_intake.source_store import _SCHEMA

    return next(sql for sql in _SCHEMA if sql.startswith(f"CREATE TRIGGER {name} "))


@contextmanager
def database(path):
    import sqlite3

    db = sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


@pytest.fixture
def private_root(tmp_path):
    import os

    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    if os.name == "nt":
        from connect_automate.connect_windows import _protect_windows_directory

        _protect_windows_directory(root)
    return root


def store(root, **kwargs):
    authority = trust()
    return SourceStore(
        root / "authority.sqlite3",
        private_root=root,
        host_id=authority.host_id,
        organization_id=authority.organization_id,
        **kwargs,
    )


def test_initialize_reopen_and_idempotent_publication(private_root):
    authority = trust()
    owner = store(private_root)
    assert owner.initialize(authority) is True
    assert store(private_root).read_authority() == authority
    assert owner.initialize(authority) is False
    next_authority = authority.model_copy(update={"generation": 2})
    assert owner.publish_authority(next_authority, expected_generation=1) is True
    assert store(private_root).publish_authority(next_authority, expected_generation=1) is False
    assert store(private_root).read_authority() == next_authority


def test_schema_lookalike_table_is_not_ignored(private_root):

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    with database(owner.path) as db:
        db.execute("CREATE TABLE sqlitex_hidden (value TEXT)")
    with pytest.raises(SourceStoreUnavailable):
        owner.read_authority()


def test_missing_store_has_no_exception_chain(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    with pytest.raises(SourceStoreUnavailable) as failure:
        store(private_root).read_authority()
    assert failure.value.__context__ is None
    assert failure.value.__cause__ is None


def next_snapshot(authority=None, **updates):
    from connect_automate.lead_intake.auth import SourceTrustSnapshot

    value = (authority or trust()).model_dump()
    value["generation"] += 1
    value.update(updates)
    return SourceTrustSnapshot.model_validate(value)


@pytest.mark.parametrize("change", ["host", "organization", "generation", "copied-invalid"])
def test_invalid_bootstrap_cannot_create_store(private_root, change):
    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.source_store import SourceStoreError

    authority = trust()
    updates = {
        "host": {"host_id": OTHER},
        "organization": {"organization_id": OTHER},
        "generation": {"generation": 2},
        "copied-invalid": {"generation": False},
    }
    owner = store(private_root)
    with pytest.raises(SourceStoreError):
        owner.initialize(authority.model_copy(update=updates[change]))
    assert not owner.path.exists()


@pytest.mark.parametrize("value", [0, "", False, -1, 30001, 1.5, None])
def test_busy_budget_is_strict(private_root, value):
    from connect_automate.lead_intake.source_store import SourceStoreInputError

    with pytest.raises(SourceStoreInputError):
        store(private_root, busy_timeout_ms=value)


@pytest.mark.parametrize("value", [1, 30000])
def test_busy_budget_boundaries(private_root, value):
    assert store(private_root, busy_timeout_ms=value).initialize(trust())


@pytest.mark.parametrize("change", ["public", "namespace", "rename", "policy"])
def test_identity_rebinding_rejected_and_preserved(private_root, change):
    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.auth import SourceTrustSnapshot
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    data = next_snapshot().model_dump()
    if change == "public":
        data["key_grants"][0]["public_key"] = b"x" * 32
    elif change == "namespace":
        data["key_grants"][0]["namespace_id"] = OTHER
    elif change == "rename":
        data["key_grants"][0]["key_id"] = OTHER
    else:
        data["retention_policies"][0]["max_recovery_seconds"] += 1
    with pytest.raises(SourceStoreConflict):
        owner.publish_authority(SourceTrustSnapshot.model_validate(data), expected_generation=1)
    assert store(private_root).read_authority() == trust()


@pytest.mark.parametrize("removal", [False, True])
def test_terminal_key_history_survives_reopen(private_root, removal):
    from connect_automate.lead_intake.auth import SourceTrustSnapshot
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    data = next_snapshot().model_dump()
    if removal:
        data["key_grants"] = []
    else:
        data["key_grants"][0]["status"] = "revoked"
    second = SourceTrustSnapshot.model_validate(data)
    owner.publish_authority(second, expected_generation=1)
    restored = trust().model_copy(update={"generation": 3})
    with pytest.raises(SourceStoreConflict):
        store(private_root).publish_authority(restored, expected_generation=2)
    assert store(private_root).read_authority() == second


def test_removed_policy_definition_cannot_be_replaced(private_root):
    from connect_automate.lead_intake.auth import SourceTrustSnapshot
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    owner.publish_authority(
        next_snapshot(key_grants=(), retention_policies=()), expected_generation=1
    )
    data = trust().model_dump()
    data.update(generation=3, key_grants=[])
    data["retention_policies"][0]["max_recovery_seconds"] += 1
    with pytest.raises(SourceStoreConflict):
        store(private_root).publish_authority(
            SourceTrustSnapshot.model_validate(data), expected_generation=2
        )


def test_whole_mailbox_tuple_and_policy_version_can_advance(private_root):
    from connect_automate.lead_intake.auth import SourceTrustSnapshot

    owner = store(private_root)
    owner.initialize(trust())
    data = next_snapshot().model_dump()
    policy = data["retention_policies"][0]
    policy["policy_version"] = 2
    policy["max_recovery_seconds"] = 7200
    grant = data["key_grants"][0]
    grant["retention_policies"] = [(policy["policy_id"], 2)]
    grant["mailboxes"] = [("provider-CaSe", "e\u0301-account", "b" * 64)]
    authority = SourceTrustSnapshot.model_validate(data)
    assert owner.publish_authority(authority, expected_generation=1)
    assert store(private_root).read_authority() == authority


@pytest.mark.parametrize("expected", [0, "", False, True, 2147483648])
def test_expected_generation_strict(private_root, expected):
    from connect_automate.lead_intake.source_store import SourceStoreInputError

    owner = store(private_root)
    owner.initialize(trust())
    with pytest.raises(SourceStoreInputError):
        owner.publish_authority(next_snapshot(), expected_generation=expected)
    assert owner.read_authority() == trust()


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_foreign_publication_preserves_usable_history(private_root, field):
    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    with pytest.raises(SourceStoreConflict):
        owner.publish_authority(next_snapshot(**{field: OTHER}), expected_generation=1)
    assert store(private_root).read_authority() == trust()
    second = next_snapshot()
    assert store(private_root).publish_authority(second, expected_generation=1)
    assert store(private_root).read_authority() == second


@pytest.mark.parametrize(
    "corruption", ["digest", "canonical", "row_generation", "gap", "host_id", "organization_id"]
)
def test_history_integrity_guards_independent(private_root, corruption):
    import hashlib
    import json

    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable, _encode

    owner = store(private_root)
    owner.initialize(trust())
    row_generation = 3 if corruption == "gap" else 2
    updates = {}
    if corruption in ("host_id", "organization_id"):
        updates[corruption] = OTHER
    if corruption in ("row_generation", "gap"):
        updates["generation"] = 3
    raw = _encode(next_snapshot(**updates))
    if corruption == "canonical":
        raw = json.dumps(json.loads(raw), indent=2)
    digest = "0" * 64 if corruption == "digest" else hashlib.sha256(raw.encode()).hexdigest()
    with database(owner.path) as db:
        # INSERT leaves the exact schema and immutability triggers intact.
        db.execute("INSERT INTO authority_history VALUES (?, ?, ?)", (row_generation, raw, digest))
    with pytest.raises(SourceStoreUnavailable):
        store(private_root).read_authority()


@pytest.mark.parametrize("field", ["host_id", "organization_id"])
def test_deployment_scope_with_original_schema(private_root, field):
    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    with database(owner.path) as db:
        db.execute("DROP TRIGGER deployment_no_update")
        db.execute(f"UPDATE deployment SET {field}=?", (OTHER,))
        db.execute(trigger_statement("deployment_no_update"))
        assert owner._schema(db)
    with pytest.raises(SourceStoreUnavailable):
        store(private_root).read_authority()


def test_initialize_preserves_unrelated_sqlite_mode_and_bytes(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.path.touch(mode=0o600)
    with database(owner.path) as db:
        db.execute("CREATE TABLE unrelated (value TEXT)")
        db.execute("INSERT INTO unrelated VALUES ('synthetic')")
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    before = owner.path.read_bytes()
    with pytest.raises(SourceStoreUnavailable):
        owner.initialize(trust())
    assert owner.path.read_bytes() == before
    with database(owner.path) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_initialize_rejects_different_first_generation(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    with pytest.raises(SourceStoreConflict):
        owner.initialize(next_snapshot(generation=1, key_grants=()))
    assert store(private_root).read_authority() == trust()
    assert owner.publish_authority(next_snapshot(), expected_generation=1)


def test_hardlinked_database_refused(private_root):
    import os

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    os.link(owner.path, private_root / "alias.sqlite3")
    assert owner.path.stat().st_nlink == 2
    with pytest.raises(SourceStoreUnavailable):
        owner.read_authority()


def test_ancestor_link_refused(private_root):
    import os
    import subprocess

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    store(private_root).initialize(trust())
    alias = private_root.parent / "parent-alias"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(private_root.parent)],
            check=True,
            capture_output=True,
        )
    else:
        alias.symlink_to(private_root.parent, target_is_directory=True)
    with pytest.raises(SourceStoreUnavailable):
        store(alias / private_root.name).read_authority()


def test_database_outside_private_root_refused(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreInputError

    authority = trust()
    with pytest.raises(SourceStoreInputError):
        SourceStore(
            private_root.parent / "outside.sqlite3",
            private_root=private_root,
            host_id=authority.host_id,
            organization_id=authority.organization_id,
        )


@pytest.mark.parametrize("operation", ["read", "publish"])
def test_established_store_requires_wal(private_root, operation):
    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    with database(owner.path) as db:
        assert db.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    before = owner.path.read_bytes()
    with pytest.raises(SourceStoreUnavailable):
        if operation == "read":
            owner.read_authority()
        else:
            owner.publish_authority(next_snapshot(), expected_generation=1)
    assert owner.path.read_bytes() == before


def test_identical_replay_rejects_older_precondition(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    second = next_snapshot()
    third = next_snapshot(second)
    owner.publish_authority(second, expected_generation=1)
    owner.publish_authority(third, expected_generation=2)
    with pytest.raises(SourceStoreConflict):
        owner.publish_authority(third, expected_generation=1)
    assert owner.read_authority() == third
    assert owner.publish_authority(next_snapshot(third), expected_generation=3)


def test_stale_conflicting_and_skipped_generations(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreConflict

    owner = store(private_root)
    owner.initialize(trust())
    second = next_snapshot()
    owner.publish_authority(second, expected_generation=1)
    for candidate, expected in (
        (next_snapshot(key_grants=()), 1),
        (next_snapshot(second), 1),
        (second.model_copy(update={"generation": 4}), 2),
    ):
        with pytest.raises(SourceStoreConflict):
            owner.publish_authority(candidate, expected_generation=expected)
    assert owner.read_authority() == second


def test_foreign_open_does_not_mutate(private_root):
    from test_lead_source_auth import OTHER

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    before = owner.path.read_bytes()
    foreign = SourceStore(
        owner.path,
        private_root=private_root,
        host_id=OTHER,
        organization_id=trust().organization_id,
    )
    with pytest.raises(SourceStoreUnavailable):
        foreign.read_authority()
    assert before == owner.path.read_bytes()


@pytest.mark.parametrize("alteration", ["version", "trigger", "snapshot", "history", "identity"])
def test_corruption_is_not_repaired(private_root, alteration):

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    with database(owner.path) as db:
        if alteration == "version":
            db.execute("PRAGMA user_version=9")
        elif alteration == "trigger":
            db.execute("DROP TRIGGER history_no_update")
        elif alteration == "snapshot":
            db.execute("INSERT INTO authority_history VALUES (2, '{}', 'bad')")
        elif alteration == "history":
            data = trust().model_copy(update={"generation": 3})
            owner._insert(db, data)
        else:
            db.execute("DROP TRIGGER deployment_no_update")
            db.execute("UPDATE deployment SET organization_id='bad'")
    before = owner.path.read_bytes()
    for operation in (owner.read_authority, lambda: owner.initialize(trust())):
        with pytest.raises(SourceStoreUnavailable) as error:
            operation()
        assert error.value.__context__ is None
        assert error.value.__cause__ is None
    assert before == owner.path.read_bytes()


def test_sql_failure_rolls_back_publication(private_root, monkeypatch):

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    original = owner._insert

    def fail(db, authority):
        original(db, authority)
        db.execute("INSERT INTO missing_table VALUES ('private data')")

    monkeypatch.setattr(owner, "_insert", fail)
    with pytest.raises(SourceStoreUnavailable) as error:
        owner.publish_authority(next_snapshot(), expected_generation=1)
    assert error.value.__context__ is None
    assert "private data" not in repr(error.value)
    assert store(private_root).read_authority() == trust()
    with database(owner.path) as db:
        assert db.execute("SELECT count(*) FROM authority_history").fetchone()[0] == 1


def test_busy_failure_bounded_and_retry_safe(private_root):
    import sqlite3
    import time

    from connect_automate.lead_intake.source_store import SourceStoreBusy

    owner = store(private_root, busy_timeout_ms=30)
    owner.initialize(trust())
    db = sqlite3.connect(owner.path)
    try:
        db.execute("BEGIN IMMEDIATE")
        start = time.monotonic()
        with pytest.raises(SourceStoreBusy) as error:
            owner.publish_authority(next_snapshot(), expected_generation=1)
        assert time.monotonic() - start < 1
        assert error.value.__context__ is None
    finally:
        db.rollback()
        db.close()
    assert owner.publish_authority(next_snapshot(), expected_generation=1)


def _authority_child(root, action, gate, result):
    import os

    from connect_automate.lead_intake.source_store import SourceStoreError

    gate.wait(20)
    owner = store(root)
    try:
        if action == "initialize":
            value = owner.initialize(trust())
        elif action in ("crash-initialize", "crash-publish"):
            original = owner._insert

            def crash(db, authority):
                original(db, authority)
                os._exit(23)

            owner._insert = crash
            if action == "crash-initialize":
                owner.initialize(trust())
            else:
                owner.publish_authority(next_snapshot(), expected_generation=1)
        elif action == "lost-reply":
            owner.publish_authority(next_snapshot(), expected_generation=1)
            os._exit(24)
        else:
            authority = next_snapshot(key_grants=()) if action == "remove" else next_snapshot()
            value = owner.publish_authority(authority, expected_generation=1)
        result.put(("ok", value))
    except SourceStoreError as exc:
        result.put((type(exc).__name__, str(exc)))


def run_children(root, actions):
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    gate, result = context.Barrier(len(actions)), context.Queue()
    children = [
        context.Process(target=_authority_child, args=(root, a, gate, result)) for a in actions
    ]
    try:
        for child in children:
            child.start()
        for child in children:
            child.join(30)
            assert not child.is_alive(), "native process did not finish"
        exits = [child.exitcode for child in children]
        messages = [result.get(timeout=5) for code in exits if code == 0]
        return exits, messages
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join(10)
            child.close()
        result.close()
        result.join_thread()


@pytest.mark.parametrize("iteration", range(3))
def test_two_process_first_initialization(private_root, iteration):
    exits, results = run_children(private_root, ["initialize", "initialize"])
    assert exits == [0, 0]
    assert ("ok", True) in results
    assert all(
        item in (("ok", True), ("ok", False), ("SourceStoreBusy", "lead source store busy"))
        for item in results
    )
    assert store(private_root).initialize(trust()) is False
    assert store(private_root).read_authority() == trust()


def test_two_process_publication_cas(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    exits, results = run_children(private_root, ["remove", "publish"])
    assert exits == [0, 0]
    assert sorted(x[0] for x in results) == ["SourceStoreConflict", "ok"]
    assert owner.read_authority().generation == 2


@pytest.mark.parametrize("action", ["crash-initialize", "crash-publish", "lost-reply"])
def test_process_crash_recovery(private_root, action):
    owner = store(private_root)
    if action != "crash-initialize":
        owner.initialize(trust())
    exits, results = run_children(private_root, [action])
    assert exits == [24 if action == "lost-reply" else 23]
    assert results == []
    if action == "crash-initialize":
        assert owner.initialize(trust())
        assert owner.read_authority() == trust()
    elif action == "crash-publish":
        assert owner.read_authority() == trust()
        assert owner.publish_authority(next_snapshot(), expected_generation=1)
    else:
        assert owner.read_authority() == next_snapshot()
        assert owner.publish_authority(next_snapshot(), expected_generation=1) is False


def test_private_database_and_live_sidecars(private_root):
    import os
    import sqlite3
    import stat

    owner = store(private_root)
    owner.initialize(trust())
    db = sqlite3.connect(owner.path)
    try:
        db.execute("BEGIN IMMEDIATE")
        files = [
            owner.path,
            owner.path.with_name(owner.path.name + "-wal"),
            owner.path.with_name(owner.path.name + "-shm"),
        ]
        assert all(p.exists() for p in files)
        for path in files:
            if os.name == "nt":
                from connect_automate.connect_windows import validate_private_regular_file

                assert validate_private_regular_file(path, root=private_root) == path
            else:
                assert stat.S_IMODE(path.stat().st_mode) == 0o600
    finally:
        db.rollback()
        db.close()


def test_unsafe_root_refused_before_creation(private_root):
    import os
    import subprocess

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    if os.name == "nt":
        subprocess.run(
            ["icacls", str(private_root), "/grant", "*S-1-1-0:(OI)(CI)R"],
            check=True,
            capture_output=True,
        )
    else:
        private_root.chmod(0o755)
    owner = store(private_root)
    with pytest.raises(SourceStoreUnavailable):
        owner.initialize(trust())
    assert not owner.path.exists()


@pytest.mark.parametrize("target", ["database", "wal", "root"])
def test_links_are_refused(private_root, target):
    import os
    import subprocess

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    if os.name == "nt" and target != "root":
        pytest.skip("file symlink creation needs Windows developer privileges")
    owner = store(private_root)
    if target == "root":
        alias = private_root.parent / "alias"
        if os.name == "nt":
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(alias), str(private_root)],
                check=True,
                capture_output=True,
            )
        else:
            alias.symlink_to(private_root, target_is_directory=True)
        owner = store(alias)
    else:
        secret = private_root / "unrelated"
        secret.write_text("synthetic private value")
        secret.chmod(0o600)
        linked = (
            owner.path if target == "database" else owner.path.with_name(owner.path.name + "-wal")
        )
        linked.symlink_to(secret)
    with pytest.raises(SourceStoreUnavailable):
        owner.initialize(trust())


@pytest.mark.parametrize("statement", ["PRAGMA synchronous=FULL", "PRAGMA journal_mode=WAL"])
def test_setup_busy_uses_shared_retry_owner(private_root, monkeypatch, statement):
    import sqlite3

    from connect_automate.lead_intake import source_store

    native = sqlite3.connect
    attempts = []

    class FirstBusy(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == statement:
                attempts.append(sql)
                if len(attempts) == 1:
                    exc = sqlite3.OperationalError("synthetic phase contention")
                    exc.sqlite_errorcode = sqlite3.SQLITE_BUSY
                    raise exc
            return super().execute(sql, *args, **kwargs)

    monkeypatch.setattr(
        source_store.sqlite3,
        "connect",
        lambda *args, **kwargs: native(*args, **kwargs, factory=FirstBusy),
    )
    assert store(private_root).initialize(trust())
    assert len(attempts) >= 2
    assert store(private_root).read_authority() == trust()


def test_commit_acknowledgement_failure_is_uncertain_and_recoverable(private_root, monkeypatch):
    import sqlite3

    from connect_automate.lead_intake import source_store
    from connect_automate.lead_intake.source_store import SourceStoreUncertain

    owner = store(private_root)
    owner.initialize(trust())
    native = sqlite3.connect

    class LostCommitReply(sqlite3.Connection):
        def commit(self):
            super().commit()
            raise sqlite3.OperationalError("synthetic lost commit reply")

    with monkeypatch.context() as patch:
        patch.setattr(
            source_store.sqlite3,
            "connect",
            lambda *args, **kwargs: native(*args, **kwargs, factory=LostCommitReply),
        )
        with pytest.raises(SourceStoreUncertain) as error:
            owner.publish_authority(next_snapshot(), expected_generation=1)
        assert error.value.__context__ is None
    assert store(private_root).read_authority() == next_snapshot()
    assert store(private_root).publish_authority(next_snapshot(), expected_generation=1) is False


def test_unrelated_database_preserved(private_root):
    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.path.write_bytes(b"synthetic unrelated file")
    owner.path.chmod(0o600)
    before = owner.path.read_bytes()
    with pytest.raises(SourceStoreUnavailable):
        owner.initialize(trust())
    assert owner.path.read_bytes() == before


def test_missing_authority_and_immutable_history(private_root):
    import sqlite3

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    with database(owner.path) as db:
        for sql in (
            "DELETE FROM authority_history",
            "UPDATE authority_history SET snapshot='{}'",
            "DELETE FROM deployment",
            "UPDATE deployment SET host_id='bad'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
        db.execute("DROP TRIGGER history_no_delete")
        db.execute("DELETE FROM authority_history")
        db.execute(trigger_statement("history_no_delete"))
    with pytest.raises(SourceStoreUnavailable):
        owner.read_authority()


def test_private_files_before_first_authority_write(private_root, monkeypatch):
    import os
    import stat

    owner = store(private_root)
    original = owner._insert
    observed = []

    def check_then_insert(db, authority):
        for suffix in ("", "-wal", "-shm"):
            path = owner.path.with_name(owner.path.name + suffix)
            assert path.exists()
            if os.name == "nt":
                from connect_automate.connect_windows import validate_private_regular_file

                validate_private_regular_file(path, root=private_root)
            else:
                assert stat.S_IMODE(path.stat().st_mode) == 0o600
            observed.append(suffix)
        original(db, authority)

    monkeypatch.setattr(owner, "_insert", check_then_insert)
    assert owner.initialize(trust())
    assert observed == ["", "-wal", "-shm"]


@pytest.mark.parametrize("suffix", ["", "-wal", "-shm"])
def test_broad_file_permissions_fail_closed(private_root, suffix):
    import os
    import subprocess

    from connect_automate.lead_intake.source_store import SourceStoreUnavailable

    owner = store(private_root)
    owner.initialize(trust())
    path = owner.path.with_name(owner.path.name + suffix)
    if suffix:
        path.write_bytes(b"synthetic sidecar")
    if os.name == "nt":
        subprocess.run(
            ["icacls", str(path), "/grant", "*S-1-1-0:R"], check=True, capture_output=True
        )
    else:
        path.chmod(0o644)
    before = path.read_bytes()
    with pytest.raises(SourceStoreUnavailable):
        owner.read_authority()
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "invalid",
    [
        {},
        {"generation": 0},
        {"generation": 2147483648},
        {"key_grants": [None]},
        {"retention_policies": [False]},
    ],
)
def test_unvalidated_and_mixed_authority_rejected_before_io(private_root, invalid):
    from connect_automate.lead_intake.source_store import SourceStoreInputError

    authority = invalid if not invalid else trust().model_copy(update=invalid)
    owner = store(private_root)
    with pytest.raises(SourceStoreInputError) as error:
        owner.initialize(authority)
    assert error.value.__context__ is None
    assert not owner.path.exists()
