"""Synthetic receipt vocabulary and deployment registration; no authenticated handoff."""

import json
from copy import deepcopy

import pytest
from test_automate_events import encoded, event_workflow

from connect_automate.automate.definition import parse_workflow
from connect_automate.automate.events import canonical_event, occurrence, parse_event

HOST = "11111111-1111-4111-8111-111111111111"
ORG = "22222222-2222-4222-8222-222222222222"
NS = "33333333-3333-4333-8333-333333333333"
EVENT = "44444444-4444-4444-8444-444444444444"
ADMISSION = "55555555-5555-4555-8555-555555555555"
OTHER = "66666666-6666-4666-8666-666666666666"
KIND = "lead.source.received"


def receipt():
    return dict(
        host_id=HOST,
        organization_id=ORG,
        namespace_id=NS,
        event_id=EVENT,
        admission_id=ADMISSION,
        payload_digest="a" * 64,
        accepted_at="2026-01-01T00:00:00.123456Z",
        recovery_deadline="2026-01-02T00:00:00Z",
    )


def event():
    return dict(source_kind=KIND, schema_version="1.0", source_receipt=receipt())


def binding(**updates):
    scope = dict(host_id=HOST, organization_id=ORG, namespace_id=NS)
    scope.update(updates)
    return dict(source_kind=KIND, source_id=scope["namespace_id"], scope=encoded(scope).decode())


def configuration(**updates):
    return {"inbox": {**binding(**updates), "policy": {"schema_version": "1.0"}}}


def workflow():
    data = event_workflow(dict(source_kind=KIND, binding="inbox", match_all=True))
    data["definitions"] = data["definitions"][:1]
    data["definitions"][0]["actions"] = []
    return data


def test_receipt_event_canonical_and_identity():
    parsed = parse_event(encoded(event()))
    assert canonical_event(parsed) == encoded(event())
    assert occurrence(parsed) == EVENT
    assert parsed.source_receipt.accepted_at == receipt()["accepted_at"]


def test_receipt_trigger_is_supported():
    assert parse_workflow(encoded(workflow())).definitions[0].trigger.match_all is True


def test_source_receipt_projection_parity_and_key_rotation():
    from connect_automate.lead_intake.admission import SourceReceipt
    from connect_automate.lead_intake.receipts import ReceiptReference

    original = dict(
        receipt(),
        schema="lead.source.receipt",
        schema_version="1.0",
        key_id=HOST,
        trust_generation=1,
        policy_id=ORG,
        policy_version=1,
    )
    for key, generation in [(HOST, 1), (OTHER, 2)]:
        full = dict(original, key_id=key, trust_generation=generation)
        parsed = SourceReceipt.model_validate(full)
        assert encoded(parsed.model_dump(by_alias=True)) == encoded(full)
        projected = {field: getattr(parsed, field) for field in ReceiptReference.model_fields}
        assert projected == receipt()
        assert canonical_event(
            parse_event(encoded(dict(event(), source_receipt=projected)))
        ) == encoded(event())
    for field in ReceiptReference.model_fields:
        assert (
            SourceReceipt.model_fields[field].annotation
            == ReceiptReference.model_fields[field].annotation
        )
        assert (
            SourceReceipt.model_fields[field].metadata
            == ReceiptReference.model_fields[field].metadata
        )


@pytest.mark.parametrize("field", list(receipt()))
@pytest.mark.parametrize("bad", [None, False, 0, "", "invalid"])
def test_receipt_field_strictness(field, bad):
    from connect_automate.automate.events import EventInputError

    data = event()
    data["source_receipt"][field] = bad
    with pytest.raises(EventInputError, match="^invalid event input$"):
        parse_event(encoded(data))


@pytest.mark.parametrize("field", list(receipt()))
def test_receipt_requires_every_field(field):
    from connect_automate.automate.events import EventInputError

    data = event()
    del data["source_receipt"][field]
    with pytest.raises(EventInputError):
        parse_event(encoded(data))


@pytest.mark.parametrize(
    "updates",
    [
        {"accepted_at": "2026-01-01T00:00:00Z"},
        {"accepted_at": "2026-01-01T00:00:00.12345Z"},
        {"accepted_at": "2026-01-01T00:00:00.1234567Z"},
        {"accepted_at": "2026-02-30T00:00:00.123456Z"},
        {"accepted_at": "2026-01-01T00:00:00.123456+00:00"},
        {"recovery_deadline": "2026-01-02T00:00:00.000000Z"},
        {"accepted_at": "2026-01-02T00:00:00.000000Z"},
        {"accepted_at": "2026-01-02T00:00:00.000001Z"},
        {"payload_digest": "A" * 64},
        {"payload_digest": "a" * 63},
        {"payload_digest": "a" * 65},
        {"event_id": "44444444-4444-1444-8444-444444444444"},
        {"event_id": "abcdefab-abcd-4bcd-8bcd-abcdefabcdef".upper()},
        {"key_id": HOST},
        {"body": "private"},
        {"sender": "private"},
    ],
)
def test_receipt_precision_interval_and_private_fields(updates):
    from connect_automate.automate.events import EventInputError

    data = event()
    data["source_receipt"].update(updates)
    with pytest.raises(EventInputError):
        parse_event(encoded(data))


@pytest.mark.parametrize("version", [None, False, 0, 1, 1.0, "", "2.0"])
def test_event_version_is_exact_string(version):
    from connect_automate.automate.events import EventInputError

    with pytest.raises(EventInputError):
        parse_event(encoded(dict(event(), schema_version=version)))


def test_duplicate_members_cap_and_microsecond_time():
    from datetime import datetime

    from connect_automate.automate.events import MAX_EVENT_BYTES, EventInputError, check_event_time

    raw = encoded(event())
    for candidate in [
        raw.replace(b'"event_id":', b'"event_id":"x","event_id":'),
        raw.replace(b'"schema_version":', b'"schema_version":"1.0","schema_version":'),
        encoded(dict(event(), body="private")),
    ]:
        with pytest.raises(EventInputError):
            parse_event(candidate)
    for size in [MAX_EVENT_BYTES - 1, MAX_EVENT_BYTES]:
        assert canonical_event(parse_event(raw + b" " * (size - len(raw)))) == raw
    with pytest.raises(EventInputError):
        parse_event(raw + b" " * (MAX_EVENT_BYTES + 1 - len(raw)))
    parsed = parse_event(raw)
    check_event_time(parsed, datetime.fromisoformat("2026-01-01T00:00:00.123456Z"))
    with pytest.raises(EventInputError):
        check_event_time(parsed, datetime.fromisoformat("2026-01-01T00:00:00.123455Z"))
    with pytest.raises(EventInputError):
        check_event_time(parsed, datetime(2026, 1, 2))


@pytest.mark.parametrize("value", [False, 0, 1, "", "true", None])
def test_trigger_match_all_requires_strict_true(value):
    from connect_automate.automate.definition import DefinitionError

    data = workflow()
    data["definitions"][0]["trigger"]["match_all"] = value
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))


@pytest.mark.parametrize("edit", ["missing", "filters", "initial", "no-guard", "external"])
def test_receipt_trigger_uses_existing_effect_and_stage_rules(edit):
    from connect_automate.automate.definition import DefinitionError

    data = workflow()
    d = data["definitions"][0]
    if edit == "missing":
        del d["trigger"]["match_all"]
    if edit == "filters":
        d["trigger"]["filters"] = []
    if edit == "initial":
        d["effects"][0]["to_stage"] = "waiting"
    if edit == "no-guard":
        d["conditions"] = []
    if edit == "external":
        d["actions"] = [{"action": "mail.send", "request": {}}]
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))


@pytest.mark.parametrize(
    "edit", ["space", "duplicate", "extra", "missing", "version", "mismatch", "overcap"]
)
def test_scope_is_strict_canonical_and_namespace_bound(edit):
    from connect_automate.automate.events import SourceBinding

    data = binding()
    scope = json.loads(data["scope"])
    if edit == "space":
        data["scope"] += " "
    if edit == "duplicate":
        data["scope"] = data["scope"].replace('"host_id":', f'"host_id":"{HOST}","host_id":')
    if edit == "extra":
        scope["other"] = "x"
    if edit == "missing":
        del scope["organization_id"]
    if edit == "version":
        scope["host_id"] = HOST.replace("-4111-", "-1111-")
    if edit == "mismatch":
        data["source_id"] = OTHER
    if edit == "overcap":
        data["scope"] = " " * 513
    if edit in {"extra", "missing", "version"}:
        data["scope"] = encoded(scope).decode()
    with pytest.raises(ValueError):
        SourceBinding.model_validate(data)


def test_registration_reopen_and_multiple_namespaces(tmp_path):
    from connect_automate.automate.events import EventBindingError
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    store.register_bindings("employee-a", HOST, configuration())
    reopened = WorkflowStore(store.path)
    reopened.register_bindings("employee-a", HOST, configuration())
    reopened.register_bindings("employee-b", OTHER, configuration(namespace_id=OTHER))
    for change in [dict(host_id=OTHER), dict(organization_id=OTHER)]:
        with pytest.raises(EventBindingError):
            reopened.register_bindings("employee-c", EVENT, configuration(**change))
    with pytest.raises(EventBindingError):
        reopened.register_bindings("employee-a", HOST, configuration(namespace_id=EVENT))
    invalid = configuration()
    invalid["inbox"]["policy"] = None
    with pytest.raises(EventBindingError):
        reopened.register_bindings("employee-c", EVENT, invalid)
    with store.read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_binding_sets").fetchone()[0] == 2


@pytest.mark.parametrize("same_deployment", [True, False])
def test_two_process_registration_is_atomic(tmp_path, same_deployment):
    import multiprocessing

    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    context = multiprocessing.get_context("spawn")
    barrier, results = context.Barrier(2), context.Queue()
    configs = [
        configuration(),
        configuration(namespace_id=OTHER, organization_id=ORG if same_deployment else OTHER),
    ]
    workers = [
        context.Process(
            target=_register_worker, args=(str(store.path), i, config, barrier, results)
        )
        for i, config in enumerate(configs)
    ]
    for worker in workers:
        worker.start()
    try:
        outcomes = sorted(results.get(timeout=30) for _ in workers)
        assert outcomes == (["ok", "ok"] if same_deployment else ["conflict", "ok"])
    finally:
        for worker in workers:
            worker.join(timeout=30)
            if worker.is_alive():
                worker.terminate()
                worker.join()
            assert worker.exitcode == 0
        results.close()
        results.join_thread()
    with store.read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_source_bindings").fetchone()[0] == (
            2 if same_deployment else 1
        )
        assert db.execute("SELECT count(*) FROM workflow_binding_sets").fetchone()[0] == (
            2 if same_deployment else 1
        )


def _register_worker(path, index, config, barrier, results):
    from connect_automate.automate.events import EventBindingError
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(path)
    barrier.wait(timeout=20)
    try:
        store.register_bindings(f"employee-{index}", HOST, config)
    except EventBindingError:
        results.put("conflict")
    else:
        results.put("ok")


@pytest.mark.parametrize(
    "case",
    [
        "scope",
        "namespace",
        "host",
        "organization",
        "policy",
        "snapshot",
        "policy-bytes",
        "snapshot-bytes",
    ],
)
def test_persisted_binding_corruption_refuses_registration(tmp_path, case):
    from connect_automate.automate.events import EventBindingError
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    config = configuration()
    store.register_bindings("employee-a", HOST, config)
    changed = deepcopy(config)
    item = changed["inbox"]
    if case == "scope":
        item["scope"] += " "
    if case == "namespace":
        item["source_id"] = OTHER
    if case == "host":
        item.update(binding(host_id=OTHER))
    if case == "organization":
        item.update(binding(organization_id=OTHER))
    if case == "policy":
        item["policy"] = {"schema_version": "2.0"}
    with store.connection() as db:
        # Restore triggers before exercising the real reader; isolate one row invariant.
        triggers = list(
            db.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name IN ('workflow_source_bindings','workflow_binding_sets')"
            )
        )
        for row in triggers:
            db.execute(f'DROP TRIGGER "{row[0]}"')
        db.execute(
            "UPDATE workflow_source_bindings SET source_id=?,scope=?,policy=?",
            (
                item["source_id"],
                item["scope"],
                encoded(item["policy"]).decode() + (" " if case == "policy-bytes" else ""),
            ),
        )
        snapshot = encoded(config if case == "snapshot" else changed).decode()
        if case == "snapshot":
            snapshot = encoded({"inbox": {**config["inbox"], "scope": "different"}}).decode()
        if case == "snapshot-bytes":
            snapshot += " "
        db.execute("UPDATE workflow_binding_sets SET bindings_json=?", (snapshot,))
        for row in triggers:
            db.execute(row[1])
    with pytest.raises(EventBindingError):
        WorkflowStore(store.path).register_bindings(
            "employee-b", OTHER, configuration(namespace_id=EVENT)
        )


def test_generic_submission_rejects_receipt_before_any_persistence(tmp_path):
    from datetime import UTC, datetime

    from test_automate_events import counts, event_runtime
    from test_automate_runtime import PACK_ID, SUBJECT

    from connect_automate.automate.engine import WorkflowEngine
    from connect_automate.automate.events import EventInputError, SourceBinding

    runtime, store, host = event_runtime(
        tmp_path, workflow=workflow(), bindings={"inbox": binding()}
    )
    before = counts(store)
    with pytest.raises(EventInputError):
        runtime.submit_event(
            binding="inbox", event=encoded(event()), now=datetime(2026, 1, 2, tzinfo=UTC)
        )
    engine = WorkflowEngine(store=store, host=host)
    with pytest.raises(EventInputError):
        engine.submit_event(
            parse_workflow(encoded(workflow())),
            subject=SUBJECT,
            pack_id=PACK_ID,
            pack_version=1,
            binding="inbox",
            source=SourceBinding.model_validate(binding()),
            event=parse_event(encoded(event())),
            now=datetime(2026, 1, 2, tzinfo=UTC),
        )
    assert counts(store) == before == (0, 0, 0, 0)


def test_incoming_mixed_deployments_roll_back_entire_registration(tmp_path):
    from connect_automate.automate.events import EventBindingError
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    config = configuration()
    config["another"] = configuration(namespace_id=OTHER, host_id=OTHER)["inbox"]
    with pytest.raises(EventBindingError):
        store.register_bindings("employee", HOST, config)
    with store.read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_binding_sets").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM workflow_source_bindings").fetchone()[0] == 0


def test_legacy_scope_strings_and_mixed_bindings_keep_their_meaning(tmp_path):
    from connect_automate.automate.events import SourceBinding
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    config = configuration()
    for kind, ident in [("mail.received", OTHER), ("schedule.tick", EVENT)]:
        raw = dict(source_kind=kind, source_id=ident, scope="legacy opaque scope")
        assert SourceBinding.model_validate(raw).scope == "legacy opaque scope"
        config[kind] = {**raw, "policy": None}
    store.register_bindings("employee", HOST, config)
    WorkflowStore(store.path).register_bindings("employee", HOST, config)


def test_same_namespace_can_be_bound_to_multiple_packs_in_one_deployment(tmp_path):
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    for subject, pack in [("a", HOST), ("a", OTHER), ("b", HOST)]:
        store.register_bindings(subject, pack, configuration())
    with store.read_connection() as db:
        assert db.execute("SELECT count(*) FROM workflow_source_bindings").fetchone()[0] == 3


@pytest.mark.parametrize(
    "policy",
    [None, False, 0, "", {}, {"schema_version": 1}, {"schema_version": "1.0", "other": True}],
)
def test_receipt_policy_is_explicit_and_closed(tmp_path, policy):
    from connect_automate.automate.events import EventBindingError
    from connect_automate.automate.store import WorkflowStore

    store = WorkflowStore(tmp_path / "workflow.db")
    store.initialize()
    config = configuration()
    config["inbox"]["policy"] = policy
    with pytest.raises(EventBindingError):
        store.register_bindings("employee", HOST, config)


def test_trigger_unknown_to_old_vocabulary_and_manifest_selectors():
    from pydantic import ValidationError

    from connect_automate.automate.definition import DefinitionError
    from connect_automate.automate.pack import validate_manifest

    data = workflow()
    del data["vocabulary_version"]
    with pytest.raises(DefinitionError):
        parse_workflow(encoded(data))
    with pytest.raises(ValidationError):
        validate_manifest(dict(format_version=1, pack_id=HOST, pack_version=1, workflow=workflow()))


def test_runtime_refusal_does_not_rely_on_engine_guard(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from test_automate_events import event_runtime

    from connect_automate.automate.engine import WorkflowEngine
    from connect_automate.automate.events import EventInputError

    runtime, _, _ = event_runtime(tmp_path, workflow=workflow(), bindings={"inbox": binding()})

    def forbidden(*args, **kwargs):
        pytest.fail("receipt reached generic engine submission")

    monkeypatch.setattr(WorkflowEngine, "submit_event", forbidden)
    with pytest.raises(EventInputError):
        runtime.submit_event(
            binding="inbox", event=encoded(event()), now=datetime(2026, 1, 2, tzinfo=UTC)
        )


@pytest.mark.parametrize(
    "entry",
    [
        "connect_automate.automate.events",
        "connect_automate.lead_intake.receipts",
        "connect_automate.lead_intake.source",
    ],
)
def test_contract_import_does_not_load_operational_lead_modules(entry):
    import subprocess
    import sys

    script = """
import importlib, sys
importlib.import_module(sys.argv[1])
for name in ('admission', 'auth', 'source_store'):
    assert 'connect_automate.lead_intake.' + name not in sys.modules, name
"""
    result = subprocess.run([sys.executable, "-c", script, entry], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("first", ["automate", "lead_intake"])
def test_public_exports_survive_reverse_import_dependency(first):
    import subprocess
    import sys

    # Simulate a future operational module consuming the workflow contract.
    # A fresh interpreter is essential: a warm module cache hides this cycle.
    script = """
import importlib, importlib.machinery, sys
original = importlib.machinery.SourceFileLoader.exec_module
observed = []
def load(self, module):
    if module.__name__ == 'connect_automate.lead_intake.admission':
        from connect_automate.automate.events import LeadSourceEvent
        observed.append(LeadSourceEvent)
    return original(self, module)
importlib.machinery.SourceFileLoader.exec_module = load
importlib.import_module('connect_automate.' + sys.argv[1])
from connect_automate import lead_intake
from connect_automate.automate.events import LeadSourceEvent
from connect_automate.lead_intake.admission import SourceAdmission
assert lead_intake.SourceAdmission is SourceAdmission
assert observed == [LeadSourceEvent]
"""
    result = subprocess.run([sys.executable, "-c", script, first], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_lead_export_identity_and_unknown_attributes():
    import importlib

    from connect_automate import lead_intake

    owners = {
        "admission": (
            "SourceAdmission",
            "SourceAdmissionConflict",
            "SourceAdmissionResult",
            "SourceReceipt",
        ),
        "auth": (
            "AuthenticatedSource",
            "SourceAuthenticationError",
            "SourceKeyGrant",
            "SourceRetentionPolicy",
            "SourceTrustSnapshot",
            "authenticate_source",
            "source_signing_bytes",
        ),
        "source": (
            "SourceInputError",
            "UntrustedSource",
            "canonical_payload",
            "canonical_source",
            "parse_untrusted_source",
            "payload_digest",
        ),
        "source_store": (
            "SourceStore",
            "SourceStoreBusy",
            "SourceStoreConflict",
            "SourceStoreError",
            "SourceStoreInputError",
            "SourceStoreUnavailable",
            "SourceStoreUncertain",
        ),
    }
    assert set(lead_intake.__all__) == {name for names in owners.values() for name in names}
    assert set(lead_intake.__all__) <= set(dir(lead_intake))
    for module, names in owners.items():
        owner = importlib.import_module("connect_automate.lead_intake." + module)
        for name in names:
            assert getattr(lead_intake, name) is getattr(owner, name)
            assert getattr(lead_intake, name) is getattr(lead_intake, name)
    with pytest.raises(AttributeError):
        _ = lead_intake.unrecognized_export
