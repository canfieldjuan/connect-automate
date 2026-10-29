# R3.4: lookup-first private recovery

Status: **IMPLEMENTED locally under the accepted work order; separate implementation review and Linux/Windows CI pending.**

This work order follows [R3.3 reference-only runtime resume](LEAD-CUSTODY-RUNTIME-RESUME.md).
It was proposed as a stack on [implementation PR #62](https://github.com/canfieldjuan/connect-automate/pull/62),
head `d98740136ff6264b875828e6843505a6f79b269a`, tree
`8c19c07ef0c91af64e4e08bbfd1cbacf2e7fa9de`. That dependency merged unchanged
as `9332cdfa81af1718892609e970da017b183d4cab`; the merge tree equals the reviewed
tree. At the reviewed contract revision, retargeting to main preserved the
original documentation-only stack delta exactly. Contract PR #63 then merged as
`4bd562639e54531962782875eda14daa0fd147b3`, with its reviewed tree unchanged.

Juan's original stacking request authorized preparation and review only. The
direct acceptance below supplies the bounded implementation work order, subject
to contract merge first. No dependency or review gate is waived.

## Acceptance record

On 2026-10-29, in this lead-intake chat, Juan stated directly: **“I accept”**.
The immediately preceding response identified the R3.4 lookup-first recovery
contract at `0f3c1732a4f33ff99c5928626615fc6d52a73999`, tree
`b79d391eb7c105ee3d898fdcdb2699a3f627a223`. That is the accepted revision.

Oversight's unconditional CONTRACT PASS at that exact revision, after verifying
the unchanged dependency merge and retarget to main, is mailbox `0affa42e` and
[the retarget review](https://github.com/canfieldjuan/connect-automate/pull/63#issuecomment-6504816185).
The operator's statement supplies acceptance; the review alone does not.

The accepted Contract and original stack-review request below remain verbatim.
Their proposal-time status passages describe the reviewed snapshot; this record
states the current status. The acceptance-only commit recorded acceptance and
parent completion without source, tests, configuration, dependency or
contract-design changes.

The acceptance-only head passed Linux/Windows checks, oversight delta review and
connector review with no findings before its guarded merge. The implementation
below began afterward, on a separate branch, with unchanged parity and the
declared fail-first proof. Transport, protected-host activation, inference,
extraction, application adoption and other slices remain excluded.

## Implementation execution record

The accepted text from `## Contract` onward remains unchanged. Its proposal-time
status and gap passages are historical; this record states the implementation's
current evidence and remaining gates.

The existing `_CustodyHandoff` now owns `recover(request=...)`: canonical request
and runtime pins, concrete metadata observation, historical workflow lookup,
closed result validation and exact receipt join. Known history keeps its lookup
schema. Only validated `not_found` calls the existing resume once with the
canonical request and unchanged fence. Unknown outcomes never become absence.
There is no source lock across workflow access, opportunistic retry, receipt
shortcut, SQL, schema or public interface change. All prior methods in this
composition are AST-identical to the merged contract baseline; frozen source
owners and prior tests are byte-identical.

Measured Linux evidence on Python 3.13.11:

- Unchanged affected baseline at `4bd562639e54531962782875eda14daa0fd147b3`:
  **3419 passed in 440.58s** before the source edit.
- Declared lost-response/revoked-key regression failed at the missing recovery
  entry, then passed with historical access forbidden from body/auth/writers and
  dispatch. Direct resume continues to refuse the revoked key.
- Final new tests: **168 passed in 59.14s**. They include native spawn/reopen,
  crash and SQL failures at observed writes, lost replies, overlapping recovery
  and upload, and lifecycle changes between lookup and fresh authorization.
- Unchanged adjacent tests: **1206 passed in 209.15s**. These overlap the baseline;
  their counts are not added to claim unique coverage.
- **26** isolated guard-removal probes fail their intended regression tests;
  Ruff reports **All checks passed!**. The two new files are in native Windows
  selection from the first implementation push; Windows execution is pending CI.

Local repairs are retained in the evidence: the initial instance revalidation
used the wire alias incorrectly, fixed at this new call site with field-name
validation; the new process file initially omitted its imported fixture's
dependency, corrected in that file; a null scope corruption was caught by a
later access instead of its intended guard, replaced by valid mismatched scope
and capture fixtures. The latter now independently kill their guard removals.
No existing schema, owner or test was changed to accommodate these repairs.

Evidence alias: `custody-r3-recovery`; `manifest.json` SHA-256
`11f8aa6d7bc212edb24df98c464c01a3a9f18965c76598c3dcfe98e59027c6d7`.
The packet pins executable inputs, commands, raw results, failed attempts,
counterfactuals and the frozen-owner audit outside the checkout.

**Gap audit: NOT DONE.** The separate implementation PR still needs exact-head
Linux/Windows CI, oversight PASS and reconciled connector review before guarded
merge. This proves a private library slice, not a receiver, machine authorization,
retention-policy qualification, inference integration or application adoption.

## Contract

### Root cause and verified inventory

The missing behavior is recovery orchestration, not a defect in fresh resume.
R3.3 deliberately authenticates retained source bytes on every submission.
After a lost response, a caller should first recover an already committed
workflow outcome without requiring the old content or signing key to remain
usable. Calling resume alone cannot provide that behavior.

All CONFIRMED source citations below are in `canfieldjuan/connect-automate` at
the pinned, unmerged dependency above. Source paths are beneath
`src/connect_automate/`. Documents are intent, not execution evidence.

| Classification and finding | Evidence at the pin |
| --- | --- |
| **CONFIRMED:** the concrete private composition owns canonical request validation, runtime/route/machine/store pins, raw submission and reference-only resume. It has no lookup-first recovery method. | `lead_intake/custody_handoff.py:43-150`. |
| **CONFIRMED:** resume observes the exact capture, reads retained bytes and revalidates the original receipt before sharing workflow completion. It always reauthenticates, even on replay. | `lead_intake/custody_handoff.py:121-150`; `automate/runtime.py:308-429`; `tests/test_lead_custody_resume.py:217-235`. |
| **CONFIRMED:** source metadata observation validates handoff, scope, machine and the full capture through a query-only snapshot. Envelope access is denied by its SQL authorizer. | `lead_intake/custody_store.py:73-93`; `lead_intake/source_store.py:212-214,583-599,774-823`. |
| **CONFIRMED:** retirement cleanup can remove the source receipt while preserving the capture, closed handoff and historical `ever_custodied` fact. Missing receipt cannot be treated as proof that nothing committed. | `tests/test_lead_custody_store.py:415-426`; `lead_intake/source_store.py:798-812`. |
| **CONFIRMED:** historical workflow lookup validates binding, event, pack revision and expected payload digest, and returns the existing closed lookup model without admission or dispatch. | `automate/runtime.py:265-279,431-472`; `lead_intake/results.py:28-73`. |
| **CONFIRMED:** existing tests exercise historical results after source revoke, expiry, purge, retirement and retired cleanup, and lookup with source writers, clock and dispatch forbidden. | `tests/test_lead_joined_lifecycle.py:229-251`; `tests/test_lead_runtime_results.py:378-418`. |
| **CONFIRMED:** lookup failure is classified as unknown, not absence. `accepted`, durable `no_match` and `not_found` have distinct closed projections. Submission and lookup have distinct schemas. | `automate/runtime.py:431-472`; `lead_intake/results.py:28-73`; `tests/test_lead_runtime_results.py:473-488`. |
| **CONFIRMED:** workflow's receipt reference contains scope/event/payload identity but not the full envelope/capture identity. Binding recovery to a handoff therefore still requires source-owned metadata observation. | `lead_intake/receipts.py:26-34`; `lead_intake/custody_protocol.py:61-75`; `lead_intake/source_store.py:785-823`. |
| **INFERRED:** these existing owners can support a small lookup-first composition without storage, protocol or workflow-engine changes. | The exact operation and proof obligations below; the proposed joined path is not implemented. |
| **UNKNOWN:** real machine authorization, durable transport operation mapping, external inference integration and installed application adoption. | These are excluded from this private-library proposal and cannot be qualified by its synthetic fixtures. |

### Validated inventory and explicit porting differences

Reuse the signed synthetic envelopes, trust snapshots, clocks, no-action pack,
concrete source/workflow stores and process fixtures already exercised by the
dependency. No real mailbox, customer data, model, prompt or inference setting is
involved. In particular, retain these existing proofs unchanged:

- `tests/test_lead_custody_resume.py:40-110,217-235`: closed-source reopen,
  body-state/reservation behavior, replay identity and mandatory authentication.
- `tests/test_lead_custody_resume_recovery.py:37-42,183-224`: reference-only child
  packet, persisted-state oracle, observed commits and lost responses.
- `tests/test_lead_joined_lifecycle.py:229-251`: historical results survive source
  lifecycle changes; source refusal and workflow history are independent.
- `tests/test_lead_runtime_results.py:378-418,473-488`: no writer/body/dispatch
  on lookup and no failure-to-absence fallback.
- `tests/test_lead_custody_store.py:405-426`: snapshot consistency and retained
  metadata after cleanup.

Recorded dependency evidence is reused, not rerun for a documentation-only
change. At the tested input set published as the pinned dependency, the affected
suite completed with **3419 passed** in disjoint groups, with Ruff clean and
**14** isolated guard-removal probes killed. One preceding combined run ended
with exit **143** and no result; it is not counted as a pass and its cause remains
unknown. The completed groups cover the same test set. This is Linux evidence;
native Windows and independent review remain dependency merge gates.

Evidence alias: `custody-r3-runtime-resume`; `manifest.json` SHA-256
`343e946d59054441054bb9ef7a776eae59ab6c262453def7b17bd4533c2afe49`.
The manifest records commands, runtime/environment, inputs, raw outputs and
interrupted-run disclosure. This contract's scope audit must verify that the
tested input hashes are unchanged. This evidence does not test R3.4.

| Proposed departure | Reason and invariant preserved |
| --- | --- |
| Add a private `recover(*, request: ResumeRequest)` operation to the existing `_CustodyHandoff`. | Choose history or fresh resume in one bounded call; no new engine, API service, state store or generic scheduler. |
| Observe metadata and look up workflow before any content read/authentication. | Preserve exact handoff/capture association while allowing known history after source eligibility ends. |
| Return an existing lookup or submission value, keeping its schema. | A historical observation is not a newly authorized submission; do not invent applied flags. |
| Call existing resume only after a validated `not_found` lookup. | Every attempted workflow creation still crosses the existing fresh authentication and fence owners. |
| Add tests for branch choice, joined identity and recovery races. | Reuse the existing native harness and state oracles; no changed source, result or lifecycle policy. |

No unlisted behavior, runtime/model configuration or retention difference is
authorized. A required frozen-owner change requires a contract revision first.

### Required change surface after acceptance

| Owner / file | Smallest allowed change |
| --- | --- |
| `src/connect_automate/lead_intake/custody_handoff.py` | Add private lookup-first recovery using its existing canonical/pinning helper, concrete source observation, runtime lookup and existing resume. Own the new join and branch choice here; no SQL, state, callback or duplicated completion. |
| New `tests/test_lead_custody_recovery.py` | Positive paths, canonical/identity boundaries, historical-vs-fresh distinction, lifecycle and refusal/error preservation. |
| New `tests/test_lead_custody_recovery_process.py` | Extend the existing native fixture pattern locally for lost response, reopen and competing recovery/lifecycle operations; retain the original state oracles. |
| `.github/workflows/ci.yml` | Include both new files in native Windows selection from the first executable push. Linux already runs all tests. |
| This contract | Record exact acceptance before code and measured results afterward. |

`automate/runtime.py`, `results.py`, `receipts.py`, `custody_protocol.py`,
`custody_store.py`, `source_store.py`, `content.py`, `admission.py`, `auth.py`,
`handoff.py`, workflow storage, schemas, dependencies, public exports and prior
tests remain unchanged. The current PR changes only this proposal and a parent
navigation note. It contains no implementation or new test inputs.

### Proposed operation and ownership

`_CustodyHandoff.recover(*, request: ResumeRequest)` returns either the existing
`SourceHandoffLookup` with `accepted`/`no_match`, or the existing
`SourceHandoffResult` from fresh resume. Preserve the discriminating schema and
all existing flags. It does not return a new wire/result model or synthesize an
R1 resolved/unresolved response. This is a private recovery building block for a
later receiver, not the complete prepare/upload/status/resume/settle adapter.

The trusted host and concrete owners remain those of R3.3. The caller provides
only the request, never raw bytes, a lookup, receipt, observation, admission ID,
prepared event, replacement owner, callback or a choice to skip lookup.

1. Reuse `_checked_request(request, ResumeRequest)` and consume its canonical
   return. Validate runtime, route, source deployment, enrolled machine,
   source-store object/incarnation and no-action pack before any store access.
   Keep operation discrimination and current license enforcement.
2. Call `custody.observe` with the exact canonical handoff, full scope, machine
   and capture. This binds the persisted handoff to this lookup; it is not source
   or machine authorization. Missing metadata raises `SourceContentUnavailable`
   without an absence/settlement claim. Mismatched metadata keeps the source
   owner's conflict. Do not look up a different event or adopt a legacy receipt.
3. Use the source-validated observation's event and persisted capture payload
   digest with `runtime.lookup_source_outcome`, using the pinned route binding.
   Finish the source read snapshot before entering the workflow owner. No source
   body, writer, source clock, current signing key or content deadline is needed
   for this historical lookup. Do not use envelope hash as payload digest.
4. Validate the returned closed lookup and its join to the observation. For a
   known outcome, require historical `ever_custodied`, exact host/organization/
   namespace/event/payload/recovery-deadline identity and no action entries. If a
   source receipt remains, require full `ReceiptReference` equality using the
   shared reference fields, including admission ID and accepted-at. Never compare
   the wider source receipt object directly with the narrower reference model.
   If retirement cleanup removed that receipt, the validated workflow receipt,
   preserved capture and historical custody fact may supply history; do not
   require the removed receipt or fabricate a replacement. Inconsistent joins
   are unknown, with no fallback or source write.
5. Return a known lookup unchanged in meaning, with `workflow_applied=False` and
   no `source_applied` field. Closure, stale-but-well-formed expected generation,
   expiry, purge and revoked signing authority do not turn this historical
   result into fresh submission or prevent its observation. This does not waive
   the initial host/license/route/store checks. Do not report current body
   availability from the workflow projection.
6. Only a successfully validated `not_found` lookup permits one call to existing
   `resume(request=canonical_request_value)`. Pass the unchanged expected
   generation; do not refresh it from the observation. Return the real submission
   result. Resume must observe and freshly authenticate through its own owners
   again; no earlier observation or lookup is submission authority. Missing
   receipt, stale fence, expiry and revocation preserve the resume refusal.

No catch-all converts an error/conflict/refusal into `not_found`. Do not perform
an internal retry, second opportunistic lookup after a failed resume, upload,
settlement, recapture, re-signing or new event allocation. A later explicit call
starts with history again and can resolve a workflow committed before a lost
response. No operation-journal or exactly-once-delivery claim is introduced.

### Transactions, races and refusal semantics

There is no cross-database atomic snapshot. The initial source observation and
workflow lookup are separate read transactions. History is an observation, not a
permission lease or promise that raw content remains available. No source lock
is held across workflow access. The fresh branch retains R3.3's successful
revalidation-commit authorization point and unchanged completion behavior.

If another process commits after `not_found`, existing resume/event idempotency
must return the same workflow identity where still authorized. If eligibility
ends first, refusal is correct even if another process meanwhile committed; a
later call may recover that history. Never refresh the caller's fence to make a
race pass. A lifecycle change after successful revalidation does not retroactively
cancel the already authorized in-call completion. Historical generation checks
and fresh generation checks are intentionally different responsibilities.

Preserve fixed public errors: canonical/pin refusal is `EventBindingError`;
missing observation is `SourceContentUnavailable`; source conflicts/busy and
fresh authentication refusals keep their existing owner errors. Unavailable,
corrupt or uncertain stores, malformed/inconsistent owner outputs and unexpected
exceptions become `SourceHandoffUnknown`, raised outside the caught handler so
no sensitive cause/context escapes. Existing runtime lookup/license/pack/event
refusals remain refusals. Every exceptional path performs no fresh resume unless
an actual valid `not_found` preceded it. No result implies permanent absence.

### Explicit non-scope, risk and rollback

No transport dispatcher/journal, source mutation/schema change, new workflow
engine, R1 result mapping, prepare/upload/settle orchestration, public API,
provider activation, machine enrollment, employee authorization, polling,
background retry, UI, extraction, CRM, Watcher/EOM/Atlas or installation changes.
Shared AI inference is a separate initiative; this operation invokes no model
and defines no model-provider interface to replace later. Local-first extraction
will use the shared inference boundary under its own accepted work order.

Main risk: mistaking historical evidence for fresh authority, or treating a
failed lookup as absence. Keep those branches explicit and prove each guard
independently. No frozen-owner redesign is an acceptable shortcut. Rollback
disables callers of the new private recovery method, preserving all stores,
history and existing upload/resume/lookup operations; no downgrade or deletion.

### Assumptions and blockers

- The private trusted host already holds valid deployment configuration. Machine
  references are not authentication; this proposal creates no external access.
- Exact source-owned intent/capture metadata must still be readable. A missing,
  corrupt or replacement source store cannot be bypassed to associate arbitrary
  workflow history with a handoff. Standalone runtime lookup remains unchanged;
  recovery is not a promise of availability after all source metadata is lost.
- The dependency must pass its own gates and merge before this contract merges.
  Re-pin and review any changed dependency; do not count its old proof for new
  executable inputs. This proposal needs exact-revision operator acceptance
  before implementation. Oversight's review does not provide that authority.
- Any required change to a frozen owner or accepted behavior blocks executable
  expansion until a revised contract is reviewed and accepted.

### Verification plan after acceptance

Run unchanged affected parity at the merged, accepted contract first. Declare a
fail-first regression: create a real managed workflow, lose the response, revoke
the original source key, reopen with only references, then call recovery. Before
implementation, failure must be the missing recovery entry. Afterward it must
return the exact historical lookup while content/authentication/writers/dispatch
are forbidden. Existing reference-only resume must still refuse the revoked source.

| Proof | Required assertions |
| --- | --- |
| Known history | Accepted and durable no-match; exact original identity after advancement; close, stale valid generation, expired reservation/content, revoked/expired key, purge, retirement and retired cleanup. No source write, body read, source clock, dispatch or resume; preserve lookup schema and flags. |
| Fresh branch | Source-only state, valid body-only and unavailable-body envelopes, expired reservation with live retained content, replay and closed current generation. Only real not-found permits resume; exact original receipt, no duplicate workflow, real result schema/flags. |
| Admission boundaries | Wrong/missing/mixed/copied request fields, operation, full scope, route, machine, capture/digest pair, incarnation and action-bearing pack; zero/false/empty/min/max/above-max values. Refuse before the prohibited owner is called; consume the canonical copy. |
| Join integrity | Independently corrupt every receipt scope/digest/deadline, admission/accepted-at equality, historical custody fact, action list and lookup projection. Each fixture reaches its intended check, not an earlier guard. Retired receipt absence with valid history succeeds; incompatible or unproven history is unknown. |
| Failure versus absence | Lookup input/conflict/license/pack refusals, unavailable/corrupt stores, bad owner output and unexpected errors never call resume. No private body/path/SQL/exception-chain exposure. Valid no-match is not retried as absent. |
| Process recovery | Reuse native spawn/SQL/checkpoint harnesses and exact persisted-row oracles. Lost reply after workflow commit then purge/revoke; source-only gap; restart with reference-only child packet; recovery/recovery and recovery/upload races; not-found followed by competitor commit or lifecycle change. No cross-owner held lock or invented source receipt. |
| Counterfactuals and parity | Remove each new branch/identity guard independently and demonstrate its intended regression failure. Preserve all prior tests and lifecycle rules, run affected adjacent evidence plus Ruff, include both new files in Windows from first push, and require Linux/Windows CI and exact-head independent reviews. |

### Implementation summary and cold diff audit

No implementation is authorized or included. This PR adds the proposed bounded
contract and parent navigation only. It does not change source, tests, fixtures,
dependencies, workflow configuration or the accepted R3.3 contract. Cold audit
must prove that delta against the pinned parent, verify local citations and
existing proof input hashes, and distinguish inherited code from this PR's diff.

### Gap audit

**NOT DONE.** Parent review/merge, this contract's review and exact-revision
operator acceptance, and all proposed executable proof remain outstanding.
Full receiver composition, protected machine/transport authorization, retention
qualification and application adoption remain separate work. No production
readiness, completed lead intake or merged dependency is claimed.

## Oversight stack review request

Review PR #62's implementation first against its accepted R3.3 contract. Then
review only this contract delta against that exact head, plus the combined
direction against the architecture foundation and parent sequence. In particular:

- Is `_CustodyHandoff` the correct single owner of this bounded join/branch?
- Does metadata observation preserve handoff/capture binding while history stays
  independent of source-body/signing-key eligibility, including retired cleanup?
- Do the distinct lookup/submission results prevent history becoming authority,
  and do races/refusals preserve source and workflow owners without new state?
- Does the slice advance receiver recovery without duplicating inference,
  transport, dispatch or storage, and without claiming the full receiver exists?

Give each PR its own exact-head disposition; a combined direction check is not a
blanket PASS. If PR #62 changes, update this stack normally without force-pushing,
re-pin the contract and invalidate affected prior review. After PR #62 merges,
retarget this PR to main and verify its net diff is still documentation-only,
then satisfy its exact-head CI/oversight/connector gates before merging.
