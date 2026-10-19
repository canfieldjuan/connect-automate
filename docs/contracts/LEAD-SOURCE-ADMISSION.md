# Durable Lead Source Admission

Status: ACCEPTED WITH CONDITIONS — acceptance record below; contract only.
Implementation boundary: this update records acceptance and clarifications only;
implementation requires a separate branch and work order. No production adoption.

## Contract and stop boundary

Root cause: the source verifier returns a point-in-time assertion. It cannot
make source custody, duplicate prevention or concurrent revocation durable.
The missing owner is the transaction boundary between current local authority
and a persisted source receipt. This is a new opt-in boundary, not a repair to
deployed EOM behavior.

This change adds only this contract and records its conditional acceptance.
Publish the clarifications for independent review, then stop. No source, test,
database, migration, dependency, service, application pin or existing contract
changes are authorized by this documentation slice. Acceptance must precede a
separate implementation branch. Acceptance does not authorize production use.

Normative behavior below is accepted design, not implemented functionality.
CONFIRMED labels describe inspected code only; INFERRED and UNKNOWN labels
preserve the limits of that inspection.

### Acceptance record

Oversight relayed the operator's exact decision, **“Accept (Recommended)”**, for
revision `1c87feb0248056a64318461a0675c56959a4e70d`, conditional on clock-floor
recovery (C1) and concurrent first initialization proof (C2):
[acceptance and conditions](https://github.com/canfieldjuan/connect-automate/pull/14#issuecomment-6257302653).
The operator's subsequent decision, **“Purge it too (Recommended)”**, adds
deletion/unfollow propagation and the producer retention ceiling (C3):
[retention decision and open alignment items](https://github.com/canfieldjuan/connect-automate/pull/14#issuecomment-6257324609).
The C3 owner below also specifies message-wide purge scope and late-delivery
rejection in response to [the purge-scope finding](https://github.com/canfieldjuan/connect-automate/pull/14#discussion_r4309599238).
These are operator decisions relayed by oversight, not authority granted by a
reviewer PASS. The current documentation update incorporates those conditions;
its independent review remains required.

C4 leaves the same-lead identity owner open for the extraction/deduplication
contract. C5 requires Watcher pairing/enrollment to define namespace identity
before adoption. Neither is implicitly decided by accepting event-level custody.
Changes beyond these accepted precisions require an operator-approved amendment.
Implementation must use a separate branch, fail-first proof and native Windows
and Linux crash, locking and permission gates. This update stops before code.

## Source baseline and reusable proof inventory

Repository: `canfieldjuan/connect-automate`.
Inspected revision: `9721cf70ae8b850912714deee418b4f065fa9ec7`.
All source citations below are relative to that revision, not moving main.

| Finding | Source evidence | Consequence |
| --- | --- | --- |
| CONFIRMED: the envelope separates organization, firing identity, message identity, snapshot and retention | `src/connect_automate/lead_intake/source.py:77-168` | Preserve the existing wire contract and canonical payload digest |
| CONFIRMED: body availability, completeness, digest and character counts are validated | `src/connect_automate/lead_intake/source.py:94-121` | Persist those assertions without treating them as extraction completeness |
| CONFIRMED: authentication checks locally supplied authority, signature, scope and time, then returns a value | `src/connect_automate/lead_intake/auth.py:151-221` | Call it inside admission; do not accept a caller-supplied authenticated result |
| CONFIRMED: trust models validate one snapshot and the result carries generation and expiry | `src/connect_automate/lead_intake/auth.py:82-126` | Add durable publication history and commit coordination, not another verifier |
| CONFIRMED: canonical payload and full-envelope encoders share validation | `src/connect_automate/lead_intake/source.py:212-269` | Reuse these encoders; never hash raw request formatting as business identity |
| CONFIRMED: Automate mail events carry message ID, time, sender and subject, with a bounded event format | `src/connect_automate/automate/events.py:15-19`, `78-90`, `134-154` | No body or Lead Intake receipt reference is currently supported |
| CONFIRMED: runtime submission validates bindings, delegates admission and dispatches stored actions | `src/connect_automate/automate/runtime.py:194-229`; `src/connect_automate/automate/engine.py:316-388` | Preserve this orchestration owner; a Lead Intake adapter is not yet present |
| CONFIRMED: workflow admission checks binding and replay identity, then atomically stores workflow state and receipt | `src/connect_automate/automate/store.py:842-961` | Reuse the atomicity/replay pattern and tests, not workflow business tables |
| CONFIRMED: workflow receipts store their event payload and prohibit update/delete | `src/connect_automate/automate/store.py:182-203` | Putting raw bodies there would defeat independent content retention |
| CONFIRMED: existing SQLite owner manages rollback/close, bounded WAL initialization and schema verification | `src/connect_automate/automate/store.py:709-775` | Preserve those safety properties; do not inherit an unrelated schema owner |
| CONFIRMED: Windows private-path helpers check ACLs and reparse points | `src/connect_automate/connect_windows.py:388-420`, `539-559` | Candidate primitives; their existence does not qualify a SQLite deployment |

CONFIRMED: the authentication regression inventory includes stateless replay and
key rotation at `tests/test_lead_source_auth.py:490-515`, copied/constructed
models at `:631-678`, and fixed error boundaries at `:569-607`. Existing workflow
tests exercise duplicate receipt reuse at `tests/test_automate_events.py:283-314`,
transaction rollback at `:577-592`, and native process race/crash cases at
`:662-697`. These are source-inspected tests, not results executed for this draft.

Previously recorded local qualification is retained outside the worktree as
alias `main-integration.tar.gz`, SHA-256
`8c9be23284281d7634431687463e338340eb7d6f199a2aa23c52c517ec159280`.
Its recorded test revision is `72d863537a775f18bfac6109740fdaa4aa79d3a2`.
It is evidence for the prior verifier/runtime combination, not for this proposed
store. Parser/auth vectors remain frozen compatibility inputs. There is no
inference runtime, model, prompt or private customer fixture in this slice.

INFERRED: the inspected production package has no caller connecting the verifier
to durable source admission; references are confined to the auth owner and its
exports. This does not establish the state of other applications or deployments.
UNKNOWN: deployed enrollment, key custody, trusted clock qualification,
employee authentication, encrypted storage/backups and operating retention policy.

Differences from the reusable baseline are explicit: a new Lead Intake-owned
store, durable authority publication, source custody, replay receipts and
expiry cleanup. Signing bytes, payload identity, parser acceptance and Automate
behavior must remain unchanged. No validated prototype of this new store is
being claimed; implementation must first prove parity with the existing vectors.

## Ownership and bounded implementation surface

Lead Intake owns one source-admission store containing deployment identity,
authority publication history, source receipts, the C3 purge metadata and
separately deletable content.
For the first library implementation, use a dedicated SQLite file under a
private deployment directory on a local filesystem with qualified SQLite locking.
Network filesystems and shared cross-machine stores are not supported. It avoids
importing workflow tables and their
immutable-payload retention policy. It is not a second workflow engine, action
outbox, polling service or scheduler. Sharing a database file later requires an
explicit transaction/interface contract; it never grants table access to peers.

One transaction owner serializes all authority changes and admission writes in
that file. No component may edit its tables directly. Automate continues owning
workflow records, action identities, dispatch, recovery and approvals. Watcher
continues owning mail access and future sender-key custody. EOM remains untouched.

Prospective implementation surface: `lead_intake/admission.py` for the boundary
and receipt models, `lead_intake/source_store.py` for schema/transactions,
explicit package exports and focused synthetic tests. Exact module factoring
may reduce this surface, but must retain one owner per invariant. Reuse existing
parser/auth APIs and dependency versions. Private-storage helpers may be reused
only after proving their behavior for this store on supported platforms.

The future implementation is library-only and has no production receiver or
administrative endpoint. A configured local host calls it; envelope fields and
Connect registration tokens cannot construct that authority. The same OS user
is the trust boundary. This does not implement employee roles or protect against
a malicious same-user process able to alter the store or invoke host code.

## Deployment and durable trust publication

Initialize an empty store explicitly with exactly one non-null host ID and
organization ID, supplied by local deployment configuration. Opening a store
requires those expected identities and checks them before any record operation.
Identity mismatch, unknown schema or damaged authority data fails closed. There
is no implicit bootstrap from an incoming envelope, fallback organization or
ordinary identity reassignment. Different businesses require different stores
and deployments. No production initialization command is included in this slice.
Concurrent first initialization is part of this store's responsibility: two
processes initializing/opening a fresh store must negotiate WAL within the
bounded wait and either obtain a complete validated schema or a typed busy
failure, never a partially usable schema. Reuse the existing SQLite owner's
bounded negotiation pattern and prove it here; an unrelated store's fix does
not qualify this owner (C2).

The internal administrative operation publishes a validated `SourceTrustSnapshot`
with an expected current generation. Initialization installs generation `1`;
subsequent publication requires an exact compare-and-swap and the next generation.
Generation exhaustion is an error, not wraparound. Publication and history update
commit together under the same SQLite writer transaction used by admission.
Concurrent updates cannot both replace the same generation. A lost reply can be
reconciled by reading back the generation and exact validated configuration;
repeating the already committed generation and identical validated configuration
is a no-op, not a second generation change. Any other same-generation value or
stale expected generation conflicts. Identity comparisons use validated typed
values, not arbitrary request JSON formatting.

Persist identity history across removed grants: a key ID cannot be rebound to
different public bytes, namespace, host or organization; public bytes cannot be
relabelled with another key ID. Revocation is terminal for that key ID. A removed
key is terminally retired just as a revoked key is; a later publication cannot
reactivate it. History survives removal from the active snapshot.
Policy definitions are immutable for each `(policy_id, policy_version)` pair;
changed definitions require another version. Scopes/validity updates advance
generation. Preserve exact code-point matching and whole mailbox tuples.

Administrative authorization is a host responsibility, outside the source wire
API. The library must expose a distinct local administrative boundary, never an
`admit_source(..., trust=request_value)` path. Host enrollment/employee controls
require a later accepted contract before exposing this boundary to applications.
Durability does not detect rollback of the entire database or clock by the OS
owner; restore/backup qualification must address that before production adoption.

## Event identity, custody and stable receipts

The unique source event key is `(organization_id, namespace_id, event_id)`;
host ID is fixed by the store. Neither `key_id`, signature, pack version nor
provider process identity participates. `watcher_event_id` and the complete
provider/account/mailbox/message tuple remain signed provenance. Do not replace
the firing UUID with the Watcher provenance digest or a summary prefix.

Use the existing `payload_digest` to compare an authorized replay with the
original event. Identical payload under a currently permitted rotation key
returns the original receipt subject to current authorization and the C3 purge
horizon. Changed payload under the same event key is a
conflict, including changes to body, message identity, rule or recovery deadline.
Conflicts never replace content, extend expiry or update first-admission facts.

Different event IDs for the same message are distinct source admissions in this
slice. They create no canonical leads or contacts. The same-lead identity owner
(message, contact or content) remains an explicit open decision (C4). Before
extraction can create leads, its deduplication contract must reconcile Watcher's
firing identity, Automate's `message_id` and Atlas's contact-plus-content rule.
Those cross-application alignment topics come from review; this document does
not independently qualify the other applications or adopt their algorithms.
Event-level custody alone does not satisfy the foundation's duplicate-lead
requirement.

Commit the receipt, canonical envelope bytes and first-authentication provenance
together. Use `canonical_source` for the protected content blob so restart reads
can reuse `parse_untrusted_source` without a second storage parser. Store an
internal SHA-256 of those exact envelope bytes alongside the immutable receipt;
it protects storage integrity and is not the business replay digest. Do not store
another raw-request copy or signing private keys. Re-signing must not rewrite the
first canonical envelope, its internal hash or the first-authentication stamp.
Available, truncated, unknown and unavailable bodies retain their exact
meaning. A stored unavailable source is not a successfully extracted lead.
Attachments remain explicitly unprocessed. No missing body is invented or fetched.

Accepted immutable receipt schema `lead.source.receipt`, version `1.0`:

| Field | Meaning |
| --- | --- |
| `admission_id` | Store-generated UUID, allocated once, never derived into a filesystem path |
| `host_id`, `organization_id`, `namespace_id`, `event_id` | Receiver and unique event ownership |
| `payload_digest` | Existing canonical payload digest |
| `accepted_at` | Trusted host UTC sample used by the admission decision |
| `key_id`, `trust_generation` | First successful authorization provenance |
| `policy_id`, `policy_version`, `recovery_deadline` | Original accepted retention authority and cutoff |

The receipt is closed and immutable: schema/version are literals, IDs use the
existing `UuidV4` type, digests use `Digest`, and revisions use strict `Revision`.
`accepted_at` is the final successful UTC decision sample, serialized with fixed
microsecond precision and `Z`; `recovery_deadline` preserves the source `Instant`.
The wrapper's `applied` is a strict Boolean and content state is a closed enum.

A response wraps this stable receipt with `applied` (new versus replay) and the
transactional `content_state` (`retained` or `purged`). Retained means the original
envelope remains stored, even when its body asserts unavailable. Expired requests
fail authentication instead of obtaining a receipt. Neither wrapper field
is part of receipt identity. A receipt says only that source custody committed;
it does not mean workflow dispatch, approval, extraction or delivery succeeded.
Admission responses, exceptions and reprs exclude body text, mailbox/message identifiers
and signatures. A receipt locator is not an authorization credential.

## Admission algorithm and linearization

The source-facing operation accepts raw envelope bytes only. It must not accept
`AuthenticatedSource`, a per-request trust snapshot, an organization override,
a caller-selected receipt or a request-supplied clock. Host construction supplies
a qualified UTC clock interface; tests inject a deterministic host clock.

1. Enforce the existing input bound. Begin a bounded-wait SQLite writer
   transaction. Read and validate the store identity, current authority and
   durable namespace retirement state. No business receipt lookup occurs yet.
2. Sample the host clock after lock acquisition; call `authenticate_source`
   against the current snapshot. Refuse a retired namespace. Untrusted clock
   samples and time earlier than the current durable clock floor fail closed.
   The current clock cannot be cached across calls or replaced by event time.
3. Only after authorization, enforce the message purge horizon defined in
   C3 below, then look up the event key. Compare its original digest.
   Identical replay preserves the receipt; conflict aborts. For new events,
   prepare receipt/content rows and minimal first-admission audit facts.
   Check persisted ownership and content-state integrity: a retained row must
   exist and pass its hash checks; purged content must not reappear. Missing or
   corrupt retained data is a storage failure, never a reason to recreate it.
4. Immediately before commit, sample the clock again and recheck authorization,
   generation and the original expiry while still holding the same transaction.
   Clock regression or expired permission rolls back even an identical replay.
   Record the successful clock floor in this transaction. No network, arbitrary
   caller callback, dispatch or inference may run while holding it.
5. Commit, then return. A commit error or interrupted response is not definite
   success or definite absence. Recover by reopening and retrying the same signed
   envelope under current authority, never by minting another event ID.
   If current authority no longer permits replay, source-facing reconciliation
   remains unavailable; do not report that the original write did not happen.
   A separately authorized host may reconcile the historical receipt.

Revocation and admission have a serial order: publication committed first means
the old key cannot admit or retrieve a receipt; admission committed first means
its historical receipt remains, while subsequent operations use the new grant
state. A precomputed authenticated object cannot bypass this order. SQLite
uniqueness constraints and transactions protect independent processes, not just
threads in one Python object. No lock spans both this store and Automate's store.

Time validity is decided at the final trusted sample before commit invocation;
it is not a claim about physical disk-flush completion at a wall-clock instant.
Receipt return may occur after the deadline. Later lookup/content access still
rechecks current authority and expiry. The host must qualify time across restart;
the persisted clock floor detects regression relative to committed trusted
samples, subject only to the explicit administrative reconciliation below.

C1: a confirmed erroneous forward sample must not permanently halt admission.
Provide a distinct local, host-authorized administrative operation to lower or
reconcile the floor under the same transaction owner. Append the old/new floor
facts to authority history atomically; never rewrite previous receipts or
authority history. Reconciliation is never automatic and is unreachable from
an envelope or the source-facing API. It never extends a deadline, reauthorizes
expired content or reverses terminal purge/retirement. It does not itself admit
content: subsequent requests still require current authorization and expiry
checks. Prove that a bad forward sample blocks admission after clock correction,
that authorized reconciliation restores admission for otherwise valid fresh
sources, and that the source-facing path cannot invoke it. Direct table edits
are not a recovery mechanism.

Use typed, fixed, input-free errors: authentication/scope rejection must not
reveal receipt existence; an authorized digest conflict is distinct from busy
storage, unavailable/corrupt storage and an uncertain commit result. Do not retain
SQLite statements, source bytes or internal exception chains in public errors.
Storage failure and conflict must never be translated into an empty successful
receipt. Busy waits have one bounded owner; callers may retry, not multiply waits.

## Content access, retention and deletion

For this slice the original signed recovery deadline is also the latest content
access time. This is an accepted policy decision, not a claim that the current
auth policy already enforces storage retention. Expiry/cleanup never extends the
deadline. Local policy may reject a requested recovery duration; it may not
silently shorten a newly promised custody interval after returning success.
Authorized early purge below is an explicit withdrawal, not a silent policy
change. C3 also requires the signed `recovery_deadline` never to exceed the
producer's own retention cutoff for that content. The later Watcher/Connect
handoff contract must define how producer retention (including `retention_days`)
bounds that absolute deadline and prove it before adoption; this library does
not infer producer retention from a signed envelope.

Source-facing receipt replay always reauthenticates the full submitted envelope
and enforces the C3 purge horizon before lookup. Content access is a separate
trusted-host library operation with the immutable deployment scope; it is not a
remotely callable lookup by UUID or organization string. It checks the stored envelope hash, reparses with the existing
source parser, and checks payload digest and ownership against the receipt. It
refuses expired, purged, retired-namespace, foreign-scope or corrupt content.
Future employee/job authorization and reference retrieval over Connect must be
qualified before exposing that operation. The trusted host reads its own
historically admitted records; source-key revocation blocks source-facing replay
but does not erase prior records or substitute for the future host reader's
authorization policy.

Store canonical envelope bytes in a separately deletable row, never inside an
immutable audit or workflow record. On every content read, enforce expiry even
if cleanup has not run. Provide bounded, restartable cleanup through the store
owner; remove expired payload rows and mark content purged atomically without
changing the receipt. Duplicate replay must never resurrect purged content.
An authorized early purge is a terminal custody withdrawal, recorded without
body text; later consumers must observe unavailable content, not success.

### C3: message-wide purge and admission horizon

Deleting or unfollowing a source in Email Watcher must reach Lead Intake as
an authorized early purge. Within the immutable organization scope, the purge
identity is the complete signed `SourceIdentity` tuple: `(namespace_id, provider,
account_id, mailbox_identity_key, message_id)`. Neither `event_id`,
`watcher_event_id`, rule identity nor a receipt locator alone scopes deletion.
Use the validated exact identity values; do not infer aliases from message text.

One atomic purge under the admission transaction owner removes the content of
EVERY matching admission and marks each `content_state=purged`, preserving its
immutable receipt. Other message identities and organization scopes remain
untouched. Retain a protected identity-to-admission association after deleting
content so this rule does not depend on reparsing a body that is already gone.
Audit records must not retain body text. The operation is a distinct authorized
host boundary; source-facing envelopes cannot invoke it.

The same transaction records a durable UTC purge horizon for that identity,
even if no matching admission has arrived yet. The trusted host supplies the
validated cutoff; authenticated producer-to-host mapping and time coordination
must be defined and qualified in the later handoff contract. The horizon never
moves backward. Repeating an already applied or older horizon is a no-op, not
another deletion of content captured later. A newer authorized purge atomically
advances the horizon and purges all then-matching admissions.

After current authentication and before event lookup/write, admission refuses
any source whose `snapshot.captured_at <= purge_horizon`. This includes a late
in-flight first delivery, a different event ID and replay of a pre-horizon event.
The horizon check and admission commit use the same transaction owner as purge:
admission ordered first is covered by purge; purge ordered first denies stale
admission. A capture after the horizon following re-follow may be admitted as a
new event under normal authorization and expiry checks. It cannot replace an
old event's payload, restore a purged admission or bypass namespace retirement.
Reopen/restart preserves both the horizon and terminal content states.

Keep the horizon while the namespace can be admitted, including when it has no
receipt yet. It may be dropped only after permanent namespace denial using the
retirement procedure below. This closes late delivery without relying on a
finite tombstone timeout or the later same-lead deduplication decision.

The later library implementation must supply and prove this primitive. Watcher
must emit purge for every physical source identity, including identities behind
coalesced aliases. Producer emission, authenticated delivery/recovery and cutoff
mapping are required clauses and adoption gates of the later Watcher/Connect
handoff contract, not implemented integration in this slice. A local primitive
alone does not prove cross-application deletion.

Keep only event/receipt/digest/authority and required purge-identity/horizon
metadata after content deletion. Even a digest is sensitive correlation data;
access remains restricted. To preserve same-event conflict detection, receipt tombstones remain while their namespace
can be admitted. The accepted retention policy is lifecycle-bound: a local
administrative retirement permanently denies that namespace and makes its
content inaccessible; content and receipts may then be purged in bounded batches.
Keep the compact retired-namespace marker so a future key cannot reactivate
forgotten identities.
Publication must reject grants to a retired namespace. Ordinary key rotation
does not retire a namespace. Full metadata erasure while
retaining the namespace's admission ability is not supported by this policy.

C5: before adoption, the Watcher-side pairing/enrollment contract must define
how `namespace_id` is minted and persisted across restart/upgrade, and how
replacement installations and retirement are handled without reusing retired
identities. Tombstones and retirement depend on that definition. Provider process
identity is not a substitute. A new namespace does not inherit another namespace's
event tombstones; this slice makes no cross-namespace lead-deduplication claim.
Watcher enrollment is a prerequisite, not an implemented capability asserted here.

Both retirement and cleanup use the admission transaction owner. Retirement
must deny new operations atomically; bulk deletion can follow in bounded batches.
Persist the retirement marker before any tombstone is dropped. No background
cleanup service is added. Production hosts must supply and qualify cleanup
invocation, operational latency, disk quotas and namespace-retirement procedures.

Private directory/database/sidecar permissions must hold from creation, including
on Windows; post-write chmod alone is not proof. Reject unsafe symlink/reparse
paths and malformed stores without destructive repair. Configure and verify
foreign keys, WAL mode, `synchronous=FULL` and schema version. Windows and
Linux process-level crash/locking/permission tests are merge requirements for
the later storage implementation, not release-note exceptions.

SQLite deletion is logical deletion, not guaranteed erasure from WAL pages,
backups or physical media. This library must not claim encryption or secure
erasure. No production-sensitive payloads may be adopted until storage/backups,
retention enforcement and restore behavior are separately qualified. No external
inference, telemetry, transport or customer data is used to prove this slice.

## Existing Automate boundary and deferred handoff

CONFIRMED: `src/connect_automate/automate/events.py:84-90` requires sender/subject
and lacks a source receipt reference; `src/connect_automate/lead_intake/source.py:144-168`
does not supply those routing
fields. INFERRED: translating this envelope directly to that event would lose
information or invent fields. Do not squeeze receipt IDs
into message IDs/subjects, fabricate those fields, enlarge immutable event
payloads with body content or read Lead Intake tables from Automate.

This implementation ends at durable source admission and authorized local
content access. No workflow is dispatched and no delivery queue is introduced.
The stable receipt is the candidate reference for a separately accepted runtime
adapter contract. That contract must identify the smallest supported event or
capability extension, authenticate the host call, bind organization and receipt,
and use the existing workflow admission/replay path. Before adoption it must
also satisfy the C3 producer retention/purge obligations and the C5 namespace
enrollment prerequisite above. It must qualify failures
between the source commit, workflow acceptance and recording the workflow receipt.

Lost handoff acknowledgement must recover through stable identities and the
existing runtime's receipt lookup/replay behavior. Do not infer that its current
mail occurrence identity is already a source-admission identity. No cross-store
atomicity or exactly-once delivery claim is made here. Whether additional durable
handoff bookkeeping is needed must be proven by that adapter's crash tests,
not assumed as a reason to build a second dispatcher now.

## Verification plan and implementation slices

Contract verification: read the pinned source and relevant tests, check the
existing evidence receipt, audit every confirmed citation, then inspect a diff
containing this document alone. No behavioral tests are run for this doc-only
change. The conditional acceptance is recorded above; independent review of these
clarifications precedes a separate implementation work order.

For separately authorized implementation, the dependent slices below each need
fail-first evidence, adjacent tests, lint, cold diff and exact-head review:

| Slice / foundation gate | Invariant and required proof | Regression risk / recovery |
| --- | --- | --- |
| Authority store / G0, G2, G6 prerequisites | Correct/foreign deployment; missing authority; generation CAS; duplicate publish; identity and policy rebinding; revoked/removed key history; cross-process publication race; two-process concurrent first initialization/open of a fresh store, bounded WAL negotiation, typed busy failure and no partial schema; malformed schema and private paths | No peer-table access; fail closed on incompatible stores; preserve file for diagnosis |
| Atomic custody and replay / G1, G2, G3 prerequisites | Frozen source/auth parity; valid body-only and unavailable sources; same-event replay; conflicting signed payload; rotation; different event IDs for one message; copied-result bypass; SQL failure between every row; simultaneous process admissions; crash before/after commit and lost response | One source receipt, no partial content or invented lead; recover by same authenticated request |
| Revocation/time coordination / G3, G6 | Barriers at grant read, signature verification, receipt lookup and commit; both revocation orderings; expiry while blocked; clock rollback and erroneous forward sample; host-authorized floor reconciliation with atomic history, restored fresh admission, unchanged deadlines and no source-facing access; concurrent stores opened in separate processes | Recheck at transaction owner; stale assertions cannot authorize writes or receipt reads |
| Access and expiry / G1, G6 prerequisites | Body bytes survive reopen; foreign-scope reads; expired/corrupt content; cleanup restart; C3 message-wide purge: two event IDs purged by one request, unrelated messages/scopes untouched, no body-bearing audit; absent-message purge then late first delivery; capture before/at horizon refused, later re-follow capture admitted; repeated purge after that capture is a no-op; restart/replay and concurrent admission/purge; event-scoped purge mutant must fail; retirement races; no tombstone removal before permanent denial; Windows/Linux crash and sidecar access | Expiry blocks reads independently of cleanup; no content resurrection; no erasure claim |

### Revocation and expiry race qualification increment

The next bounded increment qualifies the existing transaction ordering from
"Admission algorithm and linearization" above. It does not implement the rest
of the revocation/time row or claim a foundation gate complete.

Proof inventory: reuse the frozen source/auth vectors and the private SQLite
fixtures in `tests/test_lead_source_auth.py` and `tests/test_lead_source_store.py`.
Reuse the spawned-process lifecycle and rollback/replay assertions established
by `tests/test_lead_source_admission.py`. The production owners remain
`SourceStore._transaction`, `publish_authority`, and `SourceAdmission.admit_source`.
The coverage gap is deterministic contention at authorization boundaries;
existing concurrency tests do not pause at those boundaries.

Add a dedicated race test file and include it in native Windows CI from its
first push. Instrument real calls in child processes, with barriers at grant
read, successful signature verification, receipt lookup and commit. Observe a
real SQLite busy result before releasing the first writer; do not infer
serialization from sleeps or mock call counts. Cover new admissions and replay,
both revocation orderings, key/source expiry while waiting, and expiry across
the final clock sample. Preserve the distinction between the final authorization
sample and physical commit completion defined above.

No production code, schema, frozen fixtures or existing assertions change in
this qualification increment. Durable clock-floor enforcement and C1 recovery
remain a subsequent implementation together; content access, C3 purge and
application adoption remain excluded. Require owner mutations to fail the
intended assertion, adjacent tests, lint, cold diff and exact-head Linux/Windows
CI plus independent review. Keep evidence outside the worktree.

For each security guard, exercise accepted and rejected sides, partial/mixed
records, strict-type/falsy values, boundaries, Unicode identities and replay after
reopen. Mutate the controlling check at its owner and require its regression to
fail. Use real SQLite transactions and spawned processes with explicit barriers;
mock-only call assertions cannot prove serialization, crash recovery or privacy.

Store raw evidence outside worktrees with private permissions. Reuse source/auth
vectors and existing native-process test patterns. CI owns broad repeated suites;
run the required narrow and high-risk transaction probes locally. Do not claim
any full foundation gate passes merely because this library's tests pass. G1
still needs the real Watcher/Connect handoff; G2 still needs lead identity and
extraction validation and the C4 identity decision; G3 still needs runtime
handoff recovery; G6 still needs deployment authorization, encryption/backup
and retention qualification. Adoption also requires the later handoff to prove
C3 deletion/unfollow propagation and producer-bounded deadlines, and the
Watcher pairing/enrollment contract to define C5 namespace lifecycle.

## Assumptions, rollback and gap audit

The accepted source/auth wire behavior stays authoritative. Conditionally
accepted new choices include the separate owned file, serialized local trust
publication, event-level replay, content cutoff at the signed deadline and
namespace-lifecycle tombstones, with C1-C3 precisions and C4-C5 prerequisites
recorded above. No production retention duration is silently
chosen. Employee authorization, sender custody and trusted enrollment are unknown
deployment work, not supplied by an OS directory or a Python method signature.

The later library starts with a new, versioned store; it never migrates EOM or
Automate tables. Before any application adoption, rollback means disable this
opt-in integration and preserve the store. Do not downgrade or discard persisted
records to make an older binary open the file. Recovery from corrupted storage
and backups needs its own qualified procedure before live use.

Implementation summary: only this accepted contract and its clarifications are added.
Cold diff audit: all normative additions address the missing source transaction
owner; no executable behavior or existing contract is changed.
Gap audit: operator acceptance of the original revision with C1-C3 conditions
is recorded; independent review of this clarification update remains pending.
C4's same-lead identity decision and C5's Watcher enrollment contract remain open.
Implementation, production admission, runtime integration and all broader
foundation qualifications remain NOT DONE. Stop after this documentation update;
do not implement or treat oversight PASS as operator acceptance.
