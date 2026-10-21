# Lead source receipt to Automate: host handoff contract

Status: **ACCEPTED BASE CONTRACT; HOST HANDOFF WORK ORDER PREPARED FOR REVIEW.**
Receipt vocabulary, binding and corruption-regression increments are merged. No
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

### Recovery limits

This table owns the recovery rules for both the base contract and subsequent
implementation work orders. An uncertain submission remains unknown until a
permitted retry or historical lookup establishes its outcome. Recovery is not
unconditional: a source-only commit cannot complete workflow admission through
this boundary unless the same signed request still passes admission policy.

| Failure window | Required recovery / observation |
| --- | --- |
| Before source commit | Same currently authenticated request can retry; no workflow exists from that attempt |
| Source commit, lost source response | Repeat signed admission only while admission remains authorized; its stable receipt then recovers source custody before runtime is called |
| Source committed, workflow not yet called | Retry the complete host operation while admission remains authorized; source replay must not suppress the missing workflow call |
| Workflow SQL failure before commit | Preserve source custody; retry the same identities only while admission remains authorized; no partial workflow receipt/record/effects |
| Workflow commit, process dies before response | Read-only outcome lookup recovers the committed outcome; normal authenticated replay also returns it if still permitted |
| Expiry/revocation/purge prevents resubmission | Lookup can report an existing workflow without source re-admission; absent outcome remains not-found/undelivered, never recreate from a cached receipt |
| Source commits, process dies before workflow admission, then source expires or authority is revoked | Authenticated retry is refused. With no workflow receipt, lookup returns not-found. The original uncertain attempt has no accepted workflow outcome and must not be reported as accepted or persisted no-match; do not complete it from a cached source receipt. No guaranteed recovery is promised. |
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

Review repair contract: the receipt import introduced in `1025b653` reaches the
operational Lead Intake modules through the eager package initializer, contrary
to the dependency-light requirement. Keep the common projection in place and make
`lead_intake/__init__.py` the single owner of lazy public export resolution. Preserve
all exported names and object identities; importing pure source/receipt contracts
must not load admission, authentication or source-store modules. Regression probes
run in fresh interpreters, including both import orders and a simulated future
handoff import. No facade is implemented or exported by this repair.

The same commit's kit proof lacked a regression for persistence followed by
`EventInputError`: its existing fake returned success and was stopped by an earlier
guard. Add a real-store write-then-refuse probe and demonstrate that removing the
row-emptiness assertion makes it fail. Preserve production kit behavior. Run the
new negative probes before the fix, then affected source, receipt and kit tests,
lint and native Windows CI. No receipt fields, schema, signing bytes, authentication
rules, public export names or accepted application behavior change. Rollback is
limited to the lazy-export change and these tests; retained data is unchanged.

Implementation summary: `ReceiptReference` now owns the unchanged common fields
and interval validator, inherited by `SourceReceipt`. The event/trigger models,
canonical scope validator, transactional registration check and receipt-only kit
path implement the bounded surface above. Both generic submission methods reject
the new event before persistence. New synthetic tests and fixtures cover the
boundary and concurrent registration; native Windows includes both new test files.

Cold diff audit: receipt changes are factoring only; event/definition exports and
runtime policy are additive; the store uses its existing registration transaction
and tables; kit compilation reuses the existing artifact/signing owner. Existing
tests, golden fixtures, source/auth schema owners and dependencies are unchanged.
Durable proof and final CI/review status are recorded with the implementation PR.
Gap audit: the full handoff and foundation gates remain NOT DONE. This increment
is not merge-qualified until exact-head platform CI and reviews pass. No production
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
application adoption remain **NOT DONE**. Read-only receipt lookup, receipt
vocabulary and binding are merged. The subsequent bounded work orders below
record the regression repair and host-handoff preparation; no live handoff or
production adoption is claimed.

## Work order: persisted binding shape regression

Operator work order: "Let's do it", after the post-merge oversight finding on the
receipt vocabulary slice. Commit this work order before test changes.

Root cause: the corruption fixture in `tests/test_lead_receipt_vocabulary.py`
never supplies canonical non-object `bindings_json`. The production guard at
`WorkflowStore._check_lead_deployment` at that revision had the required shape
guard, but removing it allowed `.get` to raise an unbounded `AttributeError`
without failing the existing corruption cases. The guard and coverage gap originated in `1025b653`. The later
[projection review repair](#projection-review-repair-complete-binding-snapshots)
replaces the one-way comparison and shape check with complete canonical equality.

Required change surface: extend that existing fixture with canonical arrays,
null, boolean, number and string values, including empty/falsy and populated
representatives. Restore database triggers before invoking the real registration
owner. Require `EventBindingError`; do not add exception-catching or validation to
production. Prove unchanged object bindings remain accepted with adjacent tests.
No schema, API, runtime, custody, workflow, kit, dependency or CI changes.

Verification plan: record the existing corruption cases with only the dict guard
removed in an isolated process. Add the cases and require behavioral failures
from `.get` with that same mutant, then passing results with the production guard.
Run the adjacent vocabulary/event/kit tests and lint/format. Native Windows and
Linux CI must pass on the published head. Keep mutation output outside worktrees;
restore triggers in fixtures and never mutate production data. Independent review,
explicit oversight PASS and completed reconciled Codex review are all required
on the final head before merge, with no unresolved threads or changes requested.

Assumptions/blockers: this is missing regression proof, not an observed production
failure. Oversight's full-suite mutant report remains attributed until reproduced;
the targeted baseline is sufficient to isolate this fixture's gap. No new product
behavior requires acceptance. Rollback removes only these added test cases;
production behavior and stored data remain unchanged. Host submission remains a
separate contract-first slice after this repair is qualified.

Implementation summary and cold diff audit: to be recorded with test and mutation
evidence in the follow-up PR. Gap audit: NOT DONE until regression proof, platform
CI and exact-head approvals are complete.

## Work order: authenticated host submission and outcome lookup

Operator direction: "Let's do it", followed by "Continue", after the proposed
sequence of test-only regression repair followed by contract-first host submission.
The repair is merged in PR #27. This work-order change is documentation only;
implementation must follow in bounded PRs, after this work order's review. It
implements the accepted library-only boundary, not a production receiver.

### Current code inventory and integration gap

Source pin: `c1104a653c9eae092e8639359350cab55c83a62f`. Paths below are relative to
`src/connect_automate/`. These findings are source-confirmed, not qualification
results for the future combined boundary.

| Existing owner | Current evidence and invariant to preserve |
| --- | --- |
| `lead_intake/source.py:228-269` | Parse untrusted syntax and compute canonical source-payload digest; neither establishes authority. Reuse these functions rather than parse or hash source bytes independently. |
| `lead_intake/admission.py:160-235` | Every admission, including replay, authenticates signed bytes inside the source transaction; the returned receipt is constructed before leaving that transaction and returned after it exits. Preserve final authentication, replay, rotation and lifecycle rules. |
| `automate/runtime.py:111-150,203-204` | Pack/grant verification and binding registration already belong to `PackRuntime.load`. Its public submit boundary checks the current runtime license. Keep those owners and the existing grant-at-load semantics. |
| `automate/runtime.py:203-242`; `automate/engine.py:318-394` | Both generic event APIs refuse `LeadSourceEvent`; the engine has no matching branch for its trigger. Runtime dispatch is separate from admission and can run on replay. Do not repurpose generic submission for historical lookup. |
| `automate/store.py:474-548` | One reader validates canonical stored payload, fingerprint, occurrence, binding, version and record/event ownership, returning the original outcome. It currently discards the validated payload projection. |
| `automate/store.py:1019-1053` | `lookup_event` requires the digest of the complete canonical workflow event, not the source-payload digest; its result contains no source reference. |
| `automate/store.py:1055-1140` | `admit_event` already owns transactional workflow receipt/record/effects persistence and replay. Keep its operation identity and transaction. |

Root cause / required extension: source admission and workflow admission remain
unconnected. In addition, the existing lookup signature cannot satisfy historical
source lookup unchanged: event ID plus source-payload digest cannot reconstruct
first-acceptance time, admission ID and deadline after source custody disappears.
Do not obtain these fields by reading the source database or by accepting a caller's
cached receipt. The validated workflow receipt already contains them.

For `lookup_source_outcome`, `expected_payload_digest` means the canonical
**source payload** digest from `lead_intake.source.payload_digest`, as carried by
`ReceiptReference.payload_digest`. It never means the workflow-event fingerprint.
The existing `lookup_event` argument retains its existing event-fingerprint meaning.
Both digests remain validated independently; one must never substitute for the other.

Proven work inventory: preserve the existing frozen source/auth fixtures,
`test_lead_source_admission.py` replay/rotation/object-bypass tests, and source
clock/content/race tests. Preserve `test_workflow_receipt_lookup.py` original
outcome, no-match, revision, read-only and isolated-corruption tests, and
`test_lead_receipt_vocabulary.py` registration/reopen/concurrency cases. Reuse
`test_pack_kit_receipt.py` signed receipt-pack harness. Existing evidence is recorded
with the merged PRs; it is not evidence that a joined host boundary works. No
inference model, prompt, runtime settings or external provider participates here.

### Required change surface and order

Keep the following dependent implementation increments separately reviewable under
this one work order. Every implementation PR identifies its increment and includes
its own evidence. Do not expose the combined boundary as usable until all pass.

- **Validated historical receipt projection.** Extend the shared receipt reader
  at its existing owner to retain the validated event projection alongside the
  original outcome. Add a source-specific store lookup that requires the configured
  identity and source-payload digest, uses the existing read-only connection, and
  validates the embedded reference against the durable deployment binding. Reuse
  the same binding/version/canonical-bytes/ownership checks for admission, generic
  lookup and source lookup; no copied SQL validator. Keep existing `lookup_event`
  and `EventAdmission` public behavior compatible. No optional digest parameter
  that disables validation. Return a bounded immutable projection, including the
  stored source reference for both accepted and persisted no-match outcomes.
- **Authenticated host composition.** Add the library-only handoff facade and
  supported runtime operations from the accepted Submission section. Bind a real
  `SourceAdmission` owner and host clock through trusted configuration associated
  with the verified runtime; expose any necessary source deployment metadata
  through its owner rather than reaching into private database state. Freeze the
  configured binding/owner identity. License, pack and binding checks precede
  store access. Parse untrusted source syntax only to reject scope mismatch before
  mutation; authentication still belongs to `admit_source(raw)` on every submit.
  Compare its fresh durable reference with the configured route and parsed request
  before entering workflow admission. Never accept caller-created receipts or an
  earlier authentication result as submission authority.
- **Runtime selection and result boundary.** Factor the current engine selection
  path narrowly so the trusted handoff can match `LeadSourceTrigger` with the same
  initial-stage, ambiguity, version and effect rules. Keep both public generic
  submission APIs rejecting receipt-shaped input. Internal receipt plumbing is
  not a new public authorization API or reusable bypass token. Reuse existing
  admission and permitted action dispatch owners; do not add a dispatcher. The
  qualification pack has no actions. Return the exact closed/versioned result
  and lookup schemas defined above, with separate source/workflow replay flags.
- **Joined recovery and qualification.** Exercise the facade and both real stores
  through the existing synthetic signed-pack/source harnesses. Caller-driven
  retry retains the original signed request and route. Read-only lookup uses only
  authorized workflow metadata, performs no admission or dispatch, and works after
  expiry, purge, revocation and namespace retirement. Do not infer current source
  authorization or content availability from the returned historical result.

Potential files: `lead_intake/handoff.py` and its lazy export owner;
`lead_intake/admission.py` only for supported deployment metadata if required;
`automate/runtime.py`, `automate/engine.py` and the shared workflow receipt owner
in `automate/store.py`; focused handoff/lookup tests and the Windows test list.
The first increment must not introduce the facade or change engine admission.
The existing source parser, auth, custody, content lifecycle and receipt schema
are authoritative and must not acquire parallel implementations.

Differences from proven work are limited to retaining validated receipt metadata,
source-digest-specific lookup, trusted configuration and composition, explicit
lead-trigger matching, and joined result/recovery proof. No schema migration,
changed identity, new clock policy, source-lock extension or two-database commit.
If evidence requires another difference, revise this canonical work order before
editing code; a plausible implementation is not evidence of parity.

### Verification and acceptance evidence

Before executable changes, run unchanged baseline tests for each touched owner's
existing contracts. Run new targeted fail-first tests, adjacent lanes, lint/format,
then native Windows and Linux CI from the first implementation push. Every new
security or data-integrity guard needs a corruption fixture that reaches that guard
alone, with schema triggers restored, and behavioral mutation proof. Reuse existing
race/crash harnesses; a setup error or timeout is not a successful mutation kill.

| Increment / gate prerequisite | Required observable proof |
| --- | --- |
| Receipt projection / G3 | Source and workflow digests are different and each enforced; valid accepted/no-match/absent results; corrupt embedded reference, canonical payload, ownership or foreign deployment rejected; generic lookup/replay behavior unchanged; no writes, clock changes or source-store access. |
| Submission / G1, G2 | Body-only and unavailable source accepted; valid signed source reauthenticates on replay/key rotation; conflicting signed payload refuses; unknown binding, foreign host/org/namespace and license denial stop before mutation; copied result/model/dict and raw lead event cannot bypass admission; distinct events remain distinct workflow occurrences. |
| Reviewable metadata / G2 | Exact bounded result schemas, source/workflow flags independently correct, original workflow outcome after later advancement, no invented receipt/IDs on absence, durable no-match not mislabeled as extraction or approval. |
| Joined recovery / G3 | Separate-process concurrent submissions and deterministic barriers before/after each store commit, workflow row writes and lost response; no partial workflow or duplicate occurrence; retry and lookup obey [Recovery limits](#recovery-limits). Source commit alone is never reported as workflow acceptance. |
| Source-only crash with lost authorization / G3 | Commit source custody, terminate before any workflow admission, then independently test deadline expiry and key revocation. Same signed retry must be refused; authorized lookup must return not-found with no workflow receipt/record/effects. Assert no accepted or persisted no-match result and no fallback using a copied source receipt. The original uncertain submission remains non-accepted/unknown; not-found is an observation, not a guarantee against another concurrent commit. |
| Privacy/platform / G6 | Synthetic body sentinel absent from workflow rows, errors and logs; lookup survives source lifecycle changes without reading content; licensed scope enforced before absence; native Windows/Linux process and filesystem proof. |

The source writer must be released before workflow admission. Revocation after
source authorization linearizes may precede workflow commit; the accepted contract
permits only the metadata outcome, not cached content authority. Test that ordering
explicitly. Apply [Recovery limits](#recovery-limits) to uncertain submissions;
never fabricate failure, persisted no-match or acceptance from an uncertain commit.
Full foundation gates and live adoption remain open.

### Non-scope, risks and recovery

No service, CLI receiver, mailbox polling, scheduler, new queue or workflow engine;
no direct cross-application database access; no extraction, canonical lead creation,
CRM adapter, new approval policy or EOM change. Do not change retention/deletion
semantics, source authority, signed pack bytes or public mail/schedule behavior.
Production metadata retention/encryption and durable producer retry custody remain
unresolved adoption requirements. Employee authorization is not supplied by the
licensed subject or this in-process configuration. Same-process hostile Python
reflection is not a sandbox claim.

Primary risks: weakening the shared receipt validator, exposing a copied-receipt
submission path, conflating digests, dispatch during lookup, or reporting workflow
acceptance after only source commit. Preserve original fixtures and test those
paths directly. Rollback disables the configured host facade while retaining both
stores and signed artifacts; never delete receipts to retry or reinterpret lead
receipts as mail. Keep each increment unpublished to applications until joined
qualification passes. A missing review or native Windows proof blocks merge.

Implementation summary: documentation only; no facade or store behavior changed.
Cold diff audit: this work order names the current source owners, the demonstrated
lookup gap and the smallest dependent increments; the status and stale final-scope
summary are updated to point here. Gap audit: work-order review and implementation
are **NOT DONE**. Required merge gates remain explicit oversight PASS and an
independent exact-head review reporting no open blockers (a `COMMENT` verdict may
satisfy this; GitHub `APPROVED` state is not required), completed/reconciled Codex
review, green required CI and clean local/remote equality, followed by a guarded
merge commit and reviewed-tree proof.

## Implementation increment: validated historical receipt projection

Operator direction: "Continue" after the bounded projection slice was identified.
This is the first increment of the merged host-handoff work order. Commit this
implementation contract before executable changes.

Root cause: `_read_event_receipt` validates stored event bytes but discards their
projection; `lookup_event` requires the workflow fingerprint, which callers with
only the source-event identity/digest cannot reconstruct. Preserve this reader as
the integrity owner; do not create a second receipt validator.

Required change surface: `automate/store.py` retains a private validated event plus
original outcome internally, unwrapping the unchanged `EventAdmission` for existing
lookup/admission callers. Add `lookup_source_event` accepting configured subject,
pack/version, binding, a revalidated lead `SourceBinding`, source event ID and
required source-payload digest. Return a frozen `SourceEventReceipt` containing
`source_receipt` and the original `outcome`, or None for valid scoped absence.
The new store API is an internal persistence primitive, not licensed host access,
authentication or submission authority. It reads no SourceStore or clock.

Use the existing read-only connection, canonical scope validator and deployment
binding integrity owner. Check configuration against durable scope and policy
before absence; validate the embedded reference against that scope before exposing
an outcome. Keep workflow fingerprint self-integrity distinct from the required
source-payload comparison. Both digest modes are explicit and mandatory; no None
or optional argument may disable a check. Generic lookup and replay retain their
existing return types, fingerprint meanings and refusal behavior.

Non-scope: no handoff facade, engine/runtime admission change, source authentication,
custody or schema change, new dispatch, migration, wire result schema, library
adoption or EOM behavior. No changes to existing fixtures/tests except adding the
new focused test module to Windows CI. Existing models/validators remain the owners
of their field syntax and canonical representation.

Verification: run unchanged receipt/read-connection/event/vocabulary and source
parser/auth baseline before production edits. Fail first on the missing supported
lookup. Prove accepted/no-match/absence, original outcome after advancement/reopen,
strict configured scope and required input checks before opening, independent source
and event digests, immutable reference/outcome, and read-only snapshots under real
separate-process commit. Corrupt one invariant at a time with restored triggers;
cover payload, record/event ownership, persisted binding and embedded scope. Mutate
new critical guards and require behavioral failures, not setup errors. Run adjacent
legacy lanes unchanged, lint/format and native Windows/Linux CI on the published
head. Baseline fixtures and existing schema text must remain unchanged.

Assumptions: trusted host configuration will supply the binding in the later
increment; this API cannot establish principal authorization. Receipt metadata is
historical, not evidence of live content. No model/inference settings participate.
Differences from proven code are only retaining its validated projection and adding
the bounded source-specific read boundary. Rollback removes that unused read API;
preserve stored receipts and all existing lookup/admission behavior. A changed
shared validator is the primary regression risk, guarded by unchanged replay tests.

Implementation summary: the shared reader retains its parsed event and original
outcome, and `lookup_source_event` returns a frozen source-reference projection.
Existing lookup/admission callers unwrap the unchanged outcome. Deployment and
policy checks reuse the registration owner within the read-only snapshot.

Cold diff: production changes are confined to `automate/store.py`; a focused new
test module covers source lookup and is added to the existing Windows lane.
Existing tests, schemas, engine/runtime and source custody remain unchanged. Local
baseline, fail-first, affected parity and behavioral mutation proof are recorded
with the implementation PR. Gap audit: NOT DONE until native platform CI and both
exact-head reviews pass. Stop at this increment; no facade work here.

### Projection review repair: complete binding snapshots

Root cause: the deployment validator introduced in `1025b653` walks only durable
lead binding rows. A canonical snapshot may contain an extra entry, or exist with
no corresponding rows, without that configuration participating in validation.
The projection reader inherited this one-way comparison. This session owns the
origin defect; repair `_check_lead_deployment`, not a later lookup guard.

Required change: reconstruct complete per-subject/pack configurations from durable
rows and compare each canonical object snapshot to that complete map. Reject
missing snapshots, extra entries, missing entries and snapshot-only configurations.
Keep lead scope/policy validation in the same owner; registration and projection
must both consume it. Valid empty and mixed generic/lead configurations remain
supported. The existing registration comparison to incoming configuration still
owns immutability of the requested configuration, including generic-only callers.
No schema, API, custody, authentication or handoff changes. The earlier shape
regression proves object shape only, not full configuration integrity.

Verification: synthetic restored-trigger corruption tests through lookup (receipt
present and absent) and registration; same/foreign deployment extras, malformed
extra values, generic extras, snapshot-only sets and missing snapshots. Assert
failures leave rows unchanged. Include valid mixed bindings across subjects/packs
and empty snapshots. Pin refusal of a plain dictionary equal to a valid configured
binding, before opening the store. Fail-first at the published implementation;
then adjacent suites, lint/format and mutations of full-map equality, orphan-row
refusal and the configured-model type guard. Native CI and both exact-head reviews
remain required. Regression cases live in the new projection test module, already
included in Windows CI; prior test files remain unchanged.


## Implementation increment: authenticated host composition

Operator direction: "Let's start the next slice", after the reviewed projection
increment merged. This implementation contract is committed before executable
changes. Baseline is `de27e0a992e7ef176ceb0860e47bfc448109ee0f`.

Root cause: verified `PackRuntime.load` owns pack/grant and binding registration,
but has no trusted source owner or host workflow clock. `SourceAdmission` already
authenticates raw bytes on every call and releases its writer before returning.
`WorkflowStore.lookup_source_event` now provides historical metadata. Compose
those owners; do not implement another verifier or access another owner's SQL.

Proven inventory: reuse source/auth frozen fixtures, real SourceStore bootstrap,
source replay/key-rotation/conflict/uncertain-commit tests, the signed pack/grant
fixtures, licensed host harness, and projection/read-only tests. No model, prompt,
provider or runtime tuning participates. Source parsing, payload hashing, receipt
models, deployment syntax, event time and licensed access retain their current
owners. No baseline fixtures change.

Required change surface:
- `SourceAdmission.deployment` exposes only its configured host/organization tuple,
  without I/O. It is configuration metadata, not authenticated authority.
- Optional paired `source_admission` and `source_clock` configuration on verified
  `PackRuntime.load`. Validate the real owner, callable clock and all lead routes
  after pack/grant verification and before durable binding registration. Freeze
  route copies and owner/clock references for the runtime lifetime. Reject partial
  configuration, a foreign deployment, or supplying an owner to a non-lead pack.
  Existing runtimes without these options remain compatible.
- A private immutable `lead_intake/handoff.py` composition object prepares a
  metadata-only event from raw signed bytes. The runtime gate checks license and
  configured lead binding before reaching it. It parses only to reject mismatched
  host/organization/namespace before mutation; then calls the real admission owner
  every time. Its fresh validated receipt must agree with the route and request's
  identity, digest and recovery deadline. Sample the configured workflow clock and
  reuse event-time validation. Never accept caller-supplied receipts/results as
  input, never call back under a source transaction, and propagate source uncertainty.
- Private runtime preparation and historical lookup paths are the testable
  composition seams for the next increment. Lookup delegates to the existing
  source receipt reader with the verified subject/pack/version and frozen binding;
  it uses no source owner or clock, so it also works in a lookup-only runtime with
  no source admission configured. Map the existing pack-version refusal as the
  generic engine already does.

Increment boundary clarification: the work order reserves selection and public
closed/versioned results for the next increment. Therefore this increment does
not publish `submit_source` or `lookup_source_outcome`, export a facade/result as
public authority, add a callback accepting prepared receipts, or claim workflow
acceptance. Private preparation commits source custody only; its immutable metadata
is not a reusable submission credential. Next increment must compose it inline
from raw bytes, never accept it from a caller. Generic runtime and engine receipt
submission refusal stays unchanged. Lazy package exports remain unchanged until
there is a complete supported public boundary.

Non-scope: engine selection, workflow admission/dispatch, public result schemas,
joined crash qualification, migrations, retention, content, source authentication,
EOM, live application adoption and issue #31's separate test-only follow-up.
No two-store transaction or source lock extension. Same-process hostile reflection
is not a sandbox claim; employee authorization and production retention remain open.

Verification: unchanged touched-owner baseline before source edits; missing-config
API fail-first; real signed-source preparation for available/unavailable bodies,
replay, key rotation, conflicts and revoked signatures. License, pack/grant,
binding and deployment failures must precede store mutation; malformed inputs and
copied result/model/dict cannot skip admission. Probe each fresh receipt mismatch
independently, with valid neighboring fields, and fail closed on owner drift.
Prove both owner/clock references and binding mappings cannot be reassigned through
public configuration, and private preparation cannot create workflow rows or call
dispatch. Historical lookup must use only workflow reads and preserve receipt
absence/accepted/no-match/revision/digest behavior. Reuse unchanged import-cycle,
parser/auth/admission/runtime/projection lanes; add focused tests to Windows from
the first push. Mutate each new security/integrity clause and require behavioral
failures. Native Linux/Windows CI and both exact-head reviews gate merge.

Risks: returning source custody as workflow acceptance, accidentally trusting a
parsed request or copied receipt, eager import cycles, and mutable route rebinding.
Rollback removes optional host composition while retaining both stores and all
existing raw-source and generic event behavior. No production adoption. Cold diff
and evidence are recorded with the implementation. Gap audit: NOT DONE until this
bounded increment passes; public handoff and joined qualification remain later.


Implementation summary: optional owner/clock configuration is validated after
pack/grant verification and before registration. Frozen private handoffs use the
existing source admission and receipt models; private historical lookup uses the
existing workflow reader. SourceBinding model validation/copying remains solely
in the runtime binding owner; handoff does not duplicate it. Operational imports
are deferred to configured loading, preserving pure receipt import paths.

Cold diff: runtime composition and immutable binding maps, an I/O-free admission
metadata property, a private handoff module, focused real-store tests, and the
Windows lane entry. Existing source/auth/custody/engine/store implementations,
package exports and old tests are unchanged. The focused suite uses a real
signed-pack revision conflict and explicitly proves prepared metadata remains
rejected by both generic submission APIs. Gap audit: local evidence accompanies
the PR; native CI and both reviews remain pending. No public handoff, workflow
acceptance, adoption or subsequent increment is claimed.


## Runtime selection and public result work order

Operator direction: "lets start the next slice", after the reviewed merge of
host composition. This is the runtime selection and result boundary increment
of the accepted host-submission work order. Commit this section before executable
changes. Joined process-crash qualification and adoption remain a later increment.

### Inventory, root cause and differences

Baseline: `2b762a8e641a1316c3b35c3db97e6586eddc142b`. The existing
`lead_intake/handoff.py:_SourceHandoff.prepare` reauthenticates raw signed bytes,
validates the fresh durable reference and samples the workflow clock after source
admission. `PackRuntime._prepare_source` and `_lookup_source_receipt` own the
licensed configured route. `WorkflowEngine.submit_event` owns selection inside
`WorkflowStore.admit_event` but rejects lead events and cannot match their trigger.
`WorkflowStore.lookup_source_event` already returns the validated original outcome
and stored source reference without source reads. Reuse these owners unchanged
where possible, along with `_dispatch_event_actions`; no second selector,
transaction, dispatcher, source reader or digest implementation.

Validated fixtures are the existing source/auth/admission lanes, private host
composition tests, event/engine/runtime tests and source-event receipt lookup
harness. They use synthetic Ed25519 sources, signed packs, real SQLite stores and
fixed host clocks, without a model or external service. Their merged evidence is
not joined-boundary proof. Record an unchanged baseline before implementation.
The only intended departures are a private shared engine admission path with
lead-trigger matching; public runtime submit/lookup; pure closed result models
and sanitized uncertainty handling. Existing generic methods still reject leads.
The obsolete host-composition assertion that submit_source is absent is replaced
with proof that calling private preparation still cannot admit a workflow. No
other existing test behavior or fixtures are rewritten. The exact public-export
inventory test also adds the declared result/unknown names while preserving
all prior names and identity assertions.

### Required surface, invariants and failure semantics

Expose keyword-only `PackRuntime.submit_source(binding, raw_source_bytes)` and
`lookup_source_outcome(binding, event_id, expected_payload_digest)`. No public
operation accepts prepared data or a receipt as authority. Submission always calls
the existing authenticated preparation, even on replay, then checks the current
license and calls the private shared engine owner. Factor selection/admission from
`submit_event` narrowly; initial-stage conditions, ambiguity, immutable occurrence,
pack revision, effects and outbox rules stay the same. Add only explicit matching
for LeadSourceTrigger and LeadSourceEvent. Reuse permitted event dispatch and
safe-replay behavior. The proof pack emits no actions; no external effect enabled.

Pure immutable result models live in `lead_intake/results.py`, with lazy exports.
They implement the exact schema names/versions in Submission above, strict Boolean
flags, ReceiptReference and bounded workflow identifiers/stage/version. The workflow
projection fields are `workflow_record_id`, `workflow_event_id`, `stage` and
`state_version`. Accepted requires all four; no_match requires nulls and false
workflow_applied. Lookup adds not_found with null source_receipt and null projection,
never source_applied and always false workflow_applied. Unknown/extra fields and
coercion fail closed. Validate and enforce MAX_EVENT_BYTES on every returned model.
Share result projection/validation ownership; invalid internal outcomes must fail
closed rather than return partial success or manufacture absence.

Known input, authentication, route, license, conflict, ambiguity and revision
refusals retain their bounded existing exceptions; none asserts absence of prior
source custody. Unclassified operational failures, source unavailable/uncertain,
post-admission clock refusal, workflow I/O, dispatch failure and invalid result
projection raise a fixed input-free SourceHandoffUnknown outside the caught
exception context. This error asserts neither source nor workflow absence. Do
not expose raw bodies, SQL, paths, exception chains or result-validation payloads.
Use authenticated retry or historical lookup to determine durable state. Lookup
must never map store errors to not_found; its errors are also bounded. Missing
source-owner configuration still allows authorized lookup-only operation.

### Verification, risk and rollback

First record missing-public-method fail-first evidence. Then prove real body-only
and unavailable source submission, persisted no-match, independent source/workflow
replay flags, original outcome after later advancement, replay after source-only
commit, key rotation and revocation, conflicting signed payload, distinct events,
foreign/invalid route and license refusal, copied-result/raw-event bypass, mixed
lead/generic packs, initial-stage/ambiguous trigger selection and pack-version
conflicts. Test public lookup absence/accepted/no-match without source access,
clock, writers or dispatch. Test strictly closed result variants, falsy values,
size boundaries, and sanitized errors before/after source and workflow commits.
Keep result unknown when source commit has happened but preparation fails.

Use unchanged source/receipt harnesses and real stores, focused fail-first plus
adjacent tests and lint. Add the new test lane to native Windows on first push.
Behavioral mutations must separately pin lead selection, reauthentication,
source-replay continuation, uncertainty mapping, projection and lookup no-effects.
The clock-order and mixed-pack regression gaps from issue #33 may be covered in
this directly affected boundary with causal proof; do not change their correct
production semantics. Existing generic tests prove parity before new behavior.
Full separate-process joined concurrency/crash/retirement qualification remains
the next increment, not a claim of this slice.

Risk: factoring selection can regress generic events; preserve their tests and
transaction owner. Result mapping can overstate success after partial commits;
real owner fault injection and historical lookup guard this. Rollback disables
public submission and restores the generic-only engine caller while preserving
both stores and signed packs; no receipt deletion, migration or downgrade. No
new services, mailbox path, extraction, approval, delivery, scheduler, application
adoption, retention-policy change or cross-store transaction. Both exact-head
independent approval and oversight PASS, completed Codex reconciliation, native
CI and clean local/remote parity remain mandatory before guarded merge.

Gap audit: NOT DONE until this increment passes its gates. The public methods
are library-only; the combined boundary remains unqualified for adoption until
the subsequent joined recovery increment and deployment prerequisites pass.


### Pre-publication repair: result contract import boundary

The new result module initially imported MAX_EVENT_BYTES from automate.events.
Python first executes automate/__init__.py, which imports runtime/store; the new
fresh-interpreter regression fails on that operational dependency. This was
introduced by this increment's uncommitted results.py import, not by the source
or receipt owners. Move the unchanged event cap to a dependency-free package-root
`_event_limits.py` and re-export it from automate.events. Both event parser and
result models use that single owner. No event parsing, bytes, schema or cap value
changes, and no automate package initializer rewrite. Retain the fresh-interpreter
failure as the regression; prove import/validation purity and existing event tests.
Rollback restores the prior cap location when removing the new result consumer.


### Runtime/result implementation evidence

The implementation adds the public submit/lookup pair and closed result models,
with a private shared engine admission owner and an explicit lead-trigger branch.
Generic submission still rejects receipts. Known bounded refusals remain refusals;
operational uncertainty raises SourceHandoffUnknown without sensitive exception
context, including source custody committed before clock/receipt validation fails.
Historical lookup does not touch the source owner, clock, writer or dispatcher.
The event byte cap has one dependency-free owner, re-exported at its former path.

The new tests use real signed sources and packs, source-only commits, replay and
historical projection. A valid lead trigger always matches its guarded initial
stage; no-match coverage therefore seeds a historical receipt through the existing
store harness and proves it replays unchanged. Invalid initial-stage packs remain
negative tests. Issue #33 clock-order and mixed-pack regressions are included and
both corresponding mutations are detected without changing those production paths.

Cold diff: source/auth/admission/custody/content and workflow store/actions/definition
owners are byte-identical to the merged baseline. Existing generic runtime methods
and private preparation/lookup are AST-identical. The factored engine transaction
and selector are AST-identical after removing the new lead branch. Only the obsolete
absence assertion and additive export inventory change in prior test files; the
new test file is included in native Windows CI. No source schema or migration.

Local evidence: unchanged baseline 715 passed; missing-method fail-first 2 failed;
final adjacent lane 1123 passed; 19 behavioral mutants killed; lint, format and
diff checks passed. The first expanded fixtures incorrectly targeted a non-initial
stage and were corrected at the test owner. The new result import caused runtime
loading and was repaired at the shared limit dependency; its regression passes.
Raw evidence is retained outside the worktree under the lead-runtime-results alias.
Native CI and both exact-head reviews remain publication/merge gates. Gap audit:
NOT DONE until those gates pass. Joined process recovery, retirement/expiry proof,
real producer transport and deployment/adoption remain outside this increment.

### Review repair: returned dispatch failures

Root cause: this session's 364124f (ported as d55fcbd),
`PackRuntime.submit_source`, discarded returned ActionOutcome values; only raised
failures reached the bounded error path. A missing-title local action reproduces
accepted on first submit and replay while its durable action remains failed.
Required surface: inspect dispatch statuses at this owner; only settled outcomes
permit the existing result. Pending/failed outcomes use the already-contracted
SourceHandoffUnknown path outside exception handlers. Historical lookup still
reports known workflow acceptance; unknown does not assert absence or retryability.
Non-scope: result schema/exports, generic APIs, action runner/store/retry rules,
source custody and the deferred refusal pins. No compensating downstream checks.
Verification: real adapter failure, pending, mixed success/failure, safe replay,
settled replay and no-action success; fail-first regression, adjacent tests, lint.
Rollback removes only this status check. This repairs the accepted dispatch-failure
contract and intentionally breaks frozen-tree equality; record the exact delta.
Gap audit: NOT DONE until regression proof, CI and both fresh approvals pass.


### Issue #37 work order: isolated public refusal classifications

Operator direction: "lets pick up 37 next". Baseline is merged runtime
`6be0f5521b0161251d70ef513c9db3e67d7a4216`; joined-recovery preparation stays on
its separate local branch. Commit this test-only contract before executable tests.

Root cause: the public runtime refusal handlers added in 364124f (ported as
d55fcbd) are correct, but existing coverage does not independently pin phase-two
EventBindingError/EventConflict or public-lookup EventInputError. Removing those
exceptions from their handler tuples must fail behaviorally rather than hide as
SourceHandoffUnknown. This is a coverage defect, not a production behavior defect.

Required surface: extend tests/test_lead_runtime_results.py using its real signed
source/pack fixtures and the existing trigger-restoring corruption helper. Reach
the workflow reader only after successful authenticated source preparation. Change
one binding or receipt field per case, assert bounded exact refusal and unchanged
workflow rows, restore that field and prove valid replay. Lookup cases separately
cover malformed event ID/digest, including falsy/wrong types and digest boundaries;
assert refusal before any source/workflow storage access and a valid control.
Existing native Windows selection already includes this file; no CI edit needed.

Verification: unchanged focused baseline; new tests pass on unchanged production;
in-memory mutations remove only the named exception from its actual public-method
handler tuple. Each corresponding test must then fail with SourceHandoffUnknown,
not fixture/schema/setup failure. Run adjacent runtime/receipt lookup tests, lint,
format and cold diff; retain raw outputs outside worktrees. No broad duplicate CI
suite. No schema, runtime, store, authentication, dispatch, retry, retention,
dependency or joined-recovery change. Rollback removes only these new tests.
Assumption: existing behavior matches the issue; a reproduced implementation defect
requires its own origin analysis and repair contract before production edits.
Gap audit: NOT DONE until test and mutation proof, native CI and both exact-head
reviews pass. This slice does not qualify joined recovery or production adoption.

## Joined recovery and qualification work order

Operator direction: "lets merge and continue", given directly in the Codex
session and recorded on PR #36 in comment 6306879217. PR #35 and PR #36 have
merged in order. Baseline is `6be0f5521b0161251d70ef513c9db3e67d7a4216`, whose
tree equals the reviewed dispatch repair `fc76748ef1ce3c2782875c32240405bae3143edd`.
This reconciles the unpublished preparation `e2417a8` against merged code; that
preparation remains historical and is not cherry-picked over the repaired parent.
Oversight's merge verification and bounded-stack direction are recorded in mailbox
message dated 2026-10-21T03:11:34+00:00. Contract commits precede executable changes
in each qualification PR; both approvals remain required for every published head.

### Source inventory and preserved specification

Paths and lines below refer to the merged baseline, not production readiness.
Existing proof uses synthetic Ed25519-signed envelopes,
signed no-action packs, real SQLite files, licensed test hosts and explicit UTC
clocks. No model, prompt, external mail service or inference runtime participates.

| Existing owner / harness | Reuse and gap |
| --- | --- |
| `lead_intake/admission.py:165`, `source_store.py:383` | Source authentication, replay, custody and commit uncertainty remain at the source owner. |
| `lead_intake/handoff.py:55` | Fresh receipt checks and workflow clock sampling happen after source admission; do not cache this prepared value as authority. |
| `automate/runtime.py:282,356` | Public submit/lookup compose the owners; source/workflow flags remain independent. Returned failed/pending actions now use bounded unknown, while settled replay and no-action success remain valid. |
| `automate/store.py:876,1116,1161,1270,1532` | Existing writer, historical reader and workflow transaction own receipt/record/effect atomicity; do not add tables or a recovery dispatcher. |
| `lead_intake/content.py:75,101,124,156,168` | Read, expiry cleanup, capture-cutoff message purge, namespace retirement and retired cleanup remain authoritative. |
| `tests/test_lead_host_composition.py:61`, `test_lead_runtime_results.py:58,422` | Reuse signed pack/source setup and parent in-process failure proofs; they do not prove joined process-crash recovery. |
| `tests/test_lead_source_admission.py:394,422,475` | Reuse spawn-process startup, bounded joins, observed exit codes, real SQLite commit hooks and guaranteed child/IPC cleanup. |
| `tests/test_lead_source_races.py:25,108` | Reuse checkpoint/release signaling and observed writer contention, without timing-based ordering. |
| `tests/test_workflow_receipt_lookup.py:384,404` | Reuse separate-process commit/read-snapshot proof; absence is only an observation at a read. |

Root cause of the qualification gap: the parent proves in-process composition
and each store already has its own recovery tests, but no test drives the public
host boundary through both stores across an actual process exit or concurrent
process submission. A source-only receipt cannot establish workflow acceptance.
The accepted [Recovery limits](#recovery-limits) table remains the single owner
of outcome semantics; this work order specifies evidence, not a new recovery policy.

### Minimal surface and differences from existing proof

Add the bounded qualification files listed below to the existing native Windows
lane when each first publishes; Linux already collects tests. Reuse existing
synthetic signing,
source-store construction, workflow setup and lifecycle helpers. A bounded test
harness may extend their instrumentation to distinguish the two database files
and public call boundaries. Keep instrumentation in tests, never production hooks.
Use spawn-compatible module-level workers and durable parent-held request/route
fixtures. Each child reconstructs its own verified runtime against the same stores
and signed pack revision. Give each child's test entitlement files their own path;
do not race license fixture creation. Complete runtime load/binding registration
before installing submission crash hooks so setup commits cannot masquerade as
source/workflow submission checkpoints.

The only planned departures are joined-store observation, public-boundary process
fault injection, and lifecycle-aware historical lookup. Production code, schema,
source/wire contracts, timing policy, authentication, retention and result variants
must remain unchanged. If qualification reproduces a defect, isolate its first
owner and introducing commit, record a repair contract before code changes, and
retain the reproduction as a regression; do not mask it in the test harness or
change accepted behavior silently. Technical repairs remain with this coding arc.

### Bounded stack and dispatch-repair reconciliation

Split qualification into these ordered PRs, each targeting about 1,000 changed
lines or less including its contract, tests and CI selection. If the measured diff
needs another split, partition proof responsibilities before publication; do not
omit failure cases or compress assertions to satisfy the size target.

1. **Joined crash and transaction proof**, starting from the merged baseline:
   `tests/test_lead_joined_recovery.py`. Cover observed source/workflow commit
   checkpoints, lost responses, workflow row-write rollback, retained-request
   replay, durable identities/flags and body-sentinel exclusion. Reuse a no-action
   pack; explicitly assert its outbox is empty. This is the first implementation
   slice, with this work-order commit first.
2. **Joined concurrent identity proof**, stacked on the first:
   `tests/test_lead_joined_concurrency.py`, reusing its spawn/checkpoint harness.
   Cover same event, distinct events per message, signed conflict, rotated-key
   replay, opposite source/workflow winners and snapshot lookup during commit.
   Its bounded work order must be committed before extending the harness or tests.
3. **Joined authorization and lifecycle proof**, stacked on the concurrency slice:
   `tests/test_lead_joined_lifecycle.py`. Cover source-only recovery denial after
   revocation/deadline, copied-authority refusal, both lifecycle/admission orders,
   lookup-only operation after content cleanup/purge/retirement, and original
   metadata after advancement. Commit its focused work order before tests.

This preserves the complete matrix below; it does not claim any slice qualifies
another's behavior. Reconcile each child against repairs to its parent before
publishing it. Both exact-head reviews and native platform gates apply separately.

The inspected source, custody, content, handoff, workflow store and reused harness
files are byte-identical to the prior inventory. The runtime difference is the
merged dispatch-status repair. Preserve that check and its regression unchanged:
failed or pending dispatch cannot return a plain successful handoff; Unknown does
not promise absence or retryability, and lookup reports historical workflow state.
The qualification pack remains no-action, so process qualification does not claim
to prove effect delivery. Existing real-action regressions remain adjacent checks.
No other runtime, schema, clock, signing, fixture or policy difference is planned.

### Required proof matrix

- Crash before source commit, after source commit before its reply, after source
  return before workflow admission, before workflow commit, immediately after
  workflow commit, and after public completion before a response is delivered.
  Observe the targeted checkpoint before termination. Reopen both stores and
  inspect durable rows through their existing owners. Retry the original signed
  bytes and configured route only while authorization remains valid. Assert
  stable source/workflow IDs, flags and original outcome, and no duplicate records.
- Inject SQL failures and process exits between observed workflow row writes in
  the real admission transaction, including bootstrap, transition/operation and
  receipt writes. Derive the checkpoint list from the actual SQL trace so every
  exercised row write is accounted for. Before commit, no partial receipt, record,
  event, operation or action may survive. The qualification pack has no actions;
  verify its outbox remains empty. Do not invent effect delivery qualification.
- Concurrent spawned submissions cover the same signed event, different signed
  events for the same message, a signed conflicting payload, and key-rotated replay.
  Rendezvous before the public call; use observed transaction checkpoints for
  controlled overlap. Assert compatible outcomes and exact durable cardinalities,
  not merely that both child processes exited successfully. Replays preserve the
  first receipt and workflow occurrence. Also force the source-commit winner to
  pause while the replaying process wins workflow admission: source_applied and
  workflow_applied must remain independent, not tied to one process winning both
  stores. A conflict never creates an alternate ID.
- After source-only crash, separately expire the recovery deadline and revoke
  the signing grant before retry. Both retries must refuse current admission;
  authorized historical lookup must return not_found with no workflow rows or
  effects. Attempted recovery from a copied receipt/prepared result remains denied.
- For a committed workflow, exercise lookup after key revocation, expiry and
  content cleanup, message-wide purge, namespace retirement and retired cleanup.
  Reopen a lookup-only runtime with the original authorized binding/pack. It must
  return the original result without source database access, admission, a clock
  update or dispatch. Prove source content is unavailable through its owner where
  lifecycle policy requires it; workflow metadata never implies live content.
- Control both orders around the source authorization boundary: a lifecycle change
  before admission refuses under existing policy; one after final source commit
  but before workflow commit may coexist with metadata-only workflow acceptance.
  Show the source writer is released before the workflow transaction. Preserve
  the accepted late-deletion capture cutoff; do not reinterpret purge as deleting
  later captures or workflow metadata.
- Concurrent historical lookup may see absence before a later workflow commit;
  a subsequent read sees the committed outcome. Keep original record state after
  later advancement, source-payload digest conflict, pack revision refusal and
  licensed/binding refusal distinct from not_found. Use the existing snapshot
  reader; no new read/validation implementation.
- Verify synthetic raw-body sentinels are absent from workflow rows, serialized
  public results, captured logs and bounded exceptions. Retain metadata/privacy
  limitations: correlation IDs persist and no secure-erasure/compliance claim is
  established by these tests.

### Verification gates, risk and recovery

At each bounded slice, run the existing directly affected source-admission,
race/lifecycle, workflow snapshot and public-result baseline unchanged. New tests
must exercise actual operations rather than source-text assertions or mocked
successful outcomes. For existing-correct behavior, baseline success is expected;
prove causal regression sensitivity with in-memory mutants at the real owner.
For a reproduced defect, record failing-before/passing-after evidence before signoff.

Require deterministic assertions for the intended checkpoint, child exit status,
both stores' durable state, response flags and retry/lookup result. Timeouts are
harness failures, never successful crash/mutation proof. Flush checkpoint signaling
before abrupt exits; bound waits and always release/terminate/join children and
close IPC on failure. Do not use sleeps, fork-only state, global production paths,
private customer data or oversized parametrized test IDs. Native Windows and Linux
must run this lane from the first implementation push.

Run focused and adjacent lanes, lint/format, cold diff and causal mutations that
would suppress workflow admission on source replay, admit copied authority, lose
transaction atomicity or make lookup depend on live source custody. Source-level
corruption/replay fixtures remain unchanged and authoritative. Preserve artifacts
outside worktrees, including raw checkpoint traces, expected/actual outcomes and
platform results. Both independent exact-head approval and oversight PASS, Codex
reconciliation, green required CI, no unresolved threads, clean local/remote parity
and guarded merge/tree proof remain required.

Regression risk is primarily instrumentation at the wrong commit or a concurrency
harness that passes without overlap. Separate setup from operation hooks, assert
checkpoint identity and observed contention, and use real durable state as the
oracle. Rollback removes only the new qualification lane and its CI selection;
keep evidence, stores and signed fixtures. Any production repair needs its own
explicit rollback/recovery note without deleting receipts or rewriting history.

Non-scope: no new workflow engine, mailbox poller, watcher integration, scheduler,
stranded-receipt scan, queue, cross-store atomic commit, canonical lead/extraction,
approval/delivery, external effect, retention policy, authentication enrollment,
application adoption or EOM change. This proves caller-driven library recovery
under an explicitly retained request, not unattended production recovery.

Gap audit: reconciled work-order preparation only. Parent reviews and merges are
verified; executable qualification tests, joined recovery proof and native platform
qualification are NOT DONE. No tests are claimed executed by this documentation
commit. Full foundation gates and
production adoption remain open even after this bounded qualification succeeds.

### First slice implementation record

The preparation was normally merged with `12d31d61e740b1a719f5f253373ea0a651f96c17`
(PR #38), retaining its isolated refusal tests and both work orders. This parent
adds no production changes to the inventory. Operator direction for this slice:
"lets merge and pick up next slice". Only the first bounded slice is implemented
here; concurrency and authorization/lifecycle remain separate work orders.

The new spawn harness observes the actual SQLite commits after runtime loading,
derives workflow write checkpoints from executed SQL, and reopens both owners
before replaying the retained signed request. Available and unavailable bodies,
lost responses, SQL rollback and abrupt exits are covered. The no-action outbox
must stay empty. Existing production and existing test files remain unchanged.
Local evidence: 611 adjacent tests passed; injected replay suppression, rollback
commit, early commit and body logging were each rejected by behavioral assertions.
Evidence alias: `lead-joined-crash-proof`. Native platform CI and both exact-head
reviews are pending; this record does not qualify later slices or adoption.

### First slice repair contract: explicit child completion

Native Windows run 39540934788 at `11b97059d5f9179277615913d046ddc40b195266`
failed the new joined tests in `run_child`: its read loop polls after all messages
have arrived, assuming closure will be reported by recv as EOFError. Windows
PeekNamedPipe can instead raise BrokenPipeError from poll. This session introduced
that assumption in the same commit, tests/test_lead_joined_recovery.py:170-183.

Repair the harness protocol at its owner: the child sends a final completion
marker after its trace/logs and before deliberate exit; the parent consumes through
that marker and then independently verifies process exit, checkpoints, outcomes
and durable stores. Remove EOF-as-success, rather than catching arbitrary I/O errors
or increasing timeouts. Missing completion, timeout, unexpected exits and incomplete
outcomes remain failures. Search found no second copy of this EOF-draining loop in
the adjacent lead or workflow-lookup harnesses.

Reproduce with the real spawn harness and a parent-side pipe adapter that reports
peer closure as Windows poll does. Test normal and deliberate-crash completion,
and a missing-marker negative case. Run the repaired lane, lint/format and mutation
sensitivity, then require native Windows CI and both fresh reviews. Only this test
file and contract change; production, existing tests, timeout policy and CI gates
stay frozen. Rollback removes this harness repair without touching stored data.

## Joined concurrency qualification work order

Operator direction: "Lets start", following the merged crash/transaction slice.
Baseline: `580ffb51ef71b09e38b6cd517d232a71bb24ccaa` (PR #39), tree identical
to reviewed `17e82c02570bcefca80c24ca2667db9f53b57e97`. Commit this work order
before executable changes. This is only slice 2 of the bounded qualification stack.

Root cause of the evidence gap: separate-store races and joined sequential crash
recovery do not prove overlapping public submissions, independent source/workflow
winners, or a public historical read across a joined writer commit. The canonical
[Recovery limits](#recovery-limits) and preceding joined work order own semantics;
this slice adds proof without redefining identity, retry or delivery behavior.

Inventory to preserve: the signed no-action pack and source fixture, fixed NOW,
real private SQLite stores and unique per-child entitlement paths from
`tests/test_lead_joined_recovery.py:37,66`; its post-load connection hooks at :87,
explicit completion protocol at :172 and reopened custody validators at :213.
Reuse source writer-contention detection from `test_lead_source_races.py:25` and
the rotated authority/signature fixture pattern from
`test_lead_source_admission.py:219`. Reuse the pinned read-snapshot pattern at
`test_workflow_receipt_lookup.py:404`. Production owners remain
`SourceAdmission.admit_source`, `SourceStore._transaction`, `PackRuntime.submit_source`
and `WorkflowStore.admit_event/read_connection`. No runtime/model/prompt is added.

Required surface: add `tests/test_lead_joined_concurrency.py` and its first-push
native Windows CI selection. Extend the existing test worker with optional start,
pause and release signals, an observed source SQLITE_BUSY notification, and bounded
refusal results. Factor the shared parent message reader so completion recognition
has one owner and the merged Windows fix remains authoritative. Reuse fixture,
source signing, child runtime reconstruction and durable-state helpers. Extend the
custody inspection oracle only to accept the explicitly expected original envelopes
for multi-event and rotated-signature cases. Preserve all prior assertions/tests.

The planned differences from the inventory are controlled simultaneous workers,
SQLITE_BUSY observation after a real BEGIN attempt, and snapshot timing around the
public lookup. Controls are test-only and installed after runtime load. Every
worker waits for explicit parent release; no sleep-based ordering. Existing store
busy deadlines, signing inputs, clock, pack, record lifecycle and production code
stay unchanged. Only a reproduced product defect could justify a separately
recorded repair contract and regression; do not hide defects in the harness.

Required cases:
- Same signed event: two spawned public submissions overlap at the source writer;
  observe the second process's SQLITE_BUSY before releasing the first. Exactly one
  source receipt and workflow record/receipt, stable IDs and one applied flag per
  owner; authenticated replay adds nothing.
- Distinct event IDs for one message: the same overlap yields distinct admissions
  and workflow records for both events. Message identity alone must not collapse
  source-event identity; content and outcome cardinalities are checked.
- Signed conflicting payload for one event: the first source transaction wins;
  the contender receives the definite source conflict, never a second receipt,
  workflow record, or invented success. The original request remains replayable.
- Rotated-key replay: first preserve a source-only receipt, publish a new active
  grant while revoking the old one with the existing authority owner, then overlap
  two valid new-key submissions. Original receipt/content remain unchanged; only
  one workflow is created. The old signed request is refused, not used as authority.
- Opposite winners: pause the original submit after source return, let another
  process replay the same source and win workflow admission, then release the first.
  Assert source_applied/workflow_applied are independent for both responses.
- Snapshot lookup: pin the real workflow read snapshot before a spawned public
  writer commits. Observe its pre-commit checkpoint, release and finish the writer,
  then let that lookup finish on its original snapshot. It may report not_found;
  a subsequent fresh public read reports the committed original outcome. No lookup
  mutation, admission or dispatch is permitted.

Every case asserts observed checkpoints, successful process completion or explicit
expected refusal, both stores' exact durable cardinalities, retained original
content, stable receipt/workflow metadata, empty no-action outbox and body exclusion
from serialized outcomes/traces/workflow rows. Bound IPC waits, release/terminate/
join children and close handles on failure. Unexpected closure/timeout is a harness
failure, never a passing concurrency or mutation result.

Verification: unchanged joined recovery and adjacent source-race/receipt/public
result baseline; new focused concurrency lane; causal in-memory mutations at real
owners for event identity, replay/receipt reuse and independent applied flags.
Mutations must fail behavioral assertions, not setup, timeouts or absent overlap.
Run lint/format/cold diff and both native platforms; retain evidence outside the
worktree. No duplicate broad local CI suite. Both exact-head independent approval
and oversight PASS, clean Codex reconciliation and required CI remain merge gates.

Risk: false concurrency proof through sequential execution or confusing load-time
transactions with admission. Controls start only after both runtimes load, writer
contention is observed before release, and stored state is the outcome oracle.
Rollback removes only this test extension and its CI selection. No migrations,
source schema changes, retention decisions, new dispatcher, application adoption,
EOM changes or effect delivery. Arbitrary revocation/lifecycle ordering and copied
authority remain slice 3. Gap audit: contract only; implementation, native proof
and both reviews are NOT DONE.

### Concurrency slice implementation record

The unchanged joined/source-race/receipt/public-result baseline passed 340 tests
before helper edits. The completed joined lanes passed 23 tests, retaining the
original crash and Windows-completion test functions unchanged. Four real-owner
mutations were rejected by behavioral assertions: namespace substituted for event
identity, prior workflow receipt ignored, applied flags coupled, and the workflow
read snapshot unpinned. No timeout or setup failure is counted as mutation proof.

Only the work order, optional test-worker controls/shared reader, new concurrent
cases and Windows CI selection changed. The initial conflict fixture incorrectly
retained the old body length/digest after changing text; it was rejected before
contention. Repairing those fixture fields and signing again reaches the intended
SourceAdmissionConflict; parsing is now an explicit prerequisite of that test.
No production defect was reproduced. Evidence alias: `lead-joined-concurrency`.
Native Windows/Linux CI and both exact-head reviews are pending. This slice does
not qualify the deferred authorization/lifecycle slice or production adoption.
