# R3.2: source-owned retained-content read

Status: **PROPOSED — contract only; implementation is not authorized.**

R3.1 merged in [PR #57](https://github.com/canfieldjuan/connect-automate/pull/57)
at `a9cdf8b2d7e538bdf204076d75c567e43392bb0b`. Its reviewed tree is
`bec25d68975e9123ebad1bdcd1db7704370951d8`. The operator's request to check
oversight and continue starts this next contract. It is not an acceptance record
for the design below. Independent contract review and exact-revision operator
acceptance must precede a separate executable PR.

This is the source-read prerequisite for reference-only resume. It does not
implement the receiver's complete resume operation. The
[parent sequence](LEAD-RECEIVER-CUSTODY.md#bounded-implementation-sequence-and-verification),
[R2 retained revalidation rule](LEAD-CUSTODY-STORAGE.md)
and [R3.1 composition](LEAD-CUSTODY-COMPOSITION.md) retain their ownership.

## Contract

### Root cause and source inventory

Inventory pin: `canfieldjuan/connect-automate`
`a9cdf8b2d7e538bdf204076d75c567e43392bb0b`. Paths below are repository relative;
source paths beginning `lead_intake/` or `automate/` are under
`src/connect_automate/`. Line references describe this pin.

| Finding | Evidence at the pin |
| --- | --- |
| **CONFIRMED:** managed raw submission cannot recover source-only custody after upload closure or reservation expiry. This is an intentional R3.1 limit. | `tests/test_lead_custody_composition_recovery.py:292-316` preserves a receipt and no workflow record after the raw retry refuses. |
| **CONFIRMED:** the source owner already supports exact retained-custody revalidation, including closure and expired upload reservations. | `lead_intake/custody_store.py:155-165`; `lead_intake/source_store.py:1068-1105`; `tests/test_lead_custody_store.py:1326-1352,1579-1600`. |
| **CONFIRMED:** revalidation consumes raw bytes supplied by its trusted local caller. It does not retrieve them. It checks current source authentication twice under the source writer. | `lead_intake/admission.py:152-170,196-209`; `lead_intake/custody_store.py:156-165`. |
| **CONFIRMED:** `SourceContent.read_content(admission_id)` is the privileged content-read owner. It validates custody/content and lifetime, records clock progress, and commits terminal expiry before reporting unavailable. | `lead_intake/content.py:45-98`; `lead_intake/admission.py:84-138`. |
| **CONFIRMED:** that reader accepts an admission ID only. It has no expected handoff, capture, generation or incarnation argument. The generic transaction validates the stored incarnation's shape, not equality to a caller's retained incarnation. | `lead_intake/content.py:75-98`; `lead_intake/source_store.py:522-580`. |
| **CONFIRMED:** exact metadata observation is already available and does not retrieve the envelope. It is a separate snapshot from a content read. | `lead_intake/custody_store.py:72-92`; `lead_intake/source_store.py:198-209,814-823`; `tests/test_lead_custody_store.py:351-405`. |
| **CONFIRMED:** a privileged retained read may succeed after source-key revocation; current-key authorization belongs to revalidation before workflow submission. The read verifies original custody against historical authority. | `lead_intake/admission.py:107-138`; `tests/test_lead_source_content.py:102-111`; `tests/test_lead_custody_store.py:1593-1600`. |
| **CONFIRMED:** existing request vocabulary already contains a closed, reference-only `ResumeRequest`, complete scope/capture and expected generation. | `lead_intake/custody_protocol.py:61-109,140-143`. |
| **CONFIRMED:** historical workflow lookup and raw submission have different owners and meanings. | `automate/runtime.py:281-407,409-450`; `lead_intake/results.py:59-73`. Neither changes here. |

**INFERRED design consequence:** observing metadata and then calling the generic
admission-ID reader cannot guarantee that the expected handoff/incarnation and
generation still match when the blob is accessed. A later revalidation can stop
workflow submission, but cannot undo an earlier wrong bound read. This is a
missing prerequisite for the proposed composition, not a claim that an active
receiver currently exposes this path. Put the bound-read checks inside the
existing content owner's writer transaction.

**UNKNOWN / outside this slice:** protected machine authentication, employee
authorization, installed receiver operation and cross-application retention.
Synthetic local host construction does not qualify any of them.

### Inventory of validated work

Reuse the existing synthetic source envelopes and clocks, `managed_request`,
`managed_operation`, `reader`, `upload_setup`, the source-content fixtures, and
the native-process custody lifecycle harness. No inference model, model settings,
prompt or remote provider is involved in these fixtures.

Fresh inventory proof at the pin: **`25 passed in 9.85s`**, with all inventoried
source, tests, dependencies and CI inputs unchanged. Runtime: Python `3.13.11`,
pytest `8.4.2`, Pydantic `2.13.5`, Linux `7.0.0-38-generic-x86_64-with-glibc2.39`.
Durable alias `custody-r3-retained-read-contract`; `inventory-manifest.json`
SHA-256 `3b088f9a85325847783bfe6add2a823bf2b9158ac3e1234b312e906a624142eb`.
The packet retains the exact command, input digests, runtime and raw output;
`existing-seams.txt` SHA-256
`f78a1627acfedf426a77bd9682110e89d20193b258de67c9301dfcd17ab2f71d`.

That run exercises reopen, expiry equality/final sample, terminal expiry after
clock reconciliation, revoked-key privileged read, metadata observation,
incarnation mismatch, closed retained revalidation after restart and the R3.1
source-only recovery gap. It qualifies existing seams, not the proposed method.
No new managed-read test or native Windows run is claimed in this proposal.

### Required change surface after acceptance

| Owner/file | Smallest allowed change |
| --- | --- |
| `lead_intake/content.py` | Extract the existing in-transaction content-read body into one private helper shared by the unchanged legacy entry and a new private managed entry. The managed entry verifies the retained incarnation, exact handoff/capture, generation and linked receipt under that same writer before any envelope access. Keep expiry/clock/content validation at their existing owners. |
| `lead_intake/custody_store.py` | Add private-library facade method `read_retained(request) -> bytes`. Reuse `_request(request, "resume")`; delegate to the concrete content owner with this facade's store, clock and retained incarnation. No SQL, callbacks or independently supplied content reader. |
| New `tests/test_lead_custody_retained_read.py` | Reference-only boundary, shared-reader parity, process ordering, expiry/crash and current-authorization separation tests. Reuse existing fixtures and process helpers; do not rewrite earlier tests to pass the new behavior. |
| `.github/workflows/ci.yml` | Select the new file on Windows from the first executable push. Linux already selects all tests. No other workflow/dependency changes. |
| This contract | Append acceptance and measured implementation evidence; keep the proposed semantics stable unless independently reviewed and accepted again. |

`source_store.py` remains the SQL/schema, incarnation and handoff-metadata owner;
reuse `_incarnation(..., expected)` and `_custody_request_state` inside the content
owner. `admission.py` remains the one custody-content validator and fresh source
authentication owner. No changes to either file are needed by this proposal.
An implementation needing another owner or new semantics must report that gap
before broadening the work order.

### Proposed operation and invariants

`SourceCustodyStore.read_retained(request)` is a privileged, local library read
over an already established handoff. It accepts only the existing `ResumeRequest`,
round-tripped through the existing canonical parser so copied/forged model values
cannot skip validation. The caller supplies no raw bytes, admission ID, receipt,
source result, replacement store, content reader or authority callback.

1. Reuse the facade's configured store, trusted clock and explicitly retained
   incarnation. Never read a new incarnation and enroll it automatically.
2. Acquire the content owner's existing source writer once. Inside it, compare
   the actual incarnation to the retained one, resolve the exact handoff through
   the source metadata owner and compare full scope, enrolled-machine reference
   and complete capture. Check the expected generation against the current one.
3. Require already-linked, retained custody with a valid receipt. Derive its
   admission ID from the validated source facts in that transaction. Never infer
   custody from an event ID alone, adopt a legacy receipt or create missing rows.
4. Before selecting an envelope, all of those bound-read checks must succeed.
   Reuse the existing content validator, lifecycle checks and both clock samples.
   Return the original canonical envelope bytes only after a successful commit.
5. Equality at the signed recovery deadline refuses content. Preserve the existing
   commit-then-unavailable expiry path: close managed admission and purge expired
   content atomically, then raise outside the completed transaction. An exception
   that rolls back this terminal expiry is a regression.
6. Open and permanently closed handoffs may be read with their current generation
   when retained content is still eligible. Upload reservation expiry alone does
   not prohibit that read or extend the signed recovery deadline. Stale requests
   do not get an automatic generation refresh. Closure never reopens admission.
7. Return bytes only. A signed envelope whose body is explicitly unavailable is
   still retained source content; do not confuse body completeness with custody
   lifetime or invent body fields.

This method is not query-only: the inherited clock and terminal-expiry effects
are intentional. It creates no receipt, content row, workflow event or transport
operation; normal successful reads preserve the handoff's identity and generation.
Read expiry may close that handoff through the existing lifecycle owner. Repeated
reads may advance the existing clock audit and must not create another audit
system, upload slot, resume journal, queue or raw-byte cache.

The private host remains responsible for access to this facade. The request's
machine/proof/control/job references are validated values, not authentication.
This slice adds no durable resume-job mapping or proof consumption. Do not expose
the method through Connect, HTTP, CLI, an employee UI or another public export.
The stored enrolled-machine reference is compared, but control/job/proof IDs are
shape-validated only: they are not matched to the earlier prepare/upload IDs and
do not become authentication or idempotency guarantees for a receiver operation.

### Read permission and submission permission remain separate

Preserve the privileged reader's existing historical-authority validation and
revoked-key read behavior. A returned envelope never authorizes a workflow event.
The later runtime-resume work order must pass it through the existing
`revalidate_existing` path, with fresh source authentication and the current fence,
before using shared runtime completion. Do not call legacy `admit_source` for a
reserved event, accept a caller's copied receipt or treat a successful read as a
fresh authentication result.

The eventual receiver recovery coordinator still checks historical workflow
metadata first, as required by the parent contract. Known workflow status remains
read-only and need not read content. That coordinator, its result mapping and
runtime resume entry are deliberately absent from this prerequisite slice.

### Failure and concurrency contract

Use existing bounded exception owners and preserve sanitized messages/chains:

| Condition | Required outcome |
| --- | --- |
| Wrong operation, malformed/copied model or invalid scalar | `SourceStoreInputError`, before acquiring a writer or reading content. |
| Request deployment/full scope/capture mismatch or wrong retained incarnation | Existing `SourceStoreConflict`; no envelope access. |
| Stale expected generation | Existing `SourceAuthenticationError`; no envelope access. |
| Unknown intent, never-custodied/closed-empty intent, purged/retired or legitimately erased content | `SourceContentUnavailable`; no invented final-absence or workflow claim. |
| Corrupt/inconsistent metadata, blob or schema; inaccessible store | Existing `SourceStoreUnavailable`; no raw output or implicit repair/migration. |
| Signed content expiry | Commit the existing terminal expiry, then `SourceContentUnavailable`. |
| Clock rejection, writer timeout or uncertain commit | Preserve the existing source owner classification. No bytes return on an uncertain commit. |

The scope/capture guards precede the lifecycle-availability decision; the metadata
owner may refuse corruption before any operation-specific check. Do not mask a
corruption exception as ordinary unavailable content. Unknown history never means
closed-empty, and a failed read never means no earlier source receipt exists.

Checks before acquiring the writer are validation only. The bound identity and
generation comparisons that protect the body read occur after contention resolves,
inside the transaction that performs that read. No adapter SQL or outer observe-
then-read check substitutes for them. No callback runs under the source writer
apart from its already trusted clock.

A read that wins the writer may return its eligible bytes before a later purge,
closure or retirement. If the lifecycle mutation wins first, the read observes
the new state and refuses where required. No promise of erasing bytes already
returned is made. Later submission must revalidate after the read; this operation
does not hold the source writer across a workflow call or claim atomic authority
across source and workflow databases.

### Explicit non-scope and rollback

No changes to runtime, `custody_handoff.py`, shared handoff/result/event owners,
source authentication, schemas/migrations, public signatures/exports, R1 models,
retention policy or numeric capacities. No service, receiver result synthesis,
job journal, Watcher body capture/retry, mailbox access, inference, CRM, EOM,
dependency pin, installer, native protected-host qualification or adoption.
The nonblocking loading-docstring issue remains separate.

Rollback disables the unused new private method. Keep stores, receipt history,
fences, clock records and terminal expiry intact; no downgrade, reset, deletion
or reopening is a rollback step.

### Differences from the qualified inventory

| Proposed difference | Why it is necessary / proof required |
| --- | --- |
| Add request-bound retained read | The existing admission-ID API has no handoff/generation/expected-incarnation checks. Prove each new binding guard before the first envelope access, including independent host and organization cases. |
| Share the old content-read transaction body | Keep one owner for validation, clock sampling and terminal expiry. Prove old reader tests unchanged and compare the extracted logic; no intentional legacy behavior difference. |
| Reuse existing private source helpers from content owner | Resolve bound facts under the same writer; no second metadata validator or SQL in the facade/runtime. Prove replacement-store and both contention orders. |
| Add a new synthetic test file and Windows selection | Exercise the actual boundary and native process behavior on both supported platforms. No live data or fixture changes. |

There are no model, prompt, runtime-setting, source-format or retention-policy
differences. Any additional difference discovered during implementation must be
listed and reviewed before the port proceeds.

### Verification plan after acceptance

Start from current main, record any change from the inventory pin, and run the
unchanged source-content/custody parity lane before source edits. Declare the new
missing-entry fail-first probe before running it. Then implement only the surface
above and preserve failures and corrective evidence outside the worktree.

| Gate | Required reproducible proof |
| --- | --- |
| Positive parity | Open retained, closed retained at current generation, expired upload reservation with live content, reopen, all body-availability states and repeated reads return exact original bytes. No receipt/content creation or new operation slot. Existing host read and R3.1 tests remain unchanged. |
| Bound identity | Each pinned handoff/scope/capture/machine field, actual incarnation and generation independently drifts, including separate host and organization cases. Use a first-envelope-access sentinel so a later clock/lifecycle guard cannot hide the missing check. Each security guard's individual mutant must fail at its intended assertion. |
| Parser/negative boundary | Wrong operation; partial/mixed/forged models; missing capture; unsupported values and R1 scalar boundaries, including false/zero/empty/default cases. Downstream code uses the canonical validated request. Fresh valid control/job/proof references do not change read authority; malformed values refuse. Reuse R1 limits rather than introducing another validator. |
| Authority separation | Privileged read of eligible revoked-key custody preserves legacy behavior; a subsequent existing `revalidate_existing` rejects current revocation. A read result or copied metadata never authorizes a workflow or substitutes for current-source authentication. |
| Time and lifecycle | Before/equal/after recovery deadline, deadline crossed at the final sample or while waiting, backward clock and permitted administrative reconciliation; expiry remains purged after reopen/reset. Full-message cutoff and namespace retirement preserve existing meanings. |
| Native process ordering | Separate processes show actual writer blocking, not sleeps: read-first and close/purge/retire-first; stale generation after waiting; new store incarnation; no lock held for any workflow operation. Reuse existing lifecycle/lock actors and recorded checkpoints. |
| Crash and recovery | Crash before read, after envelope access but before commit, and after commit before response. Retry from fresh processes preserves identity, clock/expiry rules and no resurrection. A commit fault returns no bytes; inspect real persisted rows and classifications after reopen. |
| Privacy / query-only parity | Synthetic body markers must not enter logs, errors, exception chains, control metadata or durable diagnostics. Existing `observe` continues to deny envelope SELECT, perform no clock/write, and return metadata only. No secure memory erasure claim. |

Run the new file, the complete affected source-content/custody files and applicable
lint/diff checks locally because the legacy reader is being extracted. Reuse the
existing process harness and parity fixtures. CI owns the duplicated full suite;
Windows must run the new file from the first executable push. Exact-head Linux and
Windows success, oversight PASS, connector reconciliation, clean local/remote
equality and no unresolved review findings remain merge requirements.

## Implementation summary

None. This PR proposes the source-owned bound read and updates the parent index.
Existing code and fixtures are unchanged. The current proof verifies only the
inventory, not a new reader or complete reference-only recovery.

## Cold diff audit

Only this contract and the parent work-order index may change in this proposal.
Source, tests, fixtures, dependency and CI bytes must match the recorded inventory.
The acceptance record is intentionally absent until the operator accepts the
reviewed contract revision. No implementation or production readiness is implied.

## Gap audit

**NOT DONE — independent contract review and operator acceptance pending.**
After acceptance, implementation and its native proof require a separate PR.
Runtime resume composition, receiver result/status/settlement mapping, durable
transport operations and protected service adoption remain later work orders.
