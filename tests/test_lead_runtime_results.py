"""Closed source-handoff result contract tests."""

import pytest


def model_payload():
    from test_lead_receipt_vocabulary import OTHER, receipt

    return dict(
        schema="lead.source.handoff.result",
        schema_version="1.0",
        source_receipt=receipt(),
        workflow_outcome="accepted",
        source_applied=True,
        workflow_applied=True,
        workflow_record_id=OTHER,
        workflow_event_id=OTHER,
        stage="ready",
        state_version=2,
    )


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "schema_version",
        "source_receipt",
        "workflow_outcome",
        "source_applied",
        "workflow_applied",
        "workflow_record_id",
        "workflow_event_id",
        "stage",
        "state_version",
    ],
)
@pytest.mark.parametrize("bad", [None, False, 0, "", "wrong", [], {}])
def test_result_fields_are_required_closed_and_strict(field, bad):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = model_payload()
    value[field] = bad
    valid = (field in ("source_applied", "workflow_applied") and bad is False) or (
        field == "stage" and bad == "wrong"
    )
    if valid:
        assert SourceHandoffResult.model_validate(value).model_dump(by_alias=True) == value
    else:
        with pytest.raises(ValidationError):
            SourceHandoffResult.model_validate(value)
    value = model_payload()
    value.pop(field)
    with pytest.raises(ValidationError):
        SourceHandoffResult.model_validate(value)


@pytest.mark.parametrize("model", ["submit", "lookup"])
@pytest.mark.parametrize("variant", ["accepted", "no_match", "not_found"])
def test_result_variants_reject_mixed_projection_and_extras(model, variant):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffLookup, SourceHandoffResult

    value = model_payload()
    cls = SourceHandoffResult
    if model == "lookup":
        cls = SourceHandoffLookup
        value.pop("source_applied")
        value["schema"] = "lead.source.handoff.lookup"
        value["workflow_applied"] = False
    value["workflow_outcome"] = variant
    if variant != "accepted":
        value.update(
            workflow_applied=False,
            workflow_record_id=None,
            workflow_event_id=None,
            stage=None,
            state_version=None,
        )
    if variant == "not_found":
        value["source_receipt"] = None
    if variant == "not_found" and model == "submit":
        with pytest.raises(ValidationError):
            cls.model_validate(value)
        return
    assert cls.model_validate(value).model_dump(by_alias=True) == value
    for field in ("workflow_record_id", "workflow_event_id", "stage", "state_version"):
        bad = dict(value)
        bad[field] = None if variant == "accepted" else model_payload()[field]
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
    bad = dict(value)
    bad["private_extra"] = "private-sentinel"
    with pytest.raises(ValidationError):
        cls.model_validate(bad)
    if model == "lookup":
        bad = dict(value)
        bad["source_applied"] = False
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
        bad = dict(value)
        bad["workflow_applied"] = True
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
    if variant != "accepted":
        bad = dict(value)
        bad["workflow_applied"] = True
        with pytest.raises(ValidationError):
            cls.model_validate(bad)
    bad = dict(value)
    bad["source_receipt"] = model_payload()["source_receipt"] if variant == "not_found" else None
    with pytest.raises(ValidationError):
        cls.model_validate(bad)


@pytest.mark.parametrize(
    "field,good,bad",
    [
        ("stage", "界" * 80, "界" * 81),
        ("stage", "a", ""),
        ("state_version", 1, 0),
        ("state_version", 9223372036854775807, 9223372036854775808),
        ("state_version", 2, True),
        ("state_version", 2, 2.0),
        ("source_applied", False, 0),
        ("workflow_applied", False, 0),
    ],
)
def test_projection_field_boundaries(field, good, bad):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = model_payload()
    value[field] = good
    assert getattr(SourceHandoffResult.model_validate(value), field) == good
    value[field] = bad
    with pytest.raises(ValidationError):
        SourceHandoffResult.model_validate(value)


def test_result_byte_cap_and_immutability(monkeypatch):
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult, results

    value = model_payload()
    value["stage"] = "界" * 80
    result = SourceHandoffResult.model_validate(value)
    size = len(result.model_dump_json(by_alias=True).encode("utf-8"))
    assert size < results.MAX_EVENT_BYTES
    for limit in (size, size + 1):
        monkeypatch.setattr(results, "MAX_EVENT_BYTES", limit)
        assert SourceHandoffResult.model_validate(value) == result
    monkeypatch.setattr(results, "MAX_EVENT_BYTES", size - 1)
    with pytest.raises(ValidationError, match="byte limit"):
        SourceHandoffResult.model_validate(value)
    with pytest.raises(ValidationError, match="frozen"):
        result.workflow_applied = False
    with pytest.raises(ValidationError, match="frozen"):
        result.source_receipt.event_id = "changed"


def test_result_instance_revalidated_after_model_copy():
    from pydantic import ValidationError

    from connect_automate.lead_intake import SourceHandoffResult

    value = SourceHandoffResult.model_validate(model_payload())
    corrupt = value.model_copy(update={"source_applied": 1})
    with pytest.raises(ValidationError):
        SourceHandoffResult.model_validate(corrupt)


def test_result_contract_import_does_not_load_operational_owners():
    import subprocess
    import sys

    code = """
import sys
from connect_automate.lead_intake import (
    SourceHandoffResult, SourceHandoffLookup, SourceHandoffUnknown,
)
for suffix in ("admission", "auth", "source_store", "handoff"):
    assert "connect_automate.lead_intake." + suffix not in sys.modules
SourceHandoffLookup.model_validate(dict(
    schema="lead.source.handoff.lookup", schema_version="1.0", source_receipt=None,
    workflow_outcome="not_found", workflow_applied=False, workflow_record_id=None,
    workflow_event_id=None, stage=None, state_version=None,
))
assert "connect_automate.automate.runtime" not in sys.modules
assert "connect_automate.automate.store" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)
