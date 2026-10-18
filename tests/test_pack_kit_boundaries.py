"""Both sides of admission bounds, filesystem publication and signing secrecy."""

from __future__ import annotations

import base64
import copy
import io
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_pack_kit import FIXTURES, ROOT, catalog, cli, fixed_key, kit, spec


def test_unknown_action_rejected_at_authoring_boundary():
    value = spec()
    value["result_action"]["action"] = "unknown.action"
    with pytest.raises(kit().KitError, match="unsupported vocabulary"):
        kit().build(value)


@pytest.mark.parametrize(
    "field,values",
    [("name", ["", "x", "x" * 79, "x" * 80, "x" * 81]), ("pack_version", [0, 1, 2, False, ""])],
)
def test_identity_bounds(field, values):
    k = kit()
    for value in values:
        candidate = spec()
        candidate[field] = value
        valid = (1 <= len(value) <= 80) if field == "name" else type(value) is int and value >= 1
        if valid:
            k.build(candidate)
        else:
            with pytest.raises(k.KitError):
                k.build(candidate)


@pytest.mark.parametrize("count", [0, 1, 7, 8])
def test_condition_count_boundary(count):
    k = kit()
    candidate = spec()
    candidate["conditions"] = [
        {"field": "record.stage", "op": "in", "value": ["ready", "acting"]}
    ] * count
    if count <= 7:
        k.build(candidate)
    else:
        with pytest.raises(k.KitError):
            k.build(candidate)


@pytest.mark.parametrize("count", [0, 1, 15, 16, 17])
def test_parameter_count_boundary(count):
    k = kit()
    candidate = spec()
    candidate["invoke"]["parameters"] = {f"p{i}": i for i in range(count)}
    if count <= 16:
        k.build(candidate)
    else:
        with pytest.raises(k.KitError, match="unsupported vocabulary"):
            k.build(candidate)


def test_exact_workflow_size_boundary():
    k = kit()
    candidate = spec()
    candidate["result_action"]["request"]["body"] = ""
    overhead = len(k.canonical(json.loads(k.build(candidate))["manifest"]["workflow"]))
    for length in [16383 - overhead, 16384 - overhead, 16385 - overhead]:
        candidate["result_action"]["request"]["body"] = "x" * length
        if length + overhead <= 16384:
            assert (
                len(k.canonical(json.loads(k.build(candidate))["manifest"]["workflow"]))
                == length + overhead
            )
        else:
            with pytest.raises(k.KitError, match="input too large"):
                k.build(candidate)


def test_bounded_reads_and_nonregular_inputs(tmp_path):
    from tools.pack_kit.files import read_input

    for length in [0, 1, 65535, 65536, 65537]:
        path = tmp_path / "input"
        path.write_bytes(b"x" * length)
        if length <= 65536:
            assert read_input(path, 65536) == b"x" * length
        else:
            with pytest.raises(kit().KitError, match="input too large"):
                read_input(path, 65536)
    with pytest.raises(kit().KitError, match="I/O error"):
        read_input(tmp_path, 65536)
    if hasattr(os, "mkfifo"):
        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        with pytest.raises(kit().KitError, match="I/O error"):
            read_input(fifo, 65536)


def test_mixed_conditions_and_unsupported_ops():
    k = kit()
    for bad in [[], ["ready", "ready"], False, "", ["ready", "unknown"]]:
        candidate = spec()
        candidate["conditions"] = [{"field": "record.stage", "op": "in", "value": bad}]
        with pytest.raises(k.KitError):
            k.build(candidate)
    candidate = spec()
    candidate["conditions"] = [{"field": "record.stage", "op": "never", "value": "ready"}]
    with pytest.raises(k.KitError, match="unsupported vocabulary"):
        k.build(candidate)


@pytest.mark.parametrize(
    "alter",
    [
        lambda c: c.update(capabilities=[]),
        lambda c: c.update(format_version=True),
        lambda c: c["capabilities"].append(copy.deepcopy(c["capabilities"][0])),
        lambda c: c["capabilities"][0]["parameters"][0].update(value_type="object"),
        lambda c: c["capabilities"][0]["accepts"][0].update(max_bytes=0),
        lambda c: c["capabilities"][0]["accepts"][0].update(max_bytes=False),
        lambda c: c["capabilities"][0]["accepts"][0].update(max_bytes=""),
        lambda c: c["capabilities"][0]["accepts"][0].update(max_bytes=1073741825),
        lambda c: c["capabilities"][0].update(parameters=[{"name": "bad"}]),
        lambda c: c["capabilities"][0].update(fixed_parameters={}),
    ],
)
def test_invalid_fake_catalogues(alter):
    from tools.pack_kit.fakeapps import parse_catalogue

    value = json.loads(catalog())
    alter(value)
    with pytest.raises(kit().KitError, match="invalid input"):
        parse_catalogue(kit().canonical(value))


def test_connect_result_action_uses_real_invoker():
    k = kit()
    value = spec()
    main = json.loads(k.build(value))["manifest"]["workflow"]["definitions"][0]["actions"][0]
    value["result_action"] = main
    assert k.check(k.build(value), catalog())["scenarios"][-1] == "load-refusals"
    value["result_action"]["request"]["parameters"]["mode"] = {"overlay": "secret"}
    with pytest.raises(k.KitError, match="invalid input"):
        k.build(value)


def test_result_confirmation_and_media_are_not_assumed():
    k = kit()
    value = spec()
    main = json.loads(k.build(value))["manifest"]["workflow"]["definitions"][0]["actions"][0]
    value["result_action"] = main
    value["result_action"]["request"]["confirmed"] = False
    with pytest.raises(k.KitError, match="check failed"):
        k.check(k.build(value), catalog())
    value = spec()
    value["invoke"]["input"]["media_type"] = "application/pdf"
    with pytest.raises(k.KitError, match="check failed"):
        k.check(k.build(value), catalog())


def test_public_key_and_identifier_errors_are_redacted():
    k = kit()
    raw = k.build(spec())
    for public, key_id in [
        ("", "development"),
        ("not a key", "development"),
        ("A" * 43 + "=", "development"),
        ("A" * 43, "INVALID"),
        ("A" * 43, ""),
    ]:
        with pytest.raises(k.KitError, match="invalid signing key"):
            k.sign(raw, catalog(), key_id, public, io.BytesIO(b"x" * 32))


def test_snapshot_replacement_does_not_change_signed_candidate(tmp_path, monkeypatch):
    k = kit()
    raw = k.build(spec())
    path = tmp_path / "candidate"
    path.write_bytes(raw)
    original = k.check
    other = spec()
    other["name"] = "replacement"

    def replace(snapshot, catalogue):
        result = original(snapshot, catalogue)
        path.write_bytes(k.build(other))
        return result

    monkeypatch.setattr(k, "check", replace)
    key = fixed_key()
    signed = k.sign(
        path.read_bytes(),
        catalog(),
        "development",
        k.encoded(key.public_key().public_bytes_raw()),
        io.BytesIO(key.private_bytes_raw()),
    )
    envelope = json.loads(signed)
    assert base64.urlsafe_b64decode(
        envelope["payload_base64url"] + "=" * (-len(envelope["payload_base64url"]) % 4)
    ) == k.canonical(json.loads(raw)["manifest"])


def test_publish_competing_writers_aliases_symlinks(tmp_path):
    from tools.pack_kit.files import publish

    path = tmp_path / "pack"

    def write(content):
        try:
            publish(path, content)
            return 0
        except kit().KitError as e:
            return e.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, [b"first", b"second"])) == [0, 7]
    assert path.read_bytes() in [b"first", b"second"]
    link = tmp_path / "link"
    link.symlink_to(path)
    for target in [path, link]:
        with pytest.raises(kit().KitError, match="output exists"):
            publish(target, b"other", inputs=(path,))
    hardlink = tmp_path / "hardlink"
    os.link(path, hardlink)
    with pytest.raises(kit().KitError, match="output exists"):
        publish(hardlink, b"other", inputs=(path,))
    assert not list(tmp_path.glob(".pack-kit-*"))
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_failed_publication_cleans_staging(tmp_path, monkeypatch):
    from tools.pack_kit.files import publish

    def broken(*args):
        raise PermissionError("secret exception")

    monkeypatch.setattr(os, "link", broken)
    with pytest.raises(kit().KitError, match="I/O error"):
        publish(tmp_path / "pack", b"payload")
    assert not list(tmp_path.iterdir())


def test_interrupt_after_link_leaves_no_output(tmp_path, monkeypatch):
    from tools.pack_kit.files import publish

    link = os.link

    def interrupted(*args):
        link(*args)
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "link", interrupted)
    with pytest.raises(KeyboardInterrupt):
        publish(tmp_path / "pack", b"payload")
    assert not list(tmp_path.iterdir())


def test_unserializable_content_is_invalid_input():
    candidate = spec()
    candidate["invoke"]["input"]["content"] = "\ud800"
    with pytest.raises(kit().KitError, match="invalid input"):
        kit().build(candidate)


def test_internal_error_and_interrupt_diagnostics(tmp_path, monkeypatch, capsys):
    from tools.pack_kit.__main__ import main

    k = kit()
    for exception, code, text in [
        (RuntimeError("NEVER-ECHO"), 1, "internal error"),
        (KeyboardInterrupt(), 130, "interrupted"),
    ]:

        def fail(*args, error=exception):
            raise error

        monkeypatch.setattr(k, "build", fail)
        assert (
            main(["build", str(FIXTURES / "sample.toml"), "--out", str(tmp_path / "build")]) == code
        )
        output = capsys.readouterr()
        assert output.out == ""
        assert output.err == f"pack-kit: {text}\n"
        assert not list(tmp_path.iterdir())


def test_sign_cli_failure_never_creates_output(tmp_path):
    k = kit()
    raw = tmp_path / "build"
    raw.write_bytes(k.build(spec()))
    key = fixed_key()
    public = k.encoded(key.public_key().public_bytes_raw())
    target = tmp_path / "signed"
    for seed in [b"", b"x" * 31, b"x" * 33]:
        result = cli(
            "sign",
            raw,
            "--fake-apps",
            FIXTURES / "fake-apps.json",
            "--key-id",
            "development",
            "--public-key-base64url",
            public,
            "--out",
            target,
            seed=seed,
        )
        assert (result.returncode, result.stdout, result.stderr) == (
            6,
            b"",
            b"pack-kit: invalid signing key\n",
        )
        assert not target.exists()
    broken = spec()
    broken["invoke"]["capability"]["id"] = "absent.capability"
    raw.write_bytes(k.build(broken))
    result = cli(
        "sign",
        raw,
        "--fake-apps",
        FIXTURES / "fake-apps.json",
        "--key-id",
        "development",
        "--public-key-base64url",
        public,
        "--out",
        target,
        seed=key.private_bytes_raw(),
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        5,
        b"",
        b"pack-kit: check failed\n",
    )
    assert not target.exists()


def test_private_seeds_never_persist_or_log(monkeypatch, capsys):
    from tools.pack_kit import sandbox

    k = kit()
    secrets = []
    directory = sandbox.TemporaryDirectory

    def generate():
        key = fixed_key(100 + len(secrets))
        secrets.append(key.private_bytes_raw())
        return key

    class InspectDirectory(directory):
        def __exit__(self, *args):
            for path in Path(self.name).rglob("*"):
                if path.is_file():
                    contents = path.read_bytes()
                    assert all(secret not in contents for secret in secrets)
            return super().__exit__(*args)

    monkeypatch.setattr(Ed25519PrivateKey, "generate", generate)
    monkeypatch.setattr(sandbox, "TemporaryDirectory", InspectDirectory)
    key = generate()
    k.sign(
        k.build(spec()),
        catalog(),
        "development",
        k.encoded(key.public_key().public_bytes_raw()),
        io.BytesIO(key.private_bytes_raw()),
    )
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_no_network_or_installation_discovery(monkeypatch):
    import httpx

    from connect_automate.automate import AutomateHost

    def forbidden(*args, **kwargs):
        raise AssertionError("real I/O forbidden")

    monkeypatch.setattr(AutomateHost, "from_installation", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    kit().check(kit().build(spec()), catalog())


def test_gate_survives_optimized_python(tmp_path):
    raw = tmp_path / "build"
    raw.write_bytes(kit().build(spec()))
    result = subprocess.run(
        [
            sys.executable,
            "-O",
            "-m",
            "tools.pack_kit",
            "check",
            str(raw),
            "--fake-apps",
            str(FIXTURES / "fake-apps.json"),
        ],
        cwd=ROOT,
        capture_output=True,
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        b"pack-kit: check passed (offline only)\n",
        b"",
    )


def test_final_cli_pack_runs_under_real_runtime(tmp_path):
    from connect_automate.automate import PackRuntime
    from tools.pack_kit.fakeapps import parse_catalogue
    from tools.pack_kit.sandbox import _success, environment

    source = tmp_path / "spec.toml"
    built = tmp_path / "build.json"
    signed = tmp_path / "signed.json"
    result = cli(
        "new",
        "--archetype",
        "approve-then-act",
        "--pack-id",
        spec()["pack_id"],
        "--name",
        "sample-pack",
        "--out",
        source,
    )
    assert result.returncode == 0, result.stderr
    result = cli("build", source, "--out", built)
    assert result.returncode == 0, result.stderr
    result = cli("check", built, "--fake-apps", FIXTURES / "fake-apps.json")
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        b"pack-kit: check passed (offline only)\n",
        b"",
    )
    key = fixed_key()
    public = key.public_key().public_bytes_raw()
    result = cli(
        "sign",
        built,
        "--fake-apps",
        FIXTURES / "fake-apps.json",
        "--key-id",
        "development",
        "--public-key-base64url",
        kit().encoded(public),
        "--out",
        signed,
        seed=key.private_bytes_raw(),
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, b"pack-kit: signed pack\n", b"")
    data = json.loads(built.read_bytes())
    with environment(data, parse_catalogue(catalog())) as env:
        kwargs = {**env["kwargs"], "publisher_keys": {"development": public}}
        env["runtime"] = PackRuntime.load(signed.read_bytes(), env["signed_grant"], **kwargs)
        _success(env, data)
    assert key.private_bytes_raw() not in signed.read_bytes()


def test_tampered_final_signature_rejected():
    from connect_automate.automate import PackError, load_pack

    key = fixed_key()
    k = kit()
    envelope = json.loads(
        k.sign(
            k.build(spec()),
            catalog(),
            "development",
            k.encoded(key.public_key().public_bytes_raw()),
            io.BytesIO(key.private_bytes_raw()),
        )
    )
    envelope["signature_base64url"] = k.encoded(b"x" * 64)
    with pytest.raises(PackError):
        load_pack(k.canonical(envelope), keys={"development": key.public_key().public_bytes_raw()})


def test_final_encoded_envelope_bound():
    from tools.pack_kit.core import _envelope

    key = fixed_key()
    k = kit()
    base_size = len(_envelope(b"", key, "development"))
    boundary = max(n for n in range(32768) if base_size + (4 * n + 2) // 3 <= 32768)
    assert len(_envelope(b"x" * boundary, key, "development")) <= 32768
    with pytest.raises(k.KitError, match="input too large"):
        _envelope(b"x" * (boundary + 1), key, "development")


def test_tty_key_error_does_not_precede_runtime_check(tmp_path, monkeypatch, capsys):
    from tools.pack_kit.__main__ import main

    value = spec()
    value["invoke"]["capability"]["id"] = "absent.capability"
    built = tmp_path / "build"
    built.write_bytes(kit().build(value))

    class Terminal:
        buffer = io.BytesIO()

        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    assert (
        main(
            [
                "sign",
                str(built),
                "--fake-apps",
                str(FIXTURES / "fake-apps.json"),
                "--key-id",
                "development",
                "--public-key-base64url",
                "unused",
                "--out",
                str(tmp_path / "signed"),
            ]
        )
        == 5
    )
    assert capsys.readouterr().err == "pack-kit: check failed\n"
    assert not (tmp_path / "signed").exists()


def test_real_failed_check_never_reads_publisher_seed():
    value = spec()
    value["invoke"]["capability"]["id"] = "absent.capability"

    class Seed:
        def read(self, *args):
            raise AssertionError("publisher seed read after failed check")

    with pytest.raises(kit().KitError, match="check failed"):
        kit().sign(kit().build(value), catalog(), "development", "unused", Seed())


@pytest.mark.parametrize("raw", [b"\xff", b"format_version =", b"name='a'\nname='b'", b"x = nan"])
def test_malformed_spec_cli(raw, tmp_path):
    path = tmp_path / "spec.toml"
    path.write_bytes(raw)
    result = cli("build", path, "--out", tmp_path / "build")
    assert (result.returncode, result.stdout, result.stderr) == (
        3,
        b"",
        b"pack-kit: invalid input\n",
    )
    assert not (tmp_path / "build").exists()


@pytest.mark.parametrize("name", ["Résumé", "Review 😀", 'quoted "name"', "line\nname"])
def test_new_preserves_valid_unicode_and_quoted_names(name):
    import tomllib

    raw = kit().new_spec("approve-then-act", spec()["pack_id"], name, 1)
    candidate = tomllib.loads(raw.decode("utf-8"))
    assert candidate["name"] == name
    assert json.loads(kit().build(candidate))["manifest"]["workflow"]["name"] == name


@pytest.mark.parametrize(
    "field,maximum", [("capabilities", 64), ("accepts", 16), ("produces", 16), ("parameters", 16)]
)
def test_catalogue_count_boundaries(field, maximum):
    from tools.pack_kit.fakeapps import parse_catalogue

    for count in [0, 1, maximum - 1, maximum, maximum + 1]:
        value = json.loads(catalog())
        declaration = value["capabilities"][0]
        if field == "capabilities":
            rows = []
            for i in range(count):
                item = copy.deepcopy(declaration)
                item["id"] = f"sample.c{i}"
                rows.append(item)
            value[field] = rows
        elif field == "accepts":
            declaration[field] = [
                {"media_type": f"application/x{i}", "max_bytes": 1} for i in range(count)
            ]
        elif field == "produces":
            declaration[field] = [f"application/x{i}" for i in range(count)]
        else:
            declaration[field] = [
                {**declaration["parameters"][0], "name": f"p{i}"} for i in range(count)
            ]
        valid = count <= maximum and (count > 0 or field == "parameters")
        if valid:
            parse_catalogue(kit().canonical(value))
        else:
            with pytest.raises(kit().KitError):
                parse_catalogue(kit().canonical(value))


def test_declared_input_byte_bounds():
    from tools.pack_kit.fakeapps import parse_catalogue

    for maximum in [0, 1, 1073741823, 1073741824, 1073741825]:
        value = json.loads(catalog())
        value["capabilities"][0]["accepts"][0]["max_bytes"] = maximum
        if 1 <= maximum <= 1073741824:
            parse_catalogue(kit().canonical(value))
        else:
            with pytest.raises(kit().KitError):
                parse_catalogue(kit().canonical(value))


@pytest.mark.parametrize("field,maximum", [("label", 80), ("description", 500)])
def test_catalogue_parameter_text_bounds(field, maximum):
    from tools.pack_kit.fakeapps import parse_catalogue

    for size in [0, 1, maximum - 1, maximum, maximum + 1]:
        value = json.loads(catalog())
        value["capabilities"][0]["parameters"][0][field] = "x" * size
        if 1 <= size <= maximum:
            parse_catalogue(kit().canonical(value))
        else:
            with pytest.raises(kit().KitError):
                parse_catalogue(kit().canonical(value))


def test_artifact_and_catalogue_decode_byte_limits():
    for limit in [65536, 131072]:
        for size in [limit - 1, limit, limit + 1]:
            raw = b"{}" + b" " * (size - 2)
            if size <= limit:
                assert kit().json_object(raw, limit) == {}
            else:
                with pytest.raises(kit().KitError, match="input too large"):
                    kit().json_object(raw, limit)
