# R2: source-owned custody resolution and durable fences

Status: **R2 library implementation and qualification MERGED; receiver/adoption remain gated.**

Completion: [PR #55](https://github.com/canfieldjuan/connect-automate/pull/55) merged
at `2b893e3b320638a7fbdcc3de26b0b1ca3e66dc9b`, with tree
`c9878ce1170d8655879d616966d2bc5b15438a73` equal to reviewed head
`205a34026dc7131b220ab25f33085fe8ac70fe5e`. Exact-head Linux and native Windows CI,
oversight PASS and connector review without findings were verified before merge;
no unresolved review threads remained. Durable alias
`custody-r2-qualification/merge-205a340`, manifest SHA-256
`1ce8587b434dc8218b9792c46be9cd790ad2992fa00cadbe4e7fb026b28ee7a0`,
records those gates and merge-tree equality. Historical pending notes below remain
stage records. [R3.1 composition](LEAD-CUSTODY-COMPOSITION.md) records the next
work order and its acceptance; this completion grants no receiver, machine-authentication or adoption
authority.

Juan selected “This lead-intake session (recommended)” as its sole owner, using
pack-kit's preserved draft as input. On 2026-10-26 he directly instructed this
session, “I approve the contract lets check oversight”. This accepts PR #51's
reviewed contract at `45818bbd9cd16660a7b862f28f2a499082f0851c`, whose
`docs/contracts/LEAD-CUSTODY-STORAGE.md` SHA-256 is
`981e16b01877c45ff8261ed8b600a85a06190afbf69f292f4adca5c5d2406457`.
Oversight independently relayed his statements “i accept the contract” and
“yes, the R2 contract on 51” in mailbox `b65b0a86`, binding the same revision and
document hash. Oversight's [contract PASS](https://github.com/canfieldjuan/connect-automate/pull/51#pullrequestreview-5647625140)
also covers that revision. This acceptance-only record changes no design rule.

R1 merged in PR #50 at
`f6bb9ecf35d6a746ae17ea0e3862216ec4744426`;
its tree equals reviewed head `81f4ad0f5fdd02585eef6c96faa9a5ae34af6b4e`.

This is the R2 continuation of [receiver custody](LEAD-RECEIVER-CUSTODY.md).
The acceptance is recorded separately before executable work. After the contract
merge gates pass, the first bounded implementation PR is migration plus read-only
metadata resolution, following the verification plan below. Re-pin a changed
base before executable edits. R3 receiver composition, R4 Watcher, R5 installed
retention, and the protected machine boundary retain their own acceptance gates.

## Contract

### Root cause

**CONFIRMED at the base below:** the source owner atomically authenticates and
stores an envelope, custody metadata and an immutable receipt. It has no durable
handoff reservation, capture fingerprint or job-generation fence. Existing
admission is keyed by organization/namespace/event, and replay compares the
payload digest, preserving the first envelope. It cannot establish that an
absent upload is permanently unable to commit. This is missing receiver support,
not a defect in the existing caller-driven library contract.

The first owner that must change is `SourceStore` / `SourceAdmission`. A receiver
check before entering their writer transaction would leave a check-then-write
race. Reading `SourceContent` as status is also wrong: its read can advance the
clock and purge expired content. R2 adds a separate metadata observation path
and enforces upload eligibility inside the source writer, not in a wrapper.

### Pinned inventory and proven work

Repository: `canfieldjuan/connect-automate`.
Base: `f6bb9ecf35d6a746ae17ea0e3862216ec4744426`.
Paths and line numbers in this inventory refer to that revision.

| Existing owner / evidence | Responsibility and limit |
| --- | --- |
| `src/connect_automate/lead_intake/source_store.py:61-123` | Exact SQL manifest, schema version 4; deployment, authority, clock, receipt/content/custody, purge horizons and retirement. No handoff or operation table. |
| `source_store.py:279-307,339-351,383-428` in the same directory | Private-file checks, exact schema rejection, bounded SQLite wait, `BEGIN IMMEDIATE`, foreign keys, WAL and FULL synchronization. Commit acknowledgement failure is uncertain. No upgrade API. |
| `lead_intake/admission.py:85-162,165-240` under `src/connect_automate/` | `_existing` validates custody, including retained bytes; `admit_source` authenticates before and after staging writes, checks lifecycle under the writer and preserves first receipt/envelope. It accepts no handoff fence. |
| `lead_intake/content.py:75-98,124-153,156-191` | Content read mutates on expiry; message purge uses full identity/capture cutoff; namespace retirement precedes bounded metadata erasure. |
| `lead_intake/custody_protocol.py:49-161,164-276` | R1 private untrusted route, intent, capture, request and result vocabulary. These values are not authorization or durable observations. |
| `lead_intake/handoff.py:53-70`; `automate/runtime.py:282-418` | Existing runtime composition calls unfenced source admission; source and workflow commits remain separate. Historical workflow lookup does not authorize raw-content access. |
| `automate/store.py:296-309,893-925` | Existing workflow-owned read pattern uses a SELECT authorizer and consistent query-only snapshot with live WAL visibility. Reuse its pattern, not workflow SQL or the reserved event/action seam. |
| `tests/test_lead_source_admission.py:182-246,333-380,450-475,606-643` | Preserve formatting/key-rotation replay, atomic row writes, uncertain acknowledgement, native process races, non-resurrection and old-schema rejection. |
| `tests/test_lead_source_content.py:394-423,464-548,805-855`; `tests/test_lead_source_clock.py:381-415,478-499` | Preserve both writer/lifecycle orders, process death, purge cutoff, clock reconciliation and no implicit upgrade. |

Reuse the actual fixture/harness owners, not a new simulated store:

- `tests/test_lead_source_auth.py:22-105`: committed synthetic Ed25519 vectors,
  independent producer/signing helper, fixed UTC clock, scoped grants and policy.
  These frozen vectors contain available bodies; the joined harness below
  constructs explicitly unavailable variants. Test keys only; no mailbox or
  production credential.
- `tests/test_lead_source_store.py:33-50`: private native directory/SQLite setup,
  including the existing Windows directory-protection helper.
- `tests/test_lead_joined_recovery.py:48-86,93-179,323-360`: signed no-action pack,
  actual source/workflow owners, spawned processes, SQL-observed writes and
  before/after-commit crashes. Retain the later harness corrections in this pin.
- `tests/test_lead_joined_concurrency.py:144-264` and
  `tests/test_lead_joined_lifecycle.py:165-343`: exact identity, both transaction
  orders, source-only recovery and historical workflow observations.
- Runtime/tooling: Python 3.13 in both CI jobs, `uv sync --locked --all-groups`,
  native SQLite and the committed dependency lock. No inference model, chat
  template, prompt or model settings are involved. `uv.lock` SHA-256:
  `ef00a5b983e507a66f1dcca1687bf1f6523f031a44e640e5d9ae380832ecc5e3`.

Historical packets were inspected and hashed, **not rerun for this document**:

| Durable alias | Manifest SHA-256 | Recorded run |
| --- | --- | --- |
| `lead-joined-crash-proof` | `be6732665a3261d87111870fe1f9300288d17b4c40c2054bfe36add364d13d41` | `recovery.txt`: 14 passed in 16.89s |
| `lead-joined-concurrency` | `88fc6b135ff87bdeb6b6e1062b6cae6f1b4da5d4c7e583b626914e292837de4c` | `joined.txt`: 23 passed in 21.20s |
| `lead-joined-lifecycle` | `65a09c227f94d13d0ac69378b3da0e26529929c3a8cdaaba872ec766b0cc2546` | `joined.txt`: 44 passed in 28.22s |

Current source/fixture/lock hashes and historical log hashes: durable alias
`custody-r2-contract/inventory.json`, SHA-256
`e47963c8bf4e01be90cb6e44e30577965079a5f126e9f705aa2c106106f57edc`.
Historical test totals are not fresh qualification of this base.

### Required change surface and ownership

The implementation proposal is limited to the source library, its tests and CI
selection. New names below are proposed private APIs, not existing capabilities.
Source paths in this table are relative to `src/connect_automate/`; test, fixture,
workflow and documentation paths are repository-relative. The original contract
PR edited only this document and the parent contract's status/continuation pointers.

| Owner | Required change |
| --- | --- |
| `lead_intake/source_store.py` | `_SCHEMA`, `_SCHEMA_VERSION`, exact manifest validation, initialization and an explicit version-4-to-5 migration; private query-only snapshot and shared metadata validation; source incarnation, intent/fence/operation storage and in-writer lifecycle checks. This owns all new storage SQL. |
| `lead_intake/admission.py` | `_existing` metadata/content validation split; shared in-transaction `admit_source` core and private managed admission/revalidation entry points. Preserve both raw authentication checkpoints and one content writer. Check managed-event exclusion inside the ordinary entry's writer. |
| New private `lead_intake/custody_store.py` | Host-constructed facade: register intent, bind upload, admit bound raw bytes, observe metadata, close admission and revalidate existing custody. Calls the source owners; no SQL, callbacks under their writer, transport handler or workflow submission. |
| `lead_intake/content.py` | Only `_row`/`_existing` validation call sites and `purge_message`, `retire_namespace`, `cleanup_retired` coordination with managed records under the same writer. Preserve legacy cutoff, terminal lifecycle and unmanaged cleanup return semantics. |
| New `tests/test_lead_custody_store.py` | Explicit migration, schema/row integrity, query-only snapshots, operation identity, finite capacity and replacement-incarnation tests using the existing fixtures. |
| New `tests/test_lead_custody_races.py` | Real spawned-process writer order, per-write failure, crash/reopen, lost response and managed/unmanaged bypass tests using existing harness primitives. |
| New `tests/fixtures/lead_source_admission/v4-source-schema.sql` | Frozen schema fixture generated from the pinned `_SCHEMA`, compared with its SQL. Synthetic data only; no copy of a live store. |
| `tests/test_lead_source_admission.py`, `tests/test_lead_source_content.py` | Add managed-boundary and lifecycle regressions only; preserve existing cases/assertions. Other existing source, clock, runtime and joined tests are regression inputs, not an edit allowance. |
| `.github/workflows/ci.yml` | Include new focused files in native Windows selection from the first executable push; Linux already selects all tests. |
| This document | Acceptance and bounded implementation evidence; no retrospective acceptance of code. |

`lead_intake/results.py`, runtime submit/lookup projection hunks and the workflow
store event/action snapshot seam remain reserved to pack-kit. No edits to them,
their tests/contracts, `handoff.py`, R1 models or public exports are included.
R3 will need an accepted composition boundary for fenced raw admission and
existing-custody revalidation; a wrapper check followed by the legacy unfenced
call is not sufficient. If implementation needs any unlisted file or reserved
hunk, revise this allowlist and reconcile ownership before writing it.

R2 places durable intent and mutation identity in the **same source SQLite
deployment**, owned by the source custody API. R3 uses these APIs for authoritative
intent/fence facts. Its receiver adapter owns durable transport-operation mapping
through the existing Connect boundary; no current job cache is asserted to satisfy
that durability requirement. It must not mirror custody or issue source/workflow
SQL. No second database, scheduler, queue or cross-store transaction is introduced
in R2. R3 separately specifies placement, restart recovery, transport-result caching
and authentication for its mapping; R2 does not implement that wire protocol.

### Storage contract and explicit migration

Propose schema **5**, with the existing schema-4 objects retained unchanged and
three additional strict tables plus their integrity constraints:

1. `source_handoffs`: primary key `handoff_id`; unique
   `(organization_id, namespace_id, event_id)`; immutable canonical intent and
   its digest, full source identity, host/organization, route digest, enrolled
   machine reference and original prepare identity; complete optional capture
   metadata; reservation deadline; fence generation; monotonic state revision;
   terminal closure flag; immutable optional admission ID and an irreversible
   `ever_custodied` marker. Indexed identity columns must equal canonical data.
   Capture is bound once, all fields together. Admission ID/ever-custodied are
   recorded in the same transaction as the original receipt/content writes.
2. `source_handoff_operations`: immutable IDs, handoff, operation kind and
   canonical request fingerprint for prepare, upload and settle, with monotonic
   phase/revision evidence. Enforce uniqueness of both control and job IDs across
   these operations in the deployment; changed payload, kind or handoff under
   either ID is a conflict. Binding and admitting are two phases of the **same
   upload operation**, not different jobs. Its record progresses from bound to
   admitted in the custody commit; its identity/fingerprint never changes. At
   most one prepare, upload and settle identity is stored per handoff. Store no
   secret, raw envelope or raw body. This journal proves source mutation
   idempotency, not an immutable transport-result cache or all R3 operations.
3. `source_store_identity`: one immutable incarnation UUID created at explicit
   initialization/migration, independent of host/organization and file path.
   Each handoff and private host binding pins this value. Replacing a store with
   a freshly initialized store for the same deployment produces a different
   incarnation; old bindings refuse it. This is accidental replacement detection,
   not a secret, machine authorization or protection against restoring an older
   copy containing the same incarnation.

Use the existing closed R1 intent/capture vocabulary and canonical serializer;
do not create a second source schema or receipt serializer. The local operation
fingerprint includes all supplied immutable request fields, including operation,
handoff/control/job IDs, scope, machine/proof references, expected generation and
payload. These references are untrusted data. A changed proof reference conflicts
with an occupied source-operation slot; it cannot replace that slot or create a
second upload. Current machine authorization and credential rotation must be
reconciled by the later machine/transport contract without rewriting the pinned
source operation. Status and resume transport IDs are separate from this journal.
A mutation retry must compare the complete stored fingerprint before using an
idempotency shortcut. Register and first close record their
transition atomically; bind records the pending upload; admission can only
advance that same upload record. Lifecycle closure may precede a settle request:
it closes the handoff directly, and the first later settle identity records a
validated observation of that closure without incrementing its generation again.

An admission link is not a cascading foreign key that permits deleting a
handoff's historical fact when retired receipts are erased. Within R2, handoff
and mutation metadata are not deleted or reassigned. Existing retirement may
still erase source receipt/content rows. The surviving ever-custodied marker
then prevents any claim of fenced absence; missing receipt proof produces an
unknown observation, never a fabricated receipt. R5 must define bounded metadata
retention/erasure and restore before deployment. This is synthetic local proof,
not acceptance of indefinite production retention.

Migration is a separate, explicit privileged local `SourceStore` operation:

- No call to initialize, read, admit or observe upgrades an existing database.
  Ordinary schema-5 operations reject schema 4 until explicit migration.
- Upgrade only an exact, valid version-4 store for the configured deployment;
  reject older, future, foreign, damaged and lookalike schemas without writes.
  Validate existing authority, clock, lifecycle and each custody/receipt/content
  invariant before changing schema. An empty uninitialized file is not version 4.
- Under the existing private-path checks, bounded writer wait and FULL/WAL
  transaction, create the new objects and incarnation and set `user_version=5`
  atomically.
  Validate the full target manifest before commit. Use individual transactional
  DDL statements, not a helper that implicitly commits partway through.
- Existing receipt/content bytes, authority history, clock floor, purge horizons
  and retirement markers remain logically identical. Do not invent intents from
  old receipts, recover missing snapshot fields from guesses, rewrite envelopes
  or adopt a legacy receipt into a newly registered handoff.
- Repeating the explicit migration on exact valid schema 5 is a validated no-op,
  preserving its incarnation. Two migrators serialize; only one applies.
  Lost commit acknowledgement remains
  uncertain until reopening the expected deployment proves version 4 or valid 5
  with its committed incarnation. Preserve that identity before any managed intent.
  No catch-and-reinitialize recovery.
- New initialization creates exact schema 5. Older binaries reject it through
  their existing exact-manifest check. Rollback disables new ingress and keeps
  the version-5 store; no down migration or restoration of a pre-fence backup.
  Production backup/restore recovery is an R5 gate, not a migration convenience.

### Observable local operations and fence rules

All operations are private host-library seams under the existing trusted local
OS-user boundary. They neither accept a caller's model as authenticated authority
nor establish employee/machine permissions. R2 makes no service export or public
`lead_intake.__init__` export. A later receiver requires current protected-host
authorization in addition to these source invariants.

Private host bindings carry the expected store incarnation from explicit setup,
not an arbitrary value read and accepted from the current path on each operation.
Validate it inside the same snapshot/writer as the operation. Missing or mismatched
bindings refuse. R3 must durably retain it with its trusted installation/operation
mapping; losing that mapping requires reconciliation, not automatic re-enrollment.

| Operation | Required behavior |
| --- | --- |
| Register intent | Validate/reparse full intent, scope and route digest; reject retired namespace, conflicting handoff/event/route, or a pre-existing unowned receipt. Pin once under the writer. Start generation/state revision at 1. Caller supplies a finite reservation deadline validated against the qualified clock. Identical retry never extends it. No capture or receipt yet. |
| Bind upload | With matching open generation, complete capture metadata and exact operation identity, pin the capture once before any upload can be admitted. Recheck namespace/cutoff, policy references and deadline under the writer. Different capture/envelope under the same intent conflicts. Lost acknowledgement can be resolved from durable metadata. |
| Admit bound raw bytes | Under the same writer that commits content, check immutable intent/operation/capture binding, open generation, reservation eligibility, source lifecycle and current source authentication. Reuse the admission core and canonical artifact comparison; no parse-only admission or callback under the writer. Atomically record the handoff's admission link and ever-custodied marker with content/custody/receipt. |
| Observe | One metadata-only snapshot; exact incarnation/handoff/scope/event/route/machine comparison and, when supplied, the entire capture pair. Return private source facts only. No body read, source authentication, clock-floor update, expiry deletion, workflow query or dispatch. Not-found is an observation, not final absence. |
| Close admission | Under the same writer, compare identity/generation, permanently close first-write admission, then check exact receipt/custody metadata. Preserve a committed receipt; establish closed-empty only if a valid known intent has never had custody and no matching receipt exists. Commit closure and mutation identity together before reporting it. |

The canonical artifact is mandatory at the fenced ingress: raw bytes must equal
`canonical_source(parsed)` and their SHA-256, length, payload digest, snapshot,
capture/deadline, source/trigger/policy and deployment must match the pinned
values. Keep existing legacy formatting/key-rotation replay behavior for
**unreserved** event keys. For a reserved event key, unfenced `admit_source`
refuses both first write and replay under its own writer; a caller cannot use
the old runtime seam to bypass a closed handoff. R3 must compose the fenced seam
into the complete runtime submit path; R2 does not wire it or accept a receipt
as a workflow submission credential.

Generation is not a lease. R2 has one open generation and a permanent closed
generation; closure advances it once, and an exact repeated close does not
advance it again. There is no reopen, generation recycling or automatic recapture.
State revision advances only on actual state changes, not duplicate retries.
Use strict bounded `Revision` values, reject overflow before a mutation, and
never wrap, clamp or substitute a default. Concurrent identical mutations yield
one committed transition; conflicting mutations preserve the winner.

For an exact repeated close, compare its recorded fingerprint before treating
its original expected generation as stale; return the recorded closure evidence
without another transition. A first settle following lifecycle closure must use
the current generation and cannot reopen or increment closure again. Neither
shortcut bypasses current host access checks in a future receiver. A source
closed-empty fact alone is insufficient for R1's final `fenced_empty` response:
R3 must also reconcile the independent workflow outcome at its owner.

Reservation expiry disallows new binding/first admission but does not by itself
prove absence. Binding capture does not extend the reservation. A first upload
must satisfy reservation, signed recovery deadline and source grant validity at
the final decision sample; equality at an expiry boundary refuses. Once custody
exists, original reservation expiry does not erase it. Add a distinct private
revalidation seam for already-linked custody: exact handoff/capture/admission
references and **current** generation, current source authentication, matching
original envelope and valid retained content are all required under the writer.
It may work after closure but can never insert content or create a receipt. It
does not create another upload identity or operation record; R3 owns the separate
resume job's mapping/authentication. An old upload operation/generation cannot
use this exception through the first-admission entry point. Status remains
independent of original signing-key validity. Full reference-only resume belongs
to R3 and must still reauthenticate raw bytes through the complete submit path.

### Metadata observation and lifecycle

Add a `mode=ro`, `PRAGMA query_only=ON` snapshot owner with a SELECT-only SQL
authorizer after setup; forbid ATTACH, DDL, DML, transaction replacement and
PRAGMA changes from the query body. Preserve live WAL visibility, never use
`immutable=1`. Validate the exact schema, incarnation, deployment and required
authority/lifecycle metadata without taking the source
writer or running initialization. Keep the existing private-path and bounded
busy behavior. Do not reuse `_existing` wholesale: its retained branch reads and
authenticates raw bytes. Extract one shared metadata validator used by both the
snapshot path and `_existing`; retain the latter's content-integrity checks for
admission/content access. Do not duplicate parsing or weaken those checks.

Read receipt plus handoff/custody metadata in the same snapshot. Compare the
stored envelope hash even after raw purge; compare payload digest, full identity,
capture time, deadline and linked admission ID. An existing legacy receipt may
be looked up by its exact scoped event and expected digests, but cannot supply
missing receiver metadata or be adopted into a handoff. A scan is not a keyed
resolution API. Supplied wrong/mixed references conflict without returning facts
from another handoff.

The private observation is not an R1 `ResolvedResult`: wire composition and its
observation-time semantics are R3. In particular, a stored retained marker is
not proof of authorized/live content, and no snapshot call may return bytes.
Raw absence with a retained marker is corruption/unknown, not proof of purge;
check existence without selecting the envelope. Metadata-only status does not
claim to detect corruption inside an existing raw blob.
SQLite WAL read bookkeeping is distinct from an application mutation: test native
filesystem behavior instead of claiming query-only means no filesystem I/O.
Forbid body-column reads while allowing a metadata-only existence check; neither
that check nor a retained marker authorizes content access. A missing receipt
after permitted retired cleanup remains unknown history, never closed-empty.

Message purge retains its full physical identity and original capture cutoff.
Binding/admission must consult the existing horizon inside the writer. Purge
serializes with binding/admission and closes matching known captures at/before
cutoff while preserving later captures. A prepared intent with no capture time
cannot be guessed to be old: the durable horizon rejects an eventual old capture;
it does not reject a genuinely later one. Retirement refuses all new work for
the namespace and prevents reinitialization, including after metadata cleanup.
Expiry/purge/retirement never reset a handoff's closure or ever-custodied marker.
Reuse the source owner's lifecycle facts; do not infer a new deletion reason
from a missing content row or promise to distinguish historical purges whose
cause was never recorded. R3 must preserve unknown where evidence is insufficient.

### Capacity, failure and privacy

R2 construction requires explicit positive bounded limits for stored handoffs
and mutation records, using strict integer validation up to the existing
`Revision` maximum. No `0`, Boolean, empty value or omitted/unlimited default.
The constructor also requires an explicit positive maximum reservation duration
in seconds, bounded by that type. A supplied deadline must fit it. Numerical
production settings and byte/disk quotas are still R3 deployment inputs.

Enforce record budgets atomically at registration: reserve three operation slots
per accepted handoff (prepare, upload, settle), counting reservations as well as
occupied rows against the configured limit. Refuse registration if either budget
would overflow; never accept an intent that cannot bind, admit or close later.
Binding/admission share the upload slot. Lifecycle closure requires no additional
slot. Quota exhaustion cannot disable settlement, exact retries, metadata
observation or revalidation of existing custody. No automatic eviction of
unresolved intents, idempotency records or tombstones. New identifiers for an
already-bound source mutation conflict rather than consuming unbounded rows.
If R3 needs additional operation retention, specify it in that work order before
adoption instead of silently widening this source mutation journal.

Use fixed input-free source errors: malformed local values are input errors;
binding/idempotency collisions are conflicts; stale/closed/expired first admission
is refused; busy is retryable uncertainty, not absence; invalid storage is
unavailable. Reuse `SourceStoreUncertain` for an ambiguous commit. A post-commit
serialization/return failure must never be reported as proof of rollback.
No SQL/path, body, secret, signed envelope, model input or exception chain in
boundary errors/logs. Existing private-file rules apply to all sidecars and new
metadata; no extra raw copy in the handoff or mutation tables.

R2's expected-incarnation check covers a newly initialized replacement, not
rollback of a previously valid database with the same identity. Rollback-resistant
restore is **UNKNOWN** under the current OS-user trust boundary and remains an
R5 gate. An empty/replaced store is not proof that a previous handoff was empty.
Missing intent stays not-found/unknown; recovery never registers a replacement
intent. An existing-custody operation cannot be downgraded to first upload after
row loss. Protected installation identity and current machine authorization
remain gates before any live receiver.

### Differences from the proven library lane

| Proposed difference | Reason and required proof |
| --- | --- |
| Schema 4 becomes explicit schema 5 | Persist intent/fence and mutation identity. Exact preflight, atomic DDL, row equality, crashes and old-binary refusal must pass. |
| Unreserved signed admission gains a separate fenced path | Receiver must forbid old workers after closure. Existing unreserved tests pass unchanged; reserved-path bypass and both writer orders fail/pass at the source owner. |
| Capture pair is pinned before upload, admission link commits with custody | Recover lost adapter mapping without a second receipt owner. Kill the process after every actual write and after commit; no partial capture/admission link may survive. |
| Status gains a query-only metadata reader | Avoid body access, writer waits caused by a status writer, expiry and clock mutation. SQL trace plus concurrent snapshot proof. |
| Lifecycle also constrains handoffs | Purge/retirement cannot permit old captures to return. Test both lock orders, equal cutoff, later capture and retired metadata erasure. |
| Explicit finite metadata/reservation limits | No unbounded proposed receiver store. Test exhaustion with concurrent prepares and ensure reserved settlement capacity remains usable. |
| Immutable store incarnation in expected host binding | Refuse newly initialized replacements at the same path/scope. Preserve the value across reopen/migration retry; do not claim older-backup rollback resistance. |

No other departure is implicitly authorized. If the port cannot reproduce the
existing library lane, isolate the owner/porting difference before changing
fixtures, expected outcomes or source authentication policy.

### Explicit non-scope and assumptions/blockers

- No executable edits in the original contract PR (#51). No new service, capability registration,
  enrollment/proof wire format, HTTP endpoint, scheduler or live mailbox.
- No Watcher, EOM, Atlas, application pin, release/catalogue, keyring or production
  key changes. No pack/action-result owner changes, extraction or lead creation.
- No changes to R1 wire schemas, source envelope/signature preimage, existing
  receipt shape, workflow database or workflow result/action semantics.
- No runtime fenced-resume wiring in R2; the legacy runtime remains qualified for
  unreserved library use. Reserved-event refusal is an intentional source-boundary
  restriction. Its R3 composition needs a separate accepted contract.
- No new production retention policy, encrypted storage claim, metadata garbage
  collection, silent raw eviction, down migration or backup restore procedure.
- **Gate:** independent review and Juan's acceptance of this exact design, including
  schema migration, reserved-event restriction and finite-capacity behavior.
  Native machine trust and production capacity/retention are unresolved later
  integration gates; they do not turn synthetic identities into authorization.

### Verification plan

Implement only after exact-head contract review and explicit acceptance, in bounded
ordered PRs: migration and read-only resolution first; then the complete managed
mutation boundary including close, lifecycle and unfenced-bypass rejection; then
remaining process qualification. Do not expose intent registration in an earlier
PR without its in-writer admission/closure guards. Every PR preserves the full
existing library lane; no partial PR qualifies the receiver or production use.

Before implementation, rerun the existing source/store/auth/admission/clock/content,
receipt/runtime and joined recovery/concurrency/lifecycle lane unchanged at the
accepted base. Record runtime, lock and fixture hashes. Preserve this parity lane
as the regression guard. This source/schema change is high risk: run the combined
affected lane locally before each bounded implementation PR's grouped push, then
require the existing Linux full CI and native Windows lane at the exact published head.

| Proof | Required cases / counterfactual |
| --- | --- |
| Migration | Empty, valid 4, already-valid 5, older/future, foreign, malformed objects and rows; two migrators and migration versus old/new writer; before/after every DDL/identity/version write and commit; full old-row equality; old executable refuses 5. Mutant skipping exact schema/scope/integrity preflight must fail through intended assertions. |
| Intent and capture | Same IDs/same content idempotent; change each scope/route/machine/event/policy/trigger/capture field independently; second handoff for same event; unowned legacy receipt conflict; both digests distinguished; raw canonical bytes vs same-payload different envelope. Remove each binding clause separately. |
| Atomic custody | Fail/crash after each actual content/custody/receipt/link/operation write; reopen owner before inspection; before commit none survives, after commit all required records agree; uncertain acknowledgement resolves without reread of mailbox or another envelope copy. Remove link atomicity and prove the minimal case fails. |
| Fence race | Separate native processes: upload owns writer first, close owns writer first, reserve versus unmanaged admission in both orders, worker stalled before writer, simultaneous closes, stale upload after restart, closed existing-custody revalidation without a new mutation slot, no reopening. Observe actual lock contention/checkpoints; no sleeps as ordering proof. Mutants moving fence check before lock, skipping final check, treating absence as closed, or allowing unfenced reserved replay must fail. |
| Query-only observation | Revoke original key, expire/purge raw, preserve receipt; snapshot spanning a concurrent commit; no body select/auth/clock/write/dispatch; missing metadata vs closed-empty; corrupt/mixed links, retained row with absent blob, retired receipt erasure. Assert SQL and state, not just result labels. |
| Lifecycle | Both orders for bind/admit/close versus purge/retirement; equal cutoff, later capture, unbound capture followed by old/new upload, expiry equality, authority change and clock regression; no resurrection after cleanup/restart. |
| Boundaries and privacy | Minimum/maximum and adjacent invalid revision/count/deadline values; `0`, `False`, empty/null, partial/mixed capture; forged/copied models; capacity race and reserved close capacity. Assert fixed exception type/message/no cause/context and body-free logs, including post-commit failures. |
| Replacement and evidence loss | Same path/host/organization with a new incarnation refuses old bindings; wrong/missing incarnation refuses before effects. Missing adapter mapping or source rows cannot register a new intent or manufacture closed-empty; lose receipt after legitimate retirement without fabricating it. Restore with the same old incarnation remains explicitly unqualified. |
| Parity | Existing unreserved envelope formatting/rotation, immutable receipts, authority/clock/lifecycle rules, source-only crash and no-action workflow results remain unchanged; all earlier R1 guard counterfactuals retained. |

For every new semantic clause, keep an otherwise-valid negative, a positive
boundary and a mutation that fails at the intended assertion, not setup/import
failure. Derive crash checkpoints from executed writes and assert stored state
independently. Reuse the existing harness and preserve causal output under durable
alias `custody-r2-implementation`; private evidence stays outside worktrees.
Preserve the source clock-floor/final-auth checks after waits, including expiry,
revocation and backward/forward movement. Use short test parameter IDs and
explicit UTF-8 fixture reads on both platforms from the first executable push.
Run focused regression/adjacent files plus Ruff during iteration; do not repeatedly
rerun unrelated broad matrices. No tests were run for the original contract-only
PR; implementation evidence is recorded below.

## Implementation summary

The first bounded implementation adds schema-5 initialization, explicit migration,
a private metadata-only observer and shared receipt metadata validation. Existing
content authentication remains in the admission owner. The new handoff tables
are not exposed through registration or any managed mutation API in this slice.
The original contract/acceptance record remains above; later R2 operations are
authorized work, not implemented capabilities.

## Cold diff audit

- `lead_intake/source_store.py`: preserves the frozen schema-4 objects, adds
  schema-5 identity/handoff/operation storage, explicit atomic migration, a
  read-only snapshot with a body-denying SELECT authorizer, and the shared
  metadata/state/request validators. No managed source mutations are exposed.
- `lead_intake/admission.py`: delegates metadata validation to the source owner;
  retained content still passes canonical/hash/payload/historical signature checks
  at the existing admission owner. Public admission and receipt shapes are unchanged.
- `lead_intake/custody_store.py`: private host-bound facade; strict reference inputs,
  expected incarnation, finite constructor bounds and source facts only. No SQL,
  source authentication, clock, scheduler, workflow access or dispatch.
- `tests/test_lead_custody_store.py`: exact migration preflight/row preservation,
  metadata-only snapshots, independent state/fingerprint/corruption clauses,
  binding/capacity-type boundaries and immutable SQL identity checks.
- `tests/test_lead_custody_races.py`: actual spawned-process contention, both writer
  orders, per-write failures/crashes, uncertain commit and lost-response reopen.
- `tests/fixtures/lead_source_admission/v4-source-schema.sql`: frozen from the
  inventory pin; no live database or private content. Existing tests/fixtures are
  unchanged regression inputs.
- `.github/workflows/ci.yml`: selects both new files on native Windows from the
  first executable push. No job, dependency or application pin changes.
- This document records accepted scope and evidence; the parent document's
  implementation status is historical as of the contract-only PR.

## Gap audit

**NOT DONE:** the local combined affected lane passed; the first implementation
slice still requires exact-head Linux/Windows CI, oversight and connector review
before merge.
Managed registration/binding/admission/closure/lifecycle integration and remaining
process qualification are later bounded R2 PRs. R3-R5 and protected-machine work
remain separately gated. No receiver deployment or production adoption is claimed.

## First bounded implementation record

The contract merged in PR #51 at
`3f1397a4a0fb08bf9e7ab2e38f25541321d2ac24`, with the same tree as the reviewed
acceptance commit `9252ac2527d3b295061107c3465fe1dc1c0ba499`. Juan's subsequent
“continue” starts only the first ordered implementation slice. Source, fixture,
dependency and workflow inputs still match the inventory pin; only the accepted
contract documents changed between that pin and this base.

Required surface for this PR is limited to `source_store.py` (exact schema-5
initialization, explicit migration, read snapshot and shared metadata validation),
`admission.py` (metadata/content validation split preserving retained-byte checks),
the new private read-only `custody_store.py` facade, the two new custody test files,
the frozen version-4 schema fixture, native Windows test selection and this record.
No registration, binding, managed admission, close or revalidation entry point is
exposed. Their complete in-writer fence and lifecycle boundary remains the next
bounded PR. Existing tests and fixtures stay unchanged.

`SourceStore.migrate()` explicitly returns the applied/no-op result and committed
incarnation. Explicit setup may read that identity; observation requires an
expected incarnation supplied by its host binding and never adopts a replacement.
The private observation facade returns source facts only, including an exact
legacy receipt lookup and keyed handoff metadata observation. It does not produce
an R1 wire result or authorize source access. Synthetic fixtures may seed future
managed rows to test the schema and reader; no production writer is introduced.

Verification: unchanged baseline before edits; fail-first migration/observation
probes; exact schema and row preflight, row equality, two-process migration and
writer ordering, per-write rollback/crash/reopen, unknown commit outcomes,
read-only/live-WAL snapshots, isolated corruption guards and clause mutants.
Existing receipt/body checks must still run through their original admission
owner. Run the contract-required combined affected lane before the grouped push;
include both new test files in Windows CI from that push. No production migration,
mail access, service or application adoption is part of this work.

The scope-record commit preceded executable edits. Incremental evidence:

- Unchanged baseline: `2656 passed in 129.56s (0:02:09)`.
- New metadata suite after consolidation: `211 passed in 20.09s`.
- Native migration/write-order suite: `54 passed in 38.21s`.
- Guard/read-boundary counterfactuals: 74 intended assertion failures, no survivors
  or invalid probes. The initial masked cases were retained in the evidence packet;
  request decoding and state invariants now have single independently tested owners.
  Derived duplicate comparisons were removed; exact SQL uniqueness owns operation slots.
- Pinned old `SourceStore` accepts schema 4 and refuses migrated schema 5 with
  `SourceStoreUnavailable`. Owner SHA-256
  `18eb7132769176fb421d26ccf93b2655c8ec1cf94fd5e32dc540a40dfd302230`.

A defect introduced while developing this implementation was reproduced before publication:
`custody_store.py:_input` used the coercing default of `TypeAdapter(Digest)`, so
bytes and bytearray digest references were accepted. Four strict-text cases failed
before the fix and passed after the shared input owner began using `strict=True`.
Both digest fields use that owner; no downstream compensating check was added.
The exact coercing variant is also killed by the regression suite.

The combined required affected lane at implementation commit
`49235afb67ec1c1632b571cfc24fad0bf217d0d2` completed:
`2921 passed in 203.46s (0:03:23)`. Repository Ruff reported `All checks passed!`;
the changed Python files passed formatting. Existing tests, reserved owners,
dependencies and application pins are unchanged. This evidence-only follow-up
changes no executable input; code tests are not rerun for its prose.

Durable evidence alias: `custody-r2-implementation/manifest.json`, SHA-256
`92cdb05c2ed4d9af66e17d792f0184a496a6e2b29f5cfec764ac12894e30f291`.
The packet retains the baseline, fail-first results, strict-reference defect,
both mutation rounds, process evidence, pinned old owner and final combined run.
These are local results, not completed native Windows or receiver qualification.
No code outside the allowlist changed.


## Second implementation work order: managed mutation boundary

### Root cause

At merged base `c6aa8a9f7679c8fb89f0c0b8773f6e8f484293ca`, the source owner
persists and validates schema-5 handoff metadata but exposes no managed writer.
`SourceAdmission.admit_source` owns the existing authenticated transaction without
a reserved-event fence; `SourceContent` owns lifecycle effects without handoff
closure. Registration cannot safely ship without those same-writer protections.
This is the next implementation ordered by the accepted R2 design, authorized by
Juan's “Let’s start”; it does not change that design or qualify a receiver.

### Required change surface

- `source_store.py`: private registration, operation fingerprint/capacity,
  capture/fence/link/closure and lifecycle helpers. All new SQL stays here;
  schema-5 tables, triggers and migration remain unchanged.
- `admission.py`: extract the existing transaction body into one shared admission
  core. Add reserved-event refusal to the legacy path and private managed admission
  and existing-custody revalidation. Raw authentication remains here; no callback
  or forged authentication result may authorize an effect.
- `custody_store.py`: private host facade, no SQL. Accept an optional host clock
  for mutating operations (missing/non-callable clock refuses mutation); existing
  read-only construction and observation remain usable without a clock. Reparse
  R1 request models through canonical encoding/decoding. Return private source
  facts, not receiver wire results or employee/machine authorization.
- `content.py`: coordinate closure with existing expiry, physical-message purge
  and namespace retirement in their source writer transaction.
- `tests/test_lead_custody_store.py` and `tests/test_lead_custody_races.py`: real
  operation regressions, isolated guard counterfactuals and essential process
  ordering/crash coverage. Existing source tests remain unchanged unless adding
  managed-only cases. Both custody files already run in native Windows CI.
- This document: work order now; implementation, cold-diff and evidence later.

### Explicit non-scope

No schema migration, R1 vocabulary, exports, dependencies, runtime submission,
lookup/projection/action-result owners or tests, handoff composition, application
pins, receiver/provider/service, Watcher/EOM changes, extraction or adoption.
No new workflow engine, source copies, authorization claim or production settings.
No separate admission implementation or lifecycle reason store. Existing legacy
formatting/key-rotation semantics remain unchanged for unreserved events.

### Assumptions/blockers

Private callers remain within the accepted local OS-user trust boundary. An
expected incarnation and explicit finite limits come from the host. Private
mutations consume strict R1 request values; a host-supplied clock is required for
time-sensitive writes. It is not taken from request metadata. Prepare additionally
receives an immutable reservation deadline; revalidation additionally receives
an exact admission ID and raw canonical artifact. There is no new wire contract.
A first settlement after lifecycle closure records its operation at the existing
closed state revision; it does not advance the fence again. Exact retries never
extend reservation, consume additional slots or advance state revision.

No implementation blocker is known. Native Windows and independent exact-head
reviews remain merge gates. Later process qualification and receiver/production
gates remain separate; this PR must still prove every newly exposed safety path.

### Verification plan

Run the unchanged combined affected library lane at the pinned base before source
edits; retain runtime, dependency/fixture/source hashes and output under durable
alias `custody-r2-managed`. The first regression deliberately calls missing managed
operations, then proves registration/binding/admission/close through the real owner.
Add individual otherwise-valid negative and positive cases for full immutable
identity, replay, scope, canonical bytes, current source authentication, fence,
reservation, capacity, incarnation and revision limits. Exercise lost responses,
per-write rollback/crash and both writer orders for admission/close and
reservation/legacy admission in actual spawned processes with IPC checkpoints.
Expiry, purge cutoff equality/later captures, unbound captures, retirement and
cleanup must preserve closed/ever-custodied facts. Revalidation cannot create rows.

Run focused tests and Ruff incrementally, then the contract-required combined lane
before one grouped push. Counterfactuals must fail at the intended assertion;
preserve rejected/masked probes too. CI must run native Windows from the first
push. Independent oversight and connector reconciliation remain merge gates.
Rollback disables managed ingress while preserving the fenced schema-5 store;
never reopen, drop tombstones, down-migrate or restore a pre-fence backup.

### Implementation summary

The docs-only work order was committed as
`c4b418cb7ccc2f689a1eac84094733449d86db7e` before executable edits. The unchanged
combined baseline at the merged base completed with exit zero. This slice adds
private registration, binding, fenced raw admission, permanent settlement and
retained-custody revalidation. One shared admission core retains both current
raw-authentication checkpoints and the original content/receipt writer. The
source owner coordinates handoff linkage and operation phase in that transaction.
The legacy path now refuses reserved events under its own writer.

Expiry, physical-message purge and namespace retirement close matching handoffs
in their existing transactions. Purge preserves newer captures and unbound
intents; the existing horizon rejects an eventual old capture. Retired receipt
erasure leaves ever-custodied history intact and observation unknown. Capacity
reserves the complete operation budget at prepare; exhausted capacity does not
prevent completion of existing work. No schema, wire, runtime, workflow or
application ownership changes are introduced.

### Cold diff audit

Paths below are relative to this repository; line references describe this slice.

- `src/connect_automate/lead_intake/source_store.py:844`: owns reserved-event
  exclusion and all new SQL, scope/fingerprint/time/capacity checks, capture
  linkage and permanent closure. `:936` registers; `:1012` binds; `:1052` settles;
  `:1068` compares raw source evidence; `:1107` links custody; `:1123` coordinates
  lifecycle closure. Real-operation negatives and isolated owner probes cover
  these guards, with process ordering and per-write rollback/crash assertions.
- `src/connect_automate/lead_intake/admission.py:146`: both entry paths use the
  shared transaction body at `:160`; current authentication remains before and
  after staged writes. Revalidation cannot enter first receipt creation. Existing
  unreserved tests remain regression inputs, unchanged.
- `src/connect_automate/lead_intake/custody_store.py:117`: private request-reparsing
  facade for all managed operations. No SQL, machine authentication, transport or
  workflow composition. Incarnation and missing-clock cases cover every mutation.
- `src/connect_automate/lead_intake/content.py:66,124,157`: adds same-writer closure
  to the existing expiry/purge/retirement owners, preserving legacy return values.
- `tests/test_lead_custody_store.py:1326`: appends real managed operation, immutable
  identity, scope, body-state, quota, clock, lifecycle and independent guard cases;
  previous tests remain byte-identical prefixes.
- `tests/test_lead_custody_races.py:266`: appends the existing spawn/IPC harness
  pattern for managed writes. Checkpoints are derived from actually executed SQL;
  crashes and injected SQL errors cover every observed write, both sides of commit
  and lost responses. Separate-process tests observe actual writer contention for
  admission/close, reservation/legacy, duplicates, lifecycle, expiry and capacity.
- This document records the bounded work order and evidence. CI already selects
  both files on native Windows; the workflow is unchanged.

boundary-probe: valid and unavailable body envelopes, exact retries, falsy/copied
request values, min/max reservation and revision edges, each capture/intent
comparison, changed operation identities, and both fence outcomes are exercised.
The isolated guard probes remove individual comparisons without relying on an
earlier parser rejection or later metadata validator to kill the counterfactual.

effect-trace: permanent upload exclusion | the source owner's writer-locked
handoff generation plus legacy reserved-event check | both process orders show
closure first refuses admission; admission first preserves the committed receipt.

### Verification evidence and repairs

- Local managed matrix before counterfactuals: `139 passed, 210 deselected in 20.86s`.
- Essential process matrix: `24 passed, 54 deselected in 66.66s (0:01:06)`.
- Selected counterfactuals: 34 intended assertion failures, zero survivors or
  invalid probes. Each changed implementation is retained in the durable packet.
- Repository Ruff: `All checks passed!`; scope audit proves schema AST equality,
  unchanged prior custody-test prefixes and no edits outside the explicit allowlist.
- Final combined lane: `3107 passed in 361.98s (0:06:01)`. The recorded source,
  test and dependency hashes match implementation commit `ba7ef1c37ce405b24e10feeaba6ded12ea3328f3`.
  Existing source-store functions are AST-identical, and the extracted legacy
  admission body is AST-identical after removing only the declared managed guards.
  These local results do not establish native Windows, receiver or production readiness.

An unpublished defect introduced in this slice used `first + max_duration` at
the pre-fix snapshot at `source_store.py:970`. A valid reservation near the calendar limit reproduced an
`OverflowError`; the owner now compares `deadline - first` with the finite duration.
The same regression passes, alongside ordinary duration boundaries. No downstream
fallback or special calendar case was added.

The first expanded test run also exposed new-fixture mistakes: an invented
`captured_chars` key and tuple/list confusion in policy construction. The fixtures
now use the frozen owner's `stored_chars` and an explicit mutable copy. A related
changed-envelope case had been rejected by malformed-body validation before its
intended comparison; it now constructs a valid body digest and proves independent
source authentication before testing the custody conflict. The corrected focused
lane passed; original failed/masked attempts remain in the evidence packet.

### Gap audit

NOT DONE — native Windows and exact-head independent review remain before merge.
R2's later qualification and R3 receiver composition retain their separate gates.

Durable evidence alias: `custody-r2-managed/manifest.json`, SHA-256
`c7715cc95d74d205bd27df9cd1eb6eb9ef668859ef048e25a61a3c976e51815c`. It retains the unchanged baseline, source-input
pins, expected failures and repairs, process traces, selected counterfactuals,
combined gate and committed-input equality proof. This follow-up is documentation
only; executable tests are not rerun for evidence prose.

## Remaining R2 process qualification work order (2026-10-27)

This is the final bounded R2 qualification slice in the accepted sequence above,
started on Juan's instruction, "Let’s review over and pick up next slice".
The earlier migration/read-only and managed-boundary slices are merged. The
managed-boundary review repairs are also merged; independent oversight confirmed
their negative proofs. This work order introduces no new product or contract rule.
R3 composition still requires its separately accepted contract.

### Root cause and required change surface

The managed boundary exists, but its native-process matrix does not yet cover
all the accepted lifecycle orderings, a worker stopped before acquiring the
writer, or closed retained-custody revalidation after restart. The current WAL
snapshot and replacement-incarnation tests use local connections. These are
qualification gaps, not evidence of a production defect.

Extend `tests/test_lead_custody_races.py` through its existing spawn/pipe,
checkpoint, observed-SQLITE_BUSY, per-write crash, and reopen helpers. Keep
existing operation inputs and assertions; add the missing actions and probes at
that harness owner instead of building a second runner. Use the existing source
and custody fixtures and the real private facade, SourceStore, SourceAdmission
and SourceContent operations. This canonical document records the inventory,
planned differences and resulting evidence.

### Inventory of validated work

Base: merged `6c93681277b1a7ef4fabf9347fcd9fab007dd034`, tree
`94f99d09a833148a615ab319f7e3a4b3d62ce28e`, identical to the reviewed managed head.
The prior combined lane recorded `3117 passed in 387.58s`; this is historical
evidence, not a run performed for this work order. Exact-head Linux/Windows CI,
oversight PASS and connector review qualified that merge.

| Existing owner/proof | Retained inputs and behavior |
| --- | --- |
| `tests/test_lead_custody_races.py` | Real spawned processes, native private-directory protection, pipe checkpoints, actual busy-lock observation, executed-write crash/failure enumeration, commit/lost-response recovery and exact store snapshots. Hash `f28b86de0e9b90633cf96d9e9fb0f5ead9990d3dad3da8935d2f0ae04fc15756`. |
| `tests/test_lead_custody_store.py` | Managed request/capture fixtures and real owner operations; retired-registration and full-identity purge negatives. Hash `527c3133e1c7e8c0b005dbcad0bdf8e7face1c5dd770a06d9a026d415c638be0`. |
| `tests/test_lead_source_races.py` | Existing grant/signature/lookup/commit revocation checkpoints and post-wait/final authentication proof through the shared admission owner. Hash `8440eb6e94b3cfd9712f154d524591b8934d8266386eff9aa1fb230ef5a669fa`. |
| Existing clock, joined recovery/lifecycle and source-content tests | Clock floor, authenticated replay, retention, cutoff and no-resurrection invariants remain in the combined regression lane. |
| Synthetic signing vectors | Unchanged `tests/fixtures/lead_source_auth/vectors.json`, hash `f06d60a7beaa0ab7acbda8f53a0072288282267563070def4a7ec80263343627`; no private messages or production keys. |
| Runtime/dependencies | Local Python `3.13.11`; existing Linux and Windows CI use Python `3.13`. `uv.lock` hash `ef00a5b983e507a66f1dcca1687bf1f6523f031a44e640e5d9ae380832ecc5e3`. No model, inference prompt, service or mailbox is involved. |
| Durable previous proof | `custody-r2-managed/manifest.json`, `custody-r2-managed/review-g1-g2/manifest.json` and `custody-r2-managed/merge-72f2796/manifest.json`; existing synthetic traces and counterfactuals remain retained. |

### Planned differences from the validated harness

| Difference | Reason and required evidence |
| --- | --- |
| Add a before-writer pause and bounded action support for revalidation, authority revocation and retired cleanup | Exercise the accepted worker-stall and restart paths through real owners. Retain the old actor actions and default clock/packet behavior unchanged. |
| Reuse one ordered-process coordinator for additional lifecycle pairs | Complete both writer orders for bind/admit/close versus purge/retirement, including unbound old/new captures. Order comes from IPC and observed lock contention, never sleeps. Existing expected outcomes remain assertions. |
| Add managed post-wait clock and authority cases | Prove backward/forward changes and revocation cannot be bypassed by a queued or restarted managed admission. Keep the existing source authorization/checkpoint tests unchanged. |
| Add fresh-process closed-custody revalidation and retirement cleanup recovery | Stale generation refuses, current authenticated retained replay preserves the same receipt and creates no operation slot, purge/expiry/revocation refuse, and erased retired receipts remain unknown history. |
| Exercise metadata snapshots and replacement with a separate process | A live WAL snapshot stays stable across a real closure commit; a fresh snapshot sees closure. A new store incarnation at the same path refuses old packets without creating records. |
| Add focused counterfactual probes in durable disposable import copies | The pre-writer fence/time-of-check-to-time-of-use, final checks, admission-link/revalidation and lifecycle cases must fail at intended assertions when their owner guarantee is removed. Reuse the earlier mutation-loader pattern; do not alter checkout source to run mutants. |

No other differences are planned. Existing per-write crash/lost-response and
unmanaged replay/capacity proofs are reused; extend their operation coverage only
where the added lifecycle/revalidation paths require it. Any reproducible owner
defect is reported and repaired at its origin under the accepted invariant, with
fail-before/pass-after evidence; an untested hypothesis is not a source change.

### Explicit non-scope

No production-source change is planned. No schema, dependency, public export,
R1 protocol, result/transport, receiver/service, machine-authentication, workflow,
Watcher/EOM, application pin, extraction, retention-policy or adoption change.
Do not infer authority from synthetic machine references. R3/R4/R5 and installed
application proof remain separate work; no new dispatch or workflow mechanism.

### Assumptions and verification plan

The existing R2 acceptance authorizes this ordered qualification work; this
docs-only work-order commit precedes test edits. Source custody remains the
single transaction owner. The same native harness must run on Linux and Windows.
Any platform-specific proof still absent after the new CI run stays explicitly
unqualified rather than becoming a release-note exception.

Before test edits, rerun the unchanged combined affected lane at this base and
record executable, dependency, fixture and test hashes under durable alias
`custody-r2-qualification`. Add otherwise-valid negative cases and positive
neighbors. Reopen before state inspection, preserve actual write/lock traces,
check fixed exception type/message/no cause/context and body-free IPC/log output,
and distinguish committed success from lost response and unavailable evidence.
Every new probe must either kill its intended counterfactual or identify an
existing backstop explicitly; setup/import failure is not a killed mutation.

Run focused process/adjacent tests and Ruff incrementally, followed by the
contract-required combined affected lane before the grouped push. Preserve all
old tests and source behavior; list the exact harness-only differences in the
cold diff audit. The existing CI already selects the custody race file on native
Windows. Exact-head Linux/Windows CI, independent oversight, connector
reconciliation and tree identity remain merge gates. Rollback disables managed
ingress while retaining the fenced store; no downgrade, reopening or tombstone
erasure is authorized.

### Implementation summary, cold diff audit and gap audit

The executable change is confined to `tests/test_lead_custody_races.py`.
Production source, schemas, fixtures, dependencies, CI selection and public exports
remain identical to the merged base. This slice qualifies existing owners; it
adds no receiver, mailbox activity or new business behavior.

Cold diff audit:

- `managed_child` retains its original owner operations and defaults. It adds
  before-writer/clock-sample checkpoints, retained replay, revocation, cleanup,
  expiry, read and observe actions, plus captured diagnostics. Clocks still come
  from the embedding host fixture. New capture variants use the existing signing
  and request helpers. No production rule is implemented in the actor.
- `ordered_managed` extracts the old IPC/SQLITE_BUSY coordinator and is shared by
  old and new races. The new before-writer mode waits for closure to commit before
  releasing admission. The final-clock mode freezes the first sampled value and
  moves the next sample through an event. Sleeps never establish ordering.
- The original per-write/commit matrix remains and now includes retired cleanup,
  expiry and retained replay. Faults include the synthetic source envelope in the
  SQL exception, so fixed errors and empty captured diagnostics are asserted even
  after commit. Original migration actor/tests remain structurally unchanged.
- New native tests cover the remaining bind/admit/close lifecycle orders, authority
  ordering, equal/later capture horizons, post-wait/final time changes, stale and
  current-generation replay after reopen, no additional mutation slot, receipt
  erasure after retirement, native WAL snapshot stability, same-path replacement,
  and unknown versus closed-empty. Positive retained reads and later captures are
  asserted alongside refusals. Snapshots assert rollback and receipt preservation.
- Lost-response cases explicitly assert that neither a result nor a receipt is
  published before the crash, then recover the same durable receipt in a fresh
  process. This assertion exposed an ordering defect in the new test actor:
  the initial receipt trace preceded the response-loss checkpoint. The unchanged
  source was not responsible. Both admission and retained-replay assertions failed
  before moving that trace, and passed afterward. The regression remains in CI.

Verification recorded under durable alias `custody-r2-qualification`:

- Unchanged baseline at work-order commit
  `639de99f2e8cc56ea2cbdccb271eb4f5eca10ce2`:
  `3117 passed in 467.75s (0:07:47)`. All captured source/test/dependency inputs
  still matched when it completed, before the first test edit.
- Process file before the final lost-response assertion: `126 passed in 193.72s`.
  This earlier pass is not substituted for the final combined gate below.
- Lost-response probe: `2 failed, 126 deselected in 1.13s` at the intended premature
  receipt assertion; after repair, `2 passed, 126 deselected in 1.49s`.
- Targeted disposable-copy counterfactuals cover pre-lock fencing, final managed
  sampling, final authentication, backward time, replay generation/receipt binding,
  incarnation, lifecycle closure, invented settlement success and unfenced replay.
  Removing custody linkage is caught by the existing final metadata consistency
  check before commit: this is explicitly a backstop, not an isolated link guard.
  The import-copy loader also installs in spawned child interpreters. Checkout
  source is never replaced to run a counterfactual.
- Test construction failures are retained in the packet: the initial text edit
  matched an old migration test, then was corrected by function scope and checked
  against the committed base; an unbound capture requires the specific conflict
  error; the request fixture requires a capture dictionary; import order was fixed.
  These were test/harness corrections, not source fixes or product-rule changes.
- The initial combined attempt was deliberately interrupted for the discovered
  lost-response instrumentation defect. Its partial pass is not a passing gate.
  The final combined lane passed: `3164 passed in 440.20s (0:07:20)`.
  Its input manifest matched after completion; test file SHA-256
  `85bfe4678c959066b7ef6f1ddacade48a3889701509fbed9fc7de14c89a50404`.
  Final Ruff: `All checks passed!`. The final counterfactual rerun killed all
  11 variants at the intended assertions, with no survivors or invalid probes.
  Durable `combined-final.json`, `combined-final-inputs.json`,
  `counterfactual-final/mutations/results.json`, `cold-diff-audit.json` and
  `manifest.json` retain commands, input pins, source-copy changes and publication
  identity. The work-order and executable commits are separate.

NOT DONE — local qualification passed. Exact-head Linux and native Windows CI,
independent oversight and connector reconciliation remain required before merge.
No installed receiver, production adoption, machine trust, retention-policy choice
or R3/R4/R5 completion is claimed.
