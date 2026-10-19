"""Exercise the actual frozen-vector readers with a Windows legacy locale."""

import io
import runpy
from pathlib import Path

import pytest


def test_vector_readers_under_cp1252(monkeypatch):
    original = Path.open
    monkeypatch.setattr(
        io,
        "text_encoding",
        lambda encoding, stacklevel=2: "locale" if encoding is None else encoding,
    )

    def legacy_open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "b" not in mode and encoding in (None, "locale"):
            encoding = "cp1252"
        return original(self, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", legacy_open)
    fixture = Path(__file__).parent / "fixtures" / "lead_source_auth" / "vectors.json"
    # Prove the locale simulation is active even under Python UTF-8 mode.
    with pytest.raises(UnicodeDecodeError):
        fixture.read_text()
    namespace = runpy.run_path(str(Path(__file__).with_name("test_lead_source_auth.py")))
    assert namespace["VECTORS"]


def test_source_parameter_ids_are_bounded():
    import subprocess
    import sys

    tests = Path(__file__).parent
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            str(tests / "test_lead_source.py"),
            str(tests / "test_lead_source_auth.py"),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tests.parent,
    )
    lengths = [
        len(line.split("[", 1)[1][:-1])
        for line in result.stdout.splitlines()
        if "::" in line and "[" in line and line.endswith("]")
    ]
    assert lengths
    assert max(lengths) <= 100
