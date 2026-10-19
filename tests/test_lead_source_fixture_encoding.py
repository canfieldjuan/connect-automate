"""Exercise the actual frozen-vector readers with a Windows legacy locale."""

import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["test_lead_source", "test_lead_source_auth"])
def test_vector_readers_under_cp1252(monkeypatch, module):
    original = Path.open

    def legacy_open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "b" not in mode and encoding in (None, "locale"):
            encoding = "cp1252"
        return original(self, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", legacy_open)
    namespace = runpy.run_path(str(Path(__file__).with_name(module + ".py")))
    if module == "test_lead_source":
        namespace["test_published_sender_vectors"]()
    else:
        assert namespace["VECTORS"]
