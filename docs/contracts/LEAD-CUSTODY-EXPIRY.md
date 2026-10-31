# V1a: expired-unfenced custody status

Status: **PROPOSED. Contract only; exact-revision acceptance and a separate
implementation PR are required. No transport or live access authorized.**

This is the bounded work order for [issue #66](https://github.com/canfieldjuan/connect-automate/issues/66),
the first step of the accepted [vertical-delivery plan](LEAD-VERTICAL-DELIVERY.md#acceptance-record).
Acceptance of that plan selected the ordering and direction, not this work order.

## Baseline and root cause

Repository: `canfieldjuan/connect-automate`, merged main
`de23b6e055b090f7fe02ac8cf10633571fc7d3c6`. All source citations below refer to
that revision. `LI/` abbreviates `src/connect_automate/lead_intake/`.
Proposals and required tests below are not claims of implemented behavior.

| Finding | Evidence at the baseline |
| --- | --- |
| **CONFIRMED:** an open, never-custodied, capture-absent intent is projected as `prepared`; the result validator rejects it when the reservation deadline is at or before observation. The exception becomes unresolved `unknown`. | `LI/custody_handoff.py:327-367`; `LI/custody_protocol.py:193-209`. |
| **CONFIRMED:** this conservative result is intentional legacy behavior, including the exact expiry boundary. | `tests/test_lead_custody_status.py:632-667`. |
| **CONFIRMED:** the source owner already supplies the persisted deadline, actual generation/revision, admission identity, closure/custody facts and one checked observation time. | `LI/source_store.py:198-230,851-885`; `LI/custody_store.py:115-133`. |
| **CONFIRMED:** custody result `1.0` and precise status result `1.1` have separate closed parsers/encoders. The status model inherits existing phase/combination rules. | `LI/custody_protocol.py:161-293,342-357`; `tests/test_lead_custody_status.py:105-124`. |
| **CONFIRMED:** status validates runtime/route/machine/store references, and its source observation requires exact capture equality. An absent capture hint cannot adopt a concurrently bound capture. | `LI/custody_handoff.py:142-180,269-297`; `LI/source_store.py:851-861`. |
| **CONFIRMED:** binding and settlement already have writer owners. Binding checks capture time, reservation/recovery deadlines and policy; settlement checks current references, operation identity and generation, and commits closure. | `LI/custody_store.py:158-171`; `LI/source_store.py:952-969,1061-1128`. |
| **CONFIRMED:** source clock-floor validation and clock-history writes are separate. Status checks the floor without advancing it. | `LI/source_store.py:851-885,1298-1320`; `tests/test_lead_custody_status.py:1101-1118`. |
| **UNKNOWN:** protected receiver authentication, transport negotiation and installed-product behavior. These private reference checks do not prove machine authentication. | Scope boundary in `LI/custody_handoff.py:1-5`; no such capability is claimed by this work order. |

The missing distinction originates in the closed result vocabulary and its private
projection, not in transport or a caller's timeout handling. Blame identifies the
prepared-state rule in `f540b41a`, its time-comparison update in `d2bbc4a6`, and
the status projection in `6b0b8f17`. These are this arc's prior choices, retained
under their accepted contracts. This is a versioned capability addition, not a
retroactive claim that legacy `unknown` was a defect. This work order adds no
downstream workaround to infer this state from an `unknown` reply.

## Validated inventory and permitted differences

Reuse the existing synthetic fixtures, real SQLite owners, configured UTC clock,
query-only authorizer, spawned-process barriers and canonical encoders. There is
no inference model, prompt, chat template, external provider or real message in
this lane. The runtime is the existing private `_CustodyHandoff` over a loaded
`PackRuntime` with the no-actions restriction; its owner pins stay unchanged.

Historical evidence was read and its hashes checked while drafting; these are
recorded results, not tests executed for this contract:

| Evidence alias and SHA-256 | Recorded coverage and limits |
| --- | --- |
| `custody-status-composition/manifest.json` — `689544ac39fcce45d6bdc46c4f734cc4088a611f5752b1b56cd58f543eb6293f` | Head `6b0b8f1707e8937e8a98bf9e9269247dab22d453`; status suites recorded `326 passed`, adjacent suites `1849 passed`. Its mutation claims are subject to the later isolated-fixture repair below. |
| `custody-status-composition/review-g1-20261030/manifest.json` — `f7cf8bfbfce8a0ae3acf8300002a19c01252b532f6cafc5bb1c5e75ec9b3705a` | Head `563c4510ab7310dc16f3436ad0a17f1c6af46a54`; repaired status suite `253 passed`, focused checks `11 passed`; production unchanged. Preserve the repaired independent receipt/content/retirement checks, not only the earlier aggregate count. |
| `custody-status-composition/merge-20261030T174117Z/manifest.json` — `499ee6b8f254b9c4ff8c55a370fc93f3d4c702edc8f374b11ef780b9bb06036b` | Stored exact-head `test` and `windows-placement` conclusions are `success` at `563c4510ab7310dc16f3436ad0a17f1c6af46a54`. Historical qualification does not qualify the proposed version. |

Current regression owners include `tests/test_lead_custody_protocol.py`,
`tests/test_lead_custody_status.py`, `tests/test_lead_custody_status_process.py`,
`tests/test_lead_custody_store.py` and `tests/test_lead_custody_races.py`.
The existing status matrix uses microsecond offsets around expiry
(`tests/test_lead_custody_status.py:632-667`); existing spawned tests exercise
snapshot/writer ordering and restart (`tests/test_lead_custody_status_process.py:324-418`).
These are the starting proof, not a substitute for new-version assertions.

| Permitted difference | Reason and invariant |
| --- | --- |
| Opt-in status result `1.2`, with a closed expired-unfenced variant | Represent a known source snapshot without inventing a fence; preserve old versions' inputs, outputs and rejection behavior. |
| Private `status_v1_2(request=...)` on the existing composition | Explicit selection without changing existing callers or adding a receiver. |
| One shared status execution path with version-specific result construction | Reuse all current reference, corruption and historical-join checks; avoid divergent status readers. |
| New synthetic assertions in the existing protocol/status/process test owners | Prove both the distinction and legacy parity, using real store transactions and process barriers. |

No other departure from the inventory is authorized. If implementation needs a
source-store, writer, authentication, storage or time-policy change, report the
evidence and revise this work order before expanding its scope.

## Versioned contract and ownership

### Vocabulary owner: `LI/custody_protocol.py`

Add separate `1.2` resolved/unresolved models and codecs. Keep the following
existing APIs and their canonical bytes unchanged:

- result `1.0`: `parse_untrusted_result` / `canonical_result`;
- status result `1.1`: `parse_untrusted_status_result` / `canonical_status_result`;
- request `1.0`, nested workflow lookup `2.0`, signed source and receipt formats.

The proposed names are `ResolvedStatusResultV12`,
`ExpiredUnfencedStatusResultV12`, `UnresolvedStatusResultV12`,
`parse_untrusted_status_result_v1_2` and `canonical_status_result_v1_2`.
All remain private library vocabulary. No public export, capability registry,
media type, request negotiation or default-version change is included.

The ordinary resolved `1.2` variant preserves the legacy resolved phase and
combination rules. The separate expired variant uses required closed fields and
literal/null types, so impossible combinations are excluded by its model/schema:

| Field | Required value or constraint |
| --- | --- |
| `schema_version`, `status` | `"1.2"`, `"resolved"` |
| `capture_phase`, `reason` | `"expired_unfenced"`, `"settlement_required"` |
| `handoff_id`, `scope` | Actual validated source identifiers; existing identifier/reference types |
| `state_revision`, `fence_generation` | Actual source snapshot values; existing bounded revision type; never request hints |
| `observed_at` | Existing exact decision-time format, sampled by source owner; no rounding or replacement clock |
| `reservation_expires_at` | Required non-null existing deadline type; deadline <= observation |
| `capture`, `workflow`, `source_receipt`, `unavailable_reason` | Required explicit null, not omitted and not a permissive optional object |
| `content_state` | `"not_received"` |

Use the existing closed-model and typed/discriminated-union mechanisms to select
the ordinary resolved, expired resolved and unresolved variants. Do not widen a
legacy parser or use a permissive model followed by a duplicate regex/filter.
For the new phase's field relationships, only the cross-field chronological
comparison needs a named semantic validator; reuse the existing timestamp parser.
Preserve canonical validation, duplicate-key
rejection, exact-bytes input, input-free errors, concrete-model revalidation and
the existing `4096`-byte result cap across every new variant. Copied or constructed
models must pass the same validation as parsed data. Unknown versions and wrong
codecs fail closed; there is no negotiation fallback or version relabeling.

All unresolved `1.2` replies use the existing closed unresolved codes and carry no
invented source facts. Result syntax is an untrusted claim, not proof that the
claimed state existed or a capability to read content or perform an operation.

### Projection owner: `LI/custody_handoff.py`

Add `_CustodyHandoff.status_v1_2(*, request: StatusRequest)` returning the new
union. Keep `status(request=...)` emitting only `1.1`. Both delegate to one
private status path with an internally fixed supported version; no caller
string/default coercion. Preserve the checked-request boundary, fixed error
mapping, canonical output validation and minimal unknown fallback.

The common path reads exactly the existing source-owned observation. It validates
the same concrete fact types, strict booleans, request identity, scope, capture,
admission/ever-custodied equivalence, receipt/content consistency and runtime pins
before selecting a result. Then, in this precedence order:

1. Ever custodied: preserve the existing historical workflow lookup, receipt
   reconciliation, content availability and retirement behavior.
2. Never custodied, closed: preserve `fenced_empty`; expiry cannot erase a fence.
3. Never custodied, open, capture present: preserve `upload_possible`; expiry
   cannot erase a bound capture or become proof of safe upload/retry.
4. Never custodied, open, capture absent: preserve `prepared` strictly before the
   validated deadline. At/equal/after the deadline, emit `expired_unfenced` only
   on the new path; the existing path still emits unresolved `unknown`.

The new branch additionally requires no persisted admission, no receipt, source
content `not_received`, no unavailable reason, and a valid persisted deadline
and source observation time. Invalid or inconsistent metadata cannot be rescued
by an expiry comparison. Missing intent remains `not_found`; storage/clock
failure remains `unknown`; reference conflict remains `conflict`. Runtime,
binding, pack and license errors retain their existing exception behavior.

There is no workflow lookup on the uncustodied branch, no content read, no second
source observation, no submission/resume/settlement call and no action dispatch.
The only changed old code may be the bounded factoring needed to share this
status path. Submit, resume, recover and their owners retain their behavior.

### Source, time and mutation owners remain unchanged

`SourceCustodyStore.observe_status` and the source store own the query-only
snapshot and time check. The projection uses their returned timestamp and facts;
it does not compare the reservation with a second wall clock. `observed_at` is
the sample taken while that source snapshot is held, not a globally atomic view
of source and workflow state, nor proof of the latest state at response delivery.
A writer may have committed after the read snapshot was pinned.

`expired_unfenced` means the validated source snapshot has no committed custody
and its reservation is expired at the supplied observation time. It does not
mean closed, canceled, deleted, purged, source missing, workflow failed or future
custody impossible. It does not advance the clock floor or persist expiration.
An allowed corrected/backward clock above the floor can change a later projection;
a clock below the floor must yield uncertainty. Only a committed writer operation
establishes the corresponding durable fence/lifecycle change.

## Caller reconciliation and authorization

This slice adds no caller, scheduler or permission. A future authenticated receiver
must authorize every observation and any separate mutation using its then-current
machine/organization/route policy. Configured references and a parsed status
result are not authentication. Private-library tests can prove reference
isolation and writer policy behavior, not protected receiver authorization.

An authorized caller may separately request `settle` using the observed scope,
capture reference and actual fence generation. It uses the existing operation
identity and writer path. The writer, not this status result, decides whether
the request matches current state and can commit closure. Replaying an identical
settlement observes that owner's existing replay semantics; changing a replayed
request or using stale generation/references is not a new permission.

If binding/admission/closure won the race, preserve its current conflict/refusal
or committed result. Do not overwrite it, infer cancellation from an old status,
adopt an unseen capture, reset an operation ID, renew the reservation, recapture
bytes or create a new event to escape uncertainty. A subsequent status observation
is a new read, not replay of a durable cached result. A lost status response has
no effects to recover. Transport replay/caching policy remains a later contract.

## Required change surface and explicit non-scope

After acceptance, the bounded implementation may change:

- `LI/custody_protocol.py`: new closed models/codecs; reuse existing scalar
  owners and validators without changing legacy acceptance/rejection.
- `LI/custody_handoff.py`: private opt-in entry point and shared status path.
- Existing protocol/status/status-process test files: additive fixtures and
  assertions. Existing tests and expected legacy bytes/results stay unchanged.
- Completion/verification records in this work order. Windows already selects
  these test files (`.github/workflows/ci.yml:50-54`); no CI change is expected.

Do not change source tables, schemas/migrations, source/writer/clock/auth owners,
workflow lookup or record formats, public exports, dependencies, capability or
transport registration, Email Watcher, lead records, list UI, CRM adapters, EOM,
retention policy, shared inference runtime or deployment configuration. No new
engine, poller, database owner, service or dispatch mechanism.

## Verification plan

Start implementation with a declared failing new-version test and capture the
exact missing capability; do not weaken the legacy expiry assertions. Prove
parity with unchanged existing tests before and after the shared-path factoring.
Retain synthetic inputs and real owner transactions; don't replace the existing
spawned harness with mocks or timing sleeps. The obligations below are planned,
not passed gates.

| Proof | Required assertions |
| --- | --- |
| Version boundary | Each codec accepts only its own concrete models/version; old codecs reject new phase/version. New ordinary results match old values except version. Canonical old bytes and all existing tests stay unchanged. Reject coercions, duplicate/missing/extra keys and wrong nested lookup versions. |
| Expiry boundary | Open/unbound before, exactly at and after deadline, including adjacent microseconds. Only new at/after results are expired-unfenced. Closed, bound and custodied cases at the same times retain precedence; custodied retention expiry remains independent. |
| Closed state shape | Reject every non-null forbidden field independently, absent/null/malformed deadline, future deadline, malformed observation time, wrong content/reason/phase and mixed valid/invalid nested references. Check valid min/max revisions and result-size boundaries as well as zero, false, empty, negative and over-limit inputs. Reject copied/constructed models that evade normal construction. |
| No effects | Spy on forbidden content/submit/resume/recover/settle/action paths and use actual query-only SQL authorization. Compare source/workflow rows, generations, revisions, clock history and operation rows before/after success, fallback and lost response. No body bytes or sensitive exception text in results/logs. |
| Owner isolation | Wrong host/org/namespace/route/machine/event/capture and replacement store fail at existing owners. Keep current runtime/license/no-actions checks. Status hints never override actual generation. Revoked source-signing authority does not fabricate absence or disable historical observation; attempted new effects still use their existing authority checks. Do not claim this proves machine authentication. |
| Corruption | One otherwise-valid fixture per newly touched check, including strict boolean types, admission/custody consistency, receipt, content, clock and deadline. A premature guard must not mask the target guard. Mutation evidence must kill the claimed behavior; label equivalent predicates honestly rather than counting them as killed. |
| Clock and replay | Bad/throwing/naive clock and below-floor sample give uncertainty without writes. Clock jump/correction affects projection only. Same reference after reopen/lost reply reads current state; stale prior result cannot cause capture, renewal or action. Preserve admin-only clock-floor reset and persisted purge behavior. |
| Real process ordering | Reuse spawned source-snapshot barriers for writer before snapshot, writer after snapshot pin/before time sample, and writer after source release/before response. Cover bind/admit/settle and both commit orders using legal pre-deadline writer clocks or a writer already in progress; do not grant late upload permission to make a race test pass. A null-capture request against a now-bound row conflicts; an older pinned snapshot may still report expired-unfenced. Capture-bound committed history is read only with exact authorized references. |
| Separate settlement | Through the existing writer: expired observation then successful settle; settle or bind wins first; stale generation, changed capture and replayed operation conflict/refuse or replay according to that owner's contract. Status itself never settles. Assert actual persisted fence, not merely a returned label. |
| Restart/failure | Native child exit before/after read and before response, reopen and reread; writer rollback versus commit is visible according to snapshot order. SQL errors and missing/replaced stores never masquerade as a fence/absence. No partial rows or invented receipts. |

Run the focused fail-first/regression and adjacent protocol/status files locally,
plus Ruff on the touched surface. Let required CI own duplicated broad suites.
The new cases live in files already run by Linux and native Windows from the first
implementation push; both must pass. Carry forward unchanged custody writer,
recovery and source auth/clock tests rather than inventing parallel policy tests.
Record tested head, commands, fixtures, assertions, outputs and limitations in a
durable evidence directory outside worktrees, with manifest aliases/hashes.

## Assumptions, blockers, delivery and rollback

**INFERRED:** the existing snapshot contains every fact needed; no owner extension
is necessary. Implementation must prove that at the pinned baseline and report
any contradiction before scope expands. **UNKNOWN:** future protected caller
authorization and deployment qualification; they remain blocking before transport
exposure, not a reason to claim this private slice supplies them.

Delivery order: review and accept this exact contract revision; merge the accepted
contract with normal gates; then open one bounded implementation PR with separate
vocabulary and composition/proof commits. If the change exceeds that scope, split
or revise explicitly. No executable work begins from a peer PASS alone.

Merge gates: exact-head Linux/Windows CI, oversight PASS, reconciled connector
review, no unresolved threads or changes requested, clean local/remote parity,
guarded merge commit and reviewed-tree equality. This work contributes bounded
G0/G3 evidence; it does not pass the complete source-handoff, recovery, privacy or
live-product gates. Issue #66 remains open until the accepted implementation and
proof land; a docs-only merge must not close it.

Regression risk is concentrated in sharing the existing status path and codec
selection. Legacy parity and independent corruption tests gate that refactor.
Rollback needs no migration: stop using the opt-in private method and retain
legacy `1.1` unknown behavior. Never downgrade a `1.2` payload by editing its
version or treating expired-unfenced as a fence. Any later transport adoption
requires its own negotiated compatibility/rollback plan.

## Implementation summary, cold diff audit and gap audit

This PR adds only this proposed work order and a receiver-roadmap pointer/status
update. It changes no code, tests, configuration or accepted vertical-plan text.
The cold audit checks source citations at the pinned base, owner/compatibility
coverage, legal race schedules, existing proof reuse, explicit authentication
limits and documentation-only scope. Code tests are not run for this proposal.

**NOT DONE:** exact-revision acceptance, implementation, new regression/process
proof, native-platform CI and exact-head review/merge gates remain. This document
is a reviewable proposal, not an implementation or production-readiness claim.
