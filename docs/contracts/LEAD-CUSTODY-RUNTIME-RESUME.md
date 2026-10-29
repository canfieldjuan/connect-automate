# R3.3: reference-only runtime resume

Status: **ACCEPTED contract MERGED; implementation locally verified, CI and independent review pending.**

Juan requested: “Let’s start the reference-only runtime resume contract and open
a contract-only PR for oversight review.” That request authorized preparation and
review only. The subsequent acceptance below authorizes this bounded work order;
the contract must merge before executable work begins in a separate PR.

R3.2 merged in [PR #60](https://github.com/canfieldjuan/connect-automate/pull/60)
as `9fedc09709fb5b0fa77dc650e5eed2b64c237c3b`, with tree
`e0b655dd29fdae79f3b127c0c44764d6f02dfc52`, equal to its reviewed head
`d81d953289f2ac63e1f58f4e7db6e798c4f15414`. This is the inventory pin below.
The [parent sequence](LEAD-RECEIVER-CUSTODY.md#bounded-implementation-sequence-and-verification),
[source revalidation owner](LEAD-CUSTODY-STORAGE.md),
[raw composition](LEAD-CUSTODY-COMPOSITION.md) and
[retained reader](LEAD-CUSTODY-RETAINED-READ.md) retain their responsibilities.

## Acceptance record

On 2026-10-29, Juan stated directly in this lead-intake chat:
**“Let’s check CI, oversight and connector reviews on PR61. i accept implementation”**.
This accepts the R3.3 work order at reviewed revision
`bcd75bc049770d9b7a4369f9df6afc41af70ddf9`, tree
`9f41825cb08ef21fc8891e8d0e3acf8454bc8352`. Oversight CONTRACT REVIEW PASS is
recorded in mailbox `02ddd25b` and
[the exact-revision review](https://github.com/canfieldjuan/connect-automate/pull/61#issuecomment-6487150366).
The direct operator statement supplies authorization; oversight PASS alone does not.

At that reviewed revision, Linux `test` and `windows-placement` passed, the
connector completed without findings, and no review threads were unresolved.
This acceptance-only documentation commit must receive its own current-head
checks and review before a guarded merge commit. Then implement the accepted
slice in a separate PR, with unchanged parity and the declared fail-first proof
before source edits. No executable work precedes that contract merge.

Carry-forward from oversight, without a contract change: the stale-metadata
tests must assert `SourceAuthenticationError` when applicable purge/expiry/cutoff
lands between the bound read and revalidation. `SourceContentUnavailable`
remains the bound-read/no-observed-receipt refusal. Receiver orchestration,
transport persistence, protected service activation and adoption remain excluded.

The acceptance-only head above merged in PR #61 as
`5ea984d18c10c745b8098fad89e841dc46502c68`. Its tree
`99dc0dff1b83e0d197a53e3ad7041b54867194e9` equals the reviewed tree.
Linux and native Windows checks, oversight and connector review passed before
the guarded merge. The bounded executable work below is separately authorized.

## Contract

### Root cause and verified inventory

This is an intentionally missing composition, not a defect in upload fencing.
Raw upload must continue refusing closed or expired reservations. The missing
operation is private runtime submission from already-custodied bytes after the
source commit succeeds but workflow creation does not.

All citations in this inventory describe the pin above in
`canfieldjuan/connect-automate`; `lead_intake/` and `automate/` paths are beneath
`src/connect_automate/`. Documentation is not implementation evidence.

| Classification and finding | Source at the pin |
| --- | --- |
| **CONFIRMED:** the managed composition accepts only an upload plus raw bytes. It has no resume entry. | `lead_intake/custody_handoff.py:87-117`; `automate/runtime.py:290-339`. |
| **CONFIRMED:** a crash after source commit followed by closure or reservation expiry leaves source custody and no workflow; raw retry refuses. | `tests/test_lead_custody_composition_recovery.py:292-316`. |
| **CONFIRMED:** exact source observation compares scope, machine, capture and retained incarnation, and returns metadata without reading the envelope. | `lead_intake/custody_store.py:73-93`; `lead_intake/source_store.py:198-214,774-823`. |
| **CONFIRMED:** the bound reader checks incarnation, handoff/capture, generation and retained receipt under the source writer before reading; expiry commits before unavailability is raised. | `lead_intake/content.py:84-121`; `lead_intake/custody_store.py:168-173`. |
| **CONFIRMED:** retained revalidation takes raw bytes and an admission ID; it authenticates twice and checks current receipt identity and generation inside its writer. It cannot create a missing receipt in this mode. | `lead_intake/custody_store.py:156-166`; `lead_intake/admission.py:152-209`; `lead_intake/source_store.py:1068-1105`. |
| **CONFIRMED:** a closed handoff at its current generation, or an expired upload reservation with eligible retained content, can revalidate. Revocation refuses. | `tests/test_lead_custody_store.py:1326-1352,1579-1600`. |
| **CONFIRMED:** privileged retained reading can succeed after key revocation; the subsequent revalidation refuses. Reading is not workflow authority. | `tests/test_lead_custody_retained_read.py:345-353`. |
| **CONFIRMED:** runtime completion already owns event admission, persisted projection validation, dispatch and unknown-outcome handling. Historical lookup is a separate read-only operation. | `automate/runtime.py:303-450`; `lead_intake/results.py:59-73`. |
| **CONFIRMED:** the trusted composition pins runtime, source store, incarnation, route and machine, and rejects packs containing actions. Source-to-event validation is shared. | `lead_intake/custody_handoff.py:43-112`; `lead_intake/handoff.py:67-122`. |
| **CONFIRMED:** workflow metadata remains discoverable after source lifecycle refusal. | `tests/test_lead_joined_lifecycle.py:232-251`. |
| **INFERRED:** these owners suffice for a bounded reference-only submission primitive without new storage or a second completion path. | The observation, bound read and exact retained revalidation above supply the missing preparation chain. The joined resume behavior still needs implementation proof. |
| **UNKNOWN / later qualification:** real machine access, durable transport operation identity, installed recovery and application adoption. | No synthetic private-library proof in this work order qualifies these. |

### Inventory of validated work and porting differences

Reuse the signed synthetic envelopes, trust snapshots, clocks, no-action signed
pack and actual source/workflow stores already exercised by the existing tests:

- `tests/test_lead_custody_composition.py:17-54`: `composition`, `prepare`, and
  the existing host fixture; full route and concrete-owner construction.
- `tests/test_lead_custody_store.py:1364-1372`: `upload_setup`; existing
  `managed_operation` and `reader` fixtures construct resume values and reopen
  the same enrolled source store.
- `tests/test_lead_custody_retained_read.py:76-112,345-381`: original bytes,
  reopened/closed custody, body states, current-auth separation and deadline
  equality/final-sample expiry.
- `tests/test_lead_custody_composition_recovery.py:25-88,292-316` and
  `tests/test_lead_joined_recovery.py:72-85,93-158,224-278`: native-process reopen,
  observed SQL/commit checkpoints, completion handling and persisted-state
  inspection. Preserve the original raw-submission gap test unchanged.

Fresh existing-seam inventory at the pin **passed (process exit 0)**. The command,
raw output and input digests are recorded, with Python `3.13.11`, pytest `8.4.2`,
Pydantic `2.13.5`, on Linux `7.0.0-38-generic-x86_64-with-glibc2.39`. All source,
tests, dependency files and CI inputs were unchanged. No inference model,
prompts, remote provider or private customer data is involved.

Durable evidence alias: `custody-r3-runtime-resume-contract`.
`inventory-manifest.json` SHA-256:
`24a263faf2947b953558e775e228db7e90aed9fcaf69245fc8940e94fa4ac129`.
`existing-seams.txt` SHA-256:
`12a9a4a8915fb8d2bb5b4227220247cde267c1a0620203589fe47280d5be4a7f`.
This proves the inventoried seams, not the proposed joined resume path. Native
Windows resume proof is a later executable gate, not a claim of this contract.

Every proposed departure from those validated paths is explicit:

| Difference | Reason and preserved behavior |
| --- | --- |
| Caller provides only a canonical resume reference; the owner retrieves original bytes. | Close the source-only crash gap without another mailbox read or upload. Preserve the R3.2 reader unchanged. |
| Observe source facts, then bound-read, then revalidate the exact existing receipt. | Derive admission identity locally; observation never authorizes submission. Preserve writer-held receipt equality, current authentication and fencing. |
| Select resume preparation inside the existing runtime completion boundary. | Reuse workflow identity, exception classification and persisted results. Preserve both legacy and managed raw submission. |
| New recovery fixtures spawn a reference-only caller. | Prove recovery does not depend on parent-held email bytes. Reuse existing native checkpoints and state oracles; distinguish read and revalidation transactions. |

There are no changes to source retention, authentication policy, stored schemas,
result vocabulary, model settings or effect behavior. An unlisted difference
requires contract revision before executable work expands.

### Required change surface after acceptance

| Owner / file | Smallest allowed change |
| --- | --- |
| `src/connect_automate/lead_intake/custody_handoff.py` | Add private-library `resume(*, request: ResumeRequest)` and resume preparation. Share existing request parsing/route checks with upload without weakening operation discrimination. Compose the concrete source facade; no SQL or new durable state. |
| `src/connect_automate/automate/runtime.py` | Add a private bound resume entry. Select the concrete resume preparation inside the existing error boundary and feed the same workflow completion block. Preserve public signatures and the raw path. No callback or externally supplied prepared event/receipt. |
| New `tests/test_lead_custody_resume.py` | Reference-only composition, route/authority boundaries, exact receipt/result, lifecycle and legacy parity proof. |
| New `tests/test_lead_custody_resume_recovery.py` | Reuse native-process harnesses for source-only recovery, reference-only restart, faults, concurrency and lifecycle order. Any small test-local bridge must preserve existing oracles and label each source transaction distinctly. |
| `.github/workflows/ci.yml` | Select both new files for native Windows from the first executable push; Linux already selects all tests. No other workflow or dependency changes. |
| This contract | Record exact acceptance before code, then measured evidence and remaining gaps. |

`content.py`, `custody_store.py`, `source_store.py`, `admission.py`, `auth.py`,
`handoff.py`, protocol/result models and workflow storage remain unchanged.
The contract PR itself changes only documentation, including parent navigation
and the completed retained-read slice's stale status. It adds no tests or code.

### Proposed operation and ownership

The private `_CustodyHandoff.resume(*, request)` returns the existing
`SourceHandoffResult`. Its host supplies the already verified runtime, concrete
custody facade, route, enrolled-machine reference and clock as today. The caller
supplies no raw bytes, admission ID, copied observation, source receipt, prepared
event, content reader, replacement store or callback. There is no public export,
receiver capability or transport dispatch entry.

The operation must follow this chain:

1. Reparse the request through the existing canonical protocol parser and require
   exactly `ResumeRequest`. Consume the reparsed value throughout. Check runtime
   license, pinned pack/binding, host/organization/namespace, route digest, machine,
   source-store object/incarnation and the no-action restriction before source
   access. Use the same owner for route checks as upload. A copied valid value is
   acceptable after revalidation; a model instance is not authority.
2. Call the concrete facade's `observe` with the canonical handoff, full scope,
   enrolled machine and required capture. Keep this source-validated snapshot
   locally. If it has no receipt (including unknown or never-custodied handoffs),
   refuse with `SourceContentUnavailable`; do not infer permanent absence or
   fenced-empty. Do not adopt an unrelated receipt or query tables directly.
3. Obtain original bytes only through `read_retained(request)`. Its in-writer
   checks, current generation and content deadline remain authoritative for the
   read. An observed generation cannot replace the caller's expected generation;
   never refresh a stale request automatically. Never use the admission-ID-only
   legacy reader as a fallback.
4. Validate those bytes against the pinned source binding with
   `_source_for_binding`. Call `revalidate_existing` with the same canonical
   request and bytes, deriving `admission_id` exclusively from the observed
   source receipt. Retain the existing in-writer equality check against the
   current linked receipt. A snapshot becoming stale cannot bypass that check.
   There is no call to `admit_bound` or legacy `admit_source` in resume.
5. Require the fresh revalidation result to identify the exact observed receipt,
   with `applied is False` and retained content. An inconsistent owner result is
   `SourceStoreUnavailable`, handled by the runtime's existing unknown boundary.
   Pass this freshly obtained result and parsed bytes through the unchanged
   `_prepared_source` receipt-to-event validator. Observation or a successful read
   alone can never create a prepared workflow event.
6. Complete through the existing runtime block: recheck license and pinned
   configuration, admit the event through its owner, validate the persisted
   projection and return its result. Keep one completion implementation for raw
   and resume paths, without a caller-supplied mode/callback that skips preparation.
   Retain the existing dispatch structure for legacy parity; managed packs still
   cannot contain actions and must produce no action effects.

The composition never initiates registration, binding, settlement, re-signing,
recreation or recapture. The existing reader may close admission and purge content
when it observes expiry; that effect and the read/revalidation clock audit are
intentional. Successful resume has `source_applied=False`; `workflow_applied`
comes from the actual event transaction and is false on replay. Preserve accepted
versus durable no-match and the original workflow identity after advancement.
No new transport control/job records are created: these references remain
shape-validated values, not per-operation authentication or durable job dedupe.

### Separate transactions, lifecycle order and historical lookup

Observation, retained read, revalidation and workflow admission are separate
transactions. Do not hold a source read snapshot or writer while calling the
workflow owner. Source authorization linearizes at the successful existing
revalidation transaction, not at the earlier read or at final response delivery.

- A previously closed handoff may resume with its current generation and eligible
  retained content. Upload reservation expiry alone is not content expiry.
- Closure that changes generation before revalidation makes an old request stale.
  Applicable message-cutoff purge, namespace retirement, key revocation,
  source-key expiry or recovery-deadline expiry
  before revalidation must prevent workflow submission. Exercise both writer
  orders, including a change while resume waits on the store.
- A lifecycle mutation after successful revalidation does not retroactively
  cancel that in-call authorization. Workflow completion may still follow, as
  in R3.1. No atomic authorization across databases or cancellation promise is
  introduced. A fresh retry must authenticate again.
- If the reader observes expiry, preserve its commit-then-unavailable behavior.
  If time crosses the deadline after reading, revalidation refuses under its
  existing rules; do not add a compensating purge or change its clock policy.
- After a lost workflow response, eligible authenticated resume can replay the
  same event. If content/key/lifecycle eligibility has since ended, resume refuses;
  existing historical lookup can still report the persisted workflow outcome.
- An upload that commits after an empty observation does not turn that snapshot
  into permanent absence. A later eligible resume may resolve it. Late deletion
  preserves captures newer than its cutoff and unrelated message identities.

This is the **submission primitive**, not the receiver recovery coordinator.
It always revalidates; it does not return a historical lookup value disguised as
fresh submission. The later coordinator must check historical workflow metadata
first using the persisted payload digest, and call resume only when needed.
Known status must not require a body read or a valid original signing key.
The parent lookup-first requirement remains unchanged; orchestration and its
R1/Connect result mapping are a separate work order.

### Error and privacy contract

Preserve existing fixed, sanitized errors and runtime classification:

| Condition | Required meaning |
| --- | --- |
| Malformed/wrong-operation request, wrong pinned binding or configuration | `EventBindingError` before source access, matching managed-entry validation. |
| Content absent/expired/purged at bound read, or no observed source receipt | `SourceContentUnavailable`; not a claim that source/workflow never committed. |
| Authentication, generation, scope or canonical-capture refusal | Existing source owner error; no workflow admission and no fallback. |
| Source busy | Existing bounded `SourceStoreBusy`; not absence, success or an internal retry loop. |
| Corruption, unavailable store, uncertain commit, unexpected exception | Existing `SourceHandoffUnknown` boundary; preserve no sensitive exception chain. |
| Workflow conflict, pack-version/binding/license refusal | Existing runtime refusal unchanged; preserve committed source history. |

Only the existing metadata result leaves the composition. Retained email bytes
must not enter workflow rows, results, logs, exceptions, a new cache or transport
packet. They exist transiently for source validation; no secure memory-erasure
claim is made. The private local OS-user boundary is unchanged. Machine IDs and
proof references are not authentication, and current source signing authority is
not employee authorization.

### Explicit non-scope

No storage/schema/migration changes, authentication or retention redesign,
cross-owner SQL, second workflow engine, new queue/scheduler, public API/export,
historical-result schema/projection change, receiver status/settlement synthesis,
transport journal/cache, provider discovery, automatic generation refresh,
machine enrollment/proof consumption, employee UI or protected service activation.
No Watcher, EOM, Atlas, inference, CRM adapter, app/dependency pin or installation
changes. No production adoption or completion claim for the overall intake flow.
Existing tests/fixtures and earlier accepted semantics remain unchanged.

### Assumptions, blockers and recovery path

- **Acceptance gate:** this proposal must receive independent oversight review
  and explicit operator acceptance at its exact reviewed revision. Record the
  acceptance in a documentation-only commit, merge the contract after its current
  CI/oversight/connector gates, then use a separate executable PR. Review PASS is
  not operator acceptance.
- **Regression risk:** runtime preparation selection shares legacy exception and
  completion behavior. Preserve the completion block and existing tests, including
  legacy action behavior; restrict managed paths without restricting legacy ones.
- **Assumption:** the private host already holds valid deployment configuration.
  This work does not qualify an externally authenticated caller or route access.
- **Scope blocker:** a required change to a frozen owner/API/schema above must be
  reported and incorporated into a reviewed contract revision before expansion.
- **Rollback:** disable use of the new private resume entry, preserving all stores,
  source receipts, fences and workflow history. No downgrade, deletion, reopening
  of admission or fallback to unfenced upload. Historical lookup remains usable;
  later authorized recovery uses the same identities while still eligible.

### Verification plan after acceptance

Run unchanged affected tests at the merged contract before executable edits.
Add a declared fail-first regression: committed source, no workflow, closed
upload at the current generation, then reference-only resume in a reopened
runtime. Before implementation it must fail specifically because the private
resume entry is missing. Keep the existing raw-retry refusal test unchanged.

| Proof | Required assertions |
| --- | --- |
| Positive composition | Open and closed retained handoffs, expired reservation with live content, complete/truncated/unknown/unavailable body envelopes, accepted and no-match packs. Exact original source receipt; no new content/receipt/operation rows; source-applied false; original workflow identity on replay and after advancement. |
| Boundary and canonical-consumer | Wrong operation, forged/copied/partial/mixed values, full scope/route/machine/capture, store replacement/incarnation drift, invalid license or action-bearing pack. Assert refusal at the owning boundary, before envelope access where appropriate. Probe empty/falsy/type and valid/max/above-max protocol boundaries; consume the sanitized request. |
| No authority shortcut | No raw/ID/receipt/observation/prepared-event parameter; no legacy admission/reader/callback fallback. Revalidation must run for every resume. Copied reads or receipts cannot bypass revocation. Inconsistent fresh owner receipt, applied flag and content state each fail independently. |
| Stale metadata | Change generation, content/lifecycle or linked receipt between observation, read and revalidation. Preserve the writer-held receipt-equality check. Each corrupted fixture defeats only its intended check, not an earlier check. Missing/unknown observation never becomes fenced-empty or a new admission. |
| Time and lifecycle | Both orders of close, revoke, applicable message-cutoff purge and retire versus revalidation; source-first completion remains allowed. Preserve newer captures and unrelated message identities. Deadline equality/final sample, key expiry during a busy wait, backward clock, and time advancing after read. No revival after committed read expiry. |
| Native restart and concurrency | Separate spawned processes, concurrent resume/resume and upload/resume where eligible, source-only crash after upload commit, reference-only restart, close/expiry before retry, same event replay. Assert exact source/workflow row identities and counts with no hidden caller-supplied bytes. |
| Faults and lost replies | Pause/crash before/after read commit, revalidation commit, each actual workflow write and workflow commit, and after response loss. Reopen real stores. No fabricated success, no partial workflow transaction, no duplicate records; subsequent behavior depends on current eligibility. |
| History and privacy | Existing lookup still works after source purge/revocation/expiry without source access. Resume refusal does not erase history. Results/rows/logs/errors contain no raw body or private path/SQL/validation chain. No action dispatch effects in managed packs. |
| Frozen parity | Existing source, content, custody, raw composition, runtime-result, joined recovery/lifecycle and legacy action tests pass unchanged. No new public exports, schema or dependency changes. |

Reuse native lifecycle actors, completion handling and SQL checkpoints rather
than simulating commits with a fake receipt. New test-local bridges must mark
read versus revalidation checkpoints explicitly, not accidentally fault the
earlier clock write. The restarted resume process receives references/configuration
only; fixture creation may upload synthetic bytes beforehand. Preserve actual
failure output and native process exits on Linux and Windows.

For every new safety check, disable that check alone and require its isolated
negative test to fail at the intended assertion. Preserve the positive side too.
Run targeted new tests, adjacent files and Ruff first. This high-risk shared
runtime/authentication composition also requires the complete affected lead
source/custody/runtime/recovery lane locally before publication. Required CI runs
the full Linux suite and the selected native Windows lane from the first push.
No weakening earlier tests or claiming production readiness from synthetic CI.

## Implementation summary

The private composition now exposes `resume(request=...)`. It canonicalizes the
request, observes the exact bound receipt, reads retained bytes through the source
owner, and reauthenticates that same receipt before preparing a workflow event
(`lead_intake/custody_handoff.py:90-150`). Fresh receipt identity, applied flag and
content state are checked independently. Missing observation is unavailable, not
a permanent-absence claim. A prepared-only handoff with an unbound supplied
capture retains the existing observation owner's `SourceStoreConflict` refusal.

The runtime selects concrete resume preparation inside the existing exception
boundary (`automate/runtime.py:308-361`). Managed upload retains its own exact
operation discriminator. No caller mode, callback or supplied prepared result
selects an authority shortcut. The workflow completion block is byte-identical
to the merged baseline. Source authorization still linearizes at revalidation;
read, revalidation and workflow admission remain separate transactions.

No earlier workaround was removed: this implements a deliberately absent
composition while retaining the raw-upload refusal on closed or expired
reservations. Source owners, schemas, dependencies, public exports and every
previous test/fixture remain unchanged. Shared AI inference runtime work is
outside this path and creates no new dependency here.

## Verification evidence

- Unchanged merged-contract baseline: **3256 passed in 451.32s (0:07:31)**,
  before executable edits.
- Declared fail-first: `test_closed_source_only_gap_resumes_after_reopen` failed
  with the expected missing `resume` method `AttributeError`. The implementation
  and unchanged adjacent raw/runtime tests then passed (**401 passed in 38.45s**).
- Final new composition/recovery files: **163 passed in 74.37s (0:01:14)**.
- Native recovery run with retained checkpoint output: **49 passed in 55.36s**.
  Reused SQL/IPC/state oracles cover actual workflow writes, both source commits,
  lost replies, separate-process overlap and lifecycle writer orders. Resume
  workers receive only references/configuration; original source bytes remain
  parent-side test-oracle input or are read by the source owner inside the child.
- **14 isolated removed-guard probes killed**, including each fresh-result guard,
  operation/owner pins, canonical consumption and reauthentication. Mutation is
  process-local and does not edit production files.
- Ruff: **All checks passed!**
- Complete affected source/custody/runtime/recovery lane: **3419 passed**, as
  disjoint groups with **1653 passed in 483.59s (0:08:03)** and
  **1766 passed in 213.28s (0:03:33)**. The file union equals the original command;
  no tests were omitted, and executable-input hashes remained unchanged.

The earlier combined invocation ended at exit **143** without a pytest summary;
it is preserved as incomplete and is not counted as passing evidence. No failing
test or kernel OOM record was observed; the termination cause remains unknown.
The complete rerun above required no product-code repair.

Durable evidence alias: `custody-r3-runtime-resume`.
`manifest.json` SHA-256:
`343e946d59054441054bb9ef7a776eae59ab6c262453def7b17bd4533c2afe49`.
It binds commands, input digests, fail-first output, native traces, guard probes,
completed group results and the separate incomplete-run record.

The native bridge distinguishes read and revalidation checkpoints and observes
actual commits even when a clock sample makes no write. It preserves the original
completion protocol. Existing raw source-only gap tests remain unchanged.
Both new files are selected by the native Windows job from the first executable
push. Windows and current-head CI/review results are not yet claimed here.

`boundary-probe`: eligible open/closed envelopes, invalid/mixed/falsy and generation
boundaries, full scope/route/machine/capture and independent fresh-result checks;
all new guard probes detect their removed check. Unchanged protocol/source tests
retain the size-limit boundary proof. Downstream calls consume the canonical copy.

`effect-trace`: recover a committed source without reupload after the upload closes
| concrete retained reader, fresh source authentication and shared event admission
| missing-entry fail-first, reopened closed-source regression and native source-after
crash/replay with stable workflow identity. Source locks are released before workflow
admission; historical lookup remains usable after source eligibility ends.

## Cold diff audit

- `custody_handoff.py`: shared request validator and bounded resume preparation;
  no SQL, new store or authority callback.
- `runtime.py`: private resume entry and preparation selection; unchanged shared
  completion, legacy actions and error classification.
- New test files: real owners and synthetic data, retained native harness/oracles,
  strict stale-metadata errors and one isolated negative per new safety check.
- CI: select the new files on Windows; no other workflow/dependency changes.
- This document: measured implementation evidence outside the unchanged accepted
  Contract section. Parent document: merge-status correction only, as requested
  by oversight; no protocol or policy revision.

## Gap audit

**NOT DONE — current-head CI, native Windows and independent
oversight/connector review remain pending.**

This is private-library submission proof only. The lookup-first receiver
coordinator, status/settlement mapping, durable transport operations, protected
service wiring and adoption remain separate work orders. No production readiness,
employee authorization, inference integration or end-to-end lead extraction claim.
