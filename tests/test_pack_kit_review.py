"""Review-round regressions at the argument and publication owners."""

from __future__ import annotations

import builtins
import io
import os
import sys
import tomllib

import pytest
from test_pack_kit import FIXTURES, ROOT, catalog, cli, fixed_key, kit, spec


@pytest.mark.parametrize("index,prefix", [(33, "-"), (4, "_"), (0, None)])
def test_space_form_public_keys_sign_and_verify(tmp_path, index, prefix):
    from connect_automate.automate import canonical_workflow, load_pack

    key = fixed_key(index)
    public = kit().encoded(key.public_key().public_bytes_raw())
    if prefix is not None:
        assert public.startswith(prefix)
    source = tmp_path / "build.json"
    source.write_bytes(kit().build(spec()))
    output = tmp_path / "signed.json"
    result = cli(
        "sign",
        source,
        "--fake-apps",
        FIXTURES / "fake-apps.json",
        "--key-id",
        "development",
        "--public-key-base64url",
        public,
        "--out",
        output,
        seed=key.private_bytes_raw(),
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"pack-kit: signed pack\n", b"")
    loaded = load_pack(
        output.read_bytes(), keys={"development": key.public_key().public_bytes_raw()}
    )
    assert canonical_workflow(loaded.workflow) == (FIXTURES / "workflow.json").read_bytes()


@pytest.mark.parametrize("name", ["-review", "--help", "--out", "_review"])
def test_space_form_dash_metadata_and_paths(tmp_path, name):
    output = tmp_path / "-spec.toml"
    result = cli(
        "new",
        "--archetype",
        "approve-then-act",
        "--pack-id",
        spec()["pack_id"],
        "--name",
        name,
        "--out",
        output.name,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert (result.returncode, result.stderr) == (0, b"")
    assert tomllib.loads(output.read_text())["name"] == name
    built = tmp_path / "-build.json"
    result = cli(
        "build",
        output,
        "--out",
        built.name,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert (result.returncode, result.stderr) == (0, b"")
    fake = tmp_path / "-fake.json"
    fake.write_bytes(catalog())
    result = cli(
        "check",
        built,
        "--fake-apps",
        fake.name,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert (result.returncode, result.stderr) == (0, b"")


@pytest.mark.parametrize(
    "option,value,message",
    [
        ("--archetype", "-unknown", "unknown archetype"),
        ("--pack-id", "-invalid", "invalid input"),
        ("--pack-version", "-1", "invalid input"),
    ],
)
def test_option_values_reach_semantic_validation(tmp_path, option, value, message):
    options = {
        "--archetype": "approve-then-act",
        "--pack-id": spec()["pack_id"],
        "--name": "review",
        "--pack-version": "1",
        "--out": str(tmp_path / "spec"),
    }
    options[option] = value
    argv = [item for pair in options.items() for item in pair]
    result = cli("new", *argv)
    assert (result.returncode, result.stdout, result.stderr) == (
        3,
        b"",
        f"pack-kit: {message}\n".encode(),
    )
    assert not (tmp_path / "spec").exists()


@pytest.mark.parametrize("args", [("new", "--name"), ("new", "--unknown", "x"), ("build", "--out")])
def test_missing_values_and_unknown_options_stay_usage(args):
    result = cli(*args)
    assert (result.returncode, result.stdout, result.stderr) == (2, b"", b"pack-kit: usage:\n")


@pytest.mark.parametrize("command", ["new", "build", "sign"])
def test_success_announcement_interrupt_rolls_back(tmp_path, monkeypatch, capsys, command):
    from tools.pack_kit.__main__ import main

    key = fixed_key(0)
    output = tmp_path / "output"
    if command == "new":
        args = [
            "new",
            "--archetype",
            "approve-then-act",
            "--pack-id",
            spec()["pack_id"],
            "--name",
            "review",
            "--out",
            str(output),
        ]
    elif command == "build":
        args = ["build", str(FIXTURES / "sample.toml"), "--out", str(output)]
    else:
        source = tmp_path / "build.json"
        source.write_bytes(kit().build(spec()))
        args = [
            "sign",
            str(source),
            "--fake-apps",
            str(FIXTURES / "fake-apps.json"),
            "--key-id",
            "development",
            "--public-key-base64url",
            kit().encoded(key.public_key().public_bytes_raw()),
            "--out",
            str(output),
        ]
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(key.private_bytes_raw())))
    original = builtins.print
    messages = {
        "pack-kit: created spec",
        "pack-kit: built unsigned artifact",
        "pack-kit: signed pack",
    }

    def interrupt(*args, **kwargs):
        if args and args[0] in messages:
            assert output.exists(), "probe must interrupt after publication"
            raise KeyboardInterrupt
        return original(*args, **kwargs)

    monkeypatch.setattr(builtins, "print", interrupt)
    assert main(args) == 130
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "pack-kit: interrupted\n"
    assert not output.exists()
    assert not list(tmp_path.glob(".pack-kit-*"))


def test_late_interrupt_preserves_foreign_replacement(tmp_path, monkeypatch, capsys):
    from tools.pack_kit.__main__ import main

    output = tmp_path / "output"
    replacement = tmp_path / "other"
    replacement.write_bytes(b"someone else's output")
    original = builtins.print

    def interrupt(*args, **kwargs):
        if args and args[0] == "pack-kit: created spec":
            os.replace(replacement, output)
            raise KeyboardInterrupt
        return original(*args, **kwargs)

    monkeypatch.setattr(builtins, "print", interrupt)
    assert (
        main(
            [
                "new",
                "--archetype",
                "approve-then-act",
                "--pack-id",
                spec()["pack_id"],
                "--name",
                "review",
                "--out",
                str(output),
            ]
        )
        == 130
    )
    assert output.read_bytes() == b"someone else's output"
    assert not list(tmp_path.glob(".pack-kit-*"))
    assert capsys.readouterr().err == "pack-kit: interrupted\n"


@pytest.mark.parametrize("command", ["check", "sign"])
def test_catalogue_schema_precedes_artifact_mismatch(command):
    raw = kit().build(spec()) + b"\n"
    with pytest.raises(kit().KitError, match="invalid input") as exc:
        if command == "check":
            kit().check(raw, b"{}")
        else:
            kit().sign(raw, b"{}", "development", "unused", io.BytesIO())
    assert exc.value.code == 3


def test_size_diagnostic_uses_public_limit(monkeypatch):
    from connect_automate.automate import DefinitionError

    k = kit()
    monkeypatch.setattr(k, "MAX_DEFINITION_BYTES", 12345, raising=False)

    def oversized(raw):
        raise DefinitionError("canonical workflow exceeds 12345 bytes")

    monkeypatch.setattr(k, "parse_workflow", oversized)
    with pytest.raises(k.KitError, match="input too large"):
        k.build(spec())


@pytest.mark.parametrize(
    "option,value", [("--key-id", "-invalid"), ("--public-key-base64url", "-invalid")]
)
def test_sign_options_reach_key_validation(tmp_path, option, value):
    key = fixed_key()
    source = tmp_path / "build.json"
    source.write_bytes(kit().build(spec()))
    options = {
        "--fake-apps": str(FIXTURES / "fake-apps.json"),
        "--key-id": "development",
        "--public-key-base64url": kit().encoded(key.public_key().public_bytes_raw()),
        "--out": str(tmp_path / "output"),
    }
    options[option] = value
    result = cli(
        "sign",
        source,
        *(item for pair in options.items() for item in pair),
        seed=key.private_bytes_raw(),
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        6,
        b"",
        b"pack-kit: invalid signing key\n",
    )
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("args", [("--help",), ("new", "--help")])
def test_help_flags_keep_their_meaning(args):
    result = cli(*args)
    assert result.returncode == 0
    assert result.stdout.startswith(b"usage: pack-kit")
    assert result.stderr == b""


@pytest.mark.parametrize(
    "error,code,message", [(RuntimeError, 1, "internal error"), (OSError, 7, "I/O error")]
)
def test_success_announcement_error_rolls_back(tmp_path, monkeypatch, capsys, error, code, message):
    from tools.pack_kit.__main__ import main

    output = tmp_path / "output"
    original = builtins.print

    def failed(*args, **kwargs):
        if args and args[0] == "pack-kit: built unsigned artifact":
            assert output.exists()
            raise error("private failure detail")
        return original(*args, **kwargs)

    monkeypatch.setattr(builtins, "print", failed)
    assert main(["build", str(FIXTURES / "sample.toml"), "--out", str(output)]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"pack-kit: {message}\n"
    assert not output.exists()
    assert not list(tmp_path.glob(".pack-kit-*"))
