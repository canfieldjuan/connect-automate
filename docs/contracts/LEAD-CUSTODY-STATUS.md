# R3.5: read-only custody status and result projection

Status: **ACCEPTED at the reviewed revision below; acceptance-delta review and contract merge pending. No executable work in this PR.**

This work order follows [lookup-first recovery](LEAD-CUSTODY-RECOVERY.md).

## Acceptance record

Juan's direct message in the oversight conversation at
`2026-10-30T03:27:19.036Z` was:

> I accept 65 at 4fc8545

It accepts PR #65 at exact reviewed head
`4fc8545f57b907e028134f9c3f700e65f8e51e51`.
[Oversight's contract review](https://github.com/canfieldjuan/connect-automate/pull/65#issuecomment-6512594850)
passed that revision. Linux `test`, native `windows-placement` and the completed
connector review were green/clean there, with no unresolved threads.

Oversight relayed the decision verbatim in mailbox `ecb76c1f`. The direct user
message was independently verified; the peer relay itself grants no authority.
Evidence alias `custody-status-contract/acceptance-20261030T033045Z/operator-acceptance.json`,
SHA-256 `73e712c888b8703fd520995dc2e01a6bbfdfe15adb6181458d1c869be9166a86`.

The accepted body beginning at **Baseline and root cause** remains byte-identical
to the reviewed revision. Historical proposal/pending language below records
that revision's state; this acceptance record supplies the current authority.
The acceptance-only commit needs its own delta review and exact-head CI/connector
gates before a guarded merge. Executable work follows after contract merge.

Delivery plan adopts oversight's non-blocking packaging recommendation: use two
stacked implementation PRs, first the precise vocabulary plus source observation,
then status composition, targeting under about 1,000 lines each including tests.
This splits delivery without changing the accepted owners, behavior or proof
requirements; the reviewed body's references to separate commits remain intact.
Track explicit expired-unfenced vocabulary before transport exposure in
[issue #66](https://github.com/canfieldjuan/connect-automate/issues/66). It does
not change this slice's accepted conservative `unknown` result.

## Baseline and root cause

Repository: `canfieldjuan/connect-automate`. All source citations below are
repository-relative at merged main `be63503723f1fa397aae98a7c1af1fa2d0faea18`,
tree `82a7f63f6ee5709c8b6b1474c4ca5c5bec1a1144`. This is the merged tree of
PR #64, reviewed at `6d8ad201b52c51a95cf6bcc128c3f0845fcfe388`.
Paths abbreviated `LI/` mean `src/connect_automate/lead_intake/`; `RT` means
`src/connect_automate/automate/runtime.py`. Documents describe intent; the
following inventory was checked against source, not inferred from completion prose.

| Classification and finding | Source at the baseline |
| --- | --- |
| **CONFIRMED:** the private composition validates canonical requests and runtime/route/machine/store pins. It submits, resumes and recovers; it does not compose a custody status result. | `LI/custody_handoff.py:50-128,159-248`. |
| **CONFIRMED:** source observation is query-only and denies envelope access. It returns source facts, not receiver results; it omits reservation expiry, observation time and retirement disposition. | `LI/custody_store.py:73-93`; `LI/source_store.py:198-225,583-615,802-823`. |
| **CONFIRMED:** the reservation deadline is already persisted, checked and then omitted from the observation. No new table is required to expose it. | `LI/source_store.py:687-736,802-812,936-997`. |
| **CONFIRMED:** metadata validation checks content-row presence, not envelope integrity. Missing content for a retained row is corruption; retirement cleanup can legitimately remove receipts while preserving handoff history. | `LI/source_store.py:623-667,780-812`; `tests/test_lead_custody_store.py:415-443`. |
| **CONFIRMED:** source retirement and clock-floor history already have owners. Current content reads use a writer and may purge expired content; they cannot implement a read-only status operation. | `LI/source_store.py:1168-1258`; `LI/content.py:74-121,179-216`. |
| **CONFIRMED:** runtime lookup returns closed historical metadata without source admission or dispatch. Lookup and submission are distinct models. | `RT:265-279,431-472`; `LI/results.py:28-73`. |
| **CONFIRMED:** existing custody results require a complete receipt for custodied state, distinguish unresolved results, and enforce legal combinations and a byte limit. | `LI/custody_protocol.py:161-270`. |
| **CONFIRMED:** result `observed_at` has whole-second precision, while receipt `accepted_at` requires microseconds and must not exceed it. Immediate same-second status is not generally representable. | `LI/custody_protocol.py:175,241-258`; `LI/source.py:40-47`; `LI/receipts.py:15-34`; pure probe below. |
| **INFERRED:** a private status operation can compose these owners without new storage or transport, with a bounded source observation extension and explicit result-version amendment. | Proposed contract and proof obligations below; no status implementation exists at this pin. |
| **UNKNOWN:** protected machine authentication, durable transport-result replay and installed receiver behavior. | Outside this private-library proof; configured machine references are not authentication (`LI/custody_handoff.py:1-5`, `LI/custody_store.py:1-5`). |

The missing behavior originates at the source fact projection and the custody
result vocabulary, not at a UI or a transport cache. Blame traces the timestamp
field/comparison to `f540b41a` and the source projection to `49235afb`, before
lookup-first recovery. This arc owns those earlier choices and will correct the
new status path at those owners. Copying SQL into an adapter,
reading content to learn availability, rounding timestamps or treating expiry as
settlement would violate the existing ownership and truthfulness rules.

### Precision reproduction and proposed amendment

A pure, synthetic model probe at the baseline used an otherwise valid custodied
result with `accepted_at=2026-10-18T12:30:00.250000Z`:

- `observed_at=2026-10-18T12:30:00Z` is rejected: receipt time mismatch.
- `observed_at=2026-10-18T12:30:00.500000Z` is rejected: invalid UTC timestamp.
- `observed_at=2026-10-18T12:30:01Z` is accepted, but inventing that future
  observation time or waiting to reach it is not an acceptable fix.

Evidence alias `custody-status-contract/precision-probe.json`, SHA-256
`c117913f176c393bed5e71b52d6be417d507a81f801a274996caaaadc67d639d`.
This probe does not authenticate, open an application database or execute a
workflow. It reproduces a format limitation, not a production outage.

**Proposed compatibility decision:** status emits a separately validated custody
result version `1.1`. Its only field-format change from result `1.0` is exact
six-digit UTC fractional precision for `observed_at`, reusing the receipt owner's
decision-time validation. Other timestamps retain their current formats. Both
resolved and unresolved status results carry `schema_version="1.1"`.
The new version does not silently broaden the existing parser. Existing `1.0`
classes, parser, encoder, accepted/rejected inputs and canonical bytes remain
compatible and tested unchanged. Request `1.0`, workflow lookup `2.0`, signed
source formats and receipts are unchanged. No capability/wire endpoint is
activated or advertised. A future transport contract must explicitly select its
result version; it cannot assume an old consumer accepts `1.1`.

All cross-precision temporal comparisons use parsed UTC instants, not string
ordering. Reuse/factor the existing combination, receipt-binding and size rules
at their vocabulary owner rather than copying validators for the new version.
This amendment requires the operator's acceptance of this contract; it is not
covered by acceptance of the earlier pure-value work.

### Validated inventory and porting differences

Reuse the actual no-action pack, signed synthetic envelopes, trust snapshots,
concrete stores, reference-only child packets, native process barriers and state
oracles. No model, prompt, inference settings or private customer material applies.

| Existing proof to preserve | Location at the baseline |
| --- | --- |
| Source observation, body denial, WAL snapshot and cleanup semantics | `tests/test_lead_custody_store.py:351-443`; source/schema/clock/content tests selected in `.github/workflows/ci.yml:44-52`. |
| Historical recovery without body, writer, authentication or dispatch; exact joins | `tests/test_lead_custody_recovery.py:45-114,357-442,532-560`. |
| Real reference-only restart, lost replies and lifecycle/concurrent actors | `tests/test_lead_custody_resume_recovery.py:37-42,143-224`; `tests/test_lead_custody_recovery_process.py:30-91,138-225`. |
| Existing value bounds and legal combinations | `tests/test_lead_custody_protocol.py`, including timestamp and independent-guard fixtures; `tests/test_lead_receipt_vocabulary.py:141-168`. |

Recorded Linux proof for the tested input set published as PR #64: unchanged
baseline `3419 passed in 440.58s (0:07:20)`, new tests `168 passed in 59.14s`,
adjacent tests `1206 passed in 209.15s (0:03:29)`, and 26 killed isolated guard
mutants. This is prior evidence, not tests rerun for this proposal.
Evidence alias `custody-r3-recovery/manifest.json`, SHA-256
`11f8aa6d7bc212edb24df98c464c01a3a9f18965c76598c3dcfe98e59027c6d7`.
Its publication/merge evidence separately records Linux and native Windows CI,
oversight and connector completion at the exact head; merge packet alias
`custody-r3-recovery/merge-20261029T212028Z/manifest.json`, SHA-256
`1ac3d61e1d5c655d4686549f318f3996651c2916057d164bc6c04a7d697fd21b`.
No existing proof is claimed to exercise the new status path.

| Proposed departure from that inventory | Why it is required |
| --- | --- |
| New source-owned, timed metadata snapshot, alongside unchanged `observe` | Expose persisted reservation/admission/lifecycle facts without adding a clock dependency to old recovery. |
| New private `status(request=StatusRequest)` on the existing composition | Produce truthful receiver results without invoking recovery's possible resume branch. |
| Result `1.1` with precise observation time | Represent valid immediate observations without fabricated time; preserve strict `1.0` compatibility. |
| Shared pure historical-join validation extracted from recovery, if needed | Avoid divergent identity checks; recovery's inputs, outcomes, exceptions and I/O remain unchanged. |
| New status proof and native CI selection | Qualify the new composition, precision and concurrent snapshot semantics while retaining prior tests unmodified. |

## Contract

### Ownership and required change surface

Only the following executable owners may change in the separately authorized
implementation:

- `LI/source_store.py`: source metadata hydration and a new immutable status
  observation value/read seam. It owns all SQL, persisted facts, lifecycle and
  clock-floor validation. Share the existing metadata validators; do not create
  another unchecked query path. Preserve the old `CustodyObservation` shape and
  the existing `observe` behavior, including its lack of time sampling.
- `LI/custody_store.py`: a private-purpose `observe_status(request=StatusRequest)`
  facade over that read seam, using its configured host clock. No wrapper SQL.
- `LI/custody_handoff.py`: `_CustodyHandoff.status(*, request: StatusRequest)` and
  any shared pure join helper used by it and `recover`. No new orchestration
  owner. Caller supplies no raw bytes, clock sample, facts, lookup or receipt.
- `LI/custody_protocol.py`: separate `1.1` status result models, parser and
  canonical encoder, with shared invariant validators. Reuse the existing
  decision-time validator from `receipts.py`; do not modify that validator.
- New `tests/test_lead_custody_status.py` and
  `tests/test_lead_custody_status_process.py`; add them to native Windows CI.
  Existing fixtures may be imported unchanged. Test names/paths must be short
  enough for native Windows; text fixtures must use explicit UTF-8.

The current PR changes only this work order and the receiver roadmap navigation.
The proposed source observation extension and result-version amendment are
explicit changes to previously frozen owners, requiring acceptance here.
There are no storage-schema changes, migrations or new public exports.

### Source-owned observation

Canonicalize and pin the request through the current private host checks. The
source facade independently validates the operation and references. It opens one
existing-incarnation, query-only snapshot using the existing authorizer, and
returns a concrete immutable value containing:

- the unchanged custody facts;
- the validated persisted reservation deadline and original admission ID,
  including the ID retained after receipt cleanup;
- the namespace retirement disposition from the same snapshot;
- the exact UTC observation sample and source-owned content availability/reason.

Only the source owner can hydrate these facts. No raw envelope, sender, subject,
message narrative, secret key material, token, filesystem path or authority snapshot may enter
this value or the result. Internal source-receipt IDs remain metadata; the result
projects only the existing `ReceiptReference` fields. Stored prepared intent is validated at its existing
owner, not re-parsed by the composition.

Sample the configured source clock once after the read snapshot is pinned and
its metadata is validated. Reuse `_check_clock` against the snapshot's persisted
floor; never call `_record_clock`, reconcile, a writer, cleanup or content read.
Reject invalid, non-UTC or below-floor samples as unknown status, not caller
permission. Do not clamp the sample, borrow a receipt timestamp or use a fallback
clock. A failed clock cannot produce a resolved response. Old observe/recover
remain clock-free on their historical paths.

A source snapshot is not a lease. `observed_at` describes this source assessment;
workflow history is read afterward in a separate owner snapshot. No common
transaction or instant across both stores is claimed. Source state revision is
not a revision of workflow history or wall time. A later status may differ with
the same source revision, without contradiction.

Capture matching is exact: a request without a capture is valid only while the
stored capture is absent; a captured request requires the complete matching
pair and metadata. A pre-capture request racing with binding returns conflict,
not the newly bound identity. Any structurally valid expected generation is an
observation hint, never permission: status returns the actual generation without
requiring equality or updating the caller's generation. Mutation paths retain
their existing generation checks.

### Read-only composition and historical joins

1. Canonical request/type validation and current runtime/license/route/machine/
   source-store/incarnation/no-action-pack pins run before observation. Configured
   references remain synthetic trusted-host inputs, not a machine-auth proof.
2. Acquire the source status observation. A valid missing handoff yields
   unresolved `not_found`, meaning missing intent metadata only. Missing or
   replaced storage and corrupt metadata are unknown, never not-found.
3. When `ever_custodied` is exactly true, perform one existing runtime lookup
   using the persisted scope/event and **payload digest**, not envelope hash.
   End the source snapshot first. Never call `recover`, `resume`, submit, a
   legacy admission entry, dispatch or any mutation on this path.
4. Revalidate the concrete closed lookup and require no actions. For known
   history require the existing exact scope/event/digest/deadline joins and
   complete receipt equality while the source receipt exists. Additionally,
   require the workflow admission ID to equal the source-owned persisted
   admission ID, including after retired receipt cleanup. Retain original
   workflow identity/stage/version; never rebuild it from the current record.
5. Compose only the truth-table outcome below. Do not convert a failed lookup
   to a successful custody-only response or to workflow `not_found`. Validate
   and canonically encode the complete new result before returning it.

Any shared join-helper extraction must preserve existing recovery behavior,
including its historical availability after receipt cleanup and its existing
exception mapping. No source/clock access is introduced into that old path.
New status-only facts do not become a new prerequisite for old operations.

### Closed projection rules

Source availability has this precedence within its snapshot: namespace retired
means unavailable/retired; otherwise a validated purged row means
unavailable/purged; otherwise retained bytes with sample at or beyond the signed
recovery deadline mean unavailable/expired; otherwise the validated retained
row means retained. Purged is the persisted deletion disposition, not an invented
historical deletion cause. Missing or contradictory metadata is unknown, not
unavailable/lost. Status never claims to have verified the bytes' contents.

| Source facts and workflow read | Result |
| --- | --- |
| Missing handoff in a valid pinned store | Unresolved `not_found`; no workflow lookup. |
| Never custodied, open, no capture, unexpired reservation | Resolved prepared/not_received/ready; exact reservation expiry; no workflow. |
| Never custodied, open, no capture, reservation at/past expiry | Unresolved `unknown`. Existing states cannot truthfully express expired-unfenced readiness. Do not close, renew or claim fenced-empty. |
| Never custodied, open, capture bound | Resolved upload_possible/unknown/pending, even after reservation expiry; an old writer's absence is not proven. No workflow lookup. |
| Never custodied, source owner proves closed | Resolved fenced_empty/not_received/capture_cancelled; preserve the pinned capture if one exists. This proves closed admission without custody, not physical loss. Never infer closure from time. |
| Custodied, source receipt present, workflow valid not_found | Resolved custodied with source availability; reason custody_confirmed or content_unavailable. Embed the real not_found lookup. |
| Custodied, known accepted/no_match workflow | Resolved custodied/workflow_known with independent source availability and exact receipt projection. No action execution or delivery claim. |
| Retired, source receipt cleaned, exact known workflow | Use the validated workflow receipt only after the full historical join plus persisted admission-ID check; report unavailable/retired. Never recreate a receipt or bytes in storage. |
| Retired, source receipt cleaned, workflow not_found | Unresolved `unknown`: historical custody exists, but the required receipt projection cannot be reconstructed. |
| Any failed/corrupt/inconsistent owner result, missing proof or oversize encoding | Unresolved `unknown`, with no invented phase, generation, receipt or workflow. |

A projected expiry is an as-of-time assessment, not terminal deletion. A future
valid read after an authorized clock-floor reset can differ if bytes were never
purged. Once the content owner actually purges, that persisted state remains
unavailable. Status cannot advance the clock floor or make expiry irreversible;
those effects remain at the existing content/admin owners. Retention periods and
cross-application deletion policy are not decided here.

### Errors, privacy and size

Before a canonical request exists, preserve the current fixed validation/pin/
license errors; never fabricate a handoff ID to return a result. After validation,
source binding/capture conflicts or workflow `EventConflict` return unresolved
`conflict`. Runtime license, pack-version and binding/input refusals keep their
existing fixed exceptions. Source busy/unavailable/uncertain, invalid clock,
malformed owner output, unexpected errors and serialization failure return
unresolved `unknown`. `refused` remains a legal vocabulary value but is not used
to pretend machine authorization was checked in this private slice.

No original exception, cause/context, SQL or input is serialized or logged by the
new path. Both result variants use the existing byte cap and privacy restrictions;
no truncation or best-effort partial projection. New version-specific parsing
rejects legacy/future/mixed versions, duplicate members, unknown fields, malformed
UTF-8, noncanonical timestamps and invalid numeric types. Keep old parser behavior
unchanged. This is an in-process status value, not a cached transport completion
or an authenticated GET result; operation/job/proof references are not journaled.
Repeated calls observe again and are not guaranteed byte-identical snapshots.
If even the minimal unknown result cannot be validated/encoded, raise the existing
fixed `SourceHandoffUnknown` outside the caught handler; never return an unchecked
value or leak the original failure.

### Explicit non-scope, risk and rollback

Keep `automate/runtime.py`, workflow storage/results, admission/authentication,
content lifecycle, receipt formats, schemas/migrations, dependencies and public
exports unchanged. Preserve old tests, request formats, raw submit, reference
resume and lookup-first recovery behavior. No source writer changes, retention
scheduler, new database, queue, dispatch mechanism, inference provider, polling,
receiver service, enrollment, employee authorization, UI, extraction, CRM,
Watcher/EOM/Atlas integration or installation/adoption work.

The principal risks are false readiness, invented fenced absence, loss of
historical evidence, shared-helper regressions and mistaken cross-store atomicity.
The closed truth table, independent guard probes and real snapshot races below
are required proof. Rollback disables the new private status caller and retains
all stores and old readers; no downgrade, deletion or replay of effects.

### Assumptions, blockers and implementation slices

The trusted host and no-action pack remain prerequisites. Real machine and
employee authorization, transport journaling, retention policy and installed
native qualification remain separate acceptance gates. An unresolved private
status is not a product completion claim or permission to retry an effect.

This contract must receive independent review and exact-revision operator
acceptance. Record acceptance in a docs-only commit and merge it through its
normal gates before executable changes. Implement in a separate bounded PR;
keep precise vocabulary/source observation and status composition as separately
reviewable commits with unchanged parity between them. If the required owner
changes exceed this work order, revise the contract before expansion.

Gate mapping: contract acceptance is a G0 ownership/contract gate. The precise
vocabulary/source-observation commit and status-composition commit each provide
G1/G3 prerequisites, not end-to-end source handoff or receiver qualification.
Read-only/privacy assertions contribute to G6, whose installed authorization and
retention obligations remain open. This slice cannot pass G1, G3 or G6 as a whole.

### Verification plan after acceptance

Run unchanged affected parity before edits. First preserve the pure precision
probe as a regression, then declare a missing-status-entry fail-first using a
real committed managed workflow, source-key revocation, reference-only reopen
and forbidden body/writer/dispatch paths. It must fail at the missing entry
before implementation, then return exact history in the new bounded result.
No new fixtures/tests or implementation are added by this contract PR.

| Proof family | Required assertions |
| --- | --- |
| Compatibility and precision | Original protocol/request/receipt tests and canonical bytes unchanged; new version rejects old/future/mixed schemas; same-second receipt succeeds with exact microsecond observation; before/equal/after capture, receipt, reservation and recovery deadlines; no rounding, lexical cross-format comparison or waiting. |
| Source snapshot | Old observation shape/clock-free behavior unchanged. New exact source facts come from one snapshot with envelope reads and all writes denied; no second SQL owner. Reservation deadline, admission ID, retirement and time independently checked. |
| Every projection row | Real prepare/bind/commit/settle/purge/retire/cleanup operations establish states. Test all table rows, source-only accepted custody, real accepted/no_match/not_found, unavailable-body envelopes and bytes retained after deadline. |
| Authority and binding | Canonical copies consumed; wrong operation, partial/mixed capture, source/event/route/org/host/machine/incarnation and action-pack drift; valid stale and future generation hints, invalid zero/false/empty/above-max; no body auth or employee-auth claim. |
| Historical joins | Independently wrong scope fields, both digest identities, deadline, admission ID, accepted-at, historical flag, lookup type/actions/shape. Retired-cleanup fixtures isolate each check from remaining receipt equality. No caller-supplied receipt bypass. |
| Time and lifecycle | Invalid UTC/clock exception/below-floor becomes unknown without persisted changes; exact boundary and forward jump; explicit C1 reset with retained bytes versus terminal purge; missing retained row and corrupt BLOB distinguished without claiming body validation. |
| Errors and privacy | Missing intent vs missing/replacement/corrupt store; source busy, workflow failures and encoding cap failures; no fallback calls. Synthetic sensitive sentinels absent from results, messages and exception chains; max UTF-8 and falsy/default probes. |
| Concurrent snapshots | Native two-process barriers before/after source snapshot, its release and workflow lookup; upload/resume/settle/purge/retire/cleanup on both sides. Old coherent snapshot or later coherent snapshot/unknown as specified, never an invented combined instant. Different read completion order must not imply monotonic source revision for workflow state. |
| Restart and loss | Kill reader before/after each owner read and before response; reopen with references only. No new rows or effects from status, no deleted bodies, no advanced floor; lost response permits another read. Reuse existing native actors/state oracles. |
| Independent guard proof | One minimal corruption per check, otherwise valid enough to reach that check. Guard-removal probes must fail at the intended assertion; equivalent mutants explained. New tests run standalone and in selected CI on Linux and Windows from the first push. |

Run focused new and unchanged adjacent tests, Ruff and the repository-required
checks. CI owns duplicate broad suites unless the accepted implementation review
contract identifies a specific high-risk local need. Retain raw outputs, runtime
pins, tested hashes and before/after probes outside worktrees. Merge requires
exact-head Linux/Windows CI, oversight PASS, reconciled connector review, no
unresolved threads/changes-requested and clean local==remote. Use a guarded merge
commit and verify its tree equals the reviewed head.

## Implementation summary, cold diff audit and gap audit

Current change: this proposed work order plus a navigation/status update in
`LEAD-RECEIVER-CUSTODY.md`. No executable, test-input, schema, dependency or CI
change. Contract verification checks all cited source ranges against the pinned
base, local links, docs-only diff and unchanged executable inputs. The synthetic
precision probe is recorded separately; no code test suite is rerun for docs.

**NOT DONE:** independent contract review, exact-revision acceptance, contract
merge, implementation and its Linux/Windows proof. Neither this document nor the
prior library tests qualify a receiver service, live mailbox or production lead
intake. Shared inference integration remains an independent later work order.
