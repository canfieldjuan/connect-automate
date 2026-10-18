"""Real PackRuntime qualification with ephemeral authorities and isolated fake applications."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from connect_automate import entitlement
from connect_automate.automate import (
    ACTION_KINDS,
    AdapterRegistry,
    AutomateHost,
    AutomateLicenseError,
    ConnectInvokeAdapter,
    LocalNotifyAdapter,
    PackError,
    PackRuntime,
    WorkflowStore,
    load_pack,
    verify_grant,
)
from connect_automate.automate_connect import ConnectV2CapabilityInvoker

from .core import (
    ARTIFACT_LIMIT,
    FAILURE_REQUEST,
    KitError,
    _envelope,
    canonical,
    encoded,
    json_object,
    validate_artifact,
)
from .fakeapps import FakeApps, parse_catalogue

NOW = datetime(2026, 6, 1, tzinfo=UTC)
KEY_ID = "pack-kit-development"
SUBJECT = "pack-kit-check"
DATES = {
    "issued_at": "2026-01-01T00:00:00Z",
    "not_before": "2026-01-01T00:00:00Z",
    "expires_at": "2027-01-01T00:00:00Z",
}


def require(condition):
    # Gate remains active under python -O; assertions belong in tests, not admission code.
    if not condition:
        raise KitError(5, "check failed")


class RecordingAdapter:
    def __init__(self, kind, calls, *, fail=False):
        self.kind, self.calls, self.fail = kind, calls, fail

    def deliver(self, request):
        self.calls.append((self.kind, dict(request)))
        if self.fail:
            raise RuntimeError("Offline injected failure")
        if self.kind == "notify.local":
            return LocalNotifyAdapter().deliver(request)
        return {"delivered": True}


def _host(root: Path, key: Ed25519PrivateKey, *, valid=True):
    keyring = canonical(
        {
            "keys": [
                {
                    "key_id": KEY_ID,
                    "algorithm": "Ed25519",
                    "public_key_base64url": encoded(key.public_key().public_bytes_raw()),
                }
            ]
        }
    )
    claims = {
        "format_version": 1,
        "entitlement_id": "44444444-4444-4444-8444-444444444444",
        "subject": SUBJECT,
        "features": [entitlement.CONNECT_FEATURE_ID],
        **DATES,
    }
    if valid:
        claims["features"].append(entitlement.AUTOMATIONS_FEATURE_ID)
    directory = root / "local-connect"
    directory.mkdir(mode=0o700)
    path = directory / entitlement.ENTITLEMENT_FILE_NAME
    path.write_bytes(_envelope(canonical(claims), key, KEY_ID))
    path.chmod(0o600)
    return AutomateHost(
        entitlement.EntitlementGate.for_test(path=path, keyring_document=keyring, now=NOW)
    )


@contextmanager
def environment(data, catalogue):
    with TemporaryDirectory(prefix="pack-kit-") as name:
        root = Path(name)
        publisher, issuer, ent_key = (Ed25519PrivateKey.generate() for _ in range(3))
        pack = _envelope(canonical(data["manifest"]), publisher, KEY_ID)
        grant = {
            "format_version": 1,
            "grant_id": "55555555-5555-4555-8555-555555555555",
            "pack_id": data["manifest"]["pack_id"],
            "subject": SUBJECT,
            **DATES,
        }
        signed_grant = _envelope(canonical(grant), issuer, KEY_ID)
        publisher_keys = {KEY_ID: publisher.public_key().public_bytes_raw()}
        grant_keys = {KEY_ID: issuer.public_key().public_bytes_raw()}
        load_pack(pack, keys=publisher_keys)
        verify_grant(
            signed_grant, keys=grant_keys, pack_id=grant["pack_id"], subject=SUBJECT, now=NOW
        )
        store = WorkflowStore(root / "store" / "workflow.db")
        store.initialize()
        apps = FakeApps(catalogue)
        calls = []
        registry = AdapterRegistry()
        for kind in ACTION_KINDS:
            registry.register(kind, RecordingAdapter(kind, calls))
        registry.register(
            "connect.invoke",
            ConnectInvokeAdapter(
                ConnectV2CapabilityInvoker(
                    client=apps.client,
                    discover=apps.discover,
                    poll_interval_seconds=0,
                    sleep=lambda _: None,
                )
            ),
        )
        host = _host(root, ent_key)
        kwargs = dict(
            store=store,
            host=host,
            registry=registry,
            publisher_keys=publisher_keys,
            grant_keys=grant_keys,
            subject=SUBJECT,
            now=NOW,
        )
        runtime = PackRuntime.load(pack, signed_grant, **kwargs)
        try:
            yield dict(
                runtime=runtime,
                store=store,
                apps=apps,
                registry=registry,
                calls=calls,
                pack=pack,
                grant=grant,
                signed_grant=signed_grant,
                issuer=issuer,
                publisher=publisher,
                kwargs=kwargs,
                root=root,
                ent_key=ent_key,
            )
        finally:
            apps.client.close()


def _decision(env, record, decision, *, key=None):
    return env["runtime"].submit_decision(
        record.record_id,
        decision=decision,
        operation_key=key if key is not None else decision,
        request={},
        expected_version=record.state_version,
        now=NOW,
    )


def _state(env, record, stage, statuses):
    stored = env["store"].get_record(record.record_id)
    require(stored.stage == stage)
    require(env["store"].get_overlays(record.record_id)["pack-kit.status"] == stage)
    require([a.status for a in env["store"].list_actions(record.record_id)] == statuses)
    return stored


def _approve(env, data):
    record = env["runtime"].create_record(now=NOW)
    require(record.stage == "ready")
    run = _decision(env, record, "approve")
    require(run.outcome.matched and run.outcome.applied)
    require([a.status for a in run.actions] == ["settled"])
    row = env["store"].list_actions(record.record_id)[0]
    expected = data["manifest"]["workflow"]["definitions"][0]["actions"][0]["request"]
    require(row.request == expected and row.action_id == env["apps"].submitted[0]["job_id"])
    require(env["apps"].submitted[0]["parameters"] == expected["parameters"])
    require(
        env["apps"].contents
        == [base64.b64decode(expected["input"]["content_base64"], validate=True)]
    )
    return record, _state(env, record, "acting", ["settled"])


def _success(env, data):
    _, record = _approve(env, data)
    run = _decision(env, record, "complete")
    require([a.status for a in run.actions] == ["settled"])
    record = _state(env, record, "reporting", ["settled", "settled"])
    require(
        env["store"].list_actions(record.record_id)[1].request
        == data["spec"]["result_action"]["request"]
    )
    run = _decision(env, record, "finish")
    require(run.outcome.applied and not run.actions)
    _state(env, record, "completed", ["settled", "settled"])


def _decline(env, data):
    record = env["runtime"].create_record(now=NOW)
    record = _decision(env, record, "decline").outcome.record
    _state(env, record, "declined", [])
    require(not _decision(env, record, "approve").outcome.matched)
    require(not env["apps"].submitted and not env["calls"])


def _replay(env, data):
    record = env["runtime"].create_record(now=NOW)
    for decision in ["unknown", "complete", "finish", "fail"]:
        run = _decision(env, record, decision, key=f"early-{decision}")
        require(not run.outcome.matched and not run.actions)
    require(not env["store"].list_actions(record.record_id))
    # Use the same record after unmatched decisions; no new version was created.
    run = _decision(env, record, "approve")
    require([a.status for a in run.actions] == ["settled"])
    replay = _decision(env, record, "approve")
    require(not replay.outcome.applied and all(not a.delivered for a in replay.actions))
    require(len(env["apps"].submitted) == 1)
    later = _state(env, record, "acting", ["settled"])
    require(not _decision(env, later, "approve", key="fresh-approval").outcome.matched)
    require(len(env["store"].list_actions(record.record_id)) == 1)


def _fail_invocation(env, data):
    env["apps"].fail = True
    record = env["runtime"].create_record(now=NOW)
    run = _decision(env, record, "approve")
    require([a.status for a in run.actions] == ["failed"])
    record = _state(env, record, "acting", ["failed"])
    record = _decision(env, record, "fail").outcome.record
    _state(env, record, "failed", ["failed", "settled"])
    require(env["calls"] == [("notify.local", FAILURE_REQUEST)])


def _fail_result(env, data):
    _, record = _approve(env, data)
    kind = data["spec"]["result_action"]["action"]
    env["registry"].register(kind, RecordingAdapter(kind, env["calls"], fail=True))
    run = _decision(env, record, "complete")
    require([a.status for a in run.actions] == ["failed"])
    record = _state(env, record, "reporting", ["settled", "failed"])
    env["registry"].register("notify.local", RecordingAdapter("notify.local", env["calls"]))
    record = _decision(env, record, "fail").outcome.record
    _state(env, record, "failed", ["settled", "failed", "settled"])
    require(env["calls"][-1] == ("notify.local", FAILURE_REQUEST))
    require(len(env["apps"].submitted) == 1)


def _missing(env, data, *, result=False):
    if result:
        _, record = _approve(env, data)
    else:
        record = env["runtime"].create_record(now=NOW)
    # Registry replacement cannot mutate runtime internals: use the verified public loader again.
    registry = AdapterRegistry()  # None of the kinds configured.
    kwargs = {**env["kwargs"], "registry": registry}
    env["runtime"] = PackRuntime.load(env["pack"], env["signed_grant"], **kwargs)
    run = _decision(env, record, "complete" if result else "approve")
    require([a.status for a in run.actions] == ["pending"])
    _state(
        env,
        record,
        "reporting" if result else "acting",
        ["settled", "pending"] if result else ["pending"],
    )
    require(len(env["apps"].submitted) == (1 if result else 0))


def _load_refusals(env, data):
    options = ["missing", "subject", "pack", "expired", "authority", "entitlement"]
    for option in options:
        grant = dict(env["grant"])
        kwargs = dict(env["kwargs"])
        issuer = env["issuer"]
        if option == "subject":
            grant["subject"] = "another-subject"
        if option == "pack":
            grant["pack_id"] = "66666666-6666-4666-8666-666666666666"
        if option == "expired":
            grant["expires_at"] = "2026-02-01T00:00:00Z"
        if option == "authority":
            issuer = env["publisher"]
        if option == "entitlement":
            root = env["root"] / "invalid-entitlement"
            root.mkdir(mode=0o700)
            kwargs["host"] = _host(root, env["ent_key"], valid=False)
        signed = b"" if option == "missing" else _envelope(canonical(grant), issuer, KEY_ID)
        try:
            PackRuntime.load(env["pack"], signed, **kwargs)
        except (PackError, AutomateLicenseError):
            pass
        else:
            raise KitError(5, "check failed")
        with env["store"].connection() as db:
            require(db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 0)


def run_check(raw: bytes, catalogue_bytes: bytes) -> dict:
    # Bounded decoding precedes schemas, and catalogue schema precedes artifact consistency.
    json_object(raw, ARTIFACT_LIMIT)
    catalogue = parse_catalogue(catalogue_bytes)
    data = validate_artifact(raw)
    scenarios = [
        ("success", _success),
        ("decline", _decline),
        ("replay", _replay),
        ("invoke-failure", _fail_invocation),
        ("result-failure", _fail_result),
        ("missing-invoke", _missing),
        ("missing-result", lambda e, d: _missing(e, d, result=True)),
        ("load-refusals", _load_refusals),
    ]
    completed = []
    try:
        for name, scenario in scenarios:
            with environment(data, catalogue) as env:
                scenario(env, data)
            completed.append(name)
    except KitError:
        raise
    except Exception as exc:
        raise KitError(5, "check failed") from exc
    return {"scenarios": completed}
