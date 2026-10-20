# Lead source receipt to Automate: host handoff contract

Status: **ACCEPTED CONTRACT; RECEIPT VOCABULARY AND DEPLOYMENT BINDING INCREMENT AUTHORIZED.** No
production receiver, Watcher adoption or complete foundation gate is approved.

## Operator acceptance

On 2026-10-19, after the coding session reported oversight's PASS as a proposal
and identified direct contract acceptance as the next gate, Juan replied:

> I accept

This accepts the handoff contract at
`4f8cc7a6580cfcef834af52fac45c5f0db9c52d7`, reviewed in
[PR #23](https://github.com/canfieldjuan/connect-automate/pull/23#issuecomment-6275561224).
This acceptance-only update changes no proposed API or runtime semantics.
The accepted scope remains library-only; implementation and application adoption
are separate work orders. The operator decision about workflow receipt metadata
retention after source purge remains open before adoption. Keep implementation
PRs bounded; the read-only lookup connection may land first, but the joined
submission/lookup boundary is not usable until its recovery proof is complete.

## Root cause and baseline

Source custody and workflow event admission exist as separate owners. They have
no supported connecting call. Converting a source envelope into a mail event
would invent sender/subject fields and confuse source-event identity with mail
occurrence identity. A successful source commit is not workflow acceptance.

Source of truth: `canfieldjuan/connect-automate`, baseline commit
`bcf368503bf3e0d6ea30bd800f42a978b4c11c2f`. Paths and lines below refer to that
commit, not to a moving branch. Documentation describes constraints; executable
code and recorded test results establish the inventory.

| Finding | Evidence at baseline |
| --- | --- |
| CONFIRMED: source admission authenticates before receipt lookup, checks the lifecycle policy, and authenticates again before committing | `src/connect_automate/lead_intake/admission.py:188-264` |
| CONFIRMED: receipt carries deployment, namespace, event, digest, first acceptance and deadline; replay returns the original receipt | `lead_intake/admission.py:54-76,199-210,232-264` under `src/connect_automate/` |
| CONFIRMED: source deployment identity is checked against persisted authority, not merely accepted as a request label | `lead_intake/source_store.py:353-380` |
| CONFIRMED: content reads validate custody and refuse retirement, purge and expiry; they return the canonical envelope, not just body text | `lead_intake/content.py:74-98`; `lead_intake/admission.py:213-216` |
| CONFIRMED: available, truncated, unknown and unavailable bodies have distinct validated representations; attachments are not processed | `lead_intake/source.py:94-135` |
| CONFIRMED: Automate currently accepts only mail and schedule events; a mail event requires sender and subject and has no receipt reference | `automate/events.py:78-111,134-154` |
| CONFIRMED: runtime loading verifies pack/grant and freezes bindings; grant subject is a PC/customer identifier, not employee or organization authorization | `automate/runtime.py:103-142`; `automate/pack.py:91-100` |
| CONFIRMED: workflow admission owns the receipt, record, ledger effects and action intents in one transaction | `automate/store.py:842-961` |
| CONFIRMED: existing occurrence key is subject/pack/source/kind/occurrence; changed payload conflicts, changed pack version refuses replay, and no-match is persisted | `automate/store.py:182-198,864-911` |
| CONFIRMED: runtime submission dispatches after admission, including safe replay; it is not a read-only receipt lookup | `automate/runtime.py:194-230` |
| CONFIRMED: event definitions allow only local notifications, and require an initial-stage guard and transition | `automate/definition.py:393-440` |
| INFERRED: a bounded receipt event can reuse the workflow transaction rather than add another workflow engine or delivery queue | Existing generic store arguments at `automate/store.py:842-865`; new event/host integration is not implemented |
| UNKNOWN: current Watcher enrollment, body delivery and purge propagation satisfy this boundary | Watcher is not requalified by this contract; the prior source-admission contract explicitly leaves these adoption prerequisites open |

All shortened source paths in this document are relative to
`src/connect_automate/`. No existing API is claimed to implement the proposals
below.

## Proven work to preserve

Reuse these fixtures and assertions; do not replace them with a new mock-only
harness. Test presence alone is not a production-readiness claim.

| Inventory | Location / recorded evidence |
| --- | --- |
| Frozen source/auth syntax, canonical bytes and signatures | `tests/fixtures/lead_source/`, `tests/fixtures/lead_source_auth/`; `tests/test_lead_source.py`, `tests/test_lead_source_auth.py` |
| Source replay, rotation, copied-result refusal, lost commit acknowledgement and native processes | `tests/test_lead_source_admission.py:182-289,362-378,450-518` |
| Content lifecycle and the distinction between revoked producer authority and retained host custody | `tests/test_lead_source_content.py:30-113,394-421,464-570,805-880` |
| Workflow replay, no-match, version conflicts, concurrent processes and crash boundaries | `tests/test_automate_events.py:283-353,662-697` |
| Workflow receipt integrity and replay of original state | `tests/test_automate_review.py:122-241` |
| Existing authoring fixtures and versioned manifests | `tests/fixtures/pack_events/`, `tests/fixtures/pack_kit/`; `automate/pack.py:77-118`; `tools/pack_kit/core.py:51-52,101` |
| Recorded local gate | Reviewed head `21109669d9fb5dabda41ca53451d72aea7c0a3fe`: `1680 passed, 16 skipped in 325.25s (0:05:25)`, Ruff passed, Python 3.13.11 on Linux. Evidence alias `lead-source-local-ci/pytest.txt`, SHA-256 `5545e2e33cb91b21544412c54b9e655e115998530416c3bac1abb6ff92a8574d` |
| Recorded native qualification | GitHub Actions run `39285238240`, jobs `test` and `windows-placement` succeeded on the reviewed head. Merge tree `03f6aa4599aa4672461bf5e4d1dde5200c528315` equals that reviewed tree. The Windows workflow pins Connect contracts at `3005d82a7be885fba36f8688b5967a5b56a0abea` |

The recorded runs are prior evidence, not tests rerun for this documentation
change. No model, inference runtime, prompt, customer data or external effect
participates in this inventory. First implementation must run unchanged parity
fixtures before extending the boundary, and keep native Windows in its first CI
push.

## Ownership and required change surface

**Proposed first implementation: a library-only trusted-host handoff.** No
listening socket, CLI enrollment command, mailbox consumer or background service.
The host supplies an already configured SourceAdmission owner and a verified
PackRuntime. Neither component opens the other's database or performs SQL against
the other's tables.

| Owner | Smallest proposed change | Preserved invariant |
| --- | --- | --- |
| Lead Intake | A narrow facade, provisionally `lead_intake/handoff.py`, orchestrates existing `SourceAdmission.admit_source(raw)` and a supported runtime boundary | Raw signed bytes are authenticated on every new/replayed submission; copied results and receipt-shaped dictionaries cannot authorize workflow creation |
| Automate event/definition owners | Add a distinct, versioned `lead.source.received` event and trigger; extend occurrence/time handling explicitly | No fabricated mail fields, body-bearing events or implicit fallback between event variants |
| PackRuntime | Configure the trusted source owner and deployment binding; expose source submission and side-effect-free outcome lookup | License and configured scope precede source/receipt access; generic `submit_event` cannot create a receipt event from caller JSON |
| WorkflowStore | Reuse `admit_event`; factor its existing receipt-ownership/replay validation into one shared owner for lookup and admission | One transactional workflow receipt/record/effects commit; no parallel dedupe algorithm or second dispatcher |
| Binding registration | Enforce deployment/namespace mapping for the new source kind in the existing durable binding owner | Organization is enforced, cannot be relabeled on restart or pack upgrade, and is not inferred from the licensed subject |
| Pack authoring | Extend the established pack-kit validator/fixture path only as required to author and round-trip this trigger | Existing signed manifests, golden fixtures and mail/schedule/operator behavior remain valid and unchanged |

All identifiers below are separate: producer event, source admission, workflow
event, workflow record and eventual destination operation. A workflow record is
not a canonical lead. Different producer event IDs for one message may create
different intake workflows; C4's future lead-deduplication policy is still required.

### Deployment binding and trust boundary

Proposed configuration is immutable for the lifetime of the binding:
`host_id`, `organization_id`, `namespace_id`, licensed `subject`, `pack_id`, binding
name and source owner. The source owner must be bound to that host and organization;
never accept deployment selection, paths, pack selection or namespace creation
from the source payload. Request identities must agree with configured values.

For the new kind, use `source_id = namespace_id`. Encode `scope` as canonical,
sorted, compact JSON containing exactly `host_id`, `organization_id` and
`namespace_id`. It must fit the existing scope bound. Keep this source kind's
binding policy explicit and immutable. Across the workflow store, all such
bindings must agree on host/organization, even for different licensed subjects;
a second namespace can
be configured only within that same deployment. Enforce this at registration
inside its existing writer transaction, including reopened stores. Reject
malformed or inconsistent persisted scopes; do not silently reinterpret legacy
mail/schedule scope strings.

This is an in-process trusted-host boundary, not proof of employee authentication.
Caller-supplied Python objects, an OS directory, a bearer transport token or a pack
grant alone do not establish a person's permission. All callers in the current
same-OS-user process threat model are trusted. A production receiver must first
define and qualify the authenticated host principal and permitted operations.
No remotely callable receipt lookup or source submission is authorized here.
This extension does not retrospectively qualify unrelated workflow records for
multi-business hosting.

### Proposed receipt event

Strict schema; unknown/duplicate fields, coercions and unsupported versions fail
closed. Retain the existing event byte cap. The proposed wire fields are:

| Field | Value / owner |
| --- | --- |
| `source_kind` | Literal `lead.source.received` |
| `schema_version` | Literal `1.0` |
| `source_receipt` | Strict projection of the durable SourceReceipt below |

The projection contains exactly `host_id`, `organization_id`, `namespace_id`,
`event_id`, `admission_id`, `payload_digest`, `accepted_at`, `recovery_deadline`.
Reuse the existing receipt field validators, including microsecond acceptance
time and whole-second deadline. Do not round acceptance time to fit a mail event.
Canonical bytes must be stable across restart and producer key rotation. Exclude
the signature, current key, current authority generation and retry timestamp.
Never include bodies, subjects, senders, account/message identifiers, arbitrary
paths or customer narratives in this event, action payload or error.

Occurrence is the original source `event_id`, scoped by the configured namespace
source ID, kind, subject and pack through the existing workflow key. Admission ID
and payload digest remain immutable payload assertions, not new occurrence keys.
A different digest or receipt under that same identity conflicts. Changing the
pack revision does not authorize reprocessing: preserve the existing version
conflict and retain the old signed pack/configuration for recovery. This provides
per-pack workflow idempotency, not universal cross-pack or canonical-lead dedupe.

Extend the existing versioned event vocabulary and manifest validation additively;
retain current manifest/vocabulary selectors and reject this unknown trigger on
older binaries. Do not reinterpret any existing signed bytes. The new trigger
uses an explicit `match_all: true`, the configured binding and existing initial
stage/effect rules; it has no sender filter or model-controlled routing. The first
proof pack emits **no actions** and transitions into a source-received workflow
stage. Existing event restrictions still prohibit external effects. A later
extraction/approval slice must not treat that stage as lead approval.

## Submission, outcome lookup and recovery

Proposed supported host operation: `submit_source(binding, raw_source_bytes)`.
The clock and source owner are host configuration, not untrusted request fields.
Exact Python naming can follow existing conventions, but these semantics are
required:

1. Require current runtime license, verified pack and authorized deployment
   binding before any source or workflow receipt access. Revalidate the source
   shape and configured host/organization/namespace match before side effects.
2. Invoke the configured `SourceAdmission.admit_source(raw)` on every submission,
   including replay. Do not accept an earlier AuthenticatedSource,
   SourceAdmissionResult or SourceReceipt as a substitute. SourceStoreUncertain
   stops this attempt before workflow admission; retry the same signed request.
3. From the just-returned durable receipt, construct the canonical receipt event.
   Its fields must agree with the configured scope and authenticated request.
   Do not look up content to fabricate routing fields or extend its deadline.
4. Invoke the supported runtime path and existing `WorkflowStore.admit_event`
   with that event. The generic raw-event method rejects the new event kind;
   only the trusted source path may submit it. Preserve the normal signed-pack,
   binding, initial-stage, ambiguity and version checks.
5. Return a bounded, versioned outcome distinguishing source admission from
   workflow acceptance. Include the source reference and stable workflow event /
   record IDs when matched. `accepted` and persisted `no_match` are durable
   outcomes; replay returns the original outcome with `applied=false`.
   No-match is not an error, successful extraction, or permission to change the
   identity and retry. Uncertain commit/delivery of the response is **unknown**,
   never a definite failed/not-created result.

The proposed success result has `schema = "lead.source.handoff.result"`,
`schema_version = "1.0"`, the projected `source_receipt`, strict Boolean
`source_applied` and `workflow_applied`, and `workflow_outcome` equal to
`accepted` or `no_match`. An accepted outcome includes the original
`workflow_record_id`, `workflow_event_id`, stage and state version; no-match has
null workflow IDs/stage/version. Preserve existing no-match semantics:
`workflow_applied=false` even when its no-match receipt was just committed.
Source replay and workflow replay are independent; do not collapse their flags.
Outcome lookup uses `schema = "lead.source.handoff.lookup"` and
`schema_version = "1.0"` and returns the same workflow projection and stored source reference,
with no source-applied claim; its `not_found` variant contains no invented receipt
or workflow IDs. Both result schemas are closed, versioned, bounded by the existing
event byte cap and validated before being returned.

The source writer is released before entering the workflow writer. No cross-store
transaction, callback under a source lock or atomic two-database commit is
introduced. Source authorization linearizes at its existing final sample. A
revocation, purge or deadline reached after that sample can precede workflow
commit; the resulting metadata-only workflow does not assert live content or
current producer authority. Unavailable-body envelopes may also start this
metadata-only workflow. Any future content-consuming step must use the source
owner and its live lifecycle checks; it must not cache permission from this event.

Proposed `lookup_source_outcome(binding, event_id, expected_payload_digest)` is a
separate **read-only** host operation. It requires the same licensed, configured
deployment access; scope and pack identity come from that binding, not the lookup
request. It uses the existing workflow receipt owner, verifies stored canonical
payload/digest, binding, record/event ownership and original replay view, and
returns `accepted`, persisted `no_match`, or `not_found`. A digest mismatch is a
conflict; corrupt ownership fails closed. It never calls admission, dispatches,
creates a record, reads content or changes the source clock floor. Do not implement
it by calling `submit_event`, which currently dispatches after receipt replay.
The lookup connection must refuse to create or initialize a missing store. Its
consistent read covers the receipt, binding and ownership checks together;
schema/corruption/I/O errors are not absence. Qualify this path separately from
the current general connection helper, which opens SQLite in create-if-missing
mode (`automate/store.py:705-721`). No source-store access is needed for lookup.

Lookup must be able to report a committed workflow after producer key revocation,
source expiry, purge or namespace retirement, even after source tombstone cleanup.
This is historical metadata under host authorization, not permission to resurrect
content or send a new source. Keep lookup-only access to the retired binding; it
does not re-enable submission. It must distinguish a prior pack revision from
not-found without silently rerunning that event. License/scope denial cannot be
converted to not-found.

| Failure window | Required recovery / observation |
| --- | --- |
| Before source commit | Same currently authenticated request can retry; no workflow exists from that attempt |
| Source commit, lost source response | Repeat signed admission; its stable receipt recovers the operation before runtime is called |
| Source committed, workflow not yet called | Retry the complete host operation while admission remains authorized; source replay must not suppress the missing workflow call |
| Workflow SQL failure before commit | Preserve source custody; retry the same identities; no partial workflow receipt/record/effects |
| Workflow commit, process dies before response | Read-only outcome lookup recovers the committed outcome; normal authenticated replay also returns it if still permitted |
| Expiry/revocation/purge prevents resubmission | Lookup can report an existing workflow without source re-admission; absent outcome remains not-found/undelivered, never recreate from a cached receipt |
| Lookup says absent while another writer is in flight | Absence is an observation at the read, not proof no concurrent commit can occur; retry admission uses the same identity if authorized |
| Different payload, route, binding or pack version | Refuse/conflict; no fallback to a new ID, another pack or an available provider |

For this proof, the synthetic host harness retains the same signed request and
configured route through simulated restarts. This demonstrates caller-driven
recovery, **not unattended discovery of stranded source receipts**. A producer's
durable retry custody, retention deadline, route pin and host startup retry path
must be qualified before real adoption. Do not add a scheduler, queue, source-store
scan or dispatch table speculatively. If the joined crash proof shows missing
bookkeeping, document the precise failure and revise this contract before adding it.

## Privacy, retention and Watcher prerequisites

Only the source store owns canonical source bytes; only Automate owns workflow
receipts. Receipt IDs and digests are still sensitive correlation metadata.
The workflow ledger currently preserves immutable event receipts; this slice
does not claim to delete them when a source is purged. Production retention and
backup policy must cover that residual metadata explicitly. No raw source in
workflow errors, exception chains, notifications, traces or logs. Test fixtures
contain synthetic sources only; never copy production lead content into them.

Before Watcher/Connect adoption, a separately source-verified contract must cover:

- C5 enrollment: authenticated host/organization pairing, durable namespace minting,
  rotation, replacement installation and irreversible retirement.
- Body-only eligibility and a protected durable snapshot/handoff; completeness,
  unavailable states and unprocessed attachments preserved without invented data.
- Producer-bounded recovery deadlines and content retention across retries; no
  automatic extension when re-sending the same event.
- C3 purge emission for every physical identity behind aliases, authenticated
  propagation and restart recovery, with the operator-approved capture cutoff.
- The existing Connect input-artifact path versus any necessary host boundary:
  qualify actual caller/authentication/retention behavior before choosing transport.
  This contract chooses an in-process proof, not a new Watcher service.
- Authenticated employee access, encryption/backups, telemetry and deletion
  qualification. Local Python calls and synthetic fixtures do not prove these.

## Differences from proven work and explicit non-scope

Every proposed departure is listed here; an additional departure requires a
contract revision before implementation:

| Departure | Reason / required proof |
| --- | --- |
| New receipt event/trigger and host-bound submission | Existing mail/schedule models cannot represent this receipt; parser boundaries and raw-event bypass probes |
| Deployment-aware mapping in existing binding registration | Licensed subject is not organization authorization; mixed scopes, rebinding and concurrent registration probes |
| Side-effect-free receipt outcome lookup | Existing submit replays actions and admission can later be refused; reuse ownership validation and prove lookup cannot write/dispatch |
| Cross-owner facade | Existing tests prove each commit separately; joined two-store process-crash proof is missing |
| Additive pack-kit support and new synthetic fixtures | Existing authoring supports mail/schedule; signed round trip plus unchanged golden parity |

No change to frozen source/auth wire contracts, custody schema, C1/C3 policy,
source retention duration or EOM behavior. No canonical leads, extraction models,
contact matching, employee approval, destination delivery, retry scheduler,
external effects, CRM, Lead Inbox UI, cloud dependency or cross-app SQL. Issue
[#21](https://github.com/canfieldjuan/connect-automate/issues/21) remains a separate
test-hardening item; this contract does not silently absorb it.

## Verification and implementation slices (proposed)

Contract acceptance precedes all executable changes. Keep independent steps
reviewable; every step preserves unchanged baseline fixtures.

| Step / foundation relationship | Required evidence before dependent work |
| --- | --- |
| Contract acceptance / G0 | Source inventory, owners, identities, scope enforcement, failure semantics, content-vs-metadata lifecycle and library-only limit accepted; no full G0 claim for missing deployment contracts |
| Receipt vocabulary and binding / G1 prerequisite | Fail-first unsupported-event fixture, strict schema/version/size/time boundaries, signed pack and pack-kit round trip, namespace/deployment registration races, unchanged mail/schedule/operator vectors |
| Host submission / G1, G2 prerequisites | Body-only and unavailable envelopes, copied-result/raw-event bypass, same-event replay, key rotation, conflicting payloads, foreign host/org/namespace, unknown binding, revoked/license-denied input; exactly one workflow per configured occurrence |
| Outcome lookup and joined recovery / G3 prerequisite | Real separate-process admissions; barriers at source commit, workflow receipt/effects writes, workflow commit and response; lost replies; reopen; post-expiry/purge/revocation/retirement lookup; no partial workflow; original outcome returned after record advances |
| Privacy and platform qualification / G6 prerequisite | No bodies in workflow database/errors/logs; foreign-scope read denied; corrupt stored references fail closed; native Linux/Windows crash and filesystem proof from first implementation push |

Lookup and submission must ship together before the joined host boundary is usable.
No step may declare full G1/G2/G3/G6 satisfied: Watcher integration, canonical lead
identity, deployment authorization, retention/encryption and real recovery remain.

For guards test accepted/rejected sides, mixed valid/invalid fields, empty and
max-byte UTF-8 values, strict-type/falsy values, exact deadline/equality, fractional
acceptance time and independent corruption per check. Kill owner mutations that
skip authentication, accept raw receipt JSON, omit scope/digest from checking,
suppress workflow submission on source replay, create a new occurrence on retry,
dispatch during lookup, round timestamps or bypass receipt ownership validation.
Use real commit/crash boundaries and native process synchronization, not sleeps
or mock call counts as concurrency proof. Preserve passing-after and failing-before
results outside worktrees. Incremental local gates plus exact-head CI and review
remain mandatory; green tests alone do not establish production readiness.

## Rollback, cold diff and gap audit

### Read-only connection implementation increment

After accepting the contract, the operator instructed **"Start implementing"**.
The coding session selected the bounded read-only connection foundation first,
as contemplated by the acceptance record. Contract PR checks and merge remain
independent gates; this increment may be developed on its accepted revision but
must not bypass those gates. The rest of the handoff is not implemented here.

Root cause: the existing general `WorkflowStore.connection` opens SQLite with
create-if-missing and commits on successful exit (`automate/store.py:708-721` at
the baseline; introduced by `bf1cd1d`). Those are intentional writer semantics,
unsuitable for the future historical-outcome lookup. Preserve them for writers.

Required surface: add `WorkflowStore.read_connection` at that owner, a focused
test file, and its native Windows CI selection. Open an existing file with a
properly escaped SQLite `mode=ro` URI; do not use `immutable=1`, which could hide
live WAL commits. Start one read transaction and use the existing event-schema
validator before yielding. Refuse absent/incomplete event schema rather than
initializing it. Pin the snapshot across all caller SELECTs. Restrict yielded SQL
to reads, including refusing ATTACH and transaction-control statements, so a
caller cannot accidentally create a second database or end the read snapshot.
This is a trusted internal query interface, not a sandbox for hostile Python.
SQLite errors become a bounded WorkflowStoreError without source/path/SQL details
or exception context; valid missing-row results remain ordinary empty reads.
Always close the connection on success, setup failure and caller failure.

Verification: reproduce file creation by the old writer helper in a temporary
directory; a missing read API test fails before implementation. Then prove missing
file/parent refusal, empty/unrelated/corrupt/weakened schema refusal without repair,
valid SELECTs and missing rows, escaped/relative paths, write/DDL/ATTACH/transaction
denial, live WAL visibility, stable snapshots across a real concurrent process
commit, and resource release on every exit. Mutate URI mode, snapshot BEGIN,
schema validation and the read SQL guard independently; each must fail a targeted
assertion. Run unchanged parser/auth and adjacent workflow parity, lint/format,
and exact-head Linux/Windows CI plus independent review. A read transaction may
participate in SQLite WAL shared-memory coordination, including creating absent
`-wal` and `-shm` sidecars for an existing database and leaving them after the read
connection closes. Read-only access does not promise an unchanged filesystem
footprint or byte-for-byte immutability of sidecars. It must not write application
rows, create a missing database, initialize schema or checkpoint/migrate the store.

Non-scope: do not route existing getters through this method, change writer
semantics or schema, add receipt lookup/submission, alter source custody, or add
an application service. Regression risk is confined to the new read primitive;
unchanged writer and schema tests prove coexistence. Rollback removes this unused
primitive and its tests without data migration. This is an incomplete foundation
until the later receipt lookup and joined submission/recovery proof land.

### Read-only receipt lookup implementation work order

Operator work order: "Let’s start the read-only receipt lookup slice, with the
work-order contract commit first." This section is committed before executable
changes, on the merged read-connection foundation `6782cb7`. The accepted handoff
contract remains authoritative; this is another bounded library increment.

Root cause and owner: `WorkflowStore.admit_event` currently owns binding checks,
receipt selection, conflict detection and original-outcome reconstruction inline.
Its writer transaction can create records; runtime submission can dispatch even
on replay. The new `read_connection` owns safe snapshots but does not retrieve an
outcome. Copying the admission checks into a second reader would split ownership.
The existing receipt checks originate in `3056cc1a`, with operation ownership
strengthened in `ae5ba2c6` and `913ac870`; preserve those regressions unchanged.

Required surface: factor one connection-scoped receipt reader inside
`automate/store.py` and call it from both admission replay and a new internal
`WorkflowStore.lookup_event` method. Lookup takes the existing trusted store
identity (subject, pack ID/version, binding, source ID/kind, occurrence) plus an
expected payload digest. This digest is SHA-256 of the canonical **workflow event**
bytes, not the source envelope digest. The later host facade must construct and
map its source reference explicitly. No lead-source vocabulary is introduced here.
Return the existing `EventAdmission` with `applied=False` for persisted matched or
no-match outcomes, or `None` for an absent receipt under a valid binding. Do not
collapse those distinct results by truthiness. This is an internal store result,
not either versioned host response schema defined above.

The shared owner verifies the registered source/binding before observing absence,
then pack revision and expected digest/binding conflicts. It verifies the stored
payload against the existing event parser/canonicalizer, persisted digest and
source-kind/occurrence identity before returning even a no-match receipt. Mixed
record/event presence is corrupt. Matched receipts retain every existing
record/event/operation ownership check and reconstruct the original event view,
not the latest record projection. Invalid stored payloads and ownership produce
bounded store errors without raw JSON or exception chains. New lookup input
validation rejects empty/non-string identity fields, non-positive/non-integer pack
versions and non-lowercase SHA-256 digests before SQL; these are internal API
shape checks, not authenticated organization access.

Lookup uses only `read_connection`; it never enters the writer, invokes selection,
admits a source, changes clock state or dispatches an action. Receipt, binding,
payload and original-outcome checks share one snapshot. The read-connection
sidecar disclosure above applies unchanged. Missing/unreadable/invalid stores
are errors, never not-found. Admission uses the same reader inside its existing
writer transaction; fresh admission semantics and persisted bytes stay unchanged.

Explicit non-scope: no PackRuntime or host API, licensing or deployment enrollment,
new receipt event/trigger, source-store read, raw-source access, schema migration,
pack-kit change, retention policy, action retry, UI or application adoption.
The full host lookup's authorization, retirement and source-lifecycle tests remain
in the joined submission/recovery slice. Scope strings here come from trusted
internal callers; this primitive must not be exposed as an authenticated API.

Verification plan: run unchanged event/replay/read-connection baseline first.
Declare missing-method fail-first probes, then cover matched/no-match/not-found,
reopen and original view after record advancement, valid mail/Unicode/schedule,
wrong binding/scope identity/version/digest, invalid input types and empty values,
and separate corrupted-row fixtures for each independent owner check. Restore
schema triggers in corruption fixtures so schema validation cannot mask the row
check. Exercise both admission replay and lookup against the shared owner.
Prove no workflow row/action writes, no writer/selection/dispatch calls, and real
separate-process commits during lookup with barriers rather than sleeps. Kill
mutations that bypass the shared owner, omit critical checks, return current
state or choose the writer. Add the new test file to native Windows from the first
push; run adjacent local parity and lint, then exact-head Linux/Windows CI and
independent/oversight review. Wait for any ready-triggered Codex review to finish
before merging. Keep reproducible evidence outside worktrees.

Regression risk: factoring the existing admission replay branch can alter its
conflicts or historical view; unchanged existing tests and dual-entry corruption
probes guard that boundary. Rollback removes lookup and restores the inline reader
without deleting data or migrating a store. Stop at reviewed merge of this
increment. Host submission/lookup integration, joined crash recovery and adoption
remain NOT DONE; receipt metadata retention is still an operator decision before
adoption.

### Receipt vocabulary and deployment binding work order

Operator work order: "Lets get started", following the proposed bounded receipt
vocabulary and deployment-binding slice. Commit this work order separately before
executable changes. The merged receipt lookup remains the recovery foundation.

Root cause: `automate/events.py` and `automate/definition.py` only recognize mail
and schedule source events. `WorkflowStore.register_bindings` freezes source
configuration per subject but has no store-wide deployment invariant. A new
receipt projection must preserve the existing source receipt validators rather
than duplicate timestamp/identity rules or pull custody IO into the event parser.

Required change surface: factor the common receipt projection and interval
validation into a dependency-light `lead_intake/receipts.py`, keeping
`admission.SourceReceipt` and all persisted canonical bytes compatible. Extend
event parsing/canonicalization/occurrence, trigger validation and exports. Extend
`SourceBinding` with a strictly canonical deployment scope for the new kind;
namespace equals source ID. Register new-kind scopes and their explicit immutable
policy in the existing writer transaction, enforcing one host/organization across
subjects and packs, checking persisted scopes on reopen. No database schema change.
The explicit policy is `{"schema_version":"1.0"}` for this receipt-only binding;
it expresses no time scheduling, approval or delivery policy.

Generic `PackRuntime.submit_event` and `WorkflowEngine.submit_event` must reject
this kind before selection, receipt creation or effects. Syntax is not source
authentication. The authenticated host facade and engine handoff path are a later
work order; do not introduce a bypass token or simulate one in pack-kit. Event time
and occurrence helpers preserve acceptance microseconds and original event ID,
but their support must not itself activate submission.

Extend the existing pack-kit compiler with a receipt-only proof archetype,
`lead-source-receipt`, containing one guarded transition to `source-received`
and no actions. Its new/build/check/sign path uses existing signing, manifest,
binding and event validators. Its offline check explicitly proves registration,
reopen, canonical receipt parsing, and refusal by generic submission with no
records/actions; report these as vocabulary/binding checks, not a successful
source handoff. Existing mail/schedule/business archetypes and golden bytes stay
unchanged. The later authenticated handoff slice must prove the actual transition.

Non-scope: source custody semantics, schema migration, host submission/lookup API,
joined recovery, extraction, sender routing, action execution/retries, real mailbox
access, lead creation, application adoption and retention decisions. No new
services, workflow engine or poller. Existing mail/schedule scope semantics remain
unchanged. Trusted in-process deployment configuration is not employee identity.

Verification: unchanged source/auth/receipt and event/pack baseline; fail-first
unsupported-event/trigger/binding probes; strict missing/extra/duplicate/coerced
fields, timestamp precision and interval, canonical UUID/digest/version, byte cap,
source-ID/scope mismatch, host/organization disagreement, multiple namespaces,
reopen and changed binding/policy refusal. Corrupt one persisted scope invariant
at a time and restore schema triggers so checks cannot mask each other. Run
separate-process concurrent registrations with barriers, including competing
subjects/deployments and compatible namespaces. Prove generic runtime and engine
submission cannot create even a no-match receipt. Preserve old signed fixtures;
prove kit build/sign/load and corrupt-artifact refusal with synthetic data. Add
new tests to native Windows on first push; run affected local tests, lint/format,
then exact-head Linux/Windows CI and independent/oversight review. Keep evidence
outside worktrees. Targeted mutations must fail behaviorally for critical guards.

Assumptions: accepted canonical scope fits the existing scope byte limit; current
receipt validators are the authoritative pre-production implementation, with no
model or inference settings involved. The only factoring difference is shared
ownership of the identical fields and interval validator; unchanged source tests
and canonical receipt comparisons must prove parity before new vocabulary claims.

Regression risks: receipt inheritance could alter schema/default/canonical bytes;
new event union could change legacy parsing; registration checks could leak scope
across unrelated kinds; pack-kit branching could change existing artifacts. The
unchanged parity lanes guard these. Rollback removes the unused vocabulary and
proof archetype before adoption; retain stores and signed packs, do not delete
receipts or downgrade/reinterpret new-kind bindings. Old binaries reject the new
trigger. Stop at this increment's reviewed merge.

Implementation summary/cold diff/gap audit: to be recorded against executable
proof. The full handoff and foundation gates remain NOT DONE. No production
retention decision or adoption is implied.

Rollback before adoption: disable the new host binding and preserve both stores
and the prior signed pack/configuration. Do not delete receipts to retry, downgrade
persisted data or reinterpret the new event as mail. Existing workflows keep their
contracts; an older binary must fail closed on the new trigger. Recovery from
backup divergence needs separate qualification before live use.

The earlier contract PR was documentation-only. The read-connection increment
is merged. The receipt-lookup increment adds the shared internal receipt reader
and its focused platform proof; cold diff must verify the declared surface. Existing source/auth vectors, workflow tests, schemas,
dependencies and application integrations remain unchanged.

Gap audit: contract acceptance is **DONE**, as recorded above. Implementation and
application adoption remain **NOT DONE**. Read-only receipt lookup is merged; only the receipt vocabulary and deployment
binding increment is authorized by the current work order. Stop at its
reviewed merge; no live handoff or production adoption is claimed.
