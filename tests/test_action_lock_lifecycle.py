"""Native action-lock retention and process interleavings (synthetic data only)."""

import hashlib
import multiprocessing
import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from test_automate_actions import NOW, _licensed_host, _record, _runner

from connect_automate import locking
from connect_automate.automate import (
    ActionDeliveryError,
    ActionRunner,
    AdapterRegistry,
    WorkflowStore,
)


def action_path(root, identity="action"):
    return (
        root / ".automate-action-locks" / (hashlib.sha256(identity.encode()).hexdigest() + ".lock")
    )


def action_files(directory):
    return [p for p in directory.iterdir() if len(p.name) == 69 and p.name.endswith(".lock")]


@pytest.fixture
def processes():
    context = multiprocessing.get_context("spawn")
    children, queues, releases = [], [], []

    def start(target, *args, **kwargs):
        events = {
            name: context.Event()
            for name in ["entered", "release", "gate", "opening", "paused", "resume"]
        }
        result = context.Queue()
        child = context.Process(target=target, args=(*args, events, result), kwargs=kwargs)
        queues.append(result)
        releases.extend([events["release"], events["resume"]])
        child.start()
        children.append(child)
        return child, events, result

    yield start
    for event in releases:
        event.set()
    for child in children:
        child.join(15)
        if child.is_alive():
            child.terminate()
            child.join(10)
        child.close()
    for queue in queues:
        queue.close()
        queue.join_thread()


def lock_process(path, events, result, *, phase=None, crash=False):
    native = locking.FileLock
    path = Path(path)
    paused = False

    def pause(point):
        nonlocal paused
        if not paused and phase == point:
            paused = True
            events["paused"].set()
            if crash:
                os._exit(23)
            if not events["resume"].wait(15):
                raise RuntimeError("test phase barrier timed out")

    class ObservedLock(native):
        def acquire(self, *args, **kwargs):
            name = Path(self.lock_file)
            if name.name == ".namespace.lock":
                events["gate"].set()
            else:
                events["opening"].set()
            if name == path:
                pause("before-open")
            acquired = super().acquire(*args, **kwargs)
            if name == path:
                pause("after-acquire")
            return acquired

        def release(self, *args, **kwargs):
            if self.is_locked and Path(self.lock_file) == path:
                pause("before-release")
                super().release(*args, **kwargs)
                pause("after-release")
            else:
                super().release(*args, **kwargs)

    locking.FileLock = ObservedLock
    try:
        with locking.operation_lock(path, "busy", ephemeral=True):
            events["entered"].set()
            pause("body")
            if not events["release"].wait(15):
                raise RuntimeError("test body barrier timed out")
        result.put("completed")
    except locking.OperationLockBusy:
        result.put("busy")


def delivery_process(root, database, record, tag, events, result, *, crash=False):
    class NonIdempotent:
        idempotent = False

        def deliver(self, request):
            marker = Path(root) / "calls.txt"
            with marker.open("a") as stream:
                stream.write(tag + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            events["entered"].set()
            if crash:
                os._exit(23)
            if not events["release"].wait(15):
                raise RuntimeError("test adapter barrier timed out")
            return {"ok": True}

    registry = AdapterRegistry.with_defaults()
    registry.register("mail.send", NonIdempotent())
    store = WorkflowStore(Path(database))
    runner = ActionRunner(
        store=store, registry=registry, host=_licensed_host(Path(root) / ("host-" + tag))
    )
    outcome = runner.run(record, kind="mail.send", dedupe_key=tag, request={}, now=NOW)
    result.put((outcome.status, outcome.delivered))


def test_settled_actions_do_not_retain_historical_locks(tmp_path):
    runner, store = _runner(tmp_path)
    record = _record(store)
    for i in range(50):
        outcome = runner.run(
            record,
            kind="notify.local",
            dedupe_key=f"retention-{i}",
            request={"title": "Synthetic", "body": ""},
            now=NOW,
        )
        assert outcome.delivered and outcome.status == "settled"
    namespace = store.path.parent / ".automate-action-locks"
    retained = [p for p in namespace.iterdir() if p.name != ".namespace.lock"]
    assert len(retained) == 0
    assert len(store.list_actions(record)) == 50


@pytest.mark.parametrize("timeout", [-1, 0.01, 1, None, ""])
def test_ephemeral_lock_refuses_waiting_before_creating_files(tmp_path, timeout):
    with (
        pytest.raises(ValueError, match="timeout zero"),
        locking.operation_lock(
            action_path(tmp_path), "busy", timeout_seconds=timeout, ephemeral=True
        ),
    ):
        pytest.fail("invalid timeout acquired a lock")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "name", ["x.lock", ".namespace.lock", "a" * 63 + ".lock", "A" * 64 + ".lock"]
)
def test_ephemeral_lock_refuses_unowned_names_before_creating_files(tmp_path, name):
    with (
        pytest.raises(ValueError, match="hashed action name"),
        locking.operation_lock(tmp_path / name, "busy", ephemeral=True),
    ):
        pytest.fail("unowned name acquired a lock")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("timeout", [0, False])
def test_ephemeral_lock_cleans_empty_namespace_and_body_exception(tmp_path, timeout):
    path = action_path(tmp_path)
    with (
        pytest.raises(LookupError, match="body failed"),
        locking.operation_lock(path, "busy", timeout_seconds=timeout, ephemeral=True),
    ):
        assert path.exists()
        raise LookupError("body failed")
    assert not path.exists()
    with locking.operation_lock(path, "busy", ephemeral=True):
        assert path.exists()
    assert action_files(path.parent) == []


def test_reaping_preserves_live_locks_and_unknown_files(tmp_path):
    path, live = action_path(tmp_path), action_path(tmp_path, "live")
    locking.prepare_private_lock_path(path)
    for i in range(50):
        action_path(tmp_path, f"legacy-{i}").write_text("")
    unknown = path.parent / "operator-notes.txt"
    unknown.write_text("keep")
    with locking.operation_lock(live, "busy"):
        with locking.operation_lock(path, "busy", ephemeral=True):
            assert set(action_files(path.parent)) == {path, live}
            with pytest.raises(locking.OperationLockBusy), locking.operation_lock(live, "busy"):
                pytest.fail("cleanup unlinked a live owner")
        assert live.exists()
    with locking.operation_lock(path, "busy", ephemeral=True):
        assert action_files(path.parent) == [path]
    assert unknown.read_text() == "keep"
    assert action_files(path.parent) == []


@pytest.mark.parametrize(
    "phase", ["before-open", "after-acquire", "before-release", "after-release"]
)
@pytest.mark.parametrize("same_action", [True, False])
def test_native_gate_orders_open_acquire_release_and_cleanup(
    tmp_path, processes, phase, same_action
):
    first = action_path(tmp_path)
    second = first if same_action else action_path(tmp_path, "other")
    owner, oe, oq = processes(lock_process, first, phase=phase)
    exiting = phase in {"before-release", "after-release"}
    if exiting:
        assert oe["entered"].wait(10)
        oe["release"].set()
    assert oe["paused"].wait(10)
    contender, ce, cq = processes(lock_process, second)
    assert ce["gate"].wait(10)  # The contender has attempted the real native gate.
    assert not ce["opening"].wait(0.2)  # It cannot open even an idle action inode yet.
    oe["resume"].set()
    if not exiting:
        assert oe["entered"].wait(10)
        if same_action:
            assert cq.get(timeout=10) == "busy"
            assert not ce["entered"].is_set()
        else:
            assert ce["entered"].wait(10)  # Distinct action bodies overlap safely.
            ce["release"].set()
            assert cq.get(timeout=10) == "completed"
        oe["release"].set()
    else:
        assert ce["entered"].wait(10)
        ce["release"].set()
        assert cq.get(timeout=10) == "completed"
    assert oq.get(timeout=10) == "completed"
    owner.join(10)
    contender.join(10)
    assert owner.exitcode == contender.exitcode == 0
    assert action_files(first.parent) == []


@pytest.mark.parametrize("phase", ["before-open", "after-acquire", "body", "after-release"])
def test_native_process_crash_releases_gate_and_reclaims_orphan(tmp_path, processes, phase):
    path = action_path(tmp_path)
    child, events, _ = processes(lock_process, path, phase=phase, crash=True)
    if phase == "after-release":
        assert events["entered"].wait(10)
        events["release"].set()
    assert events["paused"].wait(10)
    child.join(10)
    assert child.exitcode == 23
    with locking.operation_lock(action_path(tmp_path, "next"), "busy", ephemeral=True):
        assert not path.exists()
    assert action_files(path.parent) == []


def test_distinct_fresh_non_idempotent_actions_are_not_stranded(tmp_path, processes):
    _, store = _runner(tmp_path)
    record = _record(store)
    first, fe, fq = processes(delivery_process, tmp_path, store.path, record, "first")
    assert fe["entered"].wait(10)
    second, se, sq = processes(delivery_process, tmp_path, store.path, record, "second")
    assert se["entered"].wait(10)  # Before releasing first: metadata gate spans no adapter.
    fe["release"].set()
    se["release"].set()
    assert fq.get(timeout=10) == sq.get(timeout=10) == ("settled", True)
    first.join(10)
    second.join(10)
    assert first.exitcode == second.exitcode == 0
    assert sorted((tmp_path / "calls.txt").read_text().splitlines()) == ["first", "second"]
    assert [a.status for a in store.list_actions(record)] == ["settled", "settled"]
    assert action_files(action_path(store.path.parent).parent) == []


def test_crash_cleanup_does_not_redeliver_ambiguous_non_idempotent_action(tmp_path, processes):
    _, store = _runner(tmp_path)
    record = _record(store)
    child, events, _ = processes(
        delivery_process, tmp_path, store.path, record, "crashed", crash=True
    )
    assert events["entered"].wait(10)
    child.join(10)
    assert child.exitcode == 23
    before = store.list_actions(record)[0]
    assert before.status == "pending"

    class NonIdempotent:
        idempotent = False

        def deliver(self, request):
            with (tmp_path / "calls.txt").open("a") as stream:
                stream.write("fresh\n")
            return {"ok": True}

    registry = AdapterRegistry.with_defaults()
    registry.register("mail.send", NonIdempotent())
    runner = ActionRunner(store=store, registry=registry, host=_licensed_host(tmp_path / "parent"))
    assert not runner.recover_pending(now=NOW)[0].delivered
    fresh = runner.run(record, kind="mail.send", dedupe_key="fresh", request={}, now=NOW)
    assert fresh.delivered
    assert store.get_action(before.action_id) == before
    assert (tmp_path / "calls.txt").read_text().splitlines() == ["crashed", "fresh"]
    assert action_files(action_path(store.path.parent).parent) == []


def test_cleanup_failure_releases_native_lock_without_repeating_delivery(tmp_path, monkeypatch):
    runner, store = _runner(tmp_path)
    record = _record(store)
    unlink = Path.unlink

    def fail_cleanup(path, *args, **kwargs):
        if len(path.name) == 69:
            raise OSError("synthetic cleanup failure")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_cleanup)
        with pytest.raises(OSError, match="synthetic cleanup failure"):
            runner.run(
                record,
                kind="notify.local",
                dedupe_key="settled",
                request={"title": "x", "body": ""},
                now=NOW,
            )
    view = store.list_actions(record)[0]
    assert view.status == "settled"
    path = action_path(store.path.parent, view.action_id)
    with locking.operation_lock(path, "busy"):
        pass  # The failed cleanup did not leak the held descriptor.
    assert not runner.dispatch(view, now=NOW).delivered
    with locking.operation_lock(path, "busy", ephemeral=True):
        pass
    assert action_files(path.parent) == []


def test_failed_adapter_leaves_no_historical_action_lock(tmp_path):
    _, store = _runner(tmp_path)
    record = _record(store)

    class Failing:
        def deliver(self, request):
            raise RuntimeError("synthetic failure")

    registry = AdapterRegistry.with_defaults()
    registry.register("mail.send", Failing())
    runner = ActionRunner(store=store, registry=registry, host=_licensed_host(tmp_path / "failure"))
    with pytest.raises(ActionDeliveryError, match="synthetic failure"):
        runner.run(record, kind="mail.send", dedupe_key="failed", request={}, now=NOW)
    assert store.list_actions(record)[0].status == "failed"
    assert action_files(action_path(store.path.parent).parent) == []


def test_cleanup_gate_failure_releases_descriptor(tmp_path, monkeypatch):
    path = action_path(tmp_path)
    native = locking.operation_lock
    gates = 0

    @contextmanager
    def failing_gate(candidate, *args, **kwargs):
        nonlocal gates
        if candidate.name == ".namespace.lock":
            gates += 1
            if gates == 2:
                raise OSError("synthetic gate failure")
        with native(candidate, *args, **kwargs):
            yield

    with monkeypatch.context() as patch:
        patch.setattr(locking, "operation_lock", failing_gate)
        with (
            pytest.raises(OSError, match="synthetic gate failure"),
            native(path, "busy", ephemeral=True),
        ):
            assert path.exists()
    assert gates == 2
    with native(path, "busy"):
        pass  # ExitStack released even though the cleanup gate could not be acquired.
    with native(path, "busy", ephemeral=True):
        pass
    assert action_files(path.parent) == []
