# Licensing sales/grant register and issuance-binding specification

Status: **PROPOSED; CONTRACT ONLY; NOT READY FOR EXECUTION.**
Juan authorized this proposal and review submission after accepting the
[US verification work order](LEAD-OWNER-US-VERIFICATION.md). This revision needs
independent oversight and Juan's exact-revision acceptance. It does not implement
a register, qualify a business, issue a licence, approve recovery or lift a hold.
Native sign-in, Hello, Gmail and live activation remain on hold.

## Problem, inventory and ownership

The US work order lists association facts but leaves their record system and
transaction owner unspecified. A provider customer ID, payment, email address or
opaque licence subject cannot establish a verified business-to-deployment link.

| Inspected revision/owner | Existing evidence and limit |
| --- | --- |
| Connect Automate main `26dd639a743c9f6a82e87a69c39e8228ab3463cd`, accepted US and enrollment contracts | Proposed journal and evidence workflow; no selected operating register or executable wire schema. |
| Same pin, `qualification/owner_authority/protocol.py`, `OwnerClaim`, `ConsumeBinding`, `RecoveryEvidenceCase.relations` | Existing closed UUID/digest models and original organization/entitlement relation across recovery. Synthetic evidence cannot claim native qualification. |
| Same pin, `qualification/owner_authority/licensing_fixture.py`, `transaction`, `ISSUER_SQL`, `connect_store` | Disposable SQLite fixture: writer transaction, unique consumption, preserved journal and restored-store lock. Not a PostgreSQL service, real business registry or production continuity proof. |
| `local-connect-licensing` fetched main `c7ac955674b680f04c2ebbcdc4806682f707f81d` | README only. No sales/grant registry to adopt as implemented. Its proposed service contract remains a separate adoption decision. |
| `connect-contracts` inventory pinned by the accepted US work order at `07cc315b97772f6eb182dcd2cda6fc8ffde707cb` | Entitlement-v1 format and fresh ID per issuance; no business identity semantics. No format or issuer changes proposed here. |

Propose **the licensing sales/grant register as the system of record for what
licensing authorized and issued**, with Juan as its accountable operating owner.
This additional appointment is proposed; his existing enrollment-record ownership
does not silently appoint him to licensing operations. One person may hold both
roles. Licensing must adopt the writer and access roles before operation.

For a sale, independently retrieved order/payment records supply commercial
provenance. For an authorized non-sale grant, licensing's attributable grant
decision is the commercial source; no fictitious purchase is required. Neither
source establishes the recipient's identity or current business authority.
The independent enrollment decision supplies those separate facts.

No external sales system has been confirmed. The provider designated in private
invoice-processor issue 94 remains the proposed sale-source integration; its
brand and terms stay private. This proposal does not claim an account, inspect
customer data or select new commercial terms. Before recording a real sale, name
and qualify that actual source and its authenticity/current-status adapter. A
manual sales row with no independent provenance cannot fill the gap. A real
grant can use the grant branch without first installing a payment integration.

## Recommended backing store and boundaries

Propose a dedicated private PostgreSQL namespace, `licensing_register`, on
Supabase as the backing store. This advances the earlier candidate to a concrete
recommendation for acceptance; no account, project, region, tier or spending is
authorized. [Supabase supplies PostgreSQL](https://supabase.com/docs/guides/database/overview).
Use its database constraints and transactions, rather than an editable spreadsheet
or a new custom database framework. Later work must pin the actual supported
database version and qualify the selected service configuration.

All mutations use the register transaction owner, through separately authorized
licensing commands or enrollment-owner commands. Neither application role gets
general table-write permission; journal append is part of the same owner transaction.
Customers cannot insert assertions directly. Authenticated actor and business
scope are derived at the canonical administrator boundary, never from request
fields. Business-side applicants do not obtain licensing-operator permissions.
An owner may not verify their own business authority by holding the register.

Identity/contact details, documents and free-form verification notes stay in the
external enrollment store. Only opaque references and bounded decision facts
cross into this namespace. The existing licence-service proposal is not amended
to accept extra records by this document: deployment may use a separate licensing
register component until that owner explicitly adopts its schema/API.

Keep authoritative opaque enrollment-head metadata in the same PostgreSQL
transaction domain as the journal, under an enrollment-owner writer role. This
is a proposed placement for decision ordering, not moving identity documents
into licensing or allowing licensing to mint enrollment evidence. The enrollment
owner controls head transitions; licensing can lock/read them but cannot invent
an active revision. Private source objects remain outside this transaction.

## Logical records and closed branches

These are requirements for a later closed schema, **not executable schemas**.
Reuse UUIDv4 identifiers, SHA-256 digests and UTC instants from the existing
protocol owners. New references are opaque UUIDv4 values, not URLs to fetch,
email addresses, document names or payment credentials. Private source adapters
map them to their actual external records. Revisions are strict positive integers;
booleans, strings and missing values cannot default into a valid revision.
Every record is bound to its register ID, schema revision and operating epoch.

| Record | Exact logical fields and owner constraints |
| --- | --- |
| Register control | `register_id`, `schema_revision`, `epoch`, `mode` (`ACTIVE` or `LOCKED`), `last_sequence`, `last_event_digest`. A restored/unreconciled instance is locked. `last_sequence=0` is valid only for explicitly created empty storage, not a fallback for a missing row. |
| Commercial revision | `commercial_id`, `revision`, `organization_id`, `basis`, `state` (`AUTHORIZED` or `WITHDRAWN`), `provenance_ref`, `provenance_revision`, `actor_ref`, `recorded_at`, `reason_code`. `basis=SALE` requires `sale_source_ref`, `sale_record_ref`, `sale_record_revision`, `source_observation_ref`; `basis=GRANT` instead requires `grant_decision_ref`, `grant_policy_revision`. Branch-exclusive fields cannot coexist or be silently ignored. No prices or personal data in this public contract or record shape. |
| Issuance | `entitlement_id`, `commercial_id`, `commercial_revision`, `organization_id`, `issuance_operation_id`, `envelope_ref`, `envelope_sha256`, `issuer_key_id`, `issued_at`. Unique entitlement ID and issuance operation; exact envelope identity must be validated by the authoritative issuer adapter. Issuance registration records an already-issued licence; it does not sign or issue one. |
| Enrollment head | `enrollment_ref`, `organization_id`, `revision`, `state` (`PENDING`, `CURRENT`, `WITHDRAWN`, `UNAVAILABLE`), `change_id`, `reason_code`. `CURRENT` additionally requires `decision_ref`, `decision_sha256`, `method_revision`, `registration_ref`, `authority_expires_at`, and a source-dependency branch below. Only the enrollment-owner role writes it. Canonical independent evidence and completed bound registration are required; this does not mean recovery is approved. Non-current branches carry a closed reason rather than invented completed-proof references. |
| Association revision | `association_id`, `revision`, `entitlement_id`, `organization_id`, `enrollment_ref`, `enrollment_revision`, `commercial_id`, `commercial_revision`, `verification_ref`, `verification_sha256`, `state` (`RECORDED` or `WITHDRAWN`), `actor_ref`, `recorded_at`, `reason_code`. Verification provenance explains the business-to-issuance link; a shared organization ID alone does not prove it. The first revision fixes the entitlement and original organization; later revisions preserve history. |
| Consumption link | `association_id`, `original_claim_id`, `consumed_operation_id`, `organization_id`, `entitlement_id`, `binding_sha256`, `receipt_ref`, `receipt_sha256`, `observed_at`. Copied only from the authoritative consumed binding and validated receipt. Unique original claim and consumed operation; one link per original association. Missing link means pending association to consumption, not proven unconsumed. |
| Operation result | `operation_id`, `command`, `actor_ref`, `business_scope`, `request_sha256`, `result_kind`, `result_ref`, `result_sha256`, `committed_sequence`. Unique operation ID across this register. The digest covers the canonical command and all fields, including expected revisions and actor/scope. No raw request or private text in audit. |
| Journal event | `sequence`, `epoch`, `operation_id`, `event_kind`, `record_ref`, `record_revision`, `previous_event_digest`, `event_digest`, `actor_ref`, `recorded_at`. Unique sequence and operation linkage; immutable history for successful mutations. Head rows point to retained revisions, not replacements for them. |

For enrollment-head variants, the later discriminated schema must put completed
proof fields only in `CURRENT`; pending/withdrawn/unavailable carry `change_id`,
reason and last-decision references where actually present. No absent-proof
sentinels, optional-everything model or caller-supplied `verified=true` flag.
The source-dependency branch is `REFERENCE_ONLY` with qualified method/source
references, or `RETAINED_REQUIRED` with those references plus
`required_source_expires_at` derived from the earliest expiry of a copy actually
needed for that decision. No invented TTL or default expiry is introduced. A
writer samples its authoritative UTC clock after lock waits and again before
the mutation, rather than reusing the transaction-start time, against both canonical
authority expiry and any required-source expiry; equality is expired even if a
cleanup worker has not run. Reference-only does not waive source-currentness checks.

Use a closed reason vocabulary: `INITIAL`, `SOURCE_UPDATED`, `SOURCE_UNAVAILABLE`,
`SOURCE_EXPIRED`, `AUTHORITY_WITHDRAWN`, `REGISTRATION_PENDING`,
`COMMERCIAL_WITHDRAWAL`, `RECORD_CORRECTION`, `RESTORE_RECONCILIATION`.
Commands restrict reasons to their applicable branch; no free-text reason can
smuggle identity data into the journal. Journal event kinds are the closed mutation
command names below, not arbitrary caller strings.

Primary/foreign keys and unique constraints bind each relation to the same
organization, entitlement and retained revision. One named writer validator owns
cross-record semantics the schema cannot express; no second string parser or
name/email join. A business may have multiple commercial records and entitlements.
One current association head per entitlement prevents conflicting concurrent
ownership; historical revisions remain. This is not a one-licence-per-business cap.
One stable `(sale_source_ref, sale_record_ref)` maps to one commercial record;
source revisions update its history. Multiple entitlements can reference that
record. The private adapter must preserve that mapping across delivery/retry and
authenticate source observations; minting a new opaque reference on each delivery
cannot evade duplicate detection. A provider's record granularity is specified in
its private profile, not inferred from a customer name or a single payment amount.

## Command and result contract

Every command has `version=licensing-register/1`, `command`, `operation_id`,
`register_id`, `expected_epoch`, and a command-specific closed body. Actor and
scope are server-derived. Creation has an explicit create branch with no expected
prior revision; updates require the exact positive `expected_revision` and exact
referenced enrollment/commercial revisions. Empty, zero or missing revision cannot
mean "latest". This is a service-boundary proposal, not a public endpoint or UI.

| Command | Preconditions and atomic result |
| --- | --- |
| `record_sale` / `record_grant` | Authorized licensing actor; independently authenticated sale observation or attributable authorized grant decision under the adopted grant policy. Create the commercial revision and journal event. A provider event delivered twice maps to the same source observation; conflicting duplicate contents require reconciliation, not another authorization. Neither command verifies identity. |
| `revise_commercial` | Exact expected head, same commercial ID/business/basis and fresh authenticated source or grant decision under the adopted policy. Append a revision without altering historical issuance. A legitimate correction may restore `AUTHORIZED` only from that new evidence; a delayed old event cannot. Changing the business or sale/grant basis is not this command. |
| `register_issuance` | Issuer-proven envelope/issuance identity and matching commercial organization/revision. Register the exact entitlement and envelope. An earlier genuine issuance may be recorded after commercial withdrawal as history, but that cannot enable a new association; absent historical proof is unresolved, not newly fabricated issuance. |
| `record_association` | Lock/check current commercial and enrollment heads, issuer identity, exact organization/entitlement relation and independent association decision. Create a `RECORDED` revision bound to those inputs. This is evidence recorded only, never an approval token. |
| `attach_consumption` | Validate the authoritative binding/receipt against the original issuance and association. Insert the immutable consumption link; exact duplicate is a replay. An already-consumed deployment may be recorded even after withdrawal to preserve history; recording it grants no new authority. Missing or contradictory required consumption evidence is STOP. |
| `correct_association` | Authenticated, independently evidenced correction, exact expected head and current supporting revisions. Append a revision; retain all prior decisions and consumption. It may correct the representative/enrollment reference for the same verified business. It cannot silently change original organization/entitlement or move consumed authority. A true business transfer needs a separate accepted policy. |
| `withdraw_commercial` / `withdraw_association` | Authorized owner and exact expected revision. Append the withdrawn revision and advance its head. Existing issuance and consumption remain historical facts. No implicit refund, licence reissuance, host retirement or reinstatement. A mistaken withdrawal can be corrected only by a new evidenced revision, never erasure. |
| Enrollment-owner `begin_change` / `finish_change` | Use the ordering below. Licensing cannot call these as an enrollment verifier merely because it owns the register. |

Successful result variants are `RECORDED` or `REPLAY`, carrying operation ID,
committed sequence, immutable record/revision references and result digest.
They carry no authorization signature, host permission or `approved` field.
Replay describes the old committed result, **not current eligibility**. Consumers
must query/revalidate current referenced heads for a new decision.

Refusal variants are `INPUT_INVALID`, `UNAUTHORIZED`, `REVISION_CONFLICT`,
`BINDING_CONFLICT`, `SOURCE_UNAVAILABLE`, or `AUTHORITY_NOT_CURRENT`; none mutates
domain history or creates a successful operation result. Separate STOP results
are `HISTORY_CORRUPT` and `REGISTER_LOCKED`; missing tables, required revisions,
stored envelopes or established consumption cannot be reinterpreted as ordinary
unavailability or fresh creation. Transient database errors report no committed
success until the operation is resolved against authoritative storage.

## Writer, retries and withdrawal ordering

Use a PostgreSQL transaction for each register mutation. The writer locks the
register control row first, then relevant head rows in stable identifier order,
and reads current values after acquiring locks. The control-row lock serializes
the journal sequence and gives this initial low-volume manual register one clear
order. It is not held while a person verifies evidence or while making network
calls. [PostgreSQL row locks](https://www.postgresql.org/docs/current/explicit-locking.html)
last through the transaction; a read outside that transaction is not the check.

Within the transaction: verify owner/schema/epoch/mode and required history;
resolve operation replay against the canonical digest and actor/scope; lock and
check current input heads; validate relations; write revision, head, journal and
operation result together. Commit before returning bytes. A crash before commit
leaves none of these effects; a lost reply after commit is an exact retry.
A reused operation ID with changed content or actor/scope conflicts. Authentication
and scope checks still precede a replay response; replay is not a bypass for a
revoked caller. Database permission separation must prevent direct application
updates that skip this owner. Privileged maintenance is a separately fenced activity.
Check effective expiry in the locked writer snapshot, not just the stored state
label or a pre-lock timestamp. A transaction that waited past expiry cannot commit
an affirmative association using the earlier time.

If a referenced withdrawal commits first, an association writer observes it and
refuses. If the association commits first, withdrawal still makes its historical
result unusable for a later approval. The future approval writer must lock and
revalidate these same heads in its authorization transaction; this work order
does not implement that consumer or permit approval from a cached result.
An out-of-order provider event cannot restore a commercial head: the source adapter
must retrieve/validate authoritative current state and apply an expected-revision
update, or leave it unresolved. Automatic commercial-policy decisions remain in
the private licensing owner; this document does not invent refund/grant rules.

### External enrollment evidence and source changes

The enrollment head is the authoritative eligibility pointer for register
decisions, not an asynchronously updated cache of mutable private records.
The enrollment owner performs every authority/required-source change as follows:

1. Commit `begin_change` with a unique change ID and expected head. Advance the
   head revision to non-current (`PENDING`, `WITHDRAWN` or `UNAVAILABLE` as appropriate)
   before changing the private evidence revision or allowing required-source deletion.
   Withdrawals become effective at this commit; acknowledge effectiveness only then.
2. Perform the private-store operation with that same change ID and an immutable
   evidence/registration revision. On failure or lost response, retain non-current
   state; retry/reconcile the existing change, never fabricate a finished decision.
3. `finish_change` can publish a new `CURRENT` head only from the matching pending
   revision and after validating the canonical evidence, registration and exact
   private-store revision/digest. It cannot finish over a newer withdrawal/change.
   A completed withdrawal remains withdrawn; making it current again requires a
   separately evidenced change, not replay of its former finish operation.

Optional raw-copy deletion that does not invalidate required evidence follows
canonical retention without unnecessarily suspending valid authority. When it
does remove required evidence, fence first and keep the head unavailable until
qualified independent evidence replaces it. Expiry is already recorded in the
CURRENT dependency branch, so a failed cleanup/fence cannot extend eligibility.
A change shortening required-source retention must commit the non-current fence
before the shorter policy is acknowledged as effective. If that coordination is
unavailable, report the requested change as pending, not saved; the prior agreed
expiry still applies. At that expiry the custody writer denies reads and continues
deletion even if the register is unreachable; it must not retain overdue bytes
while waiting for a fence acknowledgment. Unavailable authoritative source status still blocks a
new decision; a `CURRENT` head alone cannot assert that an unreachable source is
valid. The later source/approval adapter must qualify this joint failure case.

Changes outside these owners, stale restored evidence, digest mismatches and
unreconciled metadata block decisions. This protocol orders supported writes;
it is not a claim to detect an unknown external revocation or malicious database
administrator. Actual independent source-currentness and authenticated registration
methods remain requirements of the accepted enrollment policy.

## Restore, audit and retention

A digest chain detects inconsistent retained history; it cannot prove a complete
older snapshot is current. Supported restore must put the register and enrollment
writer into a fail-closed maintenance state **outside the restored snapshot**,
drain/fence old writers, and start the restored instance locked under a new epoch.
Old-epoch commands cannot write or replay affirmative results. A successful database
restore, an empty query or equal digests from two jointly restored stores cannot unlock it.

Reconciliation must compare retained journal/operation/consumption history and
withdrawals to a demonstrably current independent continuity baseline, then reconcile
private evidence and deletion tombstones before any writer resumes. Missing tail
history is STOP, never reconstructed from a caller's last receipt. The actual
external baseline, restore interlock and unlock proof need their own operating
qualification; **this slice defines no unlock command**. Its offline restored-store
case remains locked. This preserves the existing fixture's refusal boundary while
making the production continuity gap explicit, rather than claiming a second copy
or counter stored in the same backup solves rollback.

[Supabase database backups exclude Storage objects](https://supabase.com/docs/guides/platform/backups).
The chosen operating plan must cover private evidence objects separately. No tier,
backup expiry, retention-law conclusion or production recovery guarantee is inferred.
The canonical source-copy retention setting does not delete commercial history,
associations or consumption. Store only opaque provenance and required lineage;
raw sources remain subject to the accepted customer settings and deletion receipts.
Before real records, enumerate each class's schedule and retirement proof, including
when no active authority or derived replacement depends on it. This contract adds
no blanket permanent retention and no history-deletion command.

## Restriction and cost audit

| Requirement | Cost or exclusion | Concrete need; why a lighter rule fails |
| --- | --- | --- |
| Attributable commercial source and separate enrollment proof | Operator/source-adapter work; unsupported source delays its path. | Issuer authorization, payment and business authority are different facts. A paid flag or customer-entered row can misassign a deployment. Existing authenticated source provenance suffices; no new purchase, second business authority or universal document is required. |
| Proposed private PostgreSQL register and named owner | Database/custody administration; actual service cost needs acceptance before provisioning. | Current repositories supply no registry. Constraints and transactions preserve issuance/consumption relations under retries; an editable spreadsheet cannot enforce them. Reuse an adopted equivalent authoritative system if one is found, rather than duplicate it. |
| One serialized journal writer and immutable original identity | Brief internal contention and evidenced corrections; no silent transfer of consumed deployments. | Competing associations can assign one entitlement twice or overwrite original consumption. Database locks/constraints are sufficient at this small manual write volume; no distributed queue or second operator is required. A legal business transfer changes authority and needs a policy, not a disguised correction. |
| Enrollment-owned fence before evidence change | Temporary non-current state during a change/failure. | An asynchronous mirror can leave withdrawn evidence usable. Only suspend when required proof is changing; deleting an unnecessary raw copy need not suspend authority. No extra customer credential or step is introduced. |
| Locked restored store until continuity proof | Recovery work and downtime for the affected register. | An old internally valid snapshot can lose withdrawals or consumption. Hash comparison inside that snapshot cannot show currentness. Reusing the existing fail-closed restore boundary is sufficient for this offline slice; a custom witness is not claimed implemented or selected. |

## Offline qualification work order and exit

No fixtures or tests run as part of this prose proposal. Separately authorized
implementation uses synthetic businesses, disposable storage and temporary test
keys only. It must inventory and reuse existing protocol types, fixture transaction
hooks, real-process race machinery, restored-store denial and recovery parity
cases. The PostgreSQL writer requires disposable PostgreSQL qualification; SQLite
tests alone cannot prove PostgreSQL locks/permissions. No live provider is needed.

| Proof group | Required observations |
| --- | --- |
| Positive paths | Sale with independent provenance; valid grant without a purchase; own-name proprietor, owner and delegate evidence; new enrollment before consumption; multiple licences/renewal with preserved original consumed link. No record result is recovery approval. |
| Closed branches and wrong bindings | Reject mixed sale/grant fields, partial CURRENT evidence, unknown fields, caller actor/scope/verified flags, invalid UUID/digest/instant, and mismatched organization/entitlement or envelope. Valid minimal cases pass. Probe zero/negative/missing/boolean/string revisions and explicit empty-store sequence zero separately; before/at/after both expiry boundaries and a writer waiting across expiry. |
| Provenance and authority separation | Correct payment with impersonated requester, correct person without authority, correct authority with another entitlement, wrong-source sale event and expired/withdrawn source all fail the relevant component independently. A genuine issued-envelope upload alone cannot establish ownership. |
| Retry/crash | Same operation returns the committed immutable result without new rows; changed actor/content conflicts. Crash at each write and before commit leaves no partial state; crash after commit before reply replays. Revoked actor cannot retrieve replay as an authorization bypass. |
| Races | Independent database connections/processes: duplicate association, conflicting association, withdrawal versus association in both orders, stale correction, begin/finish versus withdrawal, and renewal alongside consumption recording. Use deterministic barriers and the existing recovery suite's repetition policy; one durable outcome, no erased history. |
| External-store ordering | Crash after begin, lost private-store reply, late finish, expired required source during database outage, optional raw-copy deletion, source unavailable after a previously CURRENT head. No false currentness or retention extension; late finish cannot overwrite withdrawal. |
| Corruption/restore | Remove/re-key retained operation, revision, journal or consumption; rollback register alone or both stores; present old-epoch request. STOP/locked results with unchanged domain snapshots and no affirmative result; no implicit empty-store recreation. |
| Access and confidentiality | A customer, another business, wrong role or direct application table write cannot bypass the owner. Closed results/logging contain no private documents, contacts, credentials or provider commercial terms. Correctly scoped permitted writer succeeds. |

Differences from proven work: PostgreSQL and a new commercial/association owner
replace neither the existing offline issuer nor its signed consume semantics;
opaque enrollment-head ordering is new and needs its own proof. Preserve unchanged
baseline recovery results before asserting integration parity. No inference/model
or prompt is involved, and synthetic input is not real identity qualification.

For this proposal, review the exact revision and obtain Juan's acceptance of the
register/owner/backing-store direction. Licensing adoption, private provider source
profile, infrastructure/custody decisions, real evidence methods and production
continuity remain explicit execution gates. Acceptance does not provision Supabase
or authorize code. A later bounded offline implementation request can cover these
record transitions while all live/identity/restore-unlock work remains held.
Track operating inputs in [issue 101](https://github.com/canfieldjuan/connect-automate/issues/101).
