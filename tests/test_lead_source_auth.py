"""Synthetic source authorization proofs; no services, credentials or databases."""

import base64
import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from connect_automate.lead_intake import canonical_source, parse_untrusted_source, payload_digest
from connect_automate.lead_intake.auth import (
    SourceAuthenticationError,
    SourceTrustSnapshot,
    authenticate_source,
    source_signing_bytes,
)

FIXTURES = Path(__file__).parent / "fixtures" / "lead_source_auth"
VECTORS = json.loads((FIXTURES / "vectors.json").read_text())
NOW = datetime(2026, 10, 18, 12, 30, tzinfo=UTC)
OTHER = "00000000-0000-4000-8000-000000000002"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def envelope():
    return deepcopy(VECTORS[0]["envelope"])


def key(seed=None):
    return Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(VECTORS[0]["test_only_seed_hex"]) if seed is None else seed
    )


def resign(value, signer=None):
    # Independent producer, deliberately not the production preimage helper.
    authorization = value["authorization"]
    preimage = "\n".join(
        [
            "connect-lead-source-auth-v1",
            authorization["host_id"],
            authorization["key_id"],
            hashlib.sha256(encode(value["payload"])).hexdigest(),
        ]
    ).encode("ascii")
    authorization["signature"] = (
        base64.urlsafe_b64encode((signer or key()).sign(preimage)).decode().rstrip("=")
    )
    return encode(value)


def trust_data(value=None):
    value = envelope() if value is None else value
    p, a = value["payload"], value["authorization"]
    source, retention = p["source"], p["retention"]
    return {
        "version": "1.0",
        "host_id": a["host_id"],
        "organization_id": p["organization_id"],
        "generation": 1,
        "key_grants": [
            {
                "key_id": a["key_id"],
                "namespace_id": source["namespace_id"],
                "public_key": key().public_key().public_bytes_raw(),
                "status": "active",
                "valid_from": "2026-10-18T12:00:00Z",
                "valid_until": "2026-10-18T14:00:00Z",
                "mailboxes": [
                    [source["provider"], source["account_id"], source["mailbox_identity_key"]]
                ],
                "retention_policies": [[retention["policy_id"], retention["policy_version"]]],
            }
        ],
        "retention_policies": [
            {
                "policy_id": retention["policy_id"],
                "policy_version": retention["policy_version"],
                "max_recovery_seconds": 3600,
            }
        ],
    }


def trust(value=None):
    return SourceTrustSnapshot.model_validate(trust_data(value))


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["name"])
def test_frozen_signing_vectors(vector):
    source = parse_untrusted_source(encode(vector["envelope"]))
    assert source_signing_bytes(source).hex() == vector["preimage_hex"]
    assert payload_digest(source) == vector["payload_sha256"]
    assert source.authorization.signature == vector["signature_base64url"]
    assert key().public_key().public_bytes_raw().hex() == vector["public_key_hex"]
    result = authenticate_source(canonical_source(source), trust=trust(), now=NOW)
    assert result.payload_digest == vector["payload_sha256"]
    assert result.source == source
    assert result.host_id == source.authorization.host_id
    assert result.organization_id == source.payload.organization_id
    assert result.namespace_id == source.payload.source.namespace_id
    assert result.key_id == source.authorization.key_id
    assert result.trust_generation == 1
    assert result.policy_id == source.payload.retention.policy_id
    assert result.policy_version == 1
    assert result.verified_at == NOW
    assert result.valid_until == datetime(2026, 10, 18, 13, tzinfo=UTC)


def authenticate(value=None, data=None, now=NOW):
    value = envelope() if value is None else value
    authority = trust(value) if data is None else SourceTrustSnapshot.model_validate(data)
    return authenticate_source(resign(value), trust=authority, now=now)


def rejected(raw, authority, now=NOW):
    with pytest.raises(SourceAuthenticationError) as caught:
        authenticate_source(raw, trust=authority, now=now)
    error = caught.value
    assert error.args == ("lead source authentication rejected",)
    assert error.__context__ is None
    assert error.__cause__ is None
    assert error.__dict__ == {}


def leaf_paths(value, prefix=()):
    for name, item in value.items():
        path = (*prefix, name)
        if isinstance(item, dict):
            yield from leaf_paths(item, path)
        elif path != ("authorization", "signature"):
            yield path


@pytest.mark.parametrize("path", list(leaf_paths(envelope())), ids=lambda p: ".".join(p))
def test_every_signed_field_is_bound(path):
    value = envelope()
    target = value
    for part in path[:-1]:
        target = target[part]
    name, before = path[-1], target[path[-1]]
    if name == "text":
        text = "A different synthetic inquiry"
        target.update(
            text=text,
            stored_chars=len(text),
            source_chars=len(text),
            sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
    elif name in {
        "host_id",
        "key_id",
        "organization_id",
        "event_id",
        "namespace_id",
        "rule_id",
        "snapshot_id",
        "policy_id",
    }:
        target[name] = OTHER
    elif name in {"watcher_event_id", "mailbox_identity_key", "sha256"}:
        target[name] = "c" * 64
    elif name == "occurred_at":
        target[name] = "2026-10-18T12:01:00Z"
    elif name == "captured_at":
        target[name] = "2026-10-18T11:59:00Z"
    elif name == "recovery_deadline":
        target[name] = "2026-10-18T12:59:00Z"
    elif name == "completeness":
        target.update(completeness="truncated", source_chars=target["stored_chars"] + 1)
    elif before is None:
        target[name] = 0
    elif type(before) is int:
        target[name] += 1
    else:
        target[name] += "changed"
    parser_only = {
        "schema",
        "schema_version",
        "admission_kind",
        "input_kind",
        "part_id",
        "representation",
        "state",
        "processing",
        "stored_chars",
        "source_chars",
        "sha256",
    }
    if name not in parser_only:
        # Align authority to the changed envelope: only its stale signature rejects.
        parse_untrusted_source(encode(value))
    rejected(encode(value), trust(value))


@pytest.mark.parametrize(
    "kind",
    [
        "raw-json",
        "body-only",
        "context",
        "host",
        "key",
        "trailing-newline",
        "wrong-private-key",
        "zero-signature",
    ],
)
def test_wrong_signing_protocol_rejected(kind):
    value = envelope()
    preimage = bytes.fromhex(VECTORS[0]["preimage_hex"])
    if kind == "raw-json":
        preimage = encode(value["payload"])
    elif kind == "body-only":
        preimage = value["payload"]["snapshot"]["body"]["text"].encode()
    elif kind == "context":
        preimage = preimage.replace(b"connect-lead-source-auth-v1", b"connect-device-access-v1")
    elif kind in {"host", "key"}:
        lines = preimage.split(b"\n")
        lines[1 if kind == "host" else 2] = OTHER.encode()
        preimage = b"\n".join(lines)
    elif kind == "trailing-newline":
        preimage += b"\n"
    signer = key(bytes(reversed(range(32)))) if kind == "wrong-private-key" else key()
    signature = bytes(64) if kind == "zero-signature" else signer.sign(preimage)
    value["authorization"]["signature"] = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    parse_untrusted_source(encode(value))
    rejected(encode(value), trust())


@pytest.mark.parametrize(
    "scope",
    [
        "host",
        "organization",
        "key",
        "namespace",
        "provider",
        "account",
        "mailbox",
        "policy-id",
        "policy-version",
        "revoked",
    ],
)
def test_valid_signature_cannot_exceed_grant(scope):
    data = trust_data()
    grant = data["key_grants"][0]
    if scope == "host":
        data["host_id"] = OTHER
    elif scope == "organization":
        data["organization_id"] = OTHER
    elif scope in {"key", "namespace"}:
        grant[scope + "_id"] = OTHER
    elif scope in {"provider", "account", "mailbox"}:
        index = {"provider": 0, "account": 1, "mailbox": 2}[scope]
        grant["mailboxes"][0][index] = "c" * 64 if index == 2 else "another"
    elif scope.startswith("policy"):
        index = 0 if scope == "policy-id" else 1
        replacement = OTHER if index == 0 else 2
        grant["retention_policies"][0][index] = replacement
        data["retention_policies"][0]["policy_id" if index == 0 else "policy_version"] = replacement
    else:
        grant["status"] = "revoked"
    rejected(encode(envelope()), SourceTrustSnapshot.model_validate(data))


@pytest.mark.parametrize("index", [0, 1, 2])
def test_mixed_mailbox_members_are_not_independent_grants(index):
    value = envelope()
    data = trust_data()
    other = ["other-provider", "other-account", "c" * 64]
    data["key_grants"][0]["mailboxes"].append(other)
    source = value["payload"]["source"]
    source[["provider", "account_id", "mailbox_identity_key"][index]] = other[index]
    rejected(resign(value), SourceTrustSnapshot.model_validate(data))
    source.update(zip(["provider", "account_id", "mailbox_identity_key"], other, strict=True))
    assert authenticate(value, data).source.payload.source.provider == "other-provider"


@pytest.mark.parametrize("member", ["provider", "account_id"])
@pytest.mark.parametrize("granted", ["café", "cafe\u0301"])
def test_unicode_scope_is_exact(member, granted):
    value = envelope()
    value["payload"]["source"][member] = granted
    data = trust_data(value)
    assert authenticate(value, data).source.payload.source.model_dump()[member] == granted
    value["payload"]["source"][member] = "cafe\u0301" if granted == "café" else "café"
    rejected(resign(value), SourceTrustSnapshot.model_validate(data))


@pytest.mark.parametrize("member", ["provider", "account_id"])
@pytest.mark.parametrize("value", ["Synthetic", "synthetic ", "*", "", "x" * 257])
def test_no_casefold_trim_wildcard_or_invalid_identifier(member, value):
    original = envelope()
    original["payload"]["source"][member] = value
    rejected(resign(original), trust())


@pytest.mark.parametrize("bad", [0, False, "", -1, 2147483648, 1.5, None])
@pytest.mark.parametrize("field", ["generation", "max_recovery_seconds", "policy_version"])
def test_trust_revision_bounds(bad, field):
    data = trust_data()
    (data if field == "generation" else data["retention_policies"][0])[field] = bad
    with pytest.raises(ValidationError):
        SourceTrustSnapshot.model_validate(data)
    rejected(encode(envelope()), SourceTrustSnapshot.model_construct(**data))


@pytest.mark.parametrize(
    "case",
    [
        "duplicate-key",
        "duplicate-public-key",
        "duplicate-mailbox",
        "duplicate-grant-policy",
        "duplicate-policy",
        "dangling-policy",
        "empty-mailboxes",
        "empty-grant-policies",
        "bad-key-size",
        "extra",
        "missing",
        "wrong-version",
        "null-org",
        "equal-validity",
        "reversed-validity",
        "set-input",
    ],
)
def test_invalid_trust_never_authorizes(case):
    data = trust_data()
    grant = data["key_grants"][0]
    if case.startswith("duplicate-key") or case == "duplicate-public-key":
        second = deepcopy(grant)
        if case == "duplicate-key":
            second["public_key"] = key(bytes(reversed(range(32)))).public_key().public_bytes_raw()
        else:
            second["key_id"] = OTHER
        data["key_grants"].append(second)
    elif case == "duplicate-mailbox":
        grant["mailboxes"] *= 2
    elif case == "duplicate-grant-policy":
        grant["retention_policies"] *= 2
    elif case == "duplicate-policy":
        data["retention_policies"] *= 2
    elif case == "dangling-policy":
        grant["retention_policies"].append([OTHER, 1])
    elif case == "empty-mailboxes":
        grant["mailboxes"] = []
    elif case == "empty-grant-policies":
        grant["retention_policies"] = []
    elif case == "bad-key-size":
        grant["public_key"] = b"x" * 31
    elif case == "extra":
        grant["extra"] = "sensitive-sentinel"
    elif case == "missing":
        del grant["status"]
    elif case == "wrong-version":
        data["version"] = "2.0"
    elif case == "null-org":
        data["organization_id"] = None
    elif case in {"equal-validity", "reversed-validity"}:
        grant["valid_from"] = grant["valid_until"]
        if case == "reversed-validity":
            grant["valid_from"] = "2026-10-18T15:00:00Z"
    else:
        data["key_grants"] = set()
    with pytest.raises(ValidationError):
        SourceTrustSnapshot.model_validate(data)
    rejected(encode(envelope()), SourceTrustSnapshot.model_construct(**data))


@pytest.mark.parametrize("size", [0, 31, 32, 33])
def test_public_key_representation_bounds(size):
    data = trust_data()
    data["key_grants"][0]["public_key"] = b"x" * size
    if size == 32:
        assert SourceTrustSnapshot.model_validate(data).key_grants[0].public_key == b"x" * size
    else:
        with pytest.raises(ValidationError):
            SourceTrustSnapshot.model_validate(data)
        rejected(encode(envelope()), SourceTrustSnapshot.model_construct(**data))


@pytest.mark.parametrize("record", ["snapshot", "grant", "policy"])
@pytest.mark.parametrize("kind", ["extra", "missing"])
def test_all_trust_records_are_closed_and_required(record, kind):
    data = trust_data()
    target = {
        "snapshot": data,
        "grant": data["key_grants"][0],
        "policy": data["retention_policies"][0],
    }[record]
    if kind == "extra":
        target["unexpected"] = "sensitive-sentinel"
    else:
        del target[next(iter(target))]
    with pytest.raises(ValidationError):
        SourceTrustSnapshot.model_validate(data)


def test_empty_snapshot_denies_all():
    data = trust_data()
    data.update(key_grants=[], retention_policies=[])
    rejected(encode(envelope()), SourceTrustSnapshot.model_validate(data))


def test_existing_policy_still_requires_key_permission():
    value = envelope()
    data = trust_data()
    second = deepcopy(data["retention_policies"][0])
    second["policy_id"] = OTHER
    data["retention_policies"].append(second)
    value["payload"]["retention"]["policy_id"] = OTHER
    rejected(resign(value), SourceTrustSnapshot.model_validate(data))


@pytest.mark.parametrize("target", ["key-start", "key-end", "occurred", "deadline"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_time_boundaries_to_the_microsecond(target, offset):
    data = trust_data()
    grant = data["key_grants"][0]
    grant["valid_from"] = "2026-10-18T11:00:00Z"
    point = datetime(2026, 10, 18, 12, 30, tzinfo=UTC)
    if target == "key-start":
        grant["valid_from"] = "2026-10-18T12:30:00Z"
        accepted = offset >= 0
    elif target == "key-end":
        grant["valid_until"] = "2026-10-18T12:30:00Z"
        accepted = offset < 0
    elif target == "occurred":
        point = datetime(2026, 10, 18, 12, tzinfo=UTC)
        accepted = offset >= 0
    else:
        point = datetime(2026, 10, 18, 13, tzinfo=UTC)
        accepted = offset < 0
    now = point + timedelta(microseconds=offset)
    authority = SourceTrustSnapshot.model_validate(data)
    if accepted:
        result = authenticate_source(encode(envelope()), trust=authority, now=now)
        assert result.verified_at == now
        assert result.valid_until == min(
            datetime.fromisoformat(grant["valid_until"]), datetime(2026, 10, 18, 13, tzinfo=UTC)
        )
    else:
        rejected(encode(envelope()), authority, now)


@pytest.mark.parametrize(
    "now",
    [
        0,
        False,
        "",
        "2026-10-18T12:30:00Z",
        None,
        NOW.replace(tzinfo=None),
        NOW.astimezone(timezone(timedelta(hours=1))),
    ],
)
def test_clock_must_be_explicit_utc_datetime(now):
    rejected(encode(envelope()), trust(), now)


@pytest.mark.parametrize("maximum", [1, 2147483646, 2147483647])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_recovery_policy_boundaries(maximum, delta):
    value = envelope()
    start = datetime(2026, 10, 18, 12, tzinfo=UTC)
    duration = maximum + delta
    value["payload"]["retention"]["recovery_deadline"] = (
        start + timedelta(seconds=duration)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = trust_data(value)
    data["retention_policies"][0]["max_recovery_seconds"] = maximum
    if duration <= 0 or delta > 0:
        rejected(resign(value), SourceTrustSnapshot.model_validate(data), start)
    else:
        assert authenticate(value, data, start).verified_at == start


def test_replay_and_rotation_do_not_extend_recovery():
    value = envelope()
    original = authenticate(value)
    assert authenticate(value) == original  # Authentication is deliberately stateless.
    data = trust_data()
    old = data["key_grants"][0]
    old["status"] = "revoked"
    new = deepcopy(old)
    new.update(
        key_id=OTHER,
        status="active",
        valid_from="2026-10-18T12:15:00Z",
        public_key=key(bytes(reversed(range(32)))).public_key().public_bytes_raw(),
    )
    data["key_grants"].append(new)
    data["generation"] = 2
    authority = SourceTrustSnapshot.model_validate(data)
    rejected(encode(value), authority)
    value["authorization"]["key_id"] = OTHER
    raw = resign(value, key(bytes(reversed(range(32)))))
    rotated = authenticate_source(raw, trust=authority, now=NOW)
    assert rotated.payload_digest == original.payload_digest
    assert rotated.valid_until == original.valid_until
    assert rotated.trust_generation == 2
    rejected(raw, authority, datetime(2026, 10, 18, 13, tzinfo=UTC))


def test_configuration_and_results_are_deeply_immutable():
    from dataclasses import FrozenInstanceError

    data = trust_data()
    authority = SourceTrustSnapshot.model_validate(data)
    first = authenticate_source(encode(envelope()), trust=authority, now=NOW)
    data["key_grants"][0]["mailboxes"][0][0] = "mutated"
    data["retention_policies"][0]["max_recovery_seconds"] = 0
    data["key_grants"].clear()
    assert authenticate_source(encode(envelope()), trust=authority, now=NOW) == first
    with pytest.raises(ValidationError):
        authority.key_grants[0].status = "revoked"
    with pytest.raises(ValidationError):
        authority.generation = 2
    with pytest.raises(ValidationError):
        authority.retention_policies[0].max_recovery_seconds = 0
    with pytest.raises(TypeError):
        authority.key_grants[0].mailboxes[0][0] = "changed"
    with pytest.raises(FrozenInstanceError):
        first.key_id = OTHER
    with pytest.raises(ValidationError):
        first.source.payload.source.account_id = "changed"


def test_construct_copy_and_mutation_cannot_bypass_public_boundaries():
    from connect_automate.lead_intake import SourceInputError

    authority = trust()
    for invalid in [
        authority.model_copy(update={"generation": False}),
        authority.model_copy(update={"host_id": "invalid"}),
        authority.model_copy(
            update={
                "key_grants": (authority.key_grants[0].model_copy(update={"status": "invalid"}),)
            }
        ),
    ]:
        rejected(encode(envelope()), invalid)
    source = parse_untrusted_source(encode(envelope()))
    invalid = source.model_copy(
        update={"authorization": source.authorization.model_copy(update={"host_id": "invalid"})}
    )
    with pytest.raises(SourceInputError):
        source_signing_bytes(invalid)
    # Deliberate bypass simulates a caller-mutated validated model at entry.
    object.__setattr__(authority.key_grants[0], "public_key", b"sensitive-sentinel")
    rejected(encode(envelope()), authority)


@pytest.mark.parametrize(
    "raw", [b"", b"\xff", b'{"sensitive-sentinel":', b"{}", b"[" * 10000 + b"]" * 10000]
)
def test_input_errors_have_no_internal_context(raw):
    rejected(raw, trust())


def test_repr_and_crypto_errors_omit_sensitive_content(capsys):
    value = envelope()
    body = value["payload"]["snapshot"]["body"]
    text = "sensitive-sentinel"
    body.update(
        text=text,
        stored_chars=len(text),
        source_chars=len(text),
        sha256=hashlib.sha256(text.encode()).hexdigest(),
    )
    result = authenticate(value)
    shown = repr(result)
    assert text not in shown
    assert result.source.authorization.signature not in shown
    assert repr(trust().key_grants[0].public_key) not in repr(trust())
    value["authorization"]["signature"] = VECTORS[0]["signature_base64url"]
    rejected(encode(value), trust())
    assert capsys.readouterr() == ("", "")


def test_missing_wrong_or_envelope_trust_is_not_authority():
    for invalid in [None, {}, trust_data(), envelope(), False]:
        rejected(encode(envelope()), invalid)


def test_unavailable_body_has_the_same_authentication_boundary():
    value = envelope()
    value["payload"]["snapshot"]["body"] = {"state": "unavailable", "reason": "source_gone"}
    result = authenticate(value)
    assert result.source.payload.snapshot.body.reason == "source_gone"
    raw = resign(value)
    value["payload"]["snapshot"]["body"]["reason"] = "retrieval_failed"
    rejected(encode(value), trust())
    assert authenticate_source(raw, trust=trust(), now=NOW) == result


def test_parallel_calls_share_no_mutable_authorization_state():
    from concurrent.futures import ThreadPoolExecutor

    raw, authority = encode(envelope()), trust()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: authenticate_source(raw, trust=authority, now=NOW), range(16))
        )
    assert all(result == results[0] for result in results)


def test_public_exports_use_the_authentication_owner():
    import connect_automate.lead_intake as public

    assert public.authenticate_source is authenticate_source
    assert public.source_signing_bytes is source_signing_bytes
    assert public.SourceTrustSnapshot is SourceTrustSnapshot
    assert public.SourceAuthenticationError is SourceAuthenticationError


@pytest.mark.parametrize("part", ["authorization", "payload", "both"])
@pytest.mark.parametrize("construction", ["copy", "construct"])
def test_preimage_consumes_validated_snapshot(part, construction):
    source = parse_untrusted_source(encode(envelope()))
    fields = {"payload": source.payload, "authorization": source.authorization}
    for name in fields:
        if part in {name, "both"}:
            fields[name] = fields[name].model_dump(by_alias=True)
    supplied = (
        source.model_copy(update=fields)
        if construction == "copy"
        else type(source).model_construct(**fields)
    )
    # The existing encoder accepts this representation and preserves its meaning.
    assert canonical_source(supplied) == canonical_source(source)
    assert source_signing_bytes(supplied) == bytes.fromhex(VECTORS[0]["preimage_hex"])
    if part in {"authorization", "both"}:
        assert isinstance(supplied.authorization, dict)  # Caller input was not rewritten.


@pytest.mark.parametrize("construction", ["copy", "construct"])
def test_preimage_rejects_invalid_nested_dictionary(construction):
    from connect_automate.lead_intake import SourceInputError

    source = parse_untrusted_source(encode(envelope()))
    fields = {
        "payload": source.payload,
        "authorization": {**source.authorization.model_dump(), "host_id": "sensitive-sentinel"},
    }
    supplied = (
        source.model_copy(update=fields)
        if construction == "copy"
        else type(source).model_construct(**fields)
    )
    with pytest.raises(SourceInputError) as caught:
        source_signing_bytes(supplied)
    assert caught.value.args == ("invalid lead source input",)
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("supplied", [None, False, envelope(), encode(envelope())])
def test_preimage_requires_source_model(supplied):
    from connect_automate.lead_intake import SourceInputError

    with pytest.raises(SourceInputError) as caught:
        source_signing_bytes(supplied)
    assert caught.value.args == ("invalid lead source input",)
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
