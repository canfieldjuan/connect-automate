"Real PackRuntime qualification with ephemeral authorities and isolated fake applications."

from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
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
from connect_automate.automate.events import (
    EventBindingError,
    EventConflict,
    EventInputError,
    MailEvent,
    timestamp,
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
from .fakeevents import parse_catalogue as parse_event_catalogue

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
        self.idempotent = kind == "notify.local"

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
def environment(data, catalogue, event_catalogue=None):
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
        if event_catalogue is not None:
            kwargs["event_bindings"] = event_catalogue.bindings()
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
                event_catalogue=event_catalogue,
                intake_actions=set(),
                intake_call_count=0,
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
    require([a.status for a in _business_actions(env, record)] == statuses)
    return stored


def _business_actions(env, record):
    return [
        row
        for row in env["store"].list_actions(record.record_id)
        if row.action_id not in env["intake_actions"]
    ]


def _business_calls(env):
    return env["calls"][env["intake_call_count"] :]


def _ready(env):
    catalogue = env["event_catalogue"]
    if catalogue is None:
        return env["runtime"].create_record(now=NOW)
    result = env["runtime"].submit_event(
        binding=catalogue.binding.name, event=catalogue.event_bytes(), now=NOW
    )
    require(result.matched and result.applied and result.record is not None)
    require(result.record.stage == "ready" and result.record.state_version == 2)
    require([row.status for row in result.actions] == ["settled"])
    require(not env["apps"].submitted)
    env["intake_actions"].update(row.action_id for row in result.actions)
    env["intake_call_count"] = len(env["calls"])
    require(env["intake_call_count"] == 1)
    return result.record


def _approve(env, data):
    record = _ready(env)
    require(record.stage == "ready")
    run = _decision(env, record, "approve")
    require(run.outcome.matched and run.outcome.applied)
    require([a.status for a in run.actions] == ["settled"])
    row = _business_actions(env, record)[0]
    definition = next(
        item for item in data["manifest"]["workflow"]["definitions"] if item["name"] == "approve"
    )
    expected = definition["actions"][0]["request"]
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
    require(_business_actions(env, record)[1].request == data["spec"]["result_action"]["request"])
    run = _decision(env, record, "finish")
    require(run.outcome.applied and not run.actions)
    _state(env, record, "completed", ["settled", "settled"])


def _decline(env, data):
    record = _ready(env)
    record = _decision(env, record, "decline").outcome.record
    _state(env, record, "declined", [])
    require(not _decision(env, record, "approve").outcome.matched)
    require(not env["apps"].submitted and not _business_calls(env))


def _replay(env, data):
    record = _ready(env)
    for decision in ["unknown", "complete", "finish", "fail"]:
        run = _decision(env, record, decision, key=f"early-{decision}")
        require(not run.outcome.matched and not run.actions)
    require(not _business_actions(env, record))
    # Use the same record after unmatched decisions; no new version was created.
    run = _decision(env, record, "approve")
    require([a.status for a in run.actions] == ["settled"])
    replay = _decision(env, record, "approve")
    require(not replay.outcome.applied and all(not a.delivered for a in replay.actions))
    require(len(env["apps"].submitted) == 1)
    later = _state(env, record, "acting", ["settled"])
    require(not _decision(env, later, "approve", key="fresh-approval").outcome.matched)
    require(len(_business_actions(env, record)) == 1)


def _fail_invocation(env, data):
    env["apps"].fail = True
    record = _ready(env)
    run = _decision(env, record, "approve")
    require([a.status for a in run.actions] == ["failed"])
    record = _state(env, record, "acting", ["failed"])
    record = _decision(env, record, "fail").outcome.record
    _state(env, record, "failed", ["failed", "settled"])
    require(_business_calls(env) == [("notify.local", FAILURE_REQUEST)])


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
        record = _ready(env)
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


def _event_replay(env, data):
    record = _ready(env)
    catalogue = env["event_catalogue"]
    env["runtime"] = PackRuntime.load(env["pack"], env["signed_grant"], **env["kwargs"])
    _decision(env, record, "approve")
    result = env["runtime"].submit_event(
        binding=catalogue.binding.name, event=catalogue.event_bytes(), now=NOW
    )
    require(
        not result.applied
        and result.record.record_id == record.record_id
        and result.record.stage == "ready"
    )
    require(all(not action.delivered for action in result.actions))
    with env["store"].connection() as db:
        require(db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 1)
        require(db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 1)
    if isinstance(catalogue.matching_event, MailEvent):
        changed = catalogue.matching_event.model_dump(mode="json")
        changed["subject"] = "" if changed["subject"] else "changed"
        try:
            env["runtime"].submit_event(
                binding=catalogue.binding.name, event=canonical(changed), now=NOW
            )
        except EventConflict:
            pass
        else:
            raise KitError(5, "check failed")


def _event_boundaries(env, data):
    catalogue = env["event_catalogue"]
    event = catalogue.matching_event.model_dump(mode="json")
    cases = [
        (catalogue.binding.name, {**event, "confirmed": True}, EventInputError),
        ("unconfigured-source", event, EventBindingError),
    ]
    for name, candidate, error in cases:
        try:
            env["runtime"].submit_event(binding=name, event=canonical(candidate), now=NOW)
        except error:
            pass
        else:
            raise KitError(5, "check failed")
    trigger = data["spec"]["trigger"]
    nonmatch = deepcopy(event)
    if isinstance(catalogue.matching_event, MailEvent):
        if trigger["match_all"]:
            return
        condition = trigger["filters"][0]
        field = condition["field"]
        nonmatch[field] = ("a" if condition["value"] != "a" else "b") if field == "sender" else ""
    else:
        from datetime import timedelta

        due = timestamp(event["scheduled_at"])
        due += timedelta(seconds=-1 if due.year > 1 else 1)
        nonmatch["scheduled_at"] = due.isoformat(timespec="seconds").replace("+00:00", "Z")
    first = env["runtime"].submit_event(
        binding=catalogue.binding.name, event=canonical(nonmatch), now=NOW
    )
    replay = env["runtime"].submit_event(
        binding=catalogue.binding.name, event=canonical(nonmatch), now=NOW
    )
    require(not first.matched and not replay.matched and first.record is None)
    with env["store"].connection() as db:
        require(db.execute("SELECT count(*) FROM workflow_records").fetchone()[0] == 0)
        require(db.execute("SELECT count(*) FROM workflow_event_receipts").fetchone()[0] == 1)


def run_check(raw: bytes, catalogue_bytes: bytes, event_bytes: bytes | None = None) -> dict:
    # Bounded decoding precedes schemas, and catalogue schema precedes artifact consistency.
    json_object(raw, ARTIFACT_LIMIT)
    catalogue = parse_catalogue(catalogue_bytes)
    event_catalogue = parse_event_catalogue(event_bytes) if event_bytes is not None else None
    data = validate_artifact(raw)
    if (data["kit_format_version"] == 2) != (event_catalogue is not None):
        raise KitError(3, "invalid input")
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
    if event_catalogue is not None:
        scenarios += [("event-replay", _event_replay), ("event-boundaries", _event_boundaries)]
    completed = []
    try:
        for name, scenario in scenarios:
            with environment(data, catalogue, event_catalogue) as env:
                scenario(env, data)
            completed.append(name)
    except KitError:
        raise
    except Exception as exc:
        raise KitError(5, "check failed") from exc
    return {"scenarios": completed}
