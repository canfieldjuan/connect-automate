# R3 receiver composition: first bounded work order

Status: **R3.1 contract ACCEPTED; contract-only merge and executable proof pending.**

Juan asked, “Is R3 next? If so let’s start”, starting contract preparation. The
[parent sequence](LEAD-RECEIVER-CUSTODY.md#bounded-implementation-sequence-and-verification)
requires a committed contract and explicit acceptance before executable work.
No executable work is included in this contract PR.

## Acceptance record

On 2026-10-27, oversight mailbox `15f5c0a6` relayed Juan's decision verbatim:
**“accept R3.1”**. The relay explicitly binds that decision to contract revision
`75d093da630d955d86bedb03cc473c2d1ed4909e`, reviewed with oversight CONTRACT PASS
`537b619d` / [review 5671881148](https://github.com/canfieldjuan/connect-automate/pull/56#pullrequestreview-5671881148).
The operator's relayed acceptance supplies authority; the reviewer's PASS alone
does not. This acceptance-only record changes no design rule.

Merge PR #56 as contract-only after its exact-head gates. Implement R3.1 in a
separate PR on the merged contract: unchanged legacy-parity baseline first, then
the declared fail-first managed-entry probe. Enforce the no-action restriction in
code. Receiver activation, reference-only resume and adoption remain outside this
acceptance. No executable edits precede this acceptance record.

R2 library qualification merged in [PR #55](https://github.com/canfieldjuan/connect-automate/pull/55).
This proposal starts with **R3.1: fenced raw submission into the verified runtime**.
It is a prerequisite to receiver operations, not the complete R3 receiver. Later
reference-only resume, result composition, durable transport mapping and protected
machine/service wiring retain separate work orders. No receiver capability is
advertised or activated by R3.1.

## Contract

### Root cause and source inventory

Inventory pin: `canfieldjuan/connect-automate`
`2b893e3b320638a7fbdcc3de26b0b1ca3e66dc9b`, tree
`c9878ce1170d8655879d616966d2bc5b15438a73`.
Paths below are repository relative and line references describe that pin.

| Evidence | Finding |
| --- | --- |
| **CONFIRMED:** `src/connect_automate/lead_intake/handoff.py:55-104` | The current composition checks scope, calls `SourceAdmission.admit_source(raw)`, validates the returned receipt and constructs the workflow event. It has no managed custody request. |
| **CONFIRMED:** `src/connect_automate/automate/runtime.py:130-193,257-263,281-375` | Runtime load verifies pack/grant/license and registers source bindings. Submission uses the legacy handoff, then the existing workflow admission and persisted-result path. |
| **CONFIRMED:** `src/connect_automate/lead_intake/source_store.py:843-852,1068-1105` | Legacy admission refuses reserved event keys. Managed admission binds the canonical artifact, intent, capture, operation and generation under the source writer. A wrapper lookup followed by legacy submission cannot integrate these owners. |
| **CONFIRMED:** `src/connect_automate/lead_intake/custody_store.py:50-70,117-165` and `lead_intake/admission.py:153-170,196-245` under `src/connect_automate/` | The concrete facade already supplies an expected incarnation and bounded configuration, then delegates raw admission and retained-custody revalidation to the source transaction. The latter is not complete reference-only workflow resume. |
| **CONFIRMED:** `src/connect_automate/automate/runtime.py:324-375,377-418` | Workflow admission, persisted result validation, dispatch and historical lookup already have an owner. Custody and workflow commits remain separate. |
| **CONFIRMED:** `src/connect_automate/lead_intake/custody_protocol.py:50-149` | Existing closed values distinguish route, event, capture, upload and resume. These references are not machine authentication. |
| **CONFIRMED:** `src/connect_automate/lead_intake/content.py:75-98` and `_host_policy.py:1-6,97-116` in the same directory | Content reading can enforce expiry and mutate custody. Policy evaluation consumes supplied facts and explicitly does not authenticate them. Neither is a substitute for a protected receiver. |
| **INFERRED:** these owners need a bounded composition change | R3.1 should select fenced admission inside the existing submission path and reuse the same downstream workflow logic. It should not add a second engine or submit an observed receipt as authority. |
| **UNKNOWN / later gate:** protected machine authorization and receiver transport recovery | R3.1 cannot establish live machine identity, current route permission, durable transport-job outcomes or production readiness. |

There is no demonstrated production defect to repair here. The missing capability
is joining the qualified managed source owner to the verified runtime. Existing
legacy behavior intentionally refuses managed events; that refusal must survive.

### Proven-work inventory and permitted departures

Use these existing synthetic fixtures and harnesses, not a new recovery simulator:

- `tests/test_lead_host_composition.py:44-85`: signed pack, separate grant signer,
  licensed test host, real source/workflow stores and fixed source clock.
- `tests/test_lead_receipt_vocabulary.py:48-52`: the existing no-action workflow.
- `tests/test_lead_source_auth.py:22-56`: frozen synthetic source vectors,
  `NOW`, independent signing preimage and canonical encoding. Keep fixtures and
  signing inputs unchanged.
- `tests/test_lead_custody_store.py` and
  `tests/test_lead_custody_races.py:272-313,477-516`: real custody owners, explicit
  retained incarnation, managed request packets and spawned-process checkpoints.
- `tests/test_lead_joined_recovery.py:43-85,323-360` and the existing joined
  concurrency/lifecycle files: reopen source and workflow owners without
  initialization; preserve separate receipt identity and commit boundaries.

The runtime uses the repository Python/dependency lock and existing SQLite owners.
There is no inference runtime, model, prompt, chat template or external provider
in this lane. Native Linux and Windows qualification remain required.

Historical evidence inspected for this proposal, **not rerun here**:

| Durable alias | Manifest SHA-256 | Scope |
| --- | --- | --- |
| `custody-r2-qualification` | `55539579a48e826635cc37004d463b4bcb656ad202a831b99d2676c4b6d1f2a1` | Final combined run recorded `3164 passed in 440.20s (0:07:20)`; input/commit identity is recorded separately because the command started before the executable commit. |
| `custody-r2-qualification/merge-205a340` | `1ce8587b434dc8218b9792c46be9cd790ad2992fa00cadbe4e7fb026b28ee7a0` | Exact-head Linux/Windows success, oversight PASS, connector without findings and merge-tree equality for the inventory pin. |

This proposal's `custody-r3-composition-contract/source-inventory.json`, SHA-256
`f8860be653bafe4282e9bc3a24b7edc062d7fa8dd7d7a61d4f71947531df9f3c`,
records the source, harness and dependency bytes inspected.

Only these departures are proposed:

1. The new private managed entry selects `SourceCustodyStore.admit_bound` in place
   of legacy `SourceAdmission.admit_source`. It still requires the exact raw
   signed envelope on every call. The legacy entry and its fixtures stay unchanged.
2. Trusted host composition additionally pins the R1 route, enrolled-machine
   reference and the R2 facade with its previously retained incarnation. These
   values restrict dispatch; they do not authenticate a machine.
3. Joined tests prepare and bind a managed request through R2 before submission.
   They then exercise the real runtime with the same no-action pack, source
   vectors, clocks and separate database owners. Existing legacy cases stay in CI.
4. A common private workflow completion path may be extracted from current
   `submit_source` so legacy and managed entry paths share its exact behavior.
   Result schemas, projection semantics, event identities and action behavior do
   not change. Prove legacy parity before using that path for managed input.

An additional departure requires a contract revision before implementation.

### Required change surface and ownership

The lead-intake session owns this bounded composition work. Prior pack-kit
ownership of result schemas/projection and workflow lookup is preserved. This
proposal permits only behavior-preserving movement/calls of that existing runtime
completion block; it does not authorize redesigning those owners.

| File / owner | Proposed change after acceptance |
| --- | --- |
| `src/connect_automate/lead_intake/handoff.py` | Keep one receipt-to-event validation owner. Add the concrete managed admission path or share its validation with the existing legacy path without weakening checks. No SQL. |
| New private `src/connect_automate/lead_intake/custody_handoff.py` | Immutable trusted-host composition over a verified runtime, concrete custody facade, pinned route and machine reference. Accept raw bytes plus a validated upload request; no copied receipt or arbitrary callback authorizes submission. No SQL or durable storage. |
| `src/connect_automate/automate/runtime.py` | Add the private managed entry and share existing workflow completion. Keep public load/submit/lookup signatures and current behavior unchanged. No caller-supplied admission callback or unchecked duck-typed owner. |
| New `tests/test_lead_custody_composition.py` | New managed-entry, route, receipt, replay, privacy and no-action boundary tests using existing fixtures. |
| New `tests/test_lead_custody_composition_recovery.py` | Extend the existing spawned-process proof pattern to the joined managed path; reuse checkpoints, native completion handling and state assertions. No wholesale rewrite of R2 or legacy tests. |
| `.github/workflows/ci.yml` | Select the new files for Windows from the first executable push. Linux already selects all tests. Keep dependency pins and other jobs unchanged. |
| This contract | Record acceptance before code, then implementation evidence and gap audit. |

If the concrete implementation needs a source-store/content/facade API change,
new schema or a reserved result/lookup edit, revise this allowlist and reconcile
that owner first. Do not reach through the facade to query its tables or invent
a deployment accessor by reading its private database from the adapter.

### Required behavior and invariants

**Construction and entry.** Construct only from an already verified `PackRuntime`
and the concrete R2 facade. Copy/revalidate all supplied closed values; freeze
the binding. Valid copied request values remain valid after revalidation; their
model type is never authority. Pin the full route, not merely a provider name: provider app,
instance and app version, capability and version, verified pack ID/version and
binding. Compare pack/binding against the actual runtime. Pin host, organization,
namespace and enrolled-machine reference. Request scope and route digest must
match those configured values. No provider discovery, latest-version fallback,
per-request owner replacement or automatic store-incarnation enrollment.

The new entry is library-only under the same trusted local OS-user boundary as
R2. A request's `proof_reference`, machine UUID or eligibility result never grants
authority. Keep it private, absent from public exports, provider capability lists,
CLI, HTTP routes and generic action dispatch. Recheck the runtime license and
binding before source-owner access and before workflow admission. Configuration
drift, wrong route, wrong deployment and unsupported request kinds fail closed.

**No-action restriction.** Refuse a managed binding to any pack containing an
action before source admission. The legacy runtime continues to support its
existing action behavior. This restriction is enforced by code, not just by using
a no-action fixture. Do not introduce a second action-dispatch path.

**Fenced submission.** Only an upload request for an already registered and bound
intent is accepted. The entry must not register, bind, settle or recapture on a
caller's behalf. Call the concrete `admit_bound` owner with the exact bytes. That
owner remains the authority for canonical capture, operation identity, incarnation,
generation, reservation, clock, lifecycle and current source authentication under
the writer. A preliminary metadata check is never the fence. Never fall back to
legacy admission, use a cached receipt, substitute a fresh event ID, or convert a
closed upload into retained-custody resume.

**One workflow completion path.** Validate the source owner's returned receipt
against the request/raw source using the existing receipt-to-event checks. Only
this fresh in-call result proceeds to the runtime's common workflow path. It
must preserve license enforcement, event-time validation, the engine's transaction,
idempotency, persisted projection validation and fixed uncertainty error. Do not
add a public or adapter-visible “submit receipt/prepared event” API. Historical
workflow lookup remains read-only and never serves as submission authority.

**Separate commits and replay.** No transaction spans source and workflow stores;
no source writer encloses a workflow call. A source commit followed by workflow
failure remains custody without proven workflow acceptance. The same still-eligible
open upload may retry with the same request and raw bytes, reauthenticate through
R2 and reuse the workflow owner's event identity. After closure or expiry, do not
force this upload path to recover: retain the source fact and the workflow lookup
result for the separately gated resume work. A failure/timeout is never proof of
absence. If source or workflow commit is uncertain, report the existing bounded
unknown outcome and do not retry effects inside the call.

**Lifecycle linearization.** Source authorization/fencing linearizes at its
existing source transaction. Closure, purge or revocation that wins before that
decision refuses admission; a later lifecycle mutation does not retroactively
erase a committed receipt. Workflow submission may complete from the freshly
validated in-call receipt after the source writer releases. Do not claim atomic
authorization across both databases or promise cancellation of already-admitted
metadata. No raw bytes enter workflow records, errors, logs or a new retry cache.

**Result meaning.** Return the existing validated source-handoff result through
its owner; do not produce an R1 receiver result or Connect output in this slice.
Preserve accepted/no-match, source-applied/workflow-applied and historical action
projection meanings. No extraction, canonical lead, review approval, customer or
external delivery is implied. A source marked body-unavailable can still carry
the signed metadata envelope; preserve that distinction in the proof.

### Explicit non-scope

No changes to source/auth/custody/content schemas or migrations, R1 value models,
result schemas/projection helpers, workflow-store APIs, public exports or public
runtime signatures. No reference-only resume, status/settle result synthesis,
transport-operation journal/cache, byte quota policy, capability registration,
socket/service, machine enrollment, secret handling, employee endpoint, Watcher,
EOM, inference, destinations, app/dependency pins, installer or adoption.

The existing raw-content and lifecycle owners remain unchanged. This slice adds
no automatic reread, recapture, retry scheduler, queue, database or retention rule.

### Assumptions, blockers and rollback

- The principal regression risk is extracting the shared runtime completion path:
  legacy exception classification, result validation or action dispatch could
  change accidentally. Preserve that block's behavior and its existing tests;
  apply the new no-action restriction only to the managed entry.
- **Gate:** independent contract review and Juan's exact-revision acceptance
  are recorded above. The contract-only PR must pass its current-head gates and
  merge before executable work begins in a separate PR.
- Before implementation, re-pin current main and prove relevant existing tests
  unchanged. If main changes reserved runtime/result owners, reconcile their
  current contracts and diff before extracting the common path.
- Production machine authentication, durable operation mapping, finite ingress
  byte/concurrency budgets and native installation remain UNKNOWN/unqualified.
  They block a real receiver, not this explicitly synthetic library proof.
- Rollback disables/removes the unused private composition entry. Preserve R2
  stores and fences; do not downgrade, delete metadata or resurrect closed work.
  A failed composition attempt may have committed custody: reconciliation must
  use the existing owners, not a guessed cleanup or database rollback.

### Verification plan

Before coding, run the unchanged applicable host-composition/runtime-result and
R2/joined parity files from the pinned inventory. Preserve their inputs and raw
outputs. Declare the new managed-entry fail-first probe and expected failure
before running it. A missing seam is the expected initial failure, not evidence
that existing production behavior is defective.

| Proof | Required assertions |
| --- | --- |
| Legacy parity | Existing legacy submission, action-result, lookup, R1/R2 and joined fixtures pass unchanged. Receipt/projection bytes and error classes remain equivalent where deterministic. |
| Positive managed path | Available body, truncated-body metadata and body-unavailable envelope; matching and no-match no-action packs; exact source receipt and workflow identity, correct applied flags. |
| Scope and authority boundaries | Wrong host/organization/namespace/machine, pack ID/version/binding/provider route, malformed constructed requests, copied receipts offered as authority, invalid signature, wrong incarnation, missing intent, unbound capture and wrong operation kind refuse at the correct owner. Valid copied requests still work after full validation/authentication. No new workflow write on source refusal. |
| No-action boundary | A valid no-action pack succeeds; an action-bearing pack is refused before custody or workflow mutation. Legacy action tests still pass. |
| Replay and conflict | Exact open replay reauthenticates and creates no duplicate source/workflow record. Reused IDs with different capture/raw bytes conflict. Closed/expired/revoked/purged/retired work never falls back to legacy or resume. |
| Guard isolation | Construct each negative so only its intended check catches it; include valid neighbors, mixed fields, zero/empty/False and boundary values where the new code handles them. Counterfactual probes must distinguish direct detection from a later backstop. |
| Commit gap and lost reply | Inject before/after source commit, before/after workflow commit and before response. Reopen owners in fresh processes; compare durable receipts and replay the same eligible request without manufacturing success. No early receipt/result publication in lost-reply traces. |
| Concurrency and time | Real process writer contention in both admission/closure orders; wait then revoke/expire, final-sample clock/deadline checks, concurrent identical/conflicting upload and workflow replay. Source writer is released before workflow admission. |
| Error/privacy boundary | Source/SQL/validation errors with synthetic raw markers leave fixed public errors and no raw content in workflow rows, logs, exception cause/context or result representations. Uncertain commit never becomes definite failure/absence. |

Use the existing native process/harness lifecycle patterns and explicit completion
receipts; elapsed time or a clean child exit is not correctness. Capture test input
hashes and exact commands. Run focused regressions and adjacent files first, then
the high-risk joined/source/runtime parity lane before publication because this
change touches the shared admission path. Ruff and `git diff --check` are required.
Native Windows and Linux CI, exact-head oversight and connector reconciliation
remain merge gates. Record durable evidence outside the worktree.

## Implementation summary

Contract only: this contract, the parent continuation pointer and the R2 completion
status record change. The later acceptance record changes status and records the
operator's decision, without altering the reviewed design. No executable, test,
dependency, workflow or schema edits.
Code tests are not rerun for this documentation-only proposal. Source inventory,
reference checks and the cold diff audit validate its claims; prior test results
remain explicitly historical evidence.

## Cold diff audit

The proposal must be limited to this new contract, the parent R3 pointer/current
status, and the canonical R2 completion record. Check every source citation at the
inventory pin, verify local document links, and prove executable inputs unchanged.
Record the actual checks and proposal commit in the durable contract packet.

## Gap audit

**NOT DONE — accepted R3.1 executable work has not started.** Contract review and
operator acceptance are recorded; current-head contract-only merge gates and
executable proofs remain pending. Completing R3.1 will not
complete R3 or qualify a receiver. The next contracts must cover reference-only
resume through current custody authority, evidence-based status/settlement,
transport-operation identity/storage/retention/recovery and result bounds before
any protected provider wiring. Those must reuse the existing owners and transport;
none is delegated to an in-memory cache or an assumed machine-authentication layer.
