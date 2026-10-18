# Pack vocabulary: mail and schedule intake

Status: ACCEPTED at revision `3dd9121bc90cd462bde9c8a5803d24c1938dc864`.
Juan answered **"Accept (Recommended)"** on 2026-10-18; oversight relayed it
verbatim in mailbox message `e59f058f`. Acceptance is recorded separately
before implementation; the behavioral requirements below are unchanged.
Work: issue #5. This document does not authorize application adoption.

## Operator decision and acceptance boundary

The accepted question was:

> Accept the Connect Automate contract for issue #5, mail and schedule triggers (commit 3dd9121)? Three limits to know: (1) a matching email or a scheduled time only puts a new item into 'ready for review' and shows a notification on this machine; the actual action still waits for your approval, so this is not hands-free yet. (2) It is library groundwork only: no app listens for mail or runs a schedule until a separate adoption decision. (3) The connect-automate package code itself changes, but the apps stay pinned to their current version, so app releases are unaffected.

The relayed selected option was:

> I relay this word for word. The pack-kit session records your acceptance in its own commit, keeps the existing pack format and its tests byte-identical, then builds test-first with Linux and native Windows proof. It opens one PR for my review. No app changes, no version-pin bump, no First Public Release milestone.

On 2026-10-18, Juan said **"lets continue"** in response to the recommendation
to keep Email Watcher's existing automations built in and use packs for add-on
automations. That settles trigger ownership for this contract: an independently
configured host supplies events to packs; Email Watcher's built-in rule engine
continues to own its existing automations. It does not approve a vocabulary,
implementation, application change, or pin bump in advance.

This phase changes this contract alone. Commit it separately and submit its
exact revision for oversight review and operator acceptance. Stop before code.
An accepted revision must be recorded before test-first implementation begins.

## Root cause and inventory of proven work

Reference: fetched `origin/main` at
`10a13395ff495f1c23c931ef6cfcb5788f0f4706`, after the pack-kit merge.
Paths beginning `automate/` below are relative to `src/connect_automate/`.

| Existing owner | Behavior to preserve or reuse |
| --- | --- |
| `automate/definition.py:85`, `Trigger` | Only `operator.decision` is admitted. Mail and timer events cannot be represented. |
| `automate/definition.py:319`, `Workflow`; `canonical_workflow`, `parse_workflow` | Strict closed models, materialized defaults, duplicate-member rejection, bounded canonical UTF-8 JSON. No workflow vocabulary version field currently exists. |
| `automate/engine.py`, `submit_decision` | License and pack/record ownership checks precede replay; recorded outcomes precede stage re-matching; no-match is durable; effects and action intents commit together. |
| `automate/store.py`, `_SCHEMA`, `apply_effects`, `reserve_no_match` | SQLite immediate writer, immutable ledger, record-version compare-and-set, and record-scoped operation keys. These do not deduplicate an event that creates another record. |
| `automate/pack.py`, `PackManifest`, `load_pack`, `verify_grant` | Envelope, manifest and grant format version 1; publisher verification and separate subject-bound grant verification. Pack revision and format version are different concepts. |
| `automate/runtime.py`, `PackRuntime.load`, `submit_decision` | Verified runtime construction, defensive workflow copies, pack-version freeze on records, and dispatch after intent commit. Grant verification occurs at load; license is checked on subsequent admission/dispatch. |
| `automate/actions.py`, `ActionRunner` | Frozen persisted requests, stable action/job identity, terminal outcome replay and recovery restricted to adapters declaring idempotence. Delivery is not a transaction with an external system. |
| `locking.py`, `operation_lock` | Native process locks on supported desktop platforms, refusal of a soft-lock fallback, bounded nonblocking acquisition. |
| `tools/pack_kit/`, `tests/test_pack_kit*.py`, `tests/fixtures/pack_kit/` | Accepted approve-then-act authoring, golden canonical artifacts, offline real-runtime checks, check-before-sign, private-seed handling and no-replace publication. |
| `tests/test_automate_definition.py`, `test_automate_engine.py`, `test_automate_store.py`, `test_automate_pack.py`, `test_automate_runtime.py`, `test_automate_actions.py` | Existing parser, ownership, replay, transaction, grant, outbox and recovery regressions. Reuse these lanes rather than replace them with source-text assertions. |

The earlier kit proof is recorded by qualification packet alias
`qualification.json` at reviewed head
`98850ecf809a6defa0a3ddc90c6f56b9858eb549`, SHA256
`85c82bb613650e32bfb5551fcdddf597f24ce9f92ac8d44c45735ae26867574e`;
its constituent artifacts and hashes are listed there. The unchanged v1 golden
fixtures remain regression inputs.
There is no validated mail/schedule implementation or prior event-intake result
to port. New trigger behavior below is proposed, not qualified. No model,
prompt, chat template, inference settings, live mail account or scheduler service
is involved. Tests use explicit clocks, synthetic events, development keys and
injected fake adapters/apps, with the existing offline runtime harness.

Every intended difference from that inventory is listed here:

1. Explicit v2 workflow and manifest admission, retaining v1 bytes and behavior.
2. Typed host-supplied mail and schedule events, never synthetic operator decisions.
3. Source/occurrence receipts whose scope survives record creation and pack upgrades.
4. One transactional owner for receipt, optional record creation, ledger effects
   and outbox admission, reusing the current effect/action normalization owners.
5. Shared action delivery locking for concurrent entry points; this strengthens
   delivery serialization without promising exactly-once external effects.
6. Two opt-in kit archetypes for event intake followed by existing operator approval.
7. V2 automatic replay uses the existing adapter-idempotence policy; v1 decision
   replay retains its current pending-action continuation behavior.
8. V2 event definitions may emit only `notify.local`; effects and other actions
   still use the existing vocabulary, with external writes behind operator decisions.

## Required change surface and explicit non-scope

After acceptance, expected owners are `automate/definition.py` and a new
`automate/events.py` for versioned models and event validation;
`automate/pack.py` for explicit manifest dispatch;
`automate/engine.py`, `automate/store.py`, `automate/runtime.py` for matching and
transactional admission; `automate/actions.py` for shared delivery serialization;
and `automate/__init__.py` for deliberate public exports. Reuse `locking.py`'s
public primitive. Extend the existing kit compiler/checker and tools-local README;
add synthetic fixtures and focused tests beside their existing owners. A shared
transaction helper is allowed only to keep one implementation of ledger effects,
outbox insertion and replay, not to introduce a parallel store or executor.

Do not change any application repository, application pin, provider transport,
connect-contracts, keyring, release catalogue, dependencies, package version,
build configuration or release workflow. Issue #5 stays outside First Public
Release. No production keys, live services, app installs or model runs.
Implementation will change this library's wheel; the kit remains outside it.
The previous kit-only byte-identical-wheel promise is not a promise about a
future vocabulary implementation. Application release isolation is provided by
unchanged app pins and separate adoption contracts, not by claiming no library
code changes.

Excluded behavior: moving built-in automations onto packs; a real mail listener;
a running scheduler; OAuth/credentials; host installation/configuration UI;
cross-record aggregation or digests; attachment/body ingestion; automatic
action-result triggers, output interpolation, retries or compensation; cron,
local-time calendars and daylight-saving rules. This contract supplies bounded
intake and two matching archetypes. It does not close the broader issue by
claiming that a digest or an unattended result chain now exists.

## Version and canonical-byte contract

- Keep the existing public `Workflow` and `PackManifest` v1 models and their
  canonical serialization unchanged. An absent workflow version means the
  existing v1 shape; do not insert a default field into its canonical bytes.
- A v2 workflow explicitly contains `vocabulary_version: 2`. Its other top-level
  fields are `name`, `stages`, `initial_stage`, `definitions`. Use distinct strict
  v2 models; reject explicit `vocabulary_version: 1`, null, booleans, unknown
  versions and extra fields rather than silently downgrading or stripping them.
- A v2 workflow requires manifest `format_version: 2`, with the existing
  `pack_id`, positive `pack_version` and `workflow` fields. A v1 manifest accepts
  only a v1 workflow; a v2 manifest accepts only a v2 workflow. Dispatch on the
  explicit format before validation; never try a permissive fallback model.
- Signed-envelope and grant formats stay at 1. The publisher signs the entire
  canonical manifest, including both version selectors and the complete trigger
  semantics. Grants remain bound to pack identity and subject. Older loaders
  reject manifest 2. Existing grants do not become publisher trust or source trust.
- Retain current workflow, effect, action and envelope size caps and canonical
  rules. Parse, build, check, sign and load use the same version-dispatch owner.
  Existing v1 golden spec/build/workflow/signed bytes must remain identical.
- Preserve the existing load-time grant verification policy; this slice does
  not claim per-event grant-expiry revalidation or anti-downgrade protection.
  License checks still precede every admission, replay and delivery.

## Event sources, host binding and strict inputs

The library exposes no event HTTP endpoint and performs no provider polling.
The trusted host authenticates its upstream sources and calls the local API.
Mail headers and event JSON are untrusted data, never proof of sender authority,
operator approval or a configured source. No module, shell, URL or file path is
executed or dereferenced from an event.

At v2 runtime load the host supplies an explicit mapping from signed trigger
binding names to immutable `SourceBinding` values: `source_id` (canonical UUID4),
`source_kind` and a nonempty opaque host scope (at most 512 UTF-8 bytes). Names
obey the existing name bound. An event cannot register or override a binding.
Missing/extra bindings, kind mismatches or aliases that make one source ambiguous
are errors. Two names for one source ID, or two source IDs for the same kind and
scope, are aliases. The store owns this invariant, including registrations under
other packs for the same subject. A v1 runtime needs no bindings and cannot accept events.
Freeze defensive copies at load; later mutation of the caller's mapping cannot
change source ownership. Take the subject from verified runtime construction,
never from an event or a caller-supplied receipt key.

The store persists each binding's subject, pack identity, name, source identity,
kind and scope. Reopening requires the same mapping; changed scope, source or
schedule policy under that binding is rejected. Source IDs remain stable across
host restarts, provider reconnects and pack revisions. Reconfiguration requires
a separately specified migration; it may not erase receipts. Reusing an identity
for another account/mailbox or timer is forbidden. These are trusted-host
responsibilities, not cryptographic authentication supplied by this library.

`PackRuntime.submit_event(*, binding: str, event: bytes, now: datetime)` accepts
one bounded immutable snapshot, with no caller-selected record ID, operation key,
effect batch, action request, approval flag or event ID for a timer. It returns
`EventRun` with `matched`, `applied`, optional `record`, optional `event_id` and
the dispatched/replayed action outcomes. A no-match has no record/event/actions.
`now` must be aware UTC. Raw JSON is at most 8192 bytes; duplicate members,
invalid UTF-8, non-finite values, unknown fields and wrong strict types fail.
Bounds are public constants owned by `events.py`, reused by kit and tests.

| Event | Required JSON fields and semantics |
| --- | --- |
| Mail | `source_kind: "mail.received"`, `message_id`, `received_at`, `sender`, `subject`. The stable provider message key is nonempty and at most 512 UTF-8 bytes, qualified by the configured source; it is not the RFC message header or a poll-attempt UUID. Sender is nonempty and at most 256 UTF-8 bytes; subject may be empty and is at most 1024 UTF-8 bytes. `received_at` is the source's immutable receive timestamp. No body, attachment or arbitrary metadata map. |
| Schedule | `source_kind: "schedule.tick"`, `scheduled_at`. The occurrence is its due instant, never delivery/retry time. Reject caller-minted IDs and payload parameters. |

Timestamps have exactly `YYYY-MM-DDTHH:MM:SSZ` form and must be valid UTC dates;
offset spellings, fractional seconds and naive timestamps are rejected rather
than repaired differently by callers. Neither event timestamp may be after
`now`. Delayed mail and old due ticks are allowed; there is no arrival-order
assumption. The host supplies the same original snapshot on retry. No runtime
clock value, retry counter or new UUID enters an occurrence identity.

## Closed trigger vocabulary and matching

V2 definitions retain the existing effect/action vocabularies and stage
conditions. Their trigger is a strict discriminated union:

- `operator.decision`: exactly today's `{source_kind, decision}` shape.
- `mail.received`: `{source_kind, binding, filters, match_all}`. Filters are
  AND-combined, at most 8, with strict `{field, op, value}` members. Only
  `sender/equals` and `subject/equals` or `subject/contains` exist. Comparisons
  use exact, case-sensitive Unicode strings, no regex, expressions, globbing,
  case folding, address parsing or whitespace repair. Filter values are
  nonempty and obey the corresponding event field byte bound. `match_all`
  defaults to false by absence; a nonempty filter list requires false, and an
  empty list requires explicit true. Unsupported field/op pairs are rejected.
- `schedule.tick`: `{source_kind, binding, anchor, every_seconds}`. Anchor has
  the timestamp form above. Period is a strict integer from 60 through 604800,
  inclusive; zero, booleans and string numbers fail. A tick matches only when
  `scheduled_at >= anchor` and the whole-second distance is divisible by the
  signed period. Equality at the anchor is slot zero. The persisted binding
  freezes anchor and period across pack revisions.

A well-formed, nonfuture tick before its anchor or off its grid is a durable
no-match. A malformed timestamp or future tick is `EventInputError`, without a
receipt. Apply that distinction before interpreting any successful check result.

Event definitions may match only at the workflow's initial stage, applied to a
new record for that occurrence; require an initial-stage condition and one
transition out of that stage. They cannot target arbitrary in-flight records.
Their action list may contain only `notify.local`. Reject `connect.invoke`,
`mail.send`, `calendar.write` and external `notify` at definition validation;
neither signed `confirmed = true` nor an event field substitutes for an operator
decision in this intake slice. Later operator definitions retain existing actions.
Match against the signed definitions, source kind, bound name, initial stage
and all filters. A no-match outcome has a persisted receipt; more than one
match is an error before mutation. A pack may have multiple disjoint event
definitions; no first-match
ordering or fan-out is implied. Operator submission matches only operator
triggers even if its decision text resembles an event kind.

The host owns timer wakeups and durable upstream acknowledgement. This library
does not generate missed slots, silently advance a watermark, coalesce slots or
replace a due instant with the current time. A host may deliberately submit an
old valid slot. It acknowledges a supplied event only after a durable match or
no-match receipt, and retries after an unknown commit outcome using the same
source identity and payload.

Synthetic mail trigger and matching fake-event catalogue:

```json
{"source_kind":"mail.received","binding":"incoming-mail","filters":[{"field":"sender","op":"equals","value":"sender@example.invalid"}],"match_all":false}
```

```json
{"format_version":1,"binding":{"name":"incoming-mail","source_id":"11111111-1111-4111-8111-111111111111","source_kind":"mail.received","scope":"synthetic-mailbox"},"matching_event":{"source_kind":"mail.received","message_id":"synthetic-message-1","received_at":"2026-01-01T00:00:00Z","sender":"sender@example.invalid","subject":"Synthetic input"}}
```

Synthetic schedule trigger and matching event:

```json
{"source_kind":"schedule.tick","binding":"timer","anchor":"2026-01-01T00:00:00Z","every_seconds":86400}
```

```json
{"source_kind":"schedule.tick","scheduled_at":"2026-01-02T00:00:00Z"}
```

## Identity, transaction, replay and concurrency

The receipt's unique identity is the tuple
`(subject, pack_id, source_id, source_kind, occurrence)`.
Occurrence is the exact mail message key or canonical schedule due timestamp.
Use a canonical structured encoding, not delimiter concatenation. Pack revision,
record UUID, binding alias, delivery timestamp and retry number are deliberately
absent from the key. Store pack revision, binding and the canonical full event
fingerprint on the immutable receipt. Same event in another pack or source is
independent; upgrading a pack must not silently rerun old source occurrences.

Admission ordering is license, bounded decode/schema, configured binding and
ownership/version checks, timestamp validity, receipt lookup, then new matching
and transactional commit. A receipt from another pack revision raises
`PackVersionError`; resume through the originating runtime. The same identity
with changed canonical event content or binding is `EventConflict`, even if it
would now match another definition. Exact replay returns the original outcome
with `applied = false` before re-matching current stage/filter state.

For a new match, one SQLite `BEGIN IMMEDIATE` transaction creates the pack-bound
record and bootstrap event, applies the selected definition's effects, freezes
its action requests, appends the operation event and inserts the receipt.
Record creation plus effect application therefore has bootstrap version 1 and
applied version 2. A no-match commits only a receipt. An invalid, ambiguous or
conflicting event changes neither records, receipts nor outbox. Losing a race
must read and replay the committed winner or report its actual conflict, not
surface a raw uniqueness error or create an orphan record. A rollback leaves
none of the matched transaction's pieces; a crash after commit leaves all of
them and recoverable action intents. Records stay frozen to their originating
pack revision; receipt and ledger history are not cleared on upgrade.
Additive binding/receipt tables must initialize idempotently over an existing
v1 database without rewriting, dropping or resetting its records, ledger,
operations or outbox. Enforce receipt uniqueness and immutability in SQLite,
with references to committed records/events where present. A malformed or
incompatible store fails closed; no delete-and-recreate recovery is allowed.

One transaction helper must own effect normalization, action freezing, ledger
insertion and projections for both decisions and events. Do not implement event
intake as `create_record()` followed by `submit_decision()`, or compensate for
duplicate records by scanning/deleting them afterwards. Event fields are
receipt data only in this slice; they cannot overwrite overlays or substitute
into action templates. Existing literal/overlay request rendering is unchanged.

Concurrent action delivery must share one per-action native lock in
`ActionRunner`, including direct run, dispatch, event/decision continuation and
pending recovery. Derive the lock from the trusted store path and persisted
action ID; reload status/request after acquiring it. Lock contention leaves
intent pending, with no delivery or failed terminalization. Unsupported native
locking fails closed for delivery. Release on all exits. SQLite transactions
must not remain open across adapter calls. This common owner removes competing
unlocked delivery paths, while preserving existing admission and missing-adapter
semantics. Prove real cross-process contention on Windows and Linux.

Guarantees are at-most-once receipt/record/action admission and serialized
delivery attempts. A crash after an external side effect but before outcome
commit remains ambiguous. Replays and recovery automatically re-drive only
adapters declaring idempotence for v2 runtime continuation, with the original
stable action/job ID; reuse `ActionRunner`'s one idempotence-policy owner.
Non-idempotent pending actions remain for reconciliation. No exactly-once
external delivery, automatic retry of terminal failure or new compensation
policy is claimed.

The v1 decision-replay path retains its current pending-action continuation
behavior, covered by `test_unconfigured_action_stays_pending_and_resumes_later`.
The new idempotence restriction applies to v2 automatic continuation/replay;
the common lock applies to all deliveries. Do not change v1 replay policy as
an incidental part of this extension or claim v2 crash guarantees for v1.

The common recovery sweep deliberately requires `adapter.idempotent is True`,
including for v1 actions: a truthy non-boolean declaration no longer authorizes
automatic recovery. This is a fail-safe tightening of the adapter declaration,
separate from the unchanged v1 decision-replay continuation above. Safe replay
and recovery refuse an unrecoverable adapter before acquiring the delivery lock,
so a sweep cannot obstruct a fresh authorized delivery. The checked adapter
instance is retained through lock acquisition; status, persisted request and
recoverability are checked again under the lock before any invocation.

## Observable errors and kit archetypes

New event errors are domain exceptions with stable, payload-free messages:
`EventInputError` / `invalid event input`,
`EventBindingError` / `invalid event binding`,
`EventConflict` / `event identity conflict`, and
`AmbiguousEvent` / `event matched multiple definitions`.
Reuse existing license, pack, pack-version, store and I/O failure types where
applicable; do not hide an I/O error as no-match. Include no sender, subject,
private source key, event JSON, adapter input or traceback in expected diagnostics.
There is no new library CLI or installed service.

The kit adds `mail-review-then-act` and `schedule-review-then-act` under spec
`format_version = 2` and unsigned artifact `kit_format_version = 2`. Each has
one required typed `trigger` table as specified above, plus the existing pack
metadata, conditions, literal `invoke` and literal `result_action` business
fields. The trigger kind must agree with the archetype; unknown/cross-version
combinations fail. Existing approve-then-act remains format 1, byte-identical.

Both new archetypes prepend `waiting` to the existing lifecycle. A matching
event moves `waiting` to `ready`, sets `pack-kit.status = "ready"`, and emits
only `notify.local` with title `Pack ready for review` and body
`Inspect the source event before approving this record.` The existing approval,
decline, complete, finish and fail definitions then operate unchanged. A fresh
mail/tick cannot approve, set `confirmed`, invoke a provider or finish a result.
The operator still reviews outcomes; payload/attachment forwarding, aggregation
and automatic result routing are not represented by these archetypes.

Keep the same four commands, key stdin rules, exit codes, error ordering,
deterministic compilation, canonical artifact reconstruction, check-before-sign
and atomic no-replace publication from `PACK-KIT.md`. `new` selects the format
from the requested archetype and writes a commented synthetic trigger table.
Mail defaults use binding `incoming-mail` and the synthetic sender filter above;
schedule defaults use binding `timer`, the fixed sample anchor above and period
86400. These are editable samples, not clock- or machine-derived configuration.
`check` and `sign` require `--fake-events CATALOG` for format 2, in addition to
the existing `--fake-apps`; there is no default accepting event source. Format 1
invocations remain unchanged and reject `--fake-events` as unused input.

The fake-event catalogue has exactly `format_version: 1`, `binding`, and
`matching_event`, where binding is the typed `SourceBinding` with a separate
`name` field. It declares the candidate's one binding and one matching synthetic
event. It is bounded at 64 KiB and strict; the checker independently verifies the
match and derives boundary/replay/negative scenarios from this explicit seed.
A missing/incompatible binding, off-grid tick or nonmatching positive fixture
fails check, rather than being repaired from the workflow. Bad catalogue schema
is exit 3; failed runtime/scenario checks are exit 5. Every sign invocation runs
the complete applicable scenario suite before reading publisher seed bytes.

## Verification plan and settling evidence

Contract-only verification checks source citations, example JSON, declared
constants/bounds, whitespace, and a diff limited to this file. It does not run
code tests or claim the proposed behavior already passes.

After acceptance, reuse the existing harness and prove:

1. V1 parity first: original parser/pack/runtime/kit lanes and unchanged goldens;
   old signatures still load, old CLI still works, old loaders reject v2;
   additive store initialization preserves all v1 rows and replay outcomes.
2. Strict version matrix and signed-tamper probes for both selectors, triggers,
   filter and schedule policy. Unknown/mixed types, duplicate keys, missing
   keys, invalid UTF-8 and partial catalogues fail without writes or seed reads.
3. Both new archetype goldens, deterministic re-builds across object insertion
   order/processes, signed `load_pack` round trips and real `PackRuntime` runs
   with independent test publisher/grant authorities, fake clocks and apps.
4. Positive and negative mail matching, empty subject, explicit match-all,
   sender/subject spoofing of approval/source fields, and operator decisions
   unable to invoke event definitions. Nonmatches persist no-match receipts.
   Each nonlocal action on an event definition is rejected, including a signed
   invocation with `confirmed = true`; the same action on an operator definition
   remains valid. A runtime receives only the validated versioned model.
5. Schedule anchor/slot-zero, just-before/at/after grid, delayed slots,
   future timestamps, backward clock and repeated same-slot submissions.
6. Limits at min-1/min/max/max+1, single/empty/mixed/large valid inputs, and
   `0`, `""`, `false`, null and excess values defeating no defaults/caps.
   Probe multibyte Unicode at byte bounds, not only equal character counts.
7. Same occurrence replay after restart, after record advancement, after a
   no-match and after a pack upgrade; changed payload conflicts. Distinct source,
   message and pack cases remain independent. Frozen binding changes fail.
8. Separate-process races for identical, conflicting and distinct occurrences,
   and deterministic crash injection before/after each transaction boundary.
   Assert receipt, record, ledger and action counts together, including no
   orphan records. Use fresh on-disk SQLite stores, not only mocked calls.
9. Concurrent delivery and recovery use the same action lock; a contending
   adapter is called once, failed/unsupported locking never delivers, and an
   accept-then-crash probe preserves the pending/ambiguous outcome. A mutated
   in-memory request never changes the persisted request that dispatch uses.
10. Required mutants are killed by behavior: skip check-before-sign;
    noncanonical ordering; accept unsupported vocabulary; record-scoped event
    dedupe; receipt insertion after record commit; changed-content replay;
    timer identity from delivery time; event relabeled as operator approval;
    bypass the shared delivery lock. Retain each causal failure.
11. Wheel contents still exclude the tools, fixture data and private keys.
    Unlike the earlier kit slice, compare the intended library member changes
    explicitly; do not assert byte equality for an implementation wheel.
12. Applicable lint/format checks and required CI, including native Windows
    store/locking probes as well as Linux. No merge with unqualified Windows
    behavior, red checks, unresolved review findings or missing exact-head
    oversight PASS. Merge with a merge commit and verify its parents/tree.

Keep durable qualification and review artifacts outside worktrees, private
directories/files at modes 700/600, and reference public review artifacts by
alias and SHA256. Do not commit private mail or production credentials.

## Implementation summary, cold diff audit and gap audit

Implementation summary: the accepted v2 intake, durable receipts, shared action
delivery lock and two kit archetypes are implemented. Existing v1 test files,
goldens and model schemas are unchanged. The native Windows CI test job now
includes the new event/store/locking and kit lanes. No app repository, pin,
dependency, package version or release workflow changed.

Cold diff audit: the implementation is confined to the declared library and kit
owners, new synthetic fixtures/tests, this status record and test-CI routing.
Local Linux evidence includes the full suite (851 passed, 16 skipped), a final
event/runtime regression slice (91 passed), six additional admission boundary
checks, the isolated mutation control and
all required mutants, v1 database/schema parity and an isolated wheel-contents
proof. A warning from the new migration fixture was traced to its raw SQLite
connection and fixed with a closure regression. Public API annotation follow-ups
were verified to leave the executable production AST unchanged.

Windows qualification correction: CI at `05b0366` exposed fixture newline
conversion and rejected the sandbox's synthetic entitlement. Canonical fixtures
now have an explicit Git `-text` policy, including the existing v1 goldens;
their tracked bytes and comparisons stay unchanged. The sandbox construction
introduced by `d96268d` assumed POSIX storage. Its Windows scratch root and
entitlement now use the existing SDK private-storage owner under Local AppData,
without weakening the license reader. A controlled Linux reproduction through
the real Windows validator recorded `private directory escapes its root` before
the fix; v1 and both v2 check paths pass that policy afterward. Native CI also
replays the old storage construction to expose its exact rejection reason.
The new CLI test expects the platform's text newline for diagnostics while
continuing to compare artifacts as exact bytes. No old test file, fixture,
library implementation, dependency, app or release behavior changes in this
correction. Native Windows qualification remains a required pending gate.

Review repair contract (`537aa0c`, oversight `6254268336`):

- Delivery owner `ActionRunner._deliver/_deliver_locked` (`3056cc1`): prove the
  stale pre-lock reader cannot deliver after another caller settles, and reject
  unsafe recovery before locking while retaining the deciding under-lock guard.
- Store owners `initialize/admit_event` (new event schema/replay in `3056cc1`):
  verify all new table keys, foreign keys, CHECK constraints and immutability
  triggers in one initialization transaction; reject partial/incompatible shapes
  without repairing them. Legacy stores with none of the new tables initialize
  additively. Receipt replay must bind its event to its own record and intake operation (derived key, source-kind name and canonical request fingerprint). Reproduce
  malformed schemas and cross-record receipts using synthetic on-disk databases.
- Binding registration (`3056cc1`): consolidate alias rejection at its persisted
  owner and prove both distinct-source admission and duplicate-scope refusal.
- Diagnostic owners `parse_event/_validate_bindings` (`3056cc1`): reject outside
  exception handlers so neither the public message nor the exception chain
  carries rejected event or binding payloads. Prove decode, JSON and schema cases.
- Pin the existing event-replay safe-adapter and pre-anchor grid guards with
  direct regressions and mutants, including on-grid ticks before the anchor.
- Kit checker owners (`3056cc1`): prove both event scenarios reject a broken
  runtime, construct the unbound probe outside the declared binding, and check
  rejected submissions leave zero records/receipts even for match-all mail.
  Pin exact catalogue error codes and describe the existing read/schema/artifact
  error precedence truthfully; do not reorder validation from an untrusted header.
- Kit scratch-root owner (`537aa0c`): use public SDK directory creation only,
  remove each owned scratch tree on success and failure, and enforce the public
  SDK boundary structurally. No new SDK seam or private SDK call is authorized.
- Each defect gets a fail-before/pass-after regression and a causal mutant.
  Preserve old tests/goldens, run affected lanes and applicable lint, and publish
  one grouped repair. Native Windows CI and exact-head review remain merge gates.

The low operational lock-file retention finding is explicitly deferred by
oversight to issue #9. One small file remains per action; serialization is
unchanged. Issue #9 requires a safe lifecycle design and native Linux/Windows
process proof **before any application adopts this revision or bumps its pin**.
Do not describe retention as fixed or remove lock inodes as an incidental repair.

Review repair qualification: the full Linux suite passed with the required CI
warning policy (922 passed, 16 skipped), and the affected kit slice passed under
strict resource warnings (142 passed). The changed-file strict gate and all
required/review causal mutants passed. A stricter whole-suite experiment also
exposed the original lock test's unclosed subprocess stdout; the exact published
baseline reproduces that warning and the original test remains byte-identical.
The new library source matches the full-suite-tested snapshot; later changes
are confined to the kit, its tests and documentation and have their own gates.

Gap audit: **NOT DONE**. Exact-revision contract review and operator acceptance
are recorded above; implementation and local Linux qualification are complete.
Native Windows CI evidence, exact-head PR review and merge remain. Application
adoption and the excluded aggregation/result features require separate accepted scope.
