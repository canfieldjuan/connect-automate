# Body-only receiver custody: work order and protocol proposal

Status: **PROPOSED; contract only.** Juan's instruction, “Let’s start the next product lane.”,
starts this work order. It does not accept its new technical
interfaces or authorize executable integration. No implementation, live mailbox,
protected service, migration or production activation is delivered by this change.

The accepted [application policy](LEAD-SOURCE-HANDOFF.md#current-acceptance-and-work-order-status)
remains authoritative: one business per deployment, receiver-owned raw custody,
reference-only Watcher retries, bounded retention and local admin/user roles.
The [protected-read prerequisites](LEAD-PROTECTED-READ.md#proof-sequence-and-acceptance-gates)
remain gates. Synthetic protocol work may proceed under its own accepted work
order while those prerequisites are unresolved; synthetic identities never qualify
an employee endpoint or real-mail intake.

## Contract

### Root cause and required change surface

The existing source and workflow libraries accept a signed envelope and preserve
receipts. They do not expose a production receiver that can reserve capture,
resolve a lost acknowledgement or resume from receiver-held bytes. Watcher's
existing automation admission and Connect job source are attachment-shaped.
Replaying that path with a fake attachment would bypass the true source owner;
adding another queue would duplicate the existing dispatch owner.

This PR changes only this document and the continuation pointer in
`LEAD-SOURCE-HANDOFF.md`. It specifies the product lane and the first bounded
executable work order below. Future owner changes are proposals, not capabilities
already present. No source pin, package, test input, runtime or schema changes here.

### Source inventory and reproducible baseline

**CONFIRMED by source inspection:**

- CA = `canfieldjuan/connect-automate`, main
  `1326fcfba45fa26235e1154c4a67f0a1b8638d5a`.
- EW = `canfieldjuan/eom-email-watcher`, main
  `1ca6307fc9f47b9db88c18f260301fc08e34a9c3`.
- CA paths below start at `src/connect_automate/`; EW paths start at
  `src/eom_email_watcher/`, except repository-relative `desktop/` and `tests/`.
  EW was read with `git show` at its pin; its working branch was not modified.

| Source | Verified responsibility and limit |
| --- | --- |
| CA `lead_intake/source.py:20-24,77-174` | Closed source vocabulary, full physical identity, body completeness/unavailable states, unprocessed attachments and signed retention. Envelope ceiling is 2097152 bytes; body ceiling is 200000 characters. |
| CA `lead_intake/source.py:257-269` | Canonical envelope bytes and payload digest have different owners/meanings. Preserve both; do not substitute one for the other. |
| CA `lead_intake/auth.py:53-110,151-185` | Source grant scopes include host/organization, namespace, mailbox and retention policy. They are not an employee sign-in or a route-specific machine control grant. |
| CA `lead_intake/admission.py:165-240` | Current source authentication, replay/conflict checks, content and receipt writes belong to the source transaction. |
| CA `lead_intake/source_store.py:62-121` | Receipt uniqueness is organization/namespace/event. Content, immutable receipt, purge horizon and namespace retirement have a source owner. A custody lookup/fence must extend that owner, not add wrapper SQL. |
| CA `lead_intake/content.py:75-98,124-166` | Content access applies expiry; purge is message/capture-cutoff scoped and retirement is namespace scoped. Reading content is not a query-only status operation. |
| CA `automate/runtime.py:282-394` | Public submit reauthenticates raw bytes; lookup returns historical metadata. No application prepare/status/resume receiver is implemented there. |
| CA `automate/host.py:70-89` | The executable entry point performs a license check; it is not the receiver service. |
| CA `connect.py:55-74,330-358,2040-2089` | Existing v2 transport accepts exactly one hashed artifact per job, typed scalar parameters, and opaque hashed output bytes. Parameter strings are limited to 1000 characters; capability versions have two numeric components. |
| CA `automate/store.py:76-79,822-823` | Action/effect serialization has a 16 KiB bound. Small input parameters alone do not protect against an oversized returned artifact. |
| EW `automation/rules.py:240-241,406-419`; `db.py:752-808` | Rules require attachment media type, fires are per attachment and SQL requires a real attachment row. Body intake requires a typed source extension at these owners. |
| EW `body_state.py:38-56,80-105,109-144`; `mime.py:184-188` | Body acquisition/storage is follow-scoped, normalization is bounded and cleanup can remove bodies. Intake eligibility must be a separate explicit reason, not an implicit follow or retained retry copy. |
| EW `db.py:361-388,520-555`; `engine_api.py:3703-3749,4554-4577`; `desktop/src-tauri/src/scheduler.rs:294-306` | Durable jobs, dispatch state, retries and an existing pump exist. Extend these owners; no second scheduler, poller or dispatch mechanism. |
| EW `engine_api.py:3938-4020` | The content callback executes under source locks and exact size/hash checks before dispatch. Existing source ownership must survive the body extension. |
| EW `engine_api.py:3145-3175`; `db.py:5482-5512` | Provider instance/version and invocation identity are pinned. Restart compatibility cannot be implemented by selecting a replacement provider. |
| EW `removal.py:187-235` | Durable removal requests contain physical target identities. Cross-application purge must extend this owner, preserving aliases and the original capture cutoff. |

Source snapshots and hashes are retained under durable alias
`lead-receiver-custody-contract`; source claims refer to these pins, not a moving
branch or installed application. Native installed behavior remains UNKNOWN here.

### Proven-work inventory and departures

Preserve the existing synthetic signed-source, fixed-clock, no-action-pack harness
in CA `tests/test_lead_joined_recovery.py:48-86,323-360`,
`tests/test_lead_joined_concurrency.py:98-105,144-179,237-264` and
`tests/test_lead_joined_lifecycle.py:165-220,232-343`. It uses real SQLite owners
and spawned processes. It proves library behavior, not receiver transport or a
live mailbox. No inference model, prompt or inference settings are involved.

Historical evidence, inspected but **not rerun** in this documentation slice:

| Durable alias | Manifest SHA-256 | Recorded result |
| --- | --- | --- |
| `lead-joined-crash-proof` | `be6732665a3261d87111870fe1f9300288d17b4c40c2054bfe36add364d13d41` | `recovery.txt`: 14 passed; later harness repairs remain part of current pinned source, not retroactively part of this original run. |
| `lead-joined-concurrency` | `88fc6b135ff87bdeb6b6e1062b6cae6f1b4da5d4c7e583b626914e292837de4c` | `joined.txt`: 23 passed. |
| `lead-joined-lifecycle` | `65a09c227f94d13d0ac69378b3da0e26529929c3a8cdaaba872ec766b0cc2546` | `joined.txt`: 44 passed. |

Every proposed departure has a specific reason and requires new evidence:

1. Direct caller-held envelope becomes receiver-held custody plus reference retry:
   remove the envelope from the recovering caller and recover through owner APIs.
2. A function call becomes an existing Connect v2 invocation: prove exact request,
   artifact, principal and provider binding, including response loss and restart.
3. Attachment fire becomes a typed body fire: preserve all existing attachment
   fixtures; prove unfollowed eligibility, unavailable and truncated content.
4. Deterministic test authority becomes current protected machine authority:
   synthetic fixtures prove schema/policy only; native installation, enrollment
   and current-grant enforcement require their own accepted integration proof.
5. A no-action pack remains the first vertical proof. General action results belong
   to [Contracts issue 76](https://github.com/canfieldjuan/connect-contracts/issues/76)
   and the pack-kit lane. Do not copy its projection or edit its reserved owners.

Before each executable slice, pin the then-current base, compare these inputs and
rerun the relevant existing parity lane unchanged before altering behavior.

## Ownership and identifiers

| Owner | Owns | Forbidden shortcut |
| --- | --- | --- |
| Watcher | Sender/rule admission, physical message aliases, body capture, reference-only intent/recovery metadata and scheduling | Body spool, fake attachment, second queue/poller, reading receiver tables |
| Lead Intake source owner | Signed raw custody, keyed receipt resolution, source write fences, purge/expiry | Provider wrapper SQL, copied receipt as submission authority |
| Receiver adapter | Connect request/result mapping, durable control-operation mapping, readiness/quota reservations | New workflow engine, canonical leads, independent retry scheduler |
| Automate | Workflow transaction, event/action identity and historical outcome | Treating custody as a lead or delivery result |
| Protected host | Installed receiver identity, machine enrollment/route authorization, secret custody | Caller-supplied actor facts or native PID as authentication |

**PROPOSED invariant:** a stable `handoff_id` identifies one capture intent, not a
person/contact or destination delivery. Bind it once to host, organization, source
namespace, full `SourceIdentity`, Watcher event digest, rule/version, source event
UUID, retention policy and a pinned route. A route names provider app/instance,
capability/version, pack ID/version and binding; its canonical digest is immutable.
An ordinary update cannot reassign organization, principal, route or source.
The receiver intent owner enforces uniqueness of organization/namespace/source
event as well as handoff ID. A conflicting second route/intent is refused; no
implicit fan-out or adoption of an unrelated pre-existing receipt is introduced.

Transport `job_id` identifies one immutable Connect operation. Prepare, upload,
status, resume and settlement have distinct persisted operation IDs under the
same handoff; retries of one operation reuse its ID and exact request. A later
status observation may have a new control-operation ID, never a new source event
or upload identity to hide uncertainty. Record this mapping in the existing
Watcher queue's typed extension, with no second dispatcher.

After capture, atomically attach `envelope_sha256`, `payload_digest`, snapshot ID,
capture time, signed recovery deadline and artifact size to the original intent
before any upload. Both digests are mandatory. The receiver verifies them against
the exact canonical artifact and binds them once. Equal payload with a different
signature/envelope is not an overwrite of this job. A newly authorized control
credential may inspect the same machine's history; it may not re-sign retained
source bytes or change the upload fingerprint.

## Proposed application contract

All names and schemas in this section are **PROPOSED / NOT IMPLEMENTED**.
Use one v2 capability, `lead.source.custody`, capability version `1.0`, over the
existing loopback POST/GET job transport. Do not add custom transport endpoints.
Each operation has one input artifact; no missing-input exception is needed.

| Operation | Input artifact | Effect and result |
| --- | --- | --- |
| `prepare` | Versioned metadata-only intent/control JSON | Authenticates route/principal, pins intent and reserves bounded capacity; returns readiness and fence generation. No body fetch or custody acknowledgement. |
| `upload` | Exact canonical signed source envelope | Validates the pinned capture pair, current authority and active generation; source owner commits custody. Never persists another raw copy in adapter job state. |
| `status` | Versioned metadata-only reference/control JSON | Reports current historical workflow/custody evidence without reading bodies, dispatching actions, advancing the source clock or purging. |
| `resume` | Versioned metadata-only reference/control JSON | Resolves receiver custody, reads retained bytes through its owner, calls full `PackRuntime.submit_source` with fresh source authentication. No mailbox reread. |
| `settle` | Versioned metadata-only reference/control JSON | Closes the upload generation, fences all prior writers, then resolves absence/custody. This distinct mutation is necessary; a status read must not silently cancel an upload. |

Control JSON has a closed schema, `schema_version="1.0"`, operation, handoff and
control IDs, host/organization, enrolled machine reference, source and route
references, expected fence generation, and operation-specific payload. Unknown
keys/versions, null substitution, boolean-as-integer and incomplete digest pairs
fail closed. Status before capture identifies the pinned intent without inventing
digests; status after capture requires the entire capture pair. Only prepare may
create an intent. A missing job/receipt is not permission to recreate one.

Control artifacts use `application/vnd.local-connect.lead-custody-control+json`;
upload uses `application/vnd.local-connect.lead-source+json`. Its scalar parameters
carry operation and bounded reference/control authentication fields, never a body,
serialized envelope or oversized JSON string. All must fit the existing parameter
limits, including the parameter-count limit. The source artifact/schema stays
unchanged. A receiver-authenticated route binding must cover the operation,
handoff, transport job and artifact identity, complete capture pair and generation;
the existing source signature alone does not bind all these transport fields.

**UNKNOWN / integration gate:** the protected machine enrollment and control-proof
wire format are not implemented or qualified by the current source grant. Pin
credential scope, proof freshness, replay rules, signature/domain separation,
key rotation and authenticated GET-result access in the machine-boundary work
order before wiring a real provider. A registry bearer token is transport access,
not proof of organization/route permission. In-process fixture facts may exercise
the protocol models only; they must not be accepted as live authentication.
No broadening of the existing source-key grant is implied here.

Return one closed result artifact,
`application/vnd.local-connect.lead-custody-result+json`, version `1.0`, bounded to
4096 UTF-8 bytes. Require the complete wrapped/encoded result to fit the existing
action serialization limit too. Before a side effect, validate the result shape
and worst-case bounds; a serialization failure afterwards is uncertain outcome,
never proof that custody or workflow admission failed. Oversize is an explicit
error, not truncation. Results contain opaque references, enums and timestamps;
no body, subject, sender address, narrative, secret, path or free-form exception.

### Independent states and current-authority rules

Results are a closed union. A `resolved` result contains handoff ID, state revision,
fence generation and the fields below. An `unresolved` result contains only the
handoff reference and a fixed `unknown`, `not_found`, `refused` or `conflict` code;
it contains no invented phase, receipt, generation or workflow projection.
`not_found` is an authorized observation of missing intent metadata, never proof
that source bytes were not committed. Authentication refusal reveals no existence
information. R1 represents these values, not the authority to assert them.
Resolved results also carry `observed_at` and a bounded scope reference containing
host/organization/namespace/event IDs and route digest. Capture metadata contains
both digests, snapshot ID, capture time, recovery deadline and artifact size as
one optional closed value: required after upload is possible, absent in prepared,
absent in fenced-empty only if no capture pair was ever pinned, never partially
populated or discarded on settlement. Prepared results include a
reservation expiry; a cached readiness result cannot extend it. Unresolved replies
never erase a previously recorded custody/workflow fact.

- `capture_phase`: `prepared`, `upload_possible`, `custodied`, `fenced_empty`.
- `content_state`: `not_received`, `retained`, `unavailable`, `unknown`.
  `unavailable` has a bounded reason: `expired`, `purged`, `retired`, `lost`.
- `workflow`: null when not resolved, otherwise the existing validated historical
  lookup projection. Preserve `not_found`, `no_match` and `accepted` meanings.
- `source_receipt`: the existing validated `ReceiptReference`, required exactly
  when capture phase is `custodied`; null otherwise. It is independent of an absent
  workflow receipt and never authorizes resume by itself.
- `reason`: `ready`, `pending`, `custody_confirmed`, `workflow_known`,
  `capture_lost`, `capture_cancelled` or `content_unavailable`. Absence of a
  projection never means success.

Legal combinations are closed as follows; any unlisted combination is rejected:

| Capture phase | Content state | Workflow field | Reason |
| --- | --- | --- | --- |
| `prepared` | `not_received` | null | `ready` |
| `upload_possible` | `unknown` | null | `pending` |
| `custodied` | `retained` | null or validated `not_found` projection | `custody_confirmed` |
| `custodied` | `unavailable` plus unavailable reason | null or validated `not_found` projection | `content_unavailable` |
| `custodied` | `retained`, `unavailable` plus reason, or `unknown` | validated `accepted` or `no_match` projection | `workflow_known` |
| `fenced_empty` | `not_received` | null | `capture_lost` or `capture_cancelled` |

Every embedded source receipt must match the result's pinned scope/event/digest;
historical workflow proof does not imply retained raw bytes. `prepared` means no
upload has been admitted; `upload_possible` means a
writer may still commit, including after a lost response. Only source-owner proof
of a committed receipt permits `custodied`. Once established, that historical
fact survives raw purge and workflow-record advancement. `fenced_empty` requires
closed admission plus a post-fence source lookup proving no commit. It cannot
coexist with a source receipt or known workflow outcome. Conflict/refusal does
not erase an earlier committed outcome. Disk/metadata corruption or loss yields
unknown, not `fenced_empty` inferred from an empty replacement database.

Transport completion says the requested operation completed, not that a lead or
external delivery exists. Source custody and workflow outcome are independent.
Known action failure/pending/uncertainty must follow the pack-kit-owned result
contract when merged and re-pinned. Until then, qualify only a no-action pack;
do not claim general workflow-effect completeness or close issue 76 here.
Every result is a snapshot at its observation time. Replaying an immutable status
operation may return its original snapshot; a new authorized status operation is
needed for a new observation. Even delivery of a cached transport result must
recheck current machine access. Prior readiness never overrides a closed or expired
generation when upload finally reaches the source owner.

Historical status requires current authorized machine/route access but not a
still-valid original source signing key. Resume requires both current machine
authorization and fresh authentication of the original retained envelope. An
expired/revoked original key cannot be repaired by re-signing or a cached receipt.
Each operation rechecks authority at its owner's critical point, including waits;
never infer continued authorization from a previously returned result.

## Storage, recovery and fencing requirements

The receiver's durable intent/operation mapping contains metadata only. Logical
ownership is explicit even if it shares the source SQLite deployment. Source
receipt/content queries and writes remain inside the source owner; workflow
queries remain inside its owner. Adapter code does not issue SQL to either.
The exact migration and table placement belong to a subsequent storage work order.

New source-owned seams are needed for exact scoped custody lookup (including the
envelope hash after bytes are purged) and upload fencing. Lookup is keyed by the
complete organization/namespace/event reference and compares pinned metadata;
it is not a scan, body read or submission from a cached receipt.

**PROPOSED fence invariant:** every upload transaction must check the durable job
generation/closed state under the same source writer that commits custody. A
wrapper check before acquiring that writer is insufficient. Settlement closes
admission under that writer before establishing absence; transactions that won
before closure are observed, and old workers that arrive afterwards are refused.
Per-process locks, elapsed time, PID existence or an in-memory provider cache are
not a durable fence. Concurrent settlement is idempotent. No expiry of a lease
alone authorizes a second unfenced writer or an "unrecoverable" response.
Every new receiver path, including recovery/resume, must use the fenced owner
boundary. The existing unfenced library entry cannot be exposed as an alternate
provider route. Preserve its library parity without making it a production bypass.
Closure forbids first custody creation. Where custody already committed, the same
owner may permit exact authenticated replay of that existing receipt for workflow
resume; it must verify the pinned envelope/digest and current lifecycle under the
writer and must not insert/recreate content. This distinction prevents settlement
from either reviving bytes or making already-durable custody impossible to resume.

Prepare reserves capacity before Watcher captures; its reply is not durable raw
custody. Reservation expiry/finalization must obey the same fence, never evict a
committed unresolved source. Persist the active generation and exact request
fingerprints before accepting an upload. If a source commit beats job-mapping
publication, recover by the keyed source-owned lookup. Source and workflow commits
remain separate: neither receipt is manufactured to bridge their crash gap.

Recovery always checks historical workflow metadata first using the persisted
`payload_digest`. If no workflow outcome exists, resolve exact source custody.
If valid retained custody exists, an authorized resume calls the complete submit
path. If no custody is visible while any old upload may commit, remain pending or
unknown. If transient bytes are lost and settlement establishes `fenced_empty`,
report terminal pre-custody loss. No automatic recapture, fresh source event ID,
provider substitution or mailbox reread may disguise it. Explicit recapture is a
separate future product work order, with linked provenance.

Purge carries the authenticated full physical message scope and the original
capture cutoff, not one event ID. It fences matching pre-custody work as well as
purging committed content through the existing owner. Later captures survive a
late deletion. Watcher resolves aliases through its existing removal owner;
local removal does not claim downstream deletion while the receiver is offline.
No reset/restart/restore may erase the fence and revive an older capture.

## Privacy, installation and availability gates

Preserve the accepted raw and metadata windows in the parent policy. This document
does not reset their clocks or authorize weakening immutable receipts. Metadata
expiry, redacted-history semantics, owner exports/restore and raw-free backups
need their own source-grounded work order before deployment. Pending controls,
operation mappings, fences and reservations also need bounded retention; deleting
them must not re-enable replay while a signed request could remain eligible.

No raw intake bytes in Watcher durable jobs, parameter JSON, spool, logs, telemetry
or crash dumps. Ordinary body-view storage remains independently governed and
cannot be pinned as an intake retry cache. Receiver transient ingress, SQLite/WAL,
swap and dumps need native privacy qualification. The service enforces configured
quota and readiness without silent eviction. Numeric capacity/concurrency and
control-metadata budgets are **UNKNOWN deployment inputs**, not unlimited defaults;
their exact bounds and exhaustion behavior must be pinned before the provider slice.

Same protected installation/store must preserve enrolled provider identity across
restart, with exclusive ownership and qualified registry publication. A replacement
installation or lost mapping fails closed and requires explicit recovery/enrollment.
Current provider app-version pinning also needs an upgrade/reconciliation proof;
an app upgrade must not silently reinterpret the original request fingerprint.

Native evidence already rejects same-user GNOME/logind hints as sufficient lock
authority, Windows pipe-opener PID as per-message program attestation, and Linux
name/UID as account incarnation. Manual console observation does not fix those
limits. The existing protected-host lane retains them; no production provider,
employee source read or live mailbox activation is authorized by this work order.
These are historical bounded findings in durable aliases
`native-host-feasibility/native-session-binding` (manifest
`ea7223003022f5a4383a9e9579be000d3444093eeeef2336155a113ca49c74e9`)
and `native-host-feasibility/inherited-pipe-identity` (manifest
`7ec82f716900e86963873f7982c3dfbe48ac73d0595dbcb472394c1e93e039d7`).
No native proof was rerun in this proposal.

## Bounded implementation sequence and verification

Each slice requires its contract committed first, explicit acceptance before its
executable work, incremental proof and native Windows/Linux CI from the first
executable push. Re-pin any changed dependency before implementation. Oversight
and Codex connector review remain required; docs acceptance is not adoption.

| Slice | Smallest owner change | Required gate/evidence and rollback |
| --- | --- | --- |
| R1: pure protocol vocabulary | New private `lead_intake/custody_protocol.py` and focused tests; existing source scalar/schema validators reused | G0 prerequisite only. Closed metadata/result schemas, legal state combinations, digest distinctions and bounds. No I/O or public wiring. Rollback removes unused vocabulary. |
| R2: source-owned custody resolution and fence | Source store/admission owners, explicit migration contract; adapter metadata owner specified first | G1/G3 prerequisites. Exact lookup after purge, atomic generation check, both settlement/write orders, restart, lost mapping and every partial-write boundary. Rollback disables new ingress and preserves stores; no downgrade that ignores fences. |
| R3: receiver protocol composition | Thin adapter over qualified owners and existing Connect transport | G1/G3 prerequisites with synthetic source fixtures. Prepare/upload/status/resume/settle, exact route identity, no-action pack, loss/restart/quotas/result bounds. Real authentication/service wiring blocked on accepted and proven protected machine boundary. Disable capability; keep authenticated recovery available where qualified. |
| R4: Watcher body source and reference retry | Existing rules, source/body/removal owners, job schema and queue pump | G1/G3. Body-only unfollowed capture without follow mutation, unavailable/truncated input, reference-only restart, stable IDs, both digests and no attachment regression. Disable new lead rules; preserve reconciliation records. |
| R5: cross-app retention and installed proof | Each storage/removal owner; protected installation | G6 prerequisite. Offline purge, capture cutoff, metadata retention, raw-free backup/restore, current authorization, packaged native parity. No production activation until these and protected-host gates pass. |

### First executable work order: R1 only

Required surface after acceptance: strict private request/result **value models**
and synthetic round-trip/rejection fixtures. Reuse source identity/time/digest
validation rather than copying it. Values are untrusted; no constructor or parser
returns an authenticated principal, readiness grant or permission to read/write.
The model must represent missing capture metadata honestly and reject partial
digest pairs, mismatched operation variants and illegal state combinations.

R1 must not implement control signatures, secret custody, enrollment, SQL,
provider handlers, dispatch, source writes, public exports or a new trusted-facts
shortcut. Transport authentication fields remain an opaque, bounded untrusted
proof reference until the separately accepted machine-boundary contract pins
their wire format; R1 is not the final wire conformance or full G0 acceptance.
No edit to pack-kit's `results.py`, submit/lookup projection hunks, event-action
snapshot seam or its result tests is included. General action-status work is
consumed only after that lane lands and is explicitly re-pinned.

Verification plan for R1: baseline source/schema and result tests unchanged;
fail-first absent model/invalid-combination cases; valid empty-body/unavailable
reference cases; extra keys, missing keys, wrong versions/types and mixed digests;
zero/false/empty/null limits; boundary sizes on UTF-8 and encoded results; no body
or input-derived error leakage; no side effects/import-time filesystem access.
Tests must identify the rejecting guard and counterfactual mutation, not merely
fail at an earlier validator. No claim of signature verification or durability.

### Application qualification fixtures reserved for later slices

Reuse the existing joined harness; preserve current test functions and add public
receiver/queue boundary fixtures rather than a competing recovery simulator:

- Crash before intent commit, before/after digest-pair persistence, before/after
  source commit, before job-to-receipt mapping, before/after workflow commit and
  after response loss. Recover without a caller copy of the original envelope.
- Two processes: same operation replay, conflicting signed payload, multiple
  events for one message, source-key rotation, receiver restart and competing
  settle/upload. Prove old writers cannot commit after terminal absence.
- Status after purge/expiry/revocation with body reads, source writes and action
  dispatch forbidden. Missing payload digest, envelope-as-payload digest and mixed
  pairs cannot become false not-found or accepted outcomes.
- Copied receipt, forged actor/route, wrong organization, expired or revoked
  control authority, valid control with stale source signature and version drift.
- Incomplete ingress, disk full, reservation exhaustion, bounded cancellation,
  oversize output and corrupt/missing job metadata yield classified outcomes.
- Body-only source with no follow; complete/truncated/unknown/unavailable body;
  attachments explicitly unprocessed; malicious mail text remains inert data.
- Message-wide purge over every alias/event, both late-upload orders and later
  captures. An event-scoped purge mutant must fail the intended assertion.

## Implementation summary, cold audit and gap audit

Implementation summary: this proposal plus one parent continuation link only.
No executable change, new dependency, fixture mutation, service, mailbox read,
database operation, runtime test or production activation in this PR.

Cold audit requirements: check every source citation against the pins, preserve
the accepted policies, compare changed paths with the declared surface, validate
relative links and whitespace, and inspect the complete final diff. Historical
result inventory is provenance, not a fresh test result. Publish durable evidence
by alias and SHA-256, never private workstation names or session-ledger links.

**NOT DONE:** exact-head contract reviews and Juan's technical work-order acceptance;
R1 implementation/proof; machine control authentication and transport mapping;
source-owned fencing/migration; receiver and Watcher integration; retention,
installed native/privacy qualification and product adoption. Extraction, canonical
lead records, Lead Inbox, employee approval, CRM/export delivery and EOM changes
are separate later product lanes. This proposal does not close their gates.
