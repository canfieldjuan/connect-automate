# Offline malformed-consume refusal and recovery work order

Status: **PROPOSED; CONTRACT ONLY.** Juan authorized preparing this work order,
publishing it and sending the exact revision to oversight. Final acceptance and
merge of this document do not authorize implementation, test-key generation or
an offline run. Those require a subsequent explicit go for synthetic fixtures
and temporary test keys only. Native sign-in, Hello, Gmail and live activation
remain on hold.

## Contract and root cause

The accepted [malformed consume request contract](LEAD-OWNER-AUTHORITY.md#malformed-consume-requests)
owns the diagnostic schema, canonical bytes, HTTP recognition and pending-state
rules. PR 81 accepted revision `86aadeabb91edc3eb453242eedf8f1255f5fc8cc` as a
contract and merged it as `6c6dcca25c14872259db6f7b670632d9ea910ce3`.
This work order adopts that behavior without amending it or accepting the
licensing service's separate implementation work order.

The offline harness still marks `malformed-request-refusal` as `BLOCKED`.
Its issuer verifies a request before ledger access, but its common input-error
type also covers signature/trust failures. Its host receives body bytes without
HTTP status or content type. Thus a generic exception catch or a body-only
sample cannot demonstrate the accepted diagnostic/recovery contract. The gap is
in the harness's request-classification and response-exchange owners; it is not
a demonstrated production defect or permission to add a live client/server.

### Source and proven-work inventory

All source references and dependency pins in this inventory are at baseline
`34eefe704453c6d1e28779dccd4ee825c91d4385`. References describe inspected code,
not tests run during this document's preparation.

| Class | Existing owner, inputs and actual limit |
| --- | --- |
| CONFIRMED | `docs/contracts/LEAD-OWNER-AUTHORITY.md:435-458,489-558` specifies the consume budgets/outcomes and the separate malformed diagnostic. Its schema and canonical body remain the wire authority; do not hand-maintain another contract copy here. |
| CONFIRMED | `qualification/owner_authority/protocol.py:59-63,117-139,319-325,365-369,397-443` supplies frozen closed models, canonical UTF-8 JSON, duplicate rejection, the request parser/verifier and operation-bound refusal. Wire and verification failures currently share `ProtocolInputError`. |
| CONFIRMED | `qualification/owner_authority/licensing_fixture.py:192-244` validates before entering the issuer transaction and returns existing receipt/refusal bytes. Its own ledger is disposable; it is not the licensing service. |
| CONFIRMED | `qualification/owner_authority/host_fixture.py:26-43,193-249,255-263` owns pending binding and atomic receipt/admin/audit publication. Its callback returns body bytes. Snapshot exposes counts, operation ID and receipt digest, but not the full binding digest or a stored completion field. |
| CONFIRMED | `qualification/owner_authority/controller.py:22-29,82-101,112-142,152-213,228-235` pins the old contract revision, frozen synthetic clocks, separate spawned issuer/host processes and existing replay assertions. `cases.json:34` keeps this case blocked. |
| CONFIRMED | `tests/test_owner_harness_recovery.py:42-85,779-802,993-1015` provides `SyntheticWire`, fresh in-memory Ed25519 test keys, explicit fixture clocks, lost-response replay and corrupted-response pending preservation. Reuse these owners and fixtures. |
| CONFIRMED | `tests/test_owner_harness_protocol.py:22-61,64-90` checks derived schema drift, closed fields and native/falsy refusal. `protocol.py:88-113,163-173` derives run/result schemas. Their contract field currently admits a commit shape; the controller separately checks one value. |
| CONFIRMED | `pyproject.toml:6-21` requires Python >=3.13; `.github/workflows/ci.yml` uses Python 3.13 on Linux and Windows and already lists all four owner-harness test files at `:79-82`. Locked versions: Pydantic 2.13.5, cryptography 49.0.0, pytest 8.4.2, Ruff 0.16.8 and httpx 0.28.1. No dependency change is proposed. |
| RECORDED, NOT RERUN | Evidence alias `lead-owner-harness/h1c/h1c-round1-proof.json`, SHA-256 `9ac6fdd16c6c67e20733e0ac7715cef391f94c8c1478f78be3f4e1bfe0acae52`, records head `fcefd3c8cdcf55d6ec6ea6c07450d35088b59930`, 63 controller tests and 42 of 52 faults caught, with layered survivors individually described. The matching focused output alias `lead-owner-harness/h1c/round1-focused.txt` has SHA-256 `15c04167ec08dec34e5455d49199606638031956ac1b56b5905368b78c434bf8`. This is historical H1 proof, not malformed-diagnostic or native qualification. |
| RECORDED, NOT RERUN | Alias `owner-bootstrap-malformed-refusal/contract-check.txt`, SHA-256 `985cee40a22f34815b0a572fa1f8cb2e54305d0ba6f5fdee6fd3d8e1ac13a839`, records the earlier documentation-schema check and explicitly excludes endpoint/recovery implementation. |
| UNKNOWN | Real HTTP/TLS behavior, live issuer behavior, protected-host enrollment, native proof and installed-product qualification remain unproved. |

The dependency-lock SHA-256 is
`ef00a5b983e507a66f1dcca1687bf1f6523f031a44e640e5d9ae380832ecc5e3`.
Retain baseline source/fixture/schema hashes with the later parity packet.
Keep `SyntheticWire` and the controller's frozen January fixture clocks and
claim/manifest settings; do not use today's time or change the machine clock.
Keys remain temporary test material, never installed or retained in evidence.
There is no AI model, prompt, chat template or inference-runtime migration in
this lane. Existing native probe artifacts are neither inputs to execute nor
proof of this offline behavior.

### Intentional departures and parity first

These are the complete proposed departures from that inventory:

1. Distinguish malformed request wire at its existing parser owner; preserve
   signature, trust, binding and authenticated-clock failures as different paths.
2. Add the closed malformed-diagnostic model and a bounded synthetic response
   frame at the same protocol owner. Carry status/content type explicitly;
   retain the existing low-level body APIs for their current tests/callers.
3. Add metadata-aware fixture exchange entrypoints that reuse issuer verification
   and the host's existing publication/recovery owner. Add only the read-only
   host-owned state evidence needed to compare the complete pending binding.
   Do not add a completion column, another ledger or a second bootstrap routine.
4. Make this one blocked case runnable as offline conformance and add its exact
   assertion set/recipe to the controller. Other blocked/native cases stay so.
5. Advance new run/result provenance to this work order's final accepted commit.
   Enforce that exact pin in the closed models and derived schemas; remove the
   independently maintained controller equality rule and have readers use the
   one protocol owner. Preserve the remaining packet shape and evidence limits.
   An otherwise valid wrong profile keeps the fixed `CONTRACT_MISMATCH` refusal
   through a typed schema-origin error; do not re-parse or compare it downstream.
   Archived packets retain their original bytes, schema and harness revision;
   do not relabel them or silently admit an old profile into a new run.
6. Update only directly affected harness tests and offline README instructions.
   Existing Windows test entries already cover them. No workflow change is
   needed unless a separately justified split introduces a new test file.

After a separately authorized implementation go, capture baseline focused
results before edits, then carry the existing valid receipt, refusal,
lost-response and cached-no-dispatch controls through the new exchange adapter
before adding the malformed-response behavior. Preserve their binding, code,
transaction and dispatch-count semantics. Do not require random test keys or
receipt bytes to match across unrelated runs; compare the original stored
receipt within the same fixture run. A parity mismatch must be explained at the
changed owner before adding behavior. Record any newly necessary departure and
obtain acceptance before changing scope or product behavior.

## Ownership and required implementation surface

The current PR changes only this document and a link in
[the H1 work order](LEAD-OWNER-HARNESS.md#bounded-follow-up-work-orders).
The following are candidate changes for later authorized implementation:

| Owner / path | Required bounded change |
| --- | --- |
| `qualification/owner_authority/protocol.py` | Own request-wire classification, diagnostic model/canonical bytes, synthetic response frame/parser, exact accepted-profile pin and the single closed case inventory. |
| `qualification/owner_authority/licensing_fixture.py` | Add the disposable metadata-aware exchange boundary; use the parser's typed malformed signal before ledger access. Preserve existing transaction, signature and replay owners. |
| `qualification/owner_authority/host_fixture.py` | Admit response metadata at one owner and reuse existing pending/publication logic. Expose a bounded canonical pending-binding digest through its own read API, never cross-store SQL. |
| `qualification/owner_authority/controller.py`, `cases.json` | Add the fixed three-attempt recipe and actual state/call/receipt assertions for `malformed-request-refusal`; retain real child processes, finite deadlines and whole-selection admission. |
| `qualification/owner_authority/run.schema.json`, `result.schema.json` | Derive only the accepted-profile pin change from the model owner; retain closed offline-only/non-qualification semantics and all existing bounds. |
| `qualification/owner_authority/README.md` | Explain the new case, accepted work-order profile pin and unchanged offline commands/output-root/evidence rules. |
| `tests/test_owner_harness_protocol.py`, `test_owner_harness_wire.py`, `test_owner_harness_recovery.py`, `test_owner_harness_controller.py` | Add independent protocol, endpoint, recovery and controller proof; preserve existing controls and negative tests, adjusting only the intentionally changed profile pin/catalog. |

Keep one implementation PR around the H1 work order's existing line budget. If
the complete proof exceeds it, split protocol/fixture work before controller
adoption, with exact-head CI/connector/oversight gates for each. Do not activate
the runnable catalog entry until all its requirements are implemented and proved.
The licensing/release owner still owns its separate production implementation;
no other repository, installed host or authority store is changed here.

## Required mechanisms and behavior

### Parser-origin classification and diagnostic

Reuse the existing strict JSON/closed `ConsumeRequest` parser and canonical-form
rules. Give structural wire rejection one dedicated typed signal at that owner,
remaining compatible with callers that catch the existing input-error family.
Preserve that signal through the checker's exception handling. Do not classify
all `ProtocolInputError`, verification failures or worker exceptions as malformed.
The request byte cap and syntax stage precede request-derived authority use;
signature, claim/binding checks and authenticated clock classification remain
on their verification path before any ledger access.

The metadata-aware issuer boundary catches only that typed wire rejection and
returns the fixed diagnostic defined by the linked canonical contract. Its
closed model must express both required literal fields and forbid extras; it
must not reuse the operation-bound `Refusal` with a fabricated/null operation ID
or completion. Serialize the one canonical model at its protocol owner. Do not
extract a usable ID from rejected input, echo parser details, access the claim
or operation ledger, or create an operation-linked audit entry on that branch.
Structurally valid invalid signatures retain their existing verification refusal
or exception and cannot produce this diagnostic or authenticated clock skew.

### Bounded synthetic response exchange

A body-only callback cannot prove status/media recognition. Use one closed,
immutable fixture response model at `protocol.py`, with exactly these required
fields and no extras:

| Field | Fixture-only constraint |
| --- | --- |
| `status` | Strict integer, minimum 100, maximum 599; booleans and coercions are invalid. |
| `content_type` | Strict string of at most 256 characters, or null to represent an absent header. Empty/absent values never default to JSON. |
| `body_base64url` | Strict string of at most 5462 characters; closed base64url alphabet in the schema, then the existing real decoder/canonical round trip, admitting at most the parent's 4096 decoded response bytes. Empty bytes may represent an invalid response. |

This is private canonical-JSON IPC between explicitly spawned fixture workers,
not a new public licensing protocol or an HTTP server. Cap the enclosing frame
at 8192 bytes before JSON parsing; its maximal schema shape is 7050 canonical
bytes, including maximally escaped content-type characters. The wrapper cap
does not enlarge the consume body cap. Use one owner for these bounds and all
readers; no parallel regex, handwritten second schema or controller re-parser.
Reuse closed models, derived schema constraints, duplicate-member rejection,
canonical JSON and the existing base64 decoder. A serializer/parser failure is
an unverifiable exchange, never a successful diagnostic. Over-cap or malformed
frames refuse as a whole without decoding/publishing partial content.

The new host exchange path recognizes the diagnostic only with the exact status,
media type and original canonical body specified by the accepted contract.
Do not normalize a noncanonical body into acceptance or infer HTTP metadata
from its contents. Valid ordinary fixture responses retain the parent outcome
mapping and pass through the existing receipt/refusal verification owner.
Legacy body callbacks remain an explicit separate fixture API, never an
automatic metadata fallback for this new path. There is no live networking,
redirect, decompression or TLS experiment; production transport qualification
and timeout claims do not follow from these synthetic fields.

### Durable pending state and explicit recovery

Exercise the following recipe through separate real issuer/host processes:

1. Prepare one original pending binding with the existing synthetic observation
   and temporary installation key. The issuer commits its consumption/receipt;
   the first reply is deliberately lost. The host reports unavailability and
   keeps the original pending state without a local receipt/admin/audit triplet.
2. On a separately invoked recovery attempt for that binding, the test transport
   removes a required wire field before issuer admission. The issuer returns
   the fixed malformed diagnostic without ledger entry. The host preserves the
   same binding and unresolved completion (`UNKNOWN`), with no automatic retry,
   replacement operation, claim reuse or local authority publication.
3. A later explicit attempt carries a fresh attempt ID/time/signature for the
   original binding and a fresh synthetic observation. The issuer recovers its
   original stored signed receipt. The host publishes exactly one local triplet
   through its existing transaction. A subsequent cached invocation dispatches
   nothing and cannot change either store.

Use each store owner's read API to prove the state. Extend the host's read-only
snapshot with the digest of the actual complete canonical pending binding,
not an expected binding copied from the controller. Prove `UNKNOWN` as the
unresolved owner state: pending binding retained, no verified local commit and
no server refusal treated as proof of non-consumption. Label it as derived
pending state; the baseline has no persisted completion column. Counts or an
unchanged operation ID alone do not prove the complete binding is unchanged.
Do not expose salt, private keys or synthetic principal records in evidence.

Record three explicit exchange attempts, no hidden attempt, one issuer
consumption and the identical original/recovered/local receipt digest. Measure
the malformed branch's ledger-entry count separately from later test snapshot
inspection; state equality alone is not evidence of zero ledger reads. Reuse
existing publication fault/barrier machinery and single-writer ownership; add
no cross-store transaction. Any relevant race uses both winner orders and the
existing repetition policy, never sleeps or a process-state proxy.

### Controller, provenance and evidence

Only `malformed-request-refusal` moves from `BLOCKED` to `OFFLINE_CONFORMANCE`.
Its final code is `COMMITTED` after the explicit verified recovery; intermediate
unavailability is asserted, not overwritten or counted as an earlier success.
Its fixed assertion inventory must cover the diagnostic, zero malformed-branch
ledger access, pending/complete-binding preservation, no automatic retry,
same receipt, one local triplet, cached no-dispatch and issuer effects.
Independent signature-not-malformed and response-boundary cases also belong
in the focused fixture/protocol tests, not successful stand-ins for this recipe.

The later accepted work-order commit is the one new profile pin, not a hash of
the implementation containing itself. Put its exact value in the protocol's
closed run/result models and derived JSON Schemas, so direct model admission
also rejects another contract. The controller must consume that one owner.
Classify the model's structured profile-validation failure at the parser owner
to retain the existing CLI refusal vocabulary; unrelated or mixed-invalid
packet failures remain `INVALID_PACKET`.
Preserve `OFFLINE_CONFORMANCE` and literal boolean `qualification_pass: false`,
with no native result or aggregate PASS. Keep other native/blocked entries,
their rejection before effects, existing path/resource controls, child exit
checks, assertion truth checks and case/platform deadlines unchanged.

Retain raw sanitized proof, fixture/source/lock digests, before/after results,
selected fault receipts and a SHA-256 manifest outside worktrees under
`~/Desktop/codex-evidence/connect-automate/offline-malformed-recovery/` with
private directories/files. Public references use aliases and digests. Retain no
temporary private key, credentials, real mail/account/file contents or raw
exception input. No current run packet, test key or implementation is created
by this document.

## Verification plan for later authorized implementation

| Gate | Required falsifiable evidence |
| --- | --- |
| Baseline and parity | Run the existing affected owner-harness files at the pinned baseline before edits. Reuse existing fixtures/controls through the new exchange seam, preserving all old semantics except the listed profile/catalog changes. Record actual runtime and lock; do not cite historical passes as this run. |
| Fail first | Declare the expected missing diagnostic/parser/exchange behavior before its minimal regression. Keep actual failures, explain unexpected results and then implement at the named owner. Existing pending-preservation controls may already pass; do not manufacture a failure. |
| Malformed request boundary | Truncated/invalid UTF-8/duplicate JSON, missing/extra/incorrect fields, valid-looking operation ID with missing attempt ID, zero/empty/false/wrong types and request-cap edges. Instrument the ledger entrypoint to fail if called. The exact fixed response is independent of all rejected fields. |
| Verification second side | Otherwise valid signed control consumes or recovers normally. Wrong installation/claim signature, trust/purpose or binding must use its existing refusal/exception, never malformed or authenticated clock skew; prove no ledger access before verification succeeds. |
| Response boundary | Correct fixed response plus wrong status/media, absent/empty media, extra/missing/duplicate/wrong literal fields, body whitespace/order changes, partial JSON, arbitrary bytes and over-cap frames/bodies. Assert the actual classification and no publication, not only the shared unavailability result. |
| Bounds and schema | Prove direct model/schema closure, exact profile const, frame/status/encoded/decoded boundaries, maximal valid shapes and cap-before-parser ordering. Probe falsy/default defeat and mixed valid/invalid fields. Keep derived schemas in sync and do not relax existing offline/native guards. |
| Recovery and durability | The real-process three-attempt recipe above; complete pending binding, exact call/ledger counts and original receipt identity. Reuse crash/write-fault and concurrent recovery guards to prove no partial local publication or replacement owner. Preserve refusals, failures, cancellations and timeouts. |
| Controller and denial | Real offline CLI result validated by the derived schema and artifact hashes; fixed assertion inventory and actual code decide the case result. Selecting any native or other blocked case still refuses the entire selection before fixture effects. Forbidden-call sentinels cover network, installed trust, accounts, native/platform and product operations. |
| Regression and independent faults | Focused new regressions, adjacent affected owner files, Ruff and whitespace. Remove each new status/media/canonical/body-cap/no-ledger/pending/no-retry guard in an isolated fresh process and require its intended independent test to fail; record layered/equivalent cases honestly. CI owns duplicate broad suites. Windows already runs the four files; any new file must be explicitly listed from its first implementation push. |

No tests or faults in this table are run during contract preparation. Existing
Linux/Windows CI is portable regression evidence and does not qualify native
accounts, disk isolation, passwordless/Hello or a licensing deployment.

## Explicit non-scope, risks and rollback

Do not change accepted authority semantics, entitlement v1, production host,
source/custody/runtime behavior or their tests, public APIs, installed trust,
dependency lock, real schemas/stores, signing purposes or other repositories.
The only schema-artifact change proposed is the harness's exact profile pin.
No real HTTP endpoint/client, licensing issuance/activation, native helper,
preflight, account/VM/service/boot/disk operation, Gmail/OAuth, provider
registration, body read, dispatch, lead creation or shared inference work.
Manifest renewal, device replacement, disk-isolation execution and issue 73's
other follow-ups, issue 77 hardening and issue 84's product decision remain
outside this slice. Existing native sign-in, Hello, Gmail and live activation
holds remain in force.

The main risks are overbroad malformed classification, fake HTTP evidence,
misstated pending completion, changed legacy fixture behavior and falsely
labelling an offline packet as qualification. The owner/classification,
bounded metadata, real-store/process and schema-first checks above address
those risks without claiming product enforcement. Rollback disables only this
later synthetic case/adapter, preserving existing stores and all durable proof.
No reset, broad cleanup or deletion of retained evidence is authorized.

## Implementation summary, cold diff audit and gap audit

Current change: this work-order document and one link-only appendix in the H1
work order. Source, tests, schema artifacts, fixtures, catalog, workflows,
dependencies and the accepted authority contract are unchanged. This is not
licensing implementation or native qualification.

For this documentation PR, verify the exact two-document diff, preserved parent
text, links/anchors, source line references, inventory/retained-evidence hashes,
frame-size arithmetic, whitespace and committed bytes. Inspect the cold diff
against every proposed departure and non-scope boundary. Run no application
tests, fixtures, key generation or probes for this documentation-only change.

**DONE for work-order preparation only when those documentation checks and
publication are recorded. NOT DONE for independent review, final acceptance,
merge, implementation, offline proof, native qualification or activation.**

Send the published exact commit to oversight. Merge requires exact-head green
CI, clean connector/reconciled review, independent oversight PASS and Juan's
final acceptance of that exact contract revision. Then stop for a separate
explicit offline synthetic-fixture/temporary-test-key implementation go. An
implementation go grants no native or live authority; its later PR still needs
the standing exact-head CI/review/merge gates.
