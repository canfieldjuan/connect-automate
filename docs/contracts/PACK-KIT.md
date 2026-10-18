# Pack kit: approve then act

Status: ACCEPTED. Juan answered **"Accept (Recommended)"** on 2026-10-17;
oversight relayed his acceptance verbatim in mailbox message `44c186ae` for
contract commit `8f20f5ae174dc99bd41acb151ed9e2d1671f2d66`. The accepted prompt was:

> Accept the pack kit contract (connect-automate#4, commit 8f20f5a)? It builds a 'new / build / check / sign' tool under tools/ that turns a short spec file (pack name and version, conditions, which app capability to call and with what, and one follow-up action) into a signed pack. It changes none of the shipped code, and it proves the shipped package is byte-identical. The one real limit: today's engine can't react to a result on its own, so in this first pattern ('approve then act') a person approves, the app call runs, then a person marks it done or failed after looking at the outcome, and only then does the follow-up action fire. The follow-up can't use the app's output yet; it's fixed text. Automatic 'when the result arrives, do X' needs the new triggers in #5. This slice proves the reusable skeleton and tooling, not hands-free automations.

Acceptance is recorded separately before implementation. The behavioral
requirements below are unchanged.
Work: issue #4. Follow-up vocabulary in issue #5 is excluded.

## Root cause and source inventory

There is no reusable authoring boundary between an automation's business inputs
and the signed pack machinery. Pack assembly currently lives in test helpers.
The kit will generate the repeated machinery, not repair or extend the runtime.

The reference checkout is `canfieldjuan/connect-automate` at
`a6bbb34` (the fetched `origin/main` when this contract was prepared):

| Existing owner | Reusable behavior and limitation |
| --- | --- |
| `tests/test_automate_pack.py`, `_pack_payload`, `_envelope` | Pack manifest and Ed25519 envelope examples; test keys only. |
| `tests/test_automate_runtime.py`, `_workflow`, `_pack_payload`, `_grant_bytes`, `_licensed_host` | A real licensed runtime, pack and subject-bound grant, using generated test authorities. |
| `automate/definition.py`, `parse_workflow`, `canonical_workflow` | Strict workflow vocabulary, materialized defaults, canonical UTF-8 JSON, and canonical workflow size limit. Paths in this table below `automate/` are relative to `src/connect_automate/`. |
| `automate/definition.py`, `Condition`, `ActionEmit`, `ConnectInvokeRequest` | Conditions inspect only `record.stage`; effects are `record.transition` and `overlay.set`; invocation templates support literal inputs and overlay bindings. |
| `automate/actions.py`, `ACTION_KINDS`, `AdapterRegistry`, `ConnectInvokeAdapter` | Closed action vocabulary, adapter dispatch, stable action/job identity, and durable outcomes. |
| `automate/runtime.py`, `PackRuntime.load`, `submit_decision` | Signature, entitlement and grant verification precede execution; actions run after effects commit. No unsigned runtime entry point or action-result trigger exists. |
| `automate/pack.py`, `PackManifest`, `PackGrant`, `load_pack`, `verify_grant` | Independent publisher and grant trust stores; grant binds pack identity, subject and validity window, not pack version. |
| `automate_connect.py`, `ConnectV2CapabilityInvoker`; `tests/test_automate_connect.py` | Real invocation path with injected discovery and `httpx.MockTransport`; frozen request, submit, poll and terminal mapping without a live provider. |
| `pyproject.toml`, wheel target | Only `src/connect_automate` is packaged. |

This is an inventory of reusable tests and public interfaces, not a claim that
the new archetype has already been qualified. No previous pack-kit qualification
packet exists in this inventory. There is no model, model pin, prompt, chat
template or inference setting: this work performs no model execution. Existing
tests' explicit clocks, generated development keys and synthetic requests are
the starting proof pattern; runtime-generated IDs and signatures are not golden
workflow bytes.

Differences from those examples are limited to a strict business spec, a shared
archetype, deterministic build serialization, an offline scenario harness and
an enforced check-before-publisher-signing command. The kit uses public models,
functions and injectable seams. It imports no underscore-prefixed package
helpers and supplies no private runtime construction token. There is no port of
application behavior or new transport/runtime implementation.

## Required change surface and release isolation

This phase changes only `docs/contracts/PACK-KIT.md`. After acceptance,
implementation belongs under `tools/pack_kit/`, with focused discovery-compatible
tests under `tests/test_pack_kit*.py` and synthetic goldens/fixtures under
`tests/fixtures/pack_kit/`. Usage belongs in a tools-local README. The invocation
is `python -m tools.pack_kit` from the repository root in the existing development
environment; there is no installed entry point or new dependency.

Do not edit `src/connect_automate/**`, package formats, signed-byte semantics,
entitlement behavior, dependency files, wheel configuration or existing tests to
make the kit pass. A missing public seam or required runtime behavior is a stop
and an oversight report, not a reason to patch around it. No application,
connect-contracts, keyring or release-catalogue repository is changed; no pin
moves. No production publisher key is created, requested or used. Neither issue
is added to the First Public Release milestone. Public material contains only
technical authoring examples and synthetic data; commercial specifics are
excluded.

## Business spec and authoring inputs

The spec is UTF-8 TOML parsed as data, never executable text. It has a closed
schema, no includes, imports, environment substitution, templates, expressions,
shell commands, module paths or plugin hooks. Unknown fields, wrong primitive
types, duplicate members, non-finite numbers and unsupported versions fail.
Optional defaults are applied by presence, never by truthiness.

Required metadata is `format_version = 1`, `archetype = "approve-then-act"`,
`pack_id`, `pack_version`, and `name`. The identity and revision are explicit
authoring inputs: the kit does not mint a new identity on every build. This small
header identifies the automation; it contains no envelope, signature, grant or
handwritten workflow. `pack_id` and positive integer `pack_version` obey
`PackManifest`; `name` obeys `Workflow`.

The business fields are:

- `conditions`: optional array, default empty, of existing `record.stage`
  conditions (`equals` or `in`), AND-combined with the mandatory ready-stage
  approval condition. No document, mail, parameter or result predicates exist.
  Conditions that exclude `ready` fail validation rather than create a dead
  approval path. Author conditions may not bypass the ready-stage guard.
- `invoke`: capability `{id, version}`, literal `parameters` (default empty),
  and `input` containing `media_type`, display `filename` and UTF-8 `content`.
  The skeleton base64-encodes content and uses `pack_id` as the fixed input
  artifact identity; the actual job identity remains the runtime action ID.
  There is no file dereferencing or overlay binding in this archetype's spec.
- `result_action`: existing `ActionEmit` shape `{action, request}`. Ordinary
  requests contain only the flat scalars the public model admits; a
  `connect.invoke` result action must satisfy `ConnectInvokeRequest` and use
  literal input/parameters. Result requests are literal, with no substitution
  of capability outputs. Each referenced capability must have an offline fake
  declaration at check time.

Example business body (the header is supplied by `new`):

```toml
conditions = []

[invoke.capability]
id = "sample.process"
version = "1.0"

[invoke.input]
media_type = "text/plain"
filename = "request.txt"
content = "Synthetic request"

[invoke.parameters]
mode = "review"

[result_action]
action = "notify.local"

[result_action.request]
title = "Result reviewed"
body = "The operator reviewed the action outcome."
```

The action vocabulary comes from `ACTION_KINDS`, not a second maintained list.
Capability IDs are opaque in the shipped workflow model: build validates their
syntax and request shape, not installed availability. Check must find an exact
ID/version match in a separately supplied fake catalogue; it must not invent an
accepting provider from the spec or silently select another capability.

## Archetype lifecycle and failure semantics

Stages, in order: `ready`, `acting`, `reporting`, `completed`, `failed`,
`declined`. Initial stage: `ready`. Every definition uses `operator.decision`,
one stage condition, one `record.transition`, and an `overlay.set` of
`pack-kit.status` to the destination stage. Effects occur in transition-then-overlay
order. Single-stage guards use `equals`; the failure guard uses `in` with
`["acting", "reporting"]`. Approval additionally carries the business conditions
in spec order after its mandatory guard. Definitions occur in the table order.

| Decision / definition name | Allowed current stage | Destination | Actions |
| --- | --- | --- | --- |
| `approve` | `ready` | `acting` | One `connect.invoke` compiled from `invoke`, with `confirmed = true`. |
| `decline` | `ready` | `declined` | None. |
| `complete` | `acting` | `reporting` | One business `result_action`. |
| `finish` | `reporting` | `completed` | None. |
| `fail` | `acting` or `reporting` | `failed` | One `notify.local` with title `Pack action failed` and body `Inspect the durable action outcome before starting a new record.` |

These are operator decisions, not an automatic orchestration loop. An operator
inspects the durable invocation outcome before `complete`, and the result-action
outcome before `finish`; a failure is acknowledged by `fail`. The checker plays
the operator only in its isolated scenarios. The shipped runtime cannot enforce
that an operator's attestation agrees with an action result, and the kit makes
no such claim. Acceptance explicitly accepts that limit for this slice.

A transition records admitted intent, not successful delivery. An invocation
failure leaves the record at `acting` until an operator decides; a result-action
failure leaves it at `reporting`. Missing adapters leave actions pending and do
not imply success. Do not place invocation and result actions on the same
definition: the runtime does not condition later actions on earlier success.
There is no new retry policy, rollback, compensation, automatic result routing,
output interpolation, or blanket exactly-once claim. Terminal failed actions
stay failed under existing runtime behavior. Replaying the same operation key
uses existing idempotency; a fresh approval at a later stage does not match.

The spec cannot supply arbitrary definitions, stages, triggers, effects or
confirmation flags. The only confirmation-required invocation generated by the
skeleton is attached to explicit approval. A capability used as the result
action still requires its own explicit `confirmed` value when its declaration
requires confirmation; check must enforce that public request contract.

## Observable command contract

Paths are explicit user inputs, never constructed from spec labels or IDs.
Input is read once, bounded and held as an immutable snapshot for that command.
Spec and fake-catalogue limits are each 64 KiB; build-artifact limit is 128 KiB.
Workflow and final envelope limits come from the public package constants,
including `MAX_DEFINITION_BYTES` and `MAX_PACK_BYTES`; the base64 envelope's
final encoded size, not just its payload size, is checked before publication.

Success exits `0`. Usage errors exit `2` and start stderr with
`pack-kit: usage:`. All other expected errors emit exactly one newline-terminated
stderr line in the table's format, exit as listed, and emit no success stdout.
No raw exception, key bytes, spec content, adapter payload or traceback appears
in diagnostics. A safe structural field path may follow a validation error.
When several conditions fail, ordering is usage, bounded input/decode,
schema/vocabulary, artifact consistency, runtime check, key, output publication.
Interrupts exit `130` with `pack-kit: interrupted` and no published output.

| Command | Inputs | Success output and effect |
| --- | --- | --- |
| `new --archetype approve-then-act --pack-id UUID --name NAME [--pack-version VERSION] --out SPEC` | Explicit metadata; revision defaults to `1`. | Writes a commented, editable TOML spec with that header and the synthetic business body above. stdout: `pack-kit: created spec`. No UUID, clock, path or machine-derived defaults. |
| `build SPEC --out BUILD` | Strict spec only. | Writes canonical unsigned build JSON; stdout: `pack-kit: built unsigned artifact`. It is not a loadable or authorized pack yet. |
| `check BUILD --fake-apps CATALOG` | Exact build bytes and explicit offline fake catalogue. | Runs the full scenario suite below. stdout: `pack-kit: check passed (offline only)`. Creates no persistent receipt or pack. |
| `sign BUILD --fake-apps CATALOG --key-id ID --public-key-base64url PUBLIC --out PACK` | Same build/catalogue as check; expected Ed25519 public key supplied explicitly. Private seed is raw bytes on binary stdin only. | Revalidates the snapshot and runs the entire check in this process before reading the private seed or calling its signer. Signs the manifest payload, verifies with `load_pack`, then writes the existing envelope. stdout: `pack-kit: signed pack`. No grant is issued. |

`new` validates its metadata before writing. `build` constructs a workflow,
calls the real `parse_workflow`, and gets workflow bytes only from
`canonical_workflow`. It validates the containing `PackManifest`. The unsigned
artifact has exactly `kit_format_version`, `archetype`, `spec`, and `manifest`;
kit format is `1`; spec is the normalized JSON representation of the entire
TOML spec with defaults materialized, and manifest has only existing fields.

Canonical kit JSON is UTF-8 with sorted object keys, separators `,` and `:`,
`ensure_ascii=False`, `allow_nan=False`, no BOM or trailing newline. Arrays keep
their declared order; definition/effect/action order comes from the archetype.
The manifest's workflow is the parsed public canonical workflow, not a second
workflow serializer. Signing covers exactly the canonical manifest payload in
the existing envelope, not just the workflow or the kit wrapper. Base64url in
the envelope is unpadded. No build timestamps, random IDs, absolute paths or
environment values are embedded.

`check` and `sign` strictly reject duplicate JSON members, unknown fields,
noncanonical artifact bytes and mismatched artifact/spec/archetype/manifest.
They rebuild from the embedded normalized spec and compare the full canonical
artifact bytes. A changed payload with an old spec is rejected even if the
workflow alone parses. A self-consistent replacement of the entire unsigned
artifact is a new candidate; unsigned checksums are not provenance or trust.
Sign rechecks that candidate rather than trusting an editable report, digest,
prior process, flag, environment variable or file marker. No skip-check option
or alternate publisher-signing entry point is provided by the kit.

Private stdin must contain exactly 32 raw seed bytes, with no newline; read at
most 33 to detect excess. Empty, short, long or malformed input fails; a seed
whose derived public key differs from PUBLIC is a wrong key. PUBLIC must be a
canonical unpadded base64url encoding of a 32-byte public key and ID must satisfy
the existing key-ID model. Private key material is never accepted in argv, a spec,
catalogue, environment variable, log or tool-created file. The kit never writes
private keys, including its development authorities, to disk. It does not
promise protection from OS memory swapping or Python-memory zeroization. Tests
and this work use development keys only.

| Failure | Exit | Stable stderr |
| --- | --- | --- |
| Invalid TOML, schema/type/identity/condition, malformed catalogue or unsupported kit format | `3` | `pack-kit: invalid input` |
| Unknown archetype | `3` | `pack-kit: unknown archetype` |
| Unknown action, trigger, effect, condition field/op or malformed capability request | `3` | `pack-kit: unsupported vocabulary` |
| Input bound, public workflow bound or final pack-envelope bound exceeded | `3` | `pack-kit: input too large` |
| Canonicality or rebuilt-artifact mismatch | `4` | `pack-kit: build artifact mismatch` |
| Capability absent from fake catalogue, incompatible parameters/media, failed expected-success path, or any scenario assertion failing | `5` | `pack-kit: check failed` |
| Absent, invalid, excessive or wrong private key; malformed public key or key ID | `6` | `pack-kit: invalid signing key` |
| Existing output, including symlink | `7` | `pack-kit: output exists` |
| Input/output permission, missing input/parent, read or write failure | `7` | `pack-kit: I/O error` |
| Unexpected internal failure or failed final `load_pack` verification | `1` | `pack-kit: internal error` |

An expected injected adapter failure is a passing negative scenario only when
the harness observes exactly the specified failed/pending outcome. It is not
an exception to the mandatory expected-success scenario.

Outputs use create-if-absent publication: complete bytes are staged privately
in the destination directory and made visible atomically without replacing an
existing file. Output parent must already exist; symlinks are never followed
as output destinations. A failed invocation leaves existing output untouched,
publishes no partial destination and cleans its own staging file. No force or
overwrite option exists. Inputs and destinations cannot alias. Files are owner
only on POSIX; no claim of Windows ACL qualification is made by POSIX tests.

## Offline check, grant binding and fake applications

Catalogue JSON has exactly `format_version = 1` and `capabilities`, a nonempty
array. Each declaration contains exactly `id`, `version`, `accepts`, `produces`,
`parameters`, `external_effects`, and `confirmation_required`. `accepts` is an
array of `{media_type, max_bytes}`; `produces` is an array of media-type strings;
`parameters` is an array of `{name, value_type, required, label, description}`
using today's public capability parameter semantics. Duplicate ID/version pairs,
media types and parameter names fail; lists and primitives obey the existing
Connect declaration bounds. No fixed-parameter negotiation or manifest feature
extension is added by this slice.

The harness materializes public `DiscoveredCapability`/`CapabilityCatalog`
objects from these declarations and uses the existing public invocation and
parameter-validation path. It supplies only synthetic endpoint/instance/token
metadata. Fake discovery returns this catalogue, not installed registrations;
an injected `httpx.MockTransport` implements submit/poll and produces a fixed
synthetic JSON result. Unexpected requests fail; no fallback HTTP transport,
listening socket, service, real account, installed application or model is used.
Non-Connect actions use recording/failing fake adapters; `notify.local` also
exercises its real built-in validation. A fake catalogue is a test declaration,
not proof of real provider availability or integration behavior.

`PackRuntime.load` cannot load unsigned workflows. Check therefore generates
distinct ephemeral development publisher, grant and entitlement authorities in
memory, temporarily envelopes the exact manifest candidate, and uses the real
`load_pack`, `verify_grant`, entitlement test seam, `AutomateHost` and
`PackRuntime.load`. Public test keyring documents and signed synthetic
entitlements/grants may exist in an isolated temporary directory; private keys
never do. The clock is fixed at `2026-06-01T00:00:00Z`, and all test claims use
`2026-01-01T00:00:00Z` for issuance/not-before and `2027-01-01T00:00:00Z` for
expiry. The synthetic subject is `pack-kit-check`. Generated signing material,
store IDs and temporary paths are excluded from build bytes and success output.

This temporary development envelope is distinct from publisher signing: no
candidate is signed with the user-supplied publisher seed until check passes.
The final publisher envelope is checked again with `load_pack` and the supplied
public key. Its grant must later come from an independent authorized issuer;
the kit does not create, accept or install real grants. Existing subject,
pack-ID and expiry verification stay in the runtime, with no version-binding or
anti-downgrade claim added here.

Check creates fresh stores per scenario and verifies real state, overlays,
outbox payloads/statuses and recorded adapter calls:

1. Approve from ready, observe settled invocation, submit `complete`, observe
   settled result action, then `finish`; verify completed stage and status.
2. Decline; verify no invocation/result action, and no later approval match.
3. Wrong/out-of-order decisions and fresh repeated approval; verify no extra
   action. Replay the exact approval operation; verify no duplicate delivery.
4. Inject invocation failure; observe failed outbox action and acting stage,
   submit `fail`, observe standard local notification, and no result action.
5. Inject result-action failure; observe reporting stage, submit `fail`, verify
   failed stage, no new invocation, and the standard failure notification.
6. Remove the invocation adapter, then separately the result adapter; verify
   pending outcomes, no fabricated completion and no automatic later decisions.
7. Verify a missing, mismatched-subject, wrong-pack, expired or wrong-authority
   grant and invalid entitlement reject load before record creation.

## Invariants and concurrency model

The same complete spec under this kit format/archetype always gives identical
build bytes, across repeated processes, input member ordering, TOML whitespace,
working-directory paths and hash seeds. It always embeds a workflow accepted
by the public `parse_workflow`. Signing with the same key ID, seed and valid
artifact also yields identical envelope bytes; check's randomness cannot leak
into the signed payload. A failed or skipped check cannot publish a publisher
signature. No command persists a private key.

Each command is single-process and sequential, with no worker pool, daemon,
global registry, shared store, check cache or persistent state. Scenario stores
are per invocation. Consequently no shared runtime state or check/sign race is
introduced: sign checks and signs the same immutable memory snapshot. Separate
CLI invocations may still target one output path; atomic no-replace publication
must make exactly one succeed while all others report output-exists. File
replacement after a read cannot change the held candidate. This is not a claim
that concurrent filesystem writes are impossible.

## Settling evidence and verification plan

Implementation is not settled until all of the following are observed:

- Golden normalized spec, workflow, unsigned artifact and development-signed
  envelope for the archetype; exact full-byte equality, not substring checks.
  Assert every definition, stage guard, effect order and action request.
- Determinism across independent runs, hash seeds, metadata/key order and paths;
  changed business input changes bytes; falsy values `0`, `""`, `false`, absent
  defaults and empty collections retain their distinct meanings.
- Full `new` → `build` → `check` → `sign` → `load_pack` → `PackRuntime` round trip,
  using real models/runtime, separate development authorities and fake apps.
  Verify actual adapter requests, result/status and stored lifecycle.
- At least one negative for every failure-table row and each input in the load
  rejection scenarios; invalid UTF-8, duplicates, mixed valid/invalid members,
  unknown vocabularies, missing keys, key mismatch, artifact tampering and final
  signature tampering included. Valid sibling inputs must pass.
- Boundary probes for byte/count/string limits at minimum, minimum-minus-one,
  maximum and maximum-plus-one as applicable, including empty/single/large
  valid workflows; correct rejection direction and acceptance direction.
  Exact key sizes, malformed base64, zero/false limits and invalid defaults
  cannot bypass validation. Check the encoded envelope limit too.
- Failure atomicity, existing-output/symlink preservation, input/output aliases,
  two competing output publishers and snapshot replacement between check and
  signing. Tests must exercise file behavior, not inspect source strings.
- A failing-check sign test proves the supplied publisher signer is never
  called, no publisher output is created and stale/forged reports cannot help.
  Capture stdout/stderr and temporary-file writes to prove key secrecy on both
  successful and failing paths. Prove all network requests use the injected
  transport and no application/runtime discovery is reached.
- Required mutants must be killed by behavior tests: (a) bypass check before
  publisher signing; (b) replace canonical ordering with insertion ordering;
  (c) accept an unknown action kind. Each mutant must actually change the owning
  kit behavior; prove its intended failure, restore the owner, and show the
  corresponding unmutated test passes. If the public parser independently
  catches an action mutant, keep that defense and also test the kit's boundary;
  never weaken shipped validation to manufacture a kill.
- Build a wheel with the unchanged wheel configuration, inspect its ZIP member
  list and prove no `tools/`, kit module, kit fixture or kit documentation is
  packaged. Compare the complete `connect_automate/` member bytes and names to a
  wheel built from the pinned base with the same build toolchain. Compare the
  entire `src/connect_automate/**` tree and dependency/config files to that base.
  Scope diff proves no foreign repository or application pin is edited.
- Run focused kit tests and applicable lint during implementation; required CI
  owns the broad suites. No code tests are required for this contract-only
  commit. No runtime, mutant, wheel or integration pass is claimed by this doc.

Durable evidence belongs in `~/Desktop/codex-evidence/connect-automate/pack-kit/`,
outside disposable worktrees, with directories mode `700` and files `600`.
Retain exact commands, heads, complete failing/passing outputs, wheel member
lists/hashes and mutant results. Public PR references use aliases and SHA-256,
with no private paths/data. Existing application repositories are not touched
even to generate evidence; this arc has no authorized foreign write surface.

## Assumptions, review sequence and gap audit

Acceptance includes the explicit operator-attestation lifecycle, literal result
action, metadata header and separate fake catalogue. More expressive business
conditions, automatic outcome handling and new triggers require a separate
accepted contract. If these limits cannot satisfy the intended slice, report
that before implementation; do not add a downstream interpreter or host loop.

Commit this file alone and mail oversight its exact commit hash. Stop there.
Only Juan's explicit acceptance relayed verbatim authorizes implementation;
an oversight opinion alone is not acceptance. A missing behavioral decision
requires a contract amendment and renewed acceptance before coding it.

After implementation: one PR, required CI green and oversight PR review PASS
on the exact published head, no unresolved review threads or outstanding
changes-requested review, clean working tree and local head equal remote head.
Only then merge with a merge commit and verify the merged tree matches the
reviewed head. After a push/PR/review request, record the exact head and defer
the next PR check for fifteen minutes unless a real exact-head notification or
operator message arrives. Never poll or use a waiting agent as the timer.

Implementation summary: acceptance is recorded above. The repository-only
`tools/pack_kit/` implements the commands and offline harness, with frozen
fixtures and focused behavioral tests. Durable qualification evidence is
retained outside the checkout and identified by alias/hash in the PR.
Cold diff audit: shipped source, dependency/configuration files and application
pins are unchanged. The command behavior and operator-attestation limits above
remain the accepted contract; this status update adds no behavior.
Gap audit: NOT DONE. Required CI, exact-head oversight PASS and merge remain
outstanding until recorded by the implementation PR.
