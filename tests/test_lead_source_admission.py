"""Synthetic custody proofs through the real SQLite owner; no application adoption."""

import hashlib
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from test_lead_source_auth import NOW, OTHER, encode, envelope, key, resign, trust, trust_data
from test_lead_source_store import database, store, trigger_statement
from test_lead_source_store import private_root as private_root

from connect_automate.lead_intake import (
    SourceAdmission,
    SourceAdmissionConflict,
    SourceAdmissionResult,
    SourceAuthenticationError,
    SourceStoreUnavailable,
    SourceStoreUncertain,
    SourceTrustSnapshot,
    authenticate_source,
    canonical_source,
    parse_untrusted_source,
)


@pytest.fixture
def admission(private_root):
    owner = store(private_root)
    owner.initialize(trust())
    return SourceAdmission(owner, clock=lambda: NOW)


def test_body_custody_and_replay_after_reopen(admission, private_root):
    raw = encode(envelope())
    first = admission.admit_source(raw)
    replay = SourceAdmission(store(private_root), clock=lambda: NOW).admit_source(raw)
    assert first.applied is True
    assert replay.applied is False
    assert first.receipt == replay.receipt
    assert first.content_state == replay.content_state == "retained"
    with database(store(private_root).path) as db:
        assert db.execute("SELECT count(*) FROM source_receipts").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM source_content").fetchone()[0] == 1
        assert db.execute("SELECT envelope FROM source_content").fetchone()[0] == canonical_source(
            parse_untrusted_source(raw)
        )


def counts(owner):
    with database(owner.path) as db:
        return tuple(
            db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("source_receipts", "source_content", "source_custody")
        )


@pytest.mark.parametrize("state", ["unavailable", "complete", "truncated", "unknown"])
def test_body_semantics_preserved(admission, private_root, state):
    value = envelope()
    if state == "unavailable":
        value["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": "source_gone"}
    else:
        body = value["payload"]["snapshot"]["body"]
        body["completeness"] = state
        body["source_chars"] = (
            None if state == "unknown" else len(body["text"]) + (state == "truncated")
        )
    raw = resign(value)
    result = admission.admit_source(raw)
    assert result.content_state == "retained"
    with database(store(private_root).path) as db:
        saved = parse_untrusted_source(
            db.execute("SELECT envelope FROM source_content").fetchone()[0]
        )
        assert saved.payload.snapshot.body.model_dump() == value["payload"]["snapshot"]["body"]
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%lead%'").fetchall() == []
        )


def test_formatting_replay_does_not_rewrite_first_envelope(admission, private_root):
    value = envelope()
    first = admission.admit_source(encode(value))
    with database(store(private_root).path) as db:
        before = list(db.iterdump())
    second = admission.admit_source(json.dumps(value, indent=2).encode())
    assert first.receipt == second.receipt
    assert second.applied is False
    with database(store(private_root).path) as db:
        assert list(db.iterdump()) == before


@pytest.mark.parametrize("field", ["body", "message", "rule", "deadline"])
def test_signed_conflict_preserves_original(admission, private_root, field):
    value = envelope()
    first = admission.admit_source(encode(value))
    if field == "body":
        body = value["payload"]["snapshot"]["body"]
        body.update(
            text="different",
            sha256=hashlib.sha256(b"different").hexdigest(),
            stored_chars=9,
            source_chars=9,
        )
    elif field == "message":
        value["payload"]["source"]["message_id"] = "another-message"
    elif field == "rule":
        value["payload"]["trigger"]["rule_id"] = OTHER
    else:
        value["payload"]["retention"]["recovery_deadline"] = "2026-10-18T12:59:59Z"
    with pytest.raises(SourceAdmissionConflict) as failure:
        admission.admit_source(resign(value))
    assert failure.value.__context__ is None
    assert admission.admit_source(encode(envelope())).receipt == first.receipt
    assert counts(store(private_root)) == (1, 1, 1)


def test_rotation_preserves_first_receipt_and_content(admission, private_root):
    raw = encode(envelope())
    first = admission.admit_source(raw)
    data = trust_data()
    old = data["key_grants"][0]
    old["status"] = "revoked"
    rotated = deepcopy(old)
    signer = key(bytes(reversed(range(32))))
    rotated.update(key_id=OTHER, status="active", public_key=signer.public_key().public_bytes_raw())
    data["key_grants"].append(rotated)
    data["generation"] = 2
    store(private_root).publish_authority(
        SourceTrustSnapshot.model_validate(data), expected_generation=1
    )
    value = envelope()
    value["authorization"]["key_id"] = OTHER
    replay = admission.admit_source(resign(value, signer))
    assert replay.receipt == first.receipt
    assert replay.applied is False
    assert replay.receipt.key_id != OTHER
    assert replay.receipt.trust_generation == 1
    with pytest.raises(SourceAuthenticationError):
        admission.admit_source(raw)
    with database(store(private_root).path) as db:
        assert db.execute("SELECT envelope FROM source_content").fetchone()[0] == canonical_source(
            parse_untrusted_source(raw)
        )


def test_distinct_events_for_one_message_are_distinct_custody(admission, private_root):
    first = admission.admit_source(encode(envelope()))
    value = envelope()
    value["payload"]["event_id"] = OTHER
    second = admission.admit_source(resign(value))
    assert first.receipt.admission_id != second.receipt.admission_id
    assert counts(store(private_root)) == (2, 2, 2)
    with database(store(private_root).path) as db:
        assert len({row[0] for row in db.execute("SELECT identity FROM source_custody")}) == 1


@pytest.mark.parametrize(
    "kind", ["authenticated", "copied", "constructed", "result", "dict", "bytearray"]
)
def test_objects_cannot_bypass_raw_authentication(admission, private_root, kind):
    raw = encode(envelope())
    first = admission.admit_source(raw)
    authenticated = authenticate_source(raw, trust=trust(), now=NOW)
    from dataclasses import replace

    inputs = {
        "authenticated": authenticated,
        "copied": replace(authenticated, trust_generation=99),
        "constructed": object.__new__(type(authenticated)),
        "result": first,
        "dict": envelope(),
        "bytearray": bytearray(raw),
    }
    with pytest.raises(SourceAuthenticationError):
        admission.admit_source(inputs[kind])
    assert counts(store(private_root)) == (1, 1, 1)


@pytest.mark.parametrize("raw", [b"", b"x" * 2097153], ids=["empty", "oversized"])
def test_input_bound_precedes_store_io(private_root, raw):
    boundary = SourceAdmission(store(private_root), clock=lambda: NOW)
    with pytest.raises(SourceAuthenticationError):
        boundary.admit_source(raw)
    assert not store(private_root).path.exists()


def test_invalid_signature_cannot_lookup_existing_receipt(admission, monkeypatch):
    raw = encode(envelope())
    admission.admit_source(raw)

    def lookup(*args):
        pytest.fail("receipt lookup preceded authentication")

    monkeypatch.setattr(admission, "_existing", lookup)
    value = envelope()
    value["payload"]["source"]["message_id"] = "tampered"
    with pytest.raises(SourceAuthenticationError):
        admission.admit_source(encode(value))


def test_final_sample_is_receipt_time_and_response_is_private(admission, private_root):
    times = iter([NOW, NOW + timedelta(microseconds=123)])
    boundary = SourceAdmission(store(private_root), clock=lambda: next(times))
    result = boundary.admit_source(encode(envelope()))
    assert result.receipt.accepted_at == "2026-10-18T12:30:00.000123Z"
    assert (
        SourceAdmissionResult(
            receipt=result.receipt, applied=False, content_state="retained"
        ).receipt
        == result.receipt
    )
    for sensitive in (
        envelope()["payload"]["snapshot"]["body"]["text"],
        envelope()["payload"]["source"]["message_id"],
        envelope()["authorization"]["signature"],
    ):
        assert sensitive not in repr(result)
        assert sensitive not in result.model_dump_json()


@pytest.mark.parametrize("bad", [0, 1, "", "true", None])
def test_result_boolean_is_strict(admission, bad):
    from pydantic import ValidationError

    first = admission.admit_source(encode(envelope()))
    with pytest.raises(ValidationError):
        SourceAdmissionResult(receipt=first.receipt, applied=bad, content_state="retained")


@pytest.mark.parametrize("after_write", [1, 2, 3])
def test_sql_failure_after_each_row_rolls_back_then_retry(
    admission, private_root, monkeypatch, after_write
):
    import sqlite3

    original = sqlite3.connect

    class Fault(sqlite3.Connection):
        writes = 0

        def execute(self, sql, *args):
            result = super().execute(sql, *args)
            if sql.startswith("INSERT INTO source_"):
                self.writes += 1
                if self.writes == after_write:
                    raise sqlite3.OperationalError("synthetic-private-sql")
            return result

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=Fault))
        with pytest.raises(SourceStoreUnavailable) as failure:
            admission.admit_source(encode(envelope()))
        assert failure.value.__context__ is None
        assert "synthetic-private-sql" not in repr(failure.value)
    assert counts(store(private_root)) == (0, 0, 0)
    assert admission.admit_source(encode(envelope())).applied
    assert counts(store(private_root)) == (1, 1, 1)


def test_lost_commit_ack_is_uncertain_and_replay_recovers(admission, private_root, monkeypatch):
    import sqlite3

    original = sqlite3.connect

    class LostAck(sqlite3.Connection):
        def commit(self):
            super().commit()
            raise sqlite3.OperationalError("lost reply")

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *a, **kw: original(*a, **kw, factory=LostAck))
        with pytest.raises(SourceStoreUncertain):
            admission.admit_source(encode(envelope()))
    assert admission.admit_source(encode(envelope())).applied is False
    assert counts(store(private_root)) == (1, 1, 1)


def test_response_validation_failure_rolls_back(admission, private_root, monkeypatch):
    import connect_automate.lead_intake.admission as module

    def invalid_response(**kwargs):
        raise ValueError("synthetic response validation failure")

    with monkeypatch.context() as patch:
        patch.setattr(module, "SourceAdmissionResult", invalid_response)
        with pytest.raises(SourceStoreUnavailable):
            admission.admit_source(encode(envelope()))
    assert counts(store(private_root)) == (0, 0, 0)
    assert admission.admit_source(encode(envelope())).applied


def _admission_child(root, raw, action, gate, results):
    import os
    import sqlite3

    from connect_automate.lead_intake import SourceStoreError

    original = sqlite3.connect

    class Crash(sqlite3.Connection):
        def commit(self):
            if action == "before-commit":
                os._exit(21)
            super().commit()
            if action == "after-commit":
                os._exit(22)

    if action in ("before-commit", "after-commit"):
        sqlite3.connect = lambda *a, **kw: original(*a, **kw, factory=Crash)
    gate.wait(20)
    try:
        result = SourceAdmission(store(root), clock=lambda: NOW).admit_source(raw)
        if action == "lost-response":
            os._exit(23)
        results.put(("ok", result.applied, result.receipt.admission_id))
    except (SourceStoreError, SourceAuthenticationError) as exc:
        results.put((type(exc).__name__,))


def children(root, requests):
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    gate, results = context.Barrier(len(requests)), context.Queue()
    workers = [
        context.Process(target=_admission_child, args=(root, raw, action, gate, results))
        for raw, action in requests
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(30)
            assert not worker.is_alive()
        exits = [worker.exitcode for worker in workers]
        return exits, [results.get(timeout=5) for code in exits if code == 0]
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(10)
            worker.close()
        results.close()
        results.join_thread()


@pytest.mark.parametrize("kind", ["same", "different-event", "conflict"])
def test_simultaneous_process_admissions(admission, private_root, kind):
    value = envelope()
    if kind == "different-event":
        value["payload"]["event_id"] = OTHER
    elif kind == "conflict":
        value["payload"]["source"]["message_id"] = "other-message"
    exits, results = children(
        private_root, [(encode(envelope()), "normal"), (resign(value), "normal")]
    )
    assert exits == [0, 0]
    if kind == "same":
        assert sorted(r[1] for r in results) == [False, True]
        assert len({r[2] for r in results}) == 1
    elif kind == "different-event":
        assert all(r[:2] == ("ok", True) for r in results)
        assert len({r[2] for r in results}) == 2
    else:
        assert sorted(r[0] for r in results) == ["SourceAdmissionConflict", "ok"]
    n = 2 if kind == "different-event" else 1
    assert counts(store(private_root)) == (n, n, n)


@pytest.mark.parametrize(
    "action,code", [("before-commit", 21), ("after-commit", 22), ("lost-response", 23)]
)
def test_process_crash_recovery(admission, private_root, action, code):
    raw = encode(envelope())
    exits, results = children(private_root, [(raw, action)])
    assert exits == [code]
    assert results == []
    before = action == "before-commit"
    assert counts(store(private_root)) == ((0, 0, 0) if before else (1, 1, 1))
    result = SourceAdmission(store(private_root), clock=lambda: NOW).admit_source(raw)
    assert result.applied is before
    assert counts(store(private_root)) == (1, 1, 1)


def tamper(db, trigger, sql, params=()):
    """Synthetic corruption restores the exact trigger, avoiding schema masking."""
    db.execute(f"DROP TRIGGER {trigger}")
    db.execute(sql, params)
    db.execute(trigger_statement(trigger))


@pytest.mark.parametrize(
    "corruption",
    [
        "missing-content",
        "hash",
        "canonical",
        "payload-digest",
        "receipt-id",
        "receipt-event",
        "receipt-host",
        "receipt-org",
        "receipt-namespace",
        "receipt-key",
        "receipt-policy",
        "receipt-generation",
        "missing-custody",
        "identity",
        "capture",
        "purged-content",
        "receipt-canonical",
        "receipt-time",
        "receipt-extra",
    ],
)
def test_each_stored_integrity_layer_fails_closed(admission, private_root, corruption):
    raw = encode(envelope())
    admission.admit_source(raw)
    owner = store(private_root)
    with database(owner.path) as db:
        row = db.execute("SELECT receipt FROM source_receipts").fetchone()
        receipt = json.loads(row[0])
        if corruption == "missing-content":
            db.execute("DELETE FROM source_content")
        elif corruption == "missing-custody":
            tamper(db, "custody_no_delete", "DELETE FROM source_custody")
        elif corruption == "hash":
            tamper(
                db, "receipt_no_update", "UPDATE source_receipts SET envelope_sha256=?", ("0" * 64,)
            )
        elif corruption == "canonical":
            content = json.dumps(envelope(), indent=2).encode()
            tamper(db, "content_no_update", "UPDATE source_content SET envelope=?", (content,))
            tamper(
                db,
                "receipt_no_update",
                "UPDATE source_receipts SET envelope_sha256=?",
                (hashlib.sha256(content).hexdigest(),),
            )
        elif corruption in ("identity", "capture"):
            if corruption == "identity":
                identity = envelope()["payload"]["source"]
                identity["message_id"] = "different-message"
                tamper(
                    db,
                    "custody_identity_no_update",
                    "UPDATE source_custody SET identity=?",
                    (
                        json.dumps(
                            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                        ),
                    ),
                )
            else:
                tamper(
                    db,
                    "custody_identity_no_update",
                    "UPDATE source_custody SET captured_at=?",
                    ("2026-10-18T11:59:59Z",),
                )
        elif corruption == "purged-content":
            db.execute("UPDATE source_custody SET state='purged'")
        else:
            changes = {
                "payload-digest": ("payload_digest", "0" * 64),
                "receipt-id": ("admission_id", OTHER),
                "receipt-event": ("event_id", OTHER),
                "receipt-host": ("host_id", OTHER),
                "receipt-org": ("organization_id", OTHER),
                "receipt-namespace": ("namespace_id", OTHER),
                "receipt-key": ("key_id", OTHER),
                "receipt-policy": ("policy_id", OTHER),
                "receipt-generation": ("trust_generation", 2),
                "receipt-time": ("accepted_at", "2026-10-18T13:00:00.000000Z"),
                "receipt-extra": ("unexpected", "synthetic"),
            }
            if corruption in changes:
                k, v = changes[corruption]
                receipt[k] = v
            encoded = json.dumps(
                receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                indent=2 if corruption == "receipt-canonical" else None,
            )
            tamper(db, "receipt_no_update", "UPDATE source_receipts SET receipt=?", (encoded,))
        before = list(db.iterdump())
    with pytest.raises(SourceStoreUnavailable) as error:
        admission.admit_source(raw)
    assert error.value.__context__ is None
    with database(owner.path) as db:
        assert list(db.iterdump()) == before


def test_purged_content_is_not_resurrected(admission, private_root):
    raw = encode(envelope())
    first = admission.admit_source(raw)
    # No public purge API in this slice; prepare the future terminal state.
    with database(store(private_root).path) as db:
        db.execute("DELETE FROM source_content")
        db.execute("UPDATE source_custody SET state='purged'")
    result = admission.admit_source(raw)
    assert result.receipt == first.receipt
    assert result.content_state == "purged"
    assert result.applied is False
    assert counts(store(private_root)) == (1, 0, 1)


@pytest.mark.parametrize("replay", [False, True])
def test_final_authentication_rolls_back_new_and_replay(admission, private_root, replay):
    raw = encode(envelope())
    if replay:
        admission.admit_source(raw)
    times = iter([NOW, NOW + timedelta(hours=1)])
    boundary = SourceAdmission(store(private_root), clock=lambda: next(times))
    with pytest.raises(SourceAuthenticationError):
        boundary.admit_source(raw)
    assert counts(store(private_root)) == ((1, 1, 1) if replay else (0, 0, 0))


def test_final_clock_regression_rolls_back(admission, private_root):
    times = iter([NOW, NOW - timedelta(seconds=1)])
    boundary = SourceAdmission(store(private_root), clock=lambda: next(times))
    with pytest.raises(SourceAuthenticationError):
        boundary.admit_source(encode(envelope()))
    assert counts(store(private_root)) == (0, 0, 0)


def test_previous_store_schema_refused_without_mutation(private_root):
    from pathlib import Path

    from connect_automate.lead_intake.source_store import _encode

    fixture = (
        Path(__file__).parent / "fixtures" / "lead_source_admission" / "v1-authority-schema.sql"
    )
    owner = store(private_root)
    owner.path.touch(mode=0o600)
    with database(owner.path) as db:
        db.executescript(fixture.read_text(encoding="utf-8"))
        db.execute("PRAGMA journal_mode=WAL")
        authority = trust()
        db.execute(
            "INSERT INTO deployment VALUES (1,?,?)", (authority.host_id, authority.organization_id)
        )
        raw = _encode(authority)
        db.execute(
            "INSERT INTO authority_history VALUES (1,?,?)",
            (raw, hashlib.sha256(raw.encode()).hexdigest()),
        )
    before = owner.path.read_bytes()
    for operation in (
        lambda: owner.initialize(trust()),
        lambda: SourceAdmission(owner, clock=lambda: NOW).admit_source(encode(envelope())),
    ):
        with pytest.raises(SourceStoreUnavailable):
            operation()
    assert owner.path.read_bytes() == before
