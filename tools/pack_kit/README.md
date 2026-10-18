# Repository pack kit

The kit is development tooling outside the installed wheel. The accepted
behavioral contract is [PACK-KIT.md](../../docs/contracts/PACK-KIT.md).
Use the repository's existing `uv sync --locked --all-groups` environment.

```sh
uv run python -m tools.pack_kit new --archetype approve-then-act \
  --pack-id 11111111-1111-4111-8111-111111111111 --name sample-pack --out sample.toml
uv run python -m tools.pack_kit build sample.toml --out build.json
uv run python -m tools.pack_kit check build.json \
  --fake-apps tests/fixtures/pack_kit/fake-apps.json
```

The UUID above is a synthetic example. Choose the automation's identity once
and keep its explicit revision in the spec. Existing output files are never
replaced. Output parents must already exist. Edit the business fields in the
TOML; the fixed stage/effect/approval machinery is generated. Conditions can
inspect only `record.stage`. Capabilities must match the separate offline
catalogue exactly, including version, parameters and accepted input media.
The sample catalogue declares only the synthetic `sample.process` capability;
it does not discover or qualify an installed application.

For development signing, supply a matching expected public key and key ID:

```sh
uv run python -m tools.pack_kit sign build.json \
  --fake-apps tests/fixtures/pack_kit/fake-apps.json \
  --key-id development --public-key-base64url PUBLIC --out signed-pack.json
```

That command must receive exactly 32 raw Ed25519 seed bytes through binary
stdin from the caller's secure source, then EOF. There is no key-file, key-argv,
environment-secret or interactive-prompt option. An extra newline is invalid.
This project uses development keys only; it does not provision production
credentials. Test fixtures contain an explicitly public development signature.
Never use their test seed as an authority. The kit neither persists private
keys nor issues a real grant.

Signing repeats the complete offline check on the same held build bytes before
reading the publisher seed. There is no receipt, cache or skip-check flag.
The resulting envelope is verified with `load_pack`; running it on a host still
requires that host's entitlement and an independently issued matching grant.

The lifecycle requires operator decisions: `approve` starts the invocation;
`decline` does not call it. After inspecting a settled invocation outcome,
`complete` requests the literal follow-up action. After inspecting that action,
`finish` marks completion. Use `fail` from acting/reporting to record failure
and a local notification. Stages record intent, not proof of action success;
the current engine cannot police the truth of an operator's attestation.
Pending or failed actions do not automatically submit any later decision.
The follow-up cannot interpolate the invocation's output. These limitations
are explicit in the accepted contract.

`check` uses real pack/grant verification, entitlement, runtime, outbox and
Connect client code against disposable stores and a closed mock transport.
It opens no service, reads no installed application registrations and sends no
real mail/calendar/notification requests. It checks success, decline, replay,
invocation/result failure, missing adapters, and load refusal. A passed check
proves those offline scenarios only.

Expected errors produce one sanitized stderr line and no success stdout:
usage exits 2; invalid input/vocabulary/size exits 3; artifact mismatch exits 4;
check failure exits 5; key failure exits 6; filesystem failure exits 7.
Unexpected failure exits 1; interrupt exits 130. See the contract for messages.

Focused verification:

```sh
uv run ruff check tools/pack_kit tests/test_pack_kit.py tests/test_pack_kit_boundaries.py
uv run python -m pytest tests/test_pack_kit.py tests/test_pack_kit_boundaries.py
```

Golden files under `tests/fixtures/pack_kit/` are frozen review inputs. Tests
compare full bytes; they do not regenerate expected outputs. The golden seed
is defined only in tests. Durable mutation and wheel comparison evidence is
kept outside worktrees and referenced by alias/hash in review material.
