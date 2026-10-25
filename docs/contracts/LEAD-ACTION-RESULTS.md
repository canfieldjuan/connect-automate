# Lead source action results: submit and lookup

Status: **ACCEPTED WORK ORDER — IMPLEMENTATION AUTHORIZED; DELIVERY NOT COMPLETE.**

Work item: [connect-contracts#76](https://github.com/canfieldjuan/connect-contracts/issues/76).
This amendment covers the Automate half of Lane C. Commit this contract separately,
send its exact revision to oversight, and stop before executable implementation.
Oversight review does not substitute for operator acceptance.

## Operator acceptance

Juan directly accepted the reviewed contract at
`634d5297bf8d0d99cd36cb331858f826237c6a8a`:

> I accept the work order

The exact contract received oversight PASS in
[PR #47](https://github.com/canfieldjuan/connect-automate/pull/47#pullrequestreview-5640869912).
This acceptance authorizes implementation within the named surface and ownership
reservation. It does not establish native proof, merge, adoption or installed
caller verification, or authorize the excluded application/host work.

## Root cause and pinned inventory

Baseline: `canfieldjuan/connect-automate` at
`1326fcfba45fa26235e1154c4a67f0a1b8638d5a`. Source citations below refer to that
revision. Tests listed here are existing proof inputs, not newly qualified results.

| Status | Owner and evidence | Finding |
| --- | --- | --- |
| CONFIRMED | `src/connect_automate/lead_intake/results.py:22-44,65-86` | The closed public projection has workflow metadata but no action outcomes. It cannot distinguish an accepted workflow with a failed action from one whose actions settled. |
| CONFIRMED | `src/connect_automate/automate/runtime.py:329-354` | Submission constructs the result before dispatch and returns it only when every returned action is settled. Known failed and pending states fall through to `SourceHandoffUnknown`. |
| CONFIRMED | `src/connect_automate/automate/runtime.py:356-394` | Lookup projects the stored workflow receipt without action state. |
| CONFIRMED | `src/connect_automate/automate/actions.py:253-264,281-302,325-355` | Failed and settled actions are terminal. Only pending actions enter existing safe recovery; an unconfigured adapter can leave an action pending. |
| CONFIRMED | `src/connect_automate/automate/store.py:84-97,1704-1721` | Actions are admitted atomically with the workflow event, with a per-event maximum of eight and keys owned by the committed workflow event. |
| CONFIRMED | `src/connect_automate/automate/store.py:891-909,1116-1159,1858-1877` | Receipt lookup has a consistent query-only snapshot. Existing `list_actions` opens a writable connection and cannot be used to implement read-only public lookup. |
| CONFIRMED | `src/connect_automate/automate/definition.py:414-423` | Lead source event definitions currently admit only `notify.local` actions. This amendment does not widen that vocabulary. |
| CONFIRMED | `tests/test_lead_runtime_results.py:12-26,58-65,375-416,807-843`; `tests/test_lead_host_composition.py:60-85` | Real signed-source/pack fixtures, durable stores, read-only lookup assertions and failed/pending replay witnesses already exist. Reuse these owners. |

Introducing changes: `f852e7246e93a1845d7d1f80a7a1286d3ec0057a` introduced the
closed action-free result; `d55fcbde866536f3eac66bccf4c90f8ebce9f699` constructed
it in submission; `fc76748ef1ce3c2782875c32240405bae3143edd` added the settled-only
return condition. That repair prevented false delivery success but left known
failure indistinguishable from uncertainty. Repair the result owner and its
construction; remove this now-redundant settled-only condition. Do not compensate
with caller retry loops, error-string parsing or a second downstream classifier.

### Reproduced before the contract

Run from the pinned checkout:

```sh
uv run --locked python /home/juan-canfield/Desktop/codex-evidence/connect-automate/action-result-contract/baseline_probe.py
```

The probe reuses the existing signed fixtures and real source/workflow stores with
synthetic data and local notification adapters. A missing notification title
produces durable `[failed, settled]`; an empty adapter registry produces durable
`[pending, pending]`. In both cases first submission and replay raise the fixed
unknown error, and lookup says `accepted` without any action field. Replay does
not change action rows or increase adapter calls. Settled and no-action controls
return normally. This witnesses the current defect, not a passing regression for
the proposed behavior. No service, model, prompt or production credential is used.

Durable evidence aliases and SHA-256, outside worktrees under
`connect-automate/action-result-contract`:

- `baseline_probe.py`: `9e1f627a935d8da83ca385014c41152fcd9b1e131d21285e8354c9b82a3d570c`
- `baseline-probe.json`: `b6a15f7e7c6c45a9942de4f7e1b76f15482d0e0fbdab48a2ae4cd4a99695f241`

This is a library execution witness on the current host. Native Windows proof,
installed application delivery and adoption have not been established by it.

## Observable behavior and versioned result contract

Keep the public method names and keyword-only request arguments. Both methods
return their existing schema names with **`schema_version: "2.0"`**, retaining the
existing workflow/source fields and adding a required `actions` JSON array. Each
array element is a closed object containing exactly:

| Field | Required value |
| --- | --- |
| `action_id` | The persisted canonical UUIDv4 action identity. |
| `kind` | Literal `notify.local`, the existing admitted lead event action kind. |
| `status` | Exactly `pending`, `settled` or `failed`. |

The array contains every action belonging to this result's **workflow event**,
in durable admission order, with no duplicate action IDs, at most eight elements,
and no truncation. Producer event IDs, workflow event IDs and action IDs remain
distinct. Exclude actions of later operator decisions, other workflow events,
other records and other bindings. Do not expose request/result payloads, titles,
bodies, last errors, paths, dedupe keys, adapter exceptions or credentials.

Event-owned actions are rows with the same `record_id` and a `dedupe_key` beginning
with `ACTION_DEDUPE_PREFIX + workflow_event_id + ":"`, ordered by ascending `rowid`
(admission order, equal to index order within the committing transaction).

Missing, null, coerced, unknown or extra values fail closed. `actions: []` means
that this event admitted no actions; it is not a fallback for a read failure.
Both `no_match` and lookup-only `not_found` require an empty array and preserve
their existing null workflow projections. All existing strict flags, identifier,
stage, state-version and receipt constraints remain. Final serialized models
must remain within the existing `MAX_EVENT_BYTES` limit of 8192 UTF-8 bytes.
The model module remains importable without loading runtime/store/admission owners.

`workflow_outcome: accepted` continues to mean workflow admission, never action
delivery success. Source/workflow applied flags retain their current meanings;
lookup has no source-applied flag and always has `workflow_applied: false`.

| Known state | Submit and lookup result | Caller obligation |
| --- | --- | --- |
| Accepted, no actions | `accepted`, `actions: []` | No action delivery was requested by this event. |
| All actions settled | `accepted`, each action `settled` | Those actions completed under the existing adapter/outbox contract. This does not declare the whole workflow complete. |
| Any failed action | `accepted`, that action `failed`; retain sibling statuses | Surface terminal failure for operator attention. Never retry the failed action or mint a new source event to conceal it. |
| Any pending action | `accepted`, that action `pending`; retain sibling statuses | Delivery is unresolved. Existing safe recovery may settle or fail it; pending does not prove the external effect did not run. |
| Recorded no-match | Existing `no_match` projection, `actions: []` | Do not invent an action or a workflow record. |
| Scoped receipt absent | Lookup's existing `not_found` projection, `actions: []` | This is absence at that read, not a guarantee against a later concurrent commit. |
| Trustworthy complete projection unavailable | Fixed `SourceHandoffUnknown` exception | Look up the same scoped event or retry the same signed request under existing authorization and recovery rules. Absence, success and retryability are not asserted. |

Mixed settled/failed/pending arrays preserve every state independently. There is
no aggregate success Boolean and no priority rule that hides pending siblings
when another action failed.

### Submission, lookup and uncertainty

Submission still authenticates the original signed bytes on every call, including
replay. License, binding, signature, custody, revision, conflict and ambiguity
refusals retain their existing bounded exceptions and ordering. A copied result
or receipt never becomes submission authority.

Validate workflow/receipt integrity before dispatch, preserving the current
invalid-projection no-effects guard. Perform only the existing dispatch attempt.
After normal dispatch, obtain a complete store-owned action snapshot and return
the known projection regardless of whether statuses are settled, failed or pending.
If dispatch raises an unclassified operational exception after known admission,
attempt one read-only outcome snapshot; return it if fully known, otherwise raise
the fixed unknown exception. Never dispatch again to discover an outcome. Known
bounded refusals, including license refusal, still propagate instead of being
converted to a result by this recovery read.

Source/workflow commit uncertainty before a trustworthy admission outcome remains
unknown. A failed action-state read or invalid internal projection remains unknown,
never an empty array, terminal failure, success or not_found. Unknown retains the
exact input-free message `lead source handoff outcome unknown` and no sensitive
exception context/cause. A returned, validated failed/pending state is not itself
an operational exception.

Lookup uses the same public projection/validation owner and reads the historical
receipt and its current action statuses within one query-only store snapshot.
It never authenticates source content, samples the source clock, opens a source
or workflow writer, admits work, dispatches, or calls recovery. It works without
a configured source admission owner under the existing licensed binding checks.

Workflow identity, stage and state version describe the original admission.
Action statuses describe the durable snapshot observed by this call and may
advance from pending to settled/failed later. Equal snapshots yield equal action
projections through both APIs; sequential calls racing recovery need not match.
Never hold a read transaction across adapter delivery. A crash after admission
leaves pending actions visible to lookup; only existing idempotency/locking/CAS
rules decide whether recovery can execute them. Terminal actions remain terminal
across submit replay, recovery sweeps and process restart.

### Compatibility and precisely listed departures

This is a breaking change to a closed result schema, so do not publish it under
`1.0`, silently default a missing action field, or pretend old consumers accept
it. Runtime methods emit only `2.0` after adoption; callers must use the matching
result contract/library revision. No optional flag selects the old misleading
projection, and old serialized `1.0` results are not execution authority.

Only these departures from the inventory are proposed:

1. Closed result version changes from `1.0` to `2.0` and requires the bounded array.
2. Known failed/pending submissions return that result instead of unknown.
3. A dispatch exception can return a known durable snapshot when the bounded
   recovery read proves it; unreadable/uncertain cases remain unknown.
4. Lookup includes event-owned current action statuses without gaining effects.

Source receipts, signed envelopes, workflow vocabulary/pack versions, canonical
bytes, grants, storage schemas and existing persisted data do not change. Old
durable events are projected from their existing rows; no migration is needed.
This amendment supersedes only the action-free result and failed/pending-as-unknown
clauses in `LEAD-SOURCE-HANDOFF.md` (baseline lines 1031-1048 and 1139-1154), not
the remaining source, custody, authorization or host contracts.

## Required change surface and ownership

| Owner | Necessary implementation delta after acceptance |
| --- | --- |
| This session: `src/connect_automate/lead_intake/results.py` | Closed action items, versioned result validation and one public projection owner. Keep operational imports out. |
| Shared: `src/connect_automate/automate/runtime.py` | Only submit/lookup projection construction, pre-dispatch validation and the bounded post-dispatch read/error mapping described above. Preserve generic submit/decision behavior. |
| Shared: `src/connect_automate/automate/store.py` | Extend the existing source-receipt query boundary with an event-owned action snapshot in its current read transaction. SQL, ownership filtering and durable ordering stay in the store; do not reach into its tables from result/runtime code or reuse writable `list_actions` for lookup. |
| Shared: `tests/test_lead_runtime_results.py` | Reuse the real fixture path, amend obsolete failed/pending-as-unknown expectations and closed-version payloads, and add focused origin regressions here so the existing native Windows lane includes them. |
| This contract | Record acceptance, exact implementation/evidence revisions and completion gaps without rewriting unrelated accepted contracts. |

The lead-intake session retains the rest of lead_intake and its protected-read
work. Coordinate the named runtime/store/test hunks with that owner **before
editing any shared file**. Coordination request `c13421c2` was sent through
oversight while this checkout had no source changes. On 2026-10-25, oversight
relayed lead-intake's confirmation: those named hunks are reserved to this lane,
with no conflicting source edits. The reservation covers only the named surface;
further shared changes require coordination. It does not waive operator acceptance.

## Explicit non-scope

No action retries or retry API, new action kinds, adapters, automatic result
triggers, workflow completion decisions, second queue/dispatcher, source retention
changes, protected-host implementation, sign-in/transport changes, database schema
or migration, shared Connect protocol/SDK edits, lockfile/dependency changes,
application pin bumps, new CLI/UI/service endpoint, model work or live external
effects. Do not relax authentication, license checks, receipt integrity, pending
recovery policy or terminal-state exclusion. No unrelated refactor or formatting.

## Assumptions and blockers

- Operator acceptance of this exact behavioral/version amendment is recorded
  above. Peer PASS alone does not authorize a later behavioral amendment.
- Shared-file ownership for the listed runtime/store/test hunks is confirmed as
  recorded above. Reconfirm if that reservation or the required surface changes;
  it is not authority to modify the other active lane.
- The selected action is the already-supported local notification. Test fixtures
  may deliberately fail it; no real mail, calendar or provider send is required.
- Installed consumer identity and adoption revision remain UNKNOWN. At baseline,
  production call sites in this repository expose the two library methods only;
  `automate/host.py:76-89` is a licensing entry point. Before adoption, identify
  the actual supported installed caller and its owner. Do not invent an endpoint
  or mark a test host as installed user acceptance. New application work needs
  its own agreed ownership/scope; keep the issue open if that prerequisite is absent.

## Verification plan

Contract-only verification: validate pinned citations, rerun only the isolated
baseline witness if its inputs change, inspect the complete document diff, run
`git diff --check`, and prove the contract-only commit changes no executable inputs.
Do not rerun application suites for this documentation change.

After acceptance, preserve the defect sequence in the implementation PR:

1. **Reproduce:** turn the durable witness into a minimal regression in the existing
   runtime-result test file. Declare the expected failure: valid durable failed or
   pending actions produce Unknown/missing action projection on the unmodified base.
   Retain the exact command, head, input and failing assertion/exception.
2. **Isolate/explain:** name the introducing commits above and the result/construction
   owner. No caller workaround; remove the settled-only return condition after the
   complete projection replaces it.
3. **Fix/prove:** the same original cases pass through real public submit and lookup;
   stable action IDs, row statuses and adapter-call counts prove terminal actions
   are not redelivered on replay, recovery or restart. Kill the regression by
   removing the origin fix, with an assertion/behavior failure rather than setup error.
4. **Sibling/boundary probes:** empty, one and eight valid actions; reject nine,
   missing/extra/duplicate items, null/false/zero/empty/wrong versions and fields,
   malformed UUID/kind/status, mixed settled/failed/pending at either end, and
   other-event/record actions. Retain no-match/not_found, strict flags, Unicode
   stage/result-byte limits, lazy imports, source/license/binding/revision refusals,
   no fabricated defaults, and sensitive-error non-disclosure. Valid input must
   still pass; invalid input must fail at the real owner.
5. **Error/concurrency probes:** dispatch error plus readable snapshot versus
   unreadable snapshot, commit uncertainty, crash before dispatch, pending recovery
   to settled and failed, and a paused read racing settlement in a separate process.
   Prove snapshot consistency and lookup's no-source/no-writer/no-dispatch behavior,
   including failed/pending variants. Keep existing safe recovery and native locks.
6. **Adjacent/integration gates:** run the focused runtime-result file, affected
   source-receipt/read-only-store and action/event callers, applicable Ruff checks,
   then required Linux/native Windows CI at the published implementation head.
   Reuse existing broad CI rather than duplicating it locally without new cause.

Record exact-head oversight PASS, automatic Codex connector review/reconciliation,
green required CI, zero unresolved threads/no open changes-requested, clean local
tree and local/remote equality before the guarded merge commit. Do not request a
manual Codex review. Record the merge/tree evidence on the issue.

Then prove the built/installed library artifact exports the changed public
contract, and qualify the agreed installed caller: a real supported action failure
must be visible through submit and lookup, remain terminal after restart, and not
be presented as successful delivery. An isolated synthetic library proof is not
adoption or installed application proof. Record artifact/revision identities and
durable evidence by alias/hash; have the reviewer verify and close the issue.

## Implementation summary and cold diff audit

This increment adds only `docs/contracts/LEAD-ACTION-RESULTS.md`. The executable
baseline probe and its output are retained outside the checkout. Source, tests,
dependencies, workflows and existing contracts remain unchanged. No proposed
schema or runtime behavior is implemented by this document.

Cold audit must check this file against the pinned owners, its proposed observable
behavior and the recorded witness. Any implementation delta beyond the named
surface needs an explicit contract revision and acceptance before proceeding.

## Gap audit

**NOT DONE.** Current-state reproduction and the proposed behavioral contract are
recorded; operator acceptance and the named shared-file reservation are confirmed.
Source repair, regression proof, native qualification, exact-head reviews, merge,
adoption and installed
caller verification remain. Report each delivery stage separately as
`native-proved / merged / adopted / installed-verified`; none is claimed here.
