# Business enrollment, evidence and custody work order

Status: **PROPOSED AMENDMENT; CONTRACT ONLY; NOT READY FOR EXECUTION.**
The enrollment work order merged in PR 102. This amendment records Juan's
subsequent owner appointment and US coverage decision and develops the custody,
retention and licensing association proposal. It needs independent review and
Juan's exact-revision acceptance. It does not authorize real enrollment, records
collection, accounts, keys, fixtures or implementation.

The [business-verification policy](LEAD-OWNER-BUSINESS-VERIFICATION.md) owns
eligibility, credentials, freshness, administrator permissions and restrictions.
The [approval requirements](LEAD-OWNER-RECOVERY-APPROVAL.md) own the separate
approval/publication prerequisites. This work order develops their missing
enrollment inputs; it does not redefine either policy. Native sign-in, Hello,
Gmail and live activation remain on hold.

## Inventory and actual missing inputs

| Inspected revision | Observed capability and limit |
| --- | --- |
| Connect Automate `b7523e13514d1995f1a82399786503b286a6c8d4`, merged PR 100 | Accepted business-verification policy permits sole-authority businesses and independently verified enrollment during recovery. It does not select evidence methods, a record owner or storage. |
| Same revision, `qualification/owner_authority/protocol.py`, `OwnerClaim`, `ConsumeBinding`, `RecoveryEvidenceCase.relations` | Closed synthetic models bind UUID organization/entitlement identifiers. Recovery requires predecessor and replacement organization/entitlement equality, and changed installation/host/key/operation. No business-identity assertion or enrollment record is supplied. |
| `connect-contracts` remote main `07cc315b97772f6eb182dcd2cda6fc8ffde707cb`, ADR-0003, `entitlements/v1/claims.schema.json`, `tools/entitlement_issuer.py` | Accepted entitlement format contains a UUIDv4 entitlement ID and a bounded opaque subject. The issuer creates a fresh entitlement ID on each issuance. The subject schema does not establish business identity or installation-independent continuity. |
| `local-connect-licensing` remote main `c7ac955674b680f04c2ebbcdc4806682f707f81d` | Tracked tree contains README only. No implemented authority registry or recovery binding service. |
| Licensing PR 1, `9f9d1be530653300926315294ef1721ce3d4fc98`, `docs/contracts/LICENCE-SERVICE.md`, LS-INV-4 and storage section | Open proposed contract; acceptance was not verified. Proposed subject derives from installation ID. Identity/document storage is excluded. This is an input proposal, not an accepted business identifier or deployed trust source. |

Inspection used remote-reachable revisions. Unrelated checkout changes were
preserved. No private customer or payment-provider records were inspected.
There is no model, prompt, live inference or identity evidence in this slice.
Existing synthetic recovery proofs are not evidence of real identity verification.

Deliberate departure from existing validated work: propose an external manual
enrollment workflow and its custody/binding obligations. No behavioral port is
performed. Later implementation must inventory its actual owners and reuse the
existing recovery parity evidence without changing its meaning.

## Accepted operator inputs and proposed custody

Juan explicitly appointed himself **accountable enrollment-record owner**:
"Ok, I’ll be the owner then." His initial customer coverage is
"USA - all 50 states". His retention direction is a default within 30–90 days,
configurable by users. These decisions are recorded in
[issue 101](https://github.com/canfieldjuan/connect-automate/issues/101).
The exact default and operating details below remain proposals, not previously
accepted decisions. Supabase was raised as a candidate, not selected or provisioned.
The owner controls access, source retention, deletion and restore authorization.
Licensing remains responsible for policy adoption, administrator permissions,
the commercial/deployment binding and eventual recovery approval.

One person may hold the record-owner and authorized-verifier roles. A backup
custodian is optional; no second operator or business authority is required.
Until a separately authorized backup exists, manual work waits when the owner
is unavailable. That is an availability consequence, not a customer eligibility
restriction or a reason to grant another party access automatically.

Propose a dedicated encrypted record store outside the licence service and all
repositories, CI, model prompts and review-evidence folders. For this manual
workflow, a managed store with revision history and access/decision audit is
sufficient; no bespoke vault or database service is required merely to start.
No vendor, account, host, path, encryption key or subscription is selected.
The actual store must demonstrate the following before receiving real records:

- Owner-controlled access and recovery, per-person access attribution, and
  separation between source records and the opaque references supplied to licensing.
- Encryption in storage, backup and transfer, with custody/recovery of the keys
  specified by the selected system rather than improvised in this work order.
- Revision history and an audit trail whose changes/deletions are detectable;
  a mutable spreadsheet or editable note alone is not authoritative history.
- A separately protected encrypted backup and a demonstrated restore that
  preserves record revisions, withdrawn authority and deletion tombstones.
  The later writer must detect an older restored view before it permits new
  decisions; a backup alone is not rollback protection.

### Supabase candidate and qualification limits

Evaluate private Supabase Storage for necessary source copies and application
Postgres tables for enrollment metadata, revisions and audit. Keep both outside
the licence service; business records do not become entitlement claims.
[Supabase documents encryption at rest and in transit](https://supabase.com/security).
That is not a claim of end-to-end encryption or Juan-exclusive encryption keys.
Actual provider access, key/account recovery, selected region and cost need an
explicit custody decision before collection; no paid tier is selected here.

[Private buckets use access policies](https://supabase.com/docs/guides/storage/buckets/fundamentals).
The later implementation must use database row-level policies and Storage
policies for business/role isolation, with privileged server access separately
controlled. A private bucket label alone is not that proof. Demonstrate allowed
access and denied cross-business, revoked-user and unauthenticated access.
Use the canonical authenticated-role boundary; no new customer credential or
second operator is introduced by choosing storage.

[Database backups exclude Storage file objects](https://supabase.com/docs/guides/platform/backups).
The custody plan must cover both metadata and needed files, retention of each
backup class, and restore with current revocations and deletion tombstones.
[Delete objects through the Storage API](https://supabase.com/docs/guides/storage/schema/design),
not by deleting their metadata rows and leaving the bytes behind. A verified
deletion receipt must distinguish primary deletion from pending backup expiry.
Neither encryption nor successful backup restore proves tamper/rollback detection.

Licensing's independently retained decision revision can detect an enrollment
view older than the revision it used. Reuse that baseline where sufficient,
rather than requiring a custom vault solely for this check. It cannot detect a
withdrawal never recorded there, or a joint rollback of both stores. The later
storage/writer contract must demonstrate ordering for those cases and a current
revision/deletion baseline outside the snapshot being restored before decisions
resume. This is an unresolved qualification requirement, not a deployed guarantee.

The [canonical retention proposal](LEAD-OWNER-BUSINESS-VERIFICATION.md#proposed-source-retention-schedule)
owns the proposed default, customer settings, deletion and required history.
Prefer source references and minimal verification records where the qualified
method permits; this candidate does not require copies of identity documents.

### Source-object creation and reconciliation

Before any source upload, the custody writer must commit a closed pending
retention record containing the unique object key, authenticated business scope,
receipt time and policy revision. Enforce required fields, key uniqueness and
policy references with the storage owner's schema/constraints; Storage write
authorization must require that committed, current record. If the commit fails,
no upload is permitted. A zero source-copy duration uses the canonical transient/
reference path, not an upload followed by deletion. This adds no customer step.

The canonical retention owner schedules pending records from the recorded
receipt time, including a crash before upload or after upload but before
finalization. Finalize only against the current policy/state; failures remain
tracked, with the same key on retry and no clock reset. Pending expiry, deletion
and upload completion must be serialized/fenced: a late object must remain
unreadable and be deleted if expiry/deletion won. Keep the deletion record long
enough to reconcile in-flight completions; an empty object lookup alone cannot
prove no late upload will arrive. The later storage contract must qualify this
ordering rather than assume a database transaction includes the Storage API.

As a last line of defense in addition to that creation invariant, reconcile the
managed source bucket's complete object inventory with the current committed
retention records. Delete an object lacking such a record through the supported
Storage API, **within one hour of its store-recorded creation time**, not one
hour after discovery. This proposed operational cleanup bound includes listing,
retry and deletion; it is not extra retention time for known copies, whose
canonical expiry still applies, nor permission to persist zero-duration copies.
Use the store's structured inventory and verify its timestamps during storage
qualification; missing/unusable age is treated as overdue. Reconciliation must
first use a current, reconciled metadata view under the restore rules above,
not mistake a partial restore for authoritative absence. Limit it to the managed
source-object scope; it must not delete unrelated objects or recreate missing
authority/consumption history. An overdue or unsuccessfully deleted orphan is a
reported retention failure with continued cleanup, never a successful receipt.
The future qualification must prove coverage and the bound; this is no claim
that a reconciler or provider guarantee exists today.

## Business-to-entitlement binding

Do not equate a licence subject, provider customer ID, email address, display
name or existing `organization_id` with a verified legal/business identity.
Those identifiers need an explicit authoritative association, not a naming rule.

Propose a stable opaque enrollment-record reference generated by the external
record owner. It identifies a private enrollment record, not a new licence
subject or a replacement for any existing protocol identifier. For recovery,
licensing must establish and retain its association to the exact original consumed
deployment using its authoritative claim/receipt/binding and independently
validated commercial provenance. Neither a caller's claimed organization ID nor
possession of a signed licence alone supplies that association.

For each consumed-deployment association, retain the exact organization ID,
original entitlement ID, claim ID, consumed operation and receipt digest from the authoritative binding;
record the issuer/key context and entitlement envelope reference used to check
the commercial evidence. The private source reference must explain how that
deployment belongs to the independently verified business and representative.
The licensing binding procedure, including its owner and authoritative commercial
source, is an explicit missing input. This proposal does not assert it exists.

Enrollment before first deployment may instead associate the verified business
with its issued entitlement and leave the consumed-deployment association pending.
Do not require a recovery case or an already consumed deployment merely to enroll
a new customer. That pending association is not evidence of non-consumption and
cannot authorize recovery. When recovery is requested, licensing must retrieve
the actual consumed record and establish the complete association above; an
absent record cannot stand in for a determined consumption outcome.

The accepted synthetic recovery relation keeps the original organization and
entitlement IDs across replacement. Preserve that relation. A newly issued or
renewed licence can have another entitlement ID; do not overwrite the original
consumption or silently substitute the new ID. Associations to other licences
need their own verified records and history. A changed installation-derived
subject is not, by itself, evidence of either a different business or continuity.
No entitlement schema, subject algorithm or cross-repository contract changes here.

### Proposed licensing association procedure

1. The record owner creates the opaque enrollment reference and records the
   independently verified business, representative authority and method revision.
   A reference is an index into evidence, never evidence of authority by itself.
2. Licensing retrieves its authoritative issuance/commercial record and verifies
   the business association against that evidence. A candidate for a direct sale
   is the operator's independently retrieved sale record and contact provenance,
   tied to the issued entitlement. No particular payment provider, new purchase
   or receipt upload is required. Actual record systems and their authenticity
   checks are still missing; a name/email match or paid status alone is insufficient.
3. Licensing records a revisioned association between the enrollment reference
   and the exact organization/entitlement identifiers. Before consumption, it
   remains an issued-entitlement association only. On consumption, licensing
   binds the authoritative original claim, operation and receipt as above.
   Customer-submitted identifiers cannot overwrite an existing association.
4. Recovery retrieves that original association; renewal adds an explicit new
   entitlement association without replacing it. Ambiguous or conflicting
   associations require evidence reconciliation, not merging by business name.
   A legitimate correction is a provenance-bearing revision; preserve the prior
   record and its effect on existing decisions instead of rewriting history.
5. The later licensing writer must enforce uniqueness for the same entitlement/
   consumed binding, exact retries and serialized conflicting updates through
   closed models, database constraints and transactions at the storage owner.
   The concrete schema is future work. One business may have multiple
   explicitly associated entitlements; no one-licence-per-business cap is proposed.
   Revocation/current-authority checks remain necessary at the approval decision.

This is a Lead Intake proposal for licensing adoption, not a new implemented
licensing registry. A separate wire/storage contract must pin the authoritative
record owner, fields, source systems and cross-store ordering before code work.

## Evidence profiles: concrete completion requirements

The proposed [US verification methods and licensing-record work order](LEAD-OWNER-US-VERIFICATION.md)
develops named source investigations and the missing issuance/association journal.
Its research coverage is not qualification or authorization to execute this workflow.

An enrollment procedure must establish three separate facts: the person is the
claimed person, that person has current authority for the business, and the
business owns the issued-entitlement association (including the exact consumed
deployment when recovering).
Public business facts or control of a contact route do not establish all three.
The distinction between validating evidence and binding it to the applicant is
also explained in [NIST's identity-proofing overview](https://pages.nist.gov/800-63-4/sp800-63a/proofing/).
This is a conceptual reference, not an identity-assurance-level claim or selection
of an identity service, document or biometric process.

Initial coverage is the United States, all 50 states, including sole proprietors
and delegated representatives. Coverage is the product target, not proof of 50
qualified methods or a universal legal retention rule. Track each state's source
coverage and actual record obligations in the method profiles; share a profile
across states when its sources establish the same facts there. Do not require a
separate document or procedure merely because a customer crosses a state line.
The following are source families to investigate, **not qualified methods**:

| Authority basis | Proposed source investigation | What must be demonstrated |
| --- | --- | --- |
| Owner or officer of a registered business, including a single-member company | The relevant issuing registry and, where it does not establish the actual authority/scope, independently validated governing or authorization records. | The source actually establishes the named person's relevant authority; registered-agent, organizer, address or company-existence entries alone are not equivalent. Bind the requester to that person independently. |
| Sole proprietor acting under their own authority | Independently maintained records linking the natural person to the business activity and commercial/deployment association; an issuing registration/trade-name source where one is applicable, or another independently validated source path. | The method works without requiring incorporation or a registration that does not apply. Self-description, possession of a receipt, or an unverified uploaded statement cannot substitute for independent evidence. |
| Delegate | A valid delegation instrument plus independently established current authority of the grantor and identity of the delegate. | Verify scope for the requested action and the full current chain; use the canonical policy's pre-case provenance rules for recovery-time enrollment. No new form is required when an existing valid instrument meets the accepted method. |

For each proposed jurisdiction and authority basis, the record owner and licensing
owner must complete one revisioned method profile with:

1. Named issuing/authoritative sources, the exact attributes they establish and
   their limits; source authenticity and independent retrieval procedure.
2. The procedure that binds the live requester to the validated identity, and
   the independently established contact route and its provenance.
3. Current-authority, withdrawal and conflict checks, including how the actual
   source exposes changes and how unavailable status is handled.
4. The authoritative commercial/deployment link, not merely a billing email or
   a submitted licence. Record why the source establishes this association.
5. Evidence retained versus discarded, access and retention obligations, cost,
   and the reason any extra document, step or purchase is needed.
6. Positive and negative qualification cases proving each fact separately and
   together. A method label, human checkbox or fixture `verified=true` is not proof.

An unqualified profile means the method is unfinished, not that the customer or
business form is categorically excluded. Investigate an alternate evidence path
meeting the same facts when a source lacks coverage. There is no universal
registry, government-ID upload, new customer purchase or second-person requirement.
This work order intentionally supplies no success path for a placeholder method.

Start identity-binding research with the lightest adequate candidate: for a
customer Juan sold to, verifier-initiated contact on an independently retrieved
sale-recorded route followed by bound credential registration. Demonstrate that
the route binds this requester to the person with current business authority;
a shared, reassigned or compromised address must not pass by contact control
alone. This candidate is not yet qualified and does not replace independent
authority and commercial-link checks. Add document or biometric steps only if
the actual method cannot establish a needed fact without them, with the cost,
threat and failed lighter method stated before adoption.

## Proposed verifier procedure

1. Select the accepted method revision for the actual authority basis and
   jurisdiction. Retrieve any existing enrollment and history from the record
   owner and the commercial association from licensing; recovery additionally
   requires the authoritative consumed binding. Distinguish a genuinely new
   enrollment from missing or corrupt required history using the canonical rules.
2. Obtain and validate the method's sources independently, establish the
   requester-to-identity link, and initiate contact on the verified route.
   During recovery-time enrollment, establish pre-case provenance and current
   validity as required by the policy. A later retrieval date is not a new trust root.
3. Establish own authority or the delegated chain and the exact commercial link.
   Record what each source proves, its revision and observation time, conflicts
   and the verifier's authenticated identity. Do not collapse identity, authority
   and deployment ownership into a single unchecked boolean.
4. Record the verified authority in a pending enrollment, bound to the method,
   evidence and commercial/deployment revisions. Complete the separately qualified
   credential-registration ceremony against that identity. A submitted key cannot
   authorize its own enrollment. Only successful bound registration completes
   enrollment; the record alone cannot approve a recovery or create host authority.
5. Supply licensing only authorized opaque record/evidence references and their
   revisions/digests. Licensing must apply the canonical current-version,
   revocation and serialized-decision rules again before approval. Specify the
   cross-store fencing/ordering protocol in the later storage/wire contract;
   a manual lookup followed by an unguarded write is not atomic authorization.

Credential and administrator profiles remain solely in the canonical policy.
The later authentication work order must include stolen/compromised-PC cases:
a credential whose only usable copy is on the affected deployment cannot serve
as the independent recovery credential merely because that PC still works.
This incorporates oversight's non-blocking follow-up without lifting the native
sign-in or Hello holds or changing the existing authenticated replay path.

## Record and implementation boundary

Later closed storage models must distinguish pending enrollment, qualified
enrollment and withdrawn/superseded authority, with explicit permitted transitions.
Represent authority basis as own authority or delegation; the delegation branch
requires its instrument and grantor chain, while own authority does not require
self-authorization. Qualification requires method/source/binding revisions,
authenticated verifier provenance and successful bound credential registration.

Use closed models and the authoritative schema for representable constraints,
then one enrollment-owner semantic validator for cross-record facts. Preserve
the existing UUID/digest/time types where they apply, without defining a second
parser. The later schema must reject unknown fields, missing provenance and
caller-supplied approval flags. The authoritative writer owns uniqueness,
revision transitions and stale-update rejection. No executable schema or state
machine is added by this prose work order.

Manual collection, verification records, licensing decisions and host publication
are separate responsibilities. A future offline synthetic slice may test record
transitions and propagation only; it cannot qualify sources, authenticate real
people, provide hardware-custody proof or retire an old host. It needs separate
authorization and must retain the existing evidence-only result semantics.

## Restriction and cost audit

Inherited restrictions and their rationale stay in the canonical policy. These
are the obligations introduced or made concrete by this work order:

| Obligation | Cost or exclusion | Concrete need; why a lighter rule is insufficient |
| --- | --- | --- |
| Explicit accountable record owner and authorized access | Owner time and an appointment; manual work may wait during absence. | Someone must control access to identity sources, deletion and recovery. An AI session or inferred role cannot accept that custody. A second operator is optional because access accountability does not require two people. |
| Dedicated encrypted, revisioned custody and protected restore | Store/key/backup administration; actual product and cost remain unselected. | Private source disclosure and rollback could enable false authority decisions. Repository copies and a mutable note do not provide access attribution or preserved withdrawals. A vault meeting these properties is sufficient; a new database or bespoke service is not inherently required. |
| Explicit commercial association, including the original consumed deployment for recovery | Verifier and licensing must establish the commercial link. | The current subject schema encodes no business semantics, and the proposed online subject is installation-derived. Matching a subject string or accepting a new entitlement cannot preserve or establish the original business-to-consumption link. |
| Source profiles demonstrate identity, authority and commercial association separately | Research, manual work and possible source-access cost; unavailable proof delays the affected method. | An attacker can copy public business facts or present a receipt. Neither binds the live claimant to current authority over that deployment. Alternate methods are allowed if they establish the same facts; no business type is excluded to avoid doing that work. |
| Closed record branches, authenticated provenance and serialized revision ordering | Implementation and qualification work before use. | Free-form assertions or stale evidence could be promoted to approval. Schema constraints cannot prove a human identity, but they can prevent a missing proof component from being represented as qualified; semantic and writer checks then enforce their own boundaries. |
| Record-class retention decisions before real collection | Owner must identify actual obligations and a deletion procedure. | Unspecified retention creates unnecessary private-data exposure or removes evidence needed for later decisions. Keeping everything forever or guessing a universal duration is not a substitute. |
| Business/role access policies and verified object deletion for the candidate store | Policy configuration, access qualification and separate file-backup/deletion work. | Private customer evidence must not be exposed to another business or remain as forgotten object bytes after metadata cleanup. Encryption alone does not authorize readers, and metadata deletion does not delete Storage objects. Built-in policies/API operations are the supported mechanism; no bespoke cryptography is required here. |
| Revisioned licensing association with preserved original identifiers | Operator/licensing verification and conflict reconciliation; no automatic email-based association. | Existing recovery models require the original organization/entitlement relation. A mutable name/email join or overwriting on renewal can assign someone else's deployment or lose consumption. Existing issued/consumed records and one explicit association are sufficient; no new identity claim inside the licence is needed. |
| Pending record before upload; bounded source-object reconciliation | One durable metadata commit before a retained copy and inventory/API/retry capacity to meet the proposed one-hour orphan cleanup budget; no new customer action. | Upload-first can leave bytes outside the only retention scheduler after a crash. Pending-first makes ordinary writes tracked; inventory cleanup handles unexpected objects without replacing that origin fix. Unbounded or discovery-relative cleanup can miss hidden bytes indefinitely. One hour is a proposed operational repair budget, not a customer retention cap or permission to extend known expiry; a metadata-only scan cannot find objects absent from metadata. |

## Future qualification and exit gates

These are proof obligations, not executed tests:

| Case | Required observation |
| --- | --- |
| Sole owner or sole proprietor with a completed, qualified evidence method | Own-authority path without self-authorization paper or a second business authority; all three facts established. |
| New customer enrolling before first deployment | Verify identity, authority and issued-entitlement association without fabricating a consumed record; the deployment association remains pending and supplies no recovery permission. |
| Existing customer without prior enrollment, with independently retrieved pre-case sources and current checks | Recovery-time enrollment can proceed through bound registration; no automatic approval. |
| Valid identity but unproven authority; valid authority but wrong commercial link; valid link but impersonated requester | Each fails independently; combining other valid facts does not rescue the missing one. |
| Registry proves company existence or lists an agent but not requested authority | Do not infer owner/officer authority; use the accepted alternate source path. |
| Legitimate sole proprietor with no applicable company registration | No incorporation requirement; qualify an independent evidence path for that form. An absent method remains unfinished, not a fabricated success. |
| Same displayed business name with different organization/entitlement binding; new issuance after original consumption | Do not merge businesses or overwrite original consumed identifiers; retain explicit associations and lineage. |
| Proposed installation-derived subject changes on PC replacement | No automatic identity change or continuity claim; use the authoritative recorded association. |
| New key before identity/authority proof, placeholder method, stale revision or modified delegation | No qualified enrollment or approval; record the actual unresolved condition. |
| Restore an old vault snapshot with previously withdrawn authority | Detect the older state before permitting new decisions; a successful file restore alone cannot pass. |
| Delete source material under accepted retention while preserving required history | Apply canonical source-unavailable versus corrupt-history semantics; never free consumption. |
| Valid enrollment but missing predecessor retirement or replacement native proof | Separate publication gate still blocks; this work order supplies neither proof. |
| Private storage with otherwise valid caller from another business, revoked role or anonymous access | Deny source access; permitted verifier can read only the authorized scope. |
| Sale-recorded route shared/reassigned/compromised or business authority no longer current | Contact control alone never qualifies enrollment; investigate evidence sufficient for the actual requester. |
| Duplicate association retry, concurrent conflicting associations, renewal or evidenced correction | Exact retry remains one association; conflict cannot overwrite original consumed history; legitimate revision and multiple entitlements remain possible. |
| Vault-only rollback versus joint rollback or withdrawal absent from licensing's last decision | Detect the first using the independently recorded revision; do not claim it proves the latter cases. Qualify their ordering/baseline before enabling decisions. |
| Pending-record commit fails or crash occurs before it commits | No source object is uploaded; zero-duration selection also creates no persistent copy. |
| Pending record commits, then crash before upload or after upload before finalization | Same canonical receipt-time expiry applies in both cases; upload retry uses the tracked key, and bytes cannot escape the pending schedule. |
| Expiry/deletion races upload completion or finalization; retry after a lost upload reply | Current record/state fences completion; no readable late object, clock reset or false deletion receipt; late bytes are reconciled and deleted. |
| Complete bucket inventory finds an unrecorded source object; known valid object alongside it | Delete only the unrecorded source object within one hour of creation; preserve the valid object until its own expiry. Probe before/at/after the bound, pagination, failed deletion and unknown age; a missed bound is a reported failure, not a pass. |

Open operator and licensing inputs are tracked in
[issue 101](https://github.com/canfieldjuan/connect-automate/issues/101).

Before execution: Juan must choose the actual custody arrangement; accept
completed source profiles covering the intended US customers and retention
obligations; and accept licensing's concrete identifier/commercial
binding procedure. Licensing must adopt those methods under the canonical policy.
No requirement here declares the open licensing PR accepted or selects its
subject scheme. Authentication, closed storage/wire models, cross-store ordering
and real qualification require their own accepted executable work orders.

Drafting/review can finish while these choices remain open. Acceptance of this
proposal accepts its workflow and completion requirements only; unanswered inputs
remain explicit and prevent execution. Do not replace them with synthetic flags.
Submit the exact revision to independent oversight, then seek Juan's acceptance.
Implementation and native/live activity require separate explicit authorization.
