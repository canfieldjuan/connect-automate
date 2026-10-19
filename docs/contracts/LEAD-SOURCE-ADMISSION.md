# Durable Lead Source Admission

Status: PROPOSED — contract only; operator acceptance pending.
Implementation authorization: NOT GRANTED by this document or a reviewer PASS.

## Contract and stop boundary

Root cause: the source verifier returns a point-in-time assertion. It cannot
make source custody, duplicate prevention or concurrent revocation durable.
The missing owner is the transaction boundary between current local authority
and a persisted source receipt. This is a new opt-in boundary, not a repair to
deployed EOM behavior.

This change adds only this contract. Commit it, request independent review and
stop for explicit operator acceptance of its exact revision. No source, test,
database, migration, dependency, service, application pin or existing contract
changes are authorized by this documentation slice. Acceptance must precede a
separate implementation branch. Acceptance does not authorize production use.

All normative behavior below is PROPOSED. CONFIRMED labels describe inspected
code only; INFERRED and UNKNOWN labels preserve the limits of that inspection.

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
authority publication history, source receipts and separately deletable content.
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
returns the original receipt. Changed payload under the same event key is a
conflict, including changes to body, message identity, rule or recovery deadline.
Conflicts never replace content, extend expiry or update first-admission facts.

Different event IDs for the same message are distinct source admissions in this
slice. They create no canonical leads or contacts. Message/contact deduplication
must be separately contracted before extraction can create leads; this event
policy alone does not satisfy the foundation's duplicate-lead requirement.

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

Proposed immutable receipt schema `lead.source.receipt`, version `1.0`:

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
   samples and time earlier than the store's last successful decision fail closed.
   The current clock cannot be cached across calls or replaced by event time.
3. Only after authorization, look up the event key. Compare its original digest.
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
the persisted clock floor only detects regression relative to committed samples.

Use typed, fixed, input-free errors: authentication/scope rejection must not
reveal receipt existence; an authorized digest conflict is distinct from busy
storage, unavailable/corrupt storage and an uncertain commit result. Do not retain
SQLite statements, source bytes or internal exception chains in public errors.
Storage failure and conflict must never be translated into an empty successful
receipt. Busy waits have one bounded owner; callers may retry, not multiply waits.

## Content access, retention and deletion

For this slice the original signed recovery deadline is also the latest content
access time. This is a proposed policy decision, not a claim that the current
auth policy already enforces storage retention. Expiry/cleanup never extends the
deadline. Local policy may reject a requested recovery duration; it may not
silently shorten a newly promised custody interval after returning success.

Source-facing receipt replay always reauthenticates the full submitted envelope
before lookup. Content access is a separate trusted-host library operation with
the immutable deployment scope; it is not a remotely callable lookup by UUID or
organization string. It checks the stored envelope hash, reparses with the existing
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

Keep only event/receipt/digest/authority metadata after content deletion. Even a
digest is sensitive correlation data; access remains restricted. To preserve
same-event conflict detection, receipt tombstones remain while their namespace
can be admitted. The proposed retention policy is lifecycle-bound: a local
administrative retirement permanently denies that namespace and makes its
content inaccessible; content and receipts may then be purged in bounded batches.
Keep the compact retired-namespace marker so a future key cannot reactivate
forgotten identities.
Publication must reject grants to a retired namespace. Ordinary key rotation
does not retire a namespace. Full metadata erasure while
retaining the namespace's admission ability is not supported by this policy.

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
and use the existing workflow admission/replay path. It must qualify failures
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
change. Review and operator acceptance of the exact revision precede code.

After acceptance, implement the following dependent slices; each needs its own
fail-first evidence, adjacent tests, lint, cold diff and exact-head review:

| Slice / foundation gate | Invariant and required proof | Regression risk / recovery |
| --- | --- | --- |
| Authority store / G0, G2, G6 prerequisites | Correct/foreign deployment; missing authority; generation CAS; duplicate publish; identity and policy rebinding; revoked/removed key history; cross-process publication race; malformed schema and private paths | No peer-table access; fail closed on incompatible stores; preserve file for diagnosis |
| Atomic custody and replay / G1, G2, G3 prerequisites | Frozen source/auth parity; valid body-only and unavailable sources; same-event replay; conflicting signed payload; rotation; different event IDs for one message; copied-result bypass; SQL failure between every row; simultaneous process admissions; crash before/after commit and lost response | One source receipt, no partial content or invented lead; recover by same authenticated request |
| Revocation/time coordination / G3, G6 | Barriers at grant read, signature verification, receipt lookup and commit; both revocation orderings; expiry while blocked; clock rollback; concurrent stores opened in separate processes | Recheck at transaction owner; stale assertions cannot authorize writes or receipt reads |
| Access and expiry / G1, G6 prerequisites | Body bytes survive reopen; foreign-scope reads; expired/corrupt content; cleanup restart; early purge and replay; retirement races; no tombstone removal before permanent denial; Windows/Linux crash and sidecar access | Expiry blocks reads independently of cleanup; no content resurrection; no erasure claim |

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
extraction validation; G3 still needs runtime handoff recovery; G6 still needs
deployment authorization, encryption/backup and retention qualification.

## Assumptions, rollback and gap audit

The accepted source/auth wire behavior stays authoritative. Proposed new choices
requiring operator acceptance include the separate owned file, serialized local
trust publication, event-level replay, content cutoff at the signed deadline and
namespace-lifecycle tombstones. No production retention duration is silently
chosen. Employee authorization, sender custody and trusted enrollment are unknown
deployment work, not supplied by an OS directory or a Python method signature.

The later library starts with a new, versioned store; it never migrates EOM or
Automate tables. Before any application adoption, rollback means disable this
opt-in integration and preserve the store. Do not downgrade or discard persisted
records to make an older binary open the file. Recovery from corrupted storage
and backups needs its own qualified procedure before live use.

Implementation summary: only this proposed contract is added.
Cold diff audit: all normative additions address the missing source transaction
owner; no executable behavior or existing contract is changed.
Gap audit: contract review and exact-revision operator acceptance are NOT DONE.
Implementation, production admission, runtime integration and all broader
foundation qualifications remain NOT DONE. Stop after the reviewed contract;
do not implement or treat oversight PASS as operator acceptance.
