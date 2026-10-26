# R2: source-owned custody resolution and durable fences

Status: **ACCEPTED R2 work order; implementation has not started.**
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
workflow and documentation paths are repository-relative. This PR edits only
this document and the parent contract's status/continuation pointers.

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

- No executable edits in this PR. No new service, capability registration,
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
rerun unrelated broad matrices. No tests were run for this documentation-only PR.

## Implementation summary

This change adds the accepted R2 contract, its acceptance-only record and a
continuation pointer/status update in the parent contract. It changes no source,
schema, migration, test, dependency, workflow or application. API/table names above
describe authorized work, not implemented capabilities.

## Cold diff audit

- `docs/contracts/LEAD-CUSTODY-STORAGE.md`: inventory, source ownership, explicit
  migration, local operations, lifecycle and failure rules, parity/mutation plan
  and acceptance gates. Checked against the pinned source and historical packets.
- `docs/contracts/LEAD-RECEIVER-CUSTODY.md`: record R1 merge and link the canonical
  R2 acceptance; do not change the accepted R1 vocabulary or duplicate R2 rules.
- Verify only these Markdown paths differ; check links, citations, base/hash
  references and whitespace. Code tests are intentionally not rerun for prose.

## Gap audit

R2 design review and operator acceptance are recorded above. The acceptance-only
head still requires its own exact-head merge gates.
**NOT DONE:** migration/owner implementation, fail-first and parity proofs,
native implementation CI and exact-head implementation reviews.
R1 is complete. R3-R5 and protected-machine work remain separately gated. A
contract approval or local synthetic pass is not production receiver qualification.

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

Implementation and qualification are **NOT DONE** at this scope-record commit.
