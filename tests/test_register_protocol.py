"""Offline register input boundary; no production authority."""

import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1]))
r = importlib.import_module("qualification.licensing_register.protocol")


def uid(n):
    return f"{n:08x}-1111-4111-8111-111111111111"


def command(**changes):
    return dict(version="offline-register/1", command="grant", operation_id=uid(1),
                epoch=uid(2), record_id=uid(3), proof_id=uid(4)) | changes


def test_register_command_is_closed():
    assert r.Command.validate_python(command()).command == "grant"
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(verified=True))


@pytest.mark.parametrize("value", [0, -1, True, False, "", "1"])
def test_invalid_revisions_do_not_default(value):
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(command="withdraw_grant", proof_id=None,
                                         expected_revision=value))


def test_create_and_withdraw_branches():
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(expected_revision=1))
    with pytest.raises(ValidationError):
        r.Command.validate_python(command(command="withdraw_grant", proof_id=None))
    assert r.Command.validate_python(command(command="withdraw_grant", proof_id=None,
                                            expected_revision=1)).expected_revision == 1
