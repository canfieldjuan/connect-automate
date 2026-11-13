# Business-verification policy and licensing administrator channel proposal

Status: **PROPOSED; CONTRACT ONLY.** Juan authorized drafting and oversight
submission. This is a Lead Intake recommendation for the licensing owner to
adopt, not a claim that licensing supplied or implemented this policy. It needs
independent oversight and Juan's exact-revision acceptance before merge. Neither
acceptance nor merge provisions an account, enrolls a business, generates keys,
collects customer evidence or authorizes implementation.

The sole-authority policy amendment merged in PR 100; its enrollment work order
merged in PR 102. This pending amendment records Juan's subsequent owner
appointment and proposes configurable source retention. Its new policy details
need independent review and exact-revision acceptance; earlier acceptance does
not accept them automatically. Independent verification remains required without
a universal second person, prior enrollment, owner self-authorization document
or customer hardware-key purchase.

The [recovery approval requirements](LEAD-OWNER-RECOVERY-APPROVAL.md) and
[canonical recovery policy](LEAD-OWNER-AUTHORITY.md#failed-or-replaced-pc-recovery)
remain controlling. Native sign-in, Hello, Gmail and live activation remain on
hold. This proposal concerns a future licensing channel, not the host's native
sign-in mechanism. No native or browser-authentication probe is authorized here.

## Problem, scope and inventory

The approval requirements leave the business-authority source and administrator
channel unspecified. An entitlement subject, receipt or recovery case does not
establish who may act for a business. A caller-supplied approver or verification
flag cannot fill that gap. This is a missing policy/channel, not a defect to fix
in the existing consume or evidence-admission owners.

This amendment changes this policy and its enrollment work order; the approval
requirements are unchanged.
No runtime, schema, catalog, dependency, workflow, fixture or entitlement format
changes. It creates no licensing endpoint and modifies no other repository.

Inspected inventory:

| Source pin | Observation and limit |
| --- | --- |
| Connect Automate `daa1427da7b42ebd2255e5987dc3c25960c935db`, `docs/contracts/LEAD-OWNER-RECOVERY-APPROVAL.md` | Merged requirements separate business verification, approval, executable authorization and host publication. This proposal supplies a recommended policy profile, not the missing execution or qualification. |
| Same pin, `qualification/owner_authority/protocol.py:615-725`, `licensing_fixture.py:355-443,482-533` | Synthetic case/admission owners remain evidence-only. Their existing types and signatures cannot authenticate a business representative or licensing administrator. |
| `local-connect-licensing` remote main `c7ac955674b680f04c2ebbcdc4806682f707f81d` | Tracked tree contains only README. Its service description is not implementation evidence. No business registry or admin channel is supplied by this tree. |
| Licensing proposal checkout `9f9d1be530653300926315294ef1721ce3d4fc98`, `docs/contracts/LICENCE-SERVICE.md` sections 1, 4, 9 | Proposed entitlement service uses pseudonymous subjects and keeps identity/document data outside its store. Its operator questions and commercial owner are not a recovery-verification policy. Preserve that separation. |
| `connect-contracts` checkout `a168b9a67450556d95b4939a59ca36aa7aedfda5`, `tools/entitlement_issuer.py:359-451` | Entitlement issuer accepts a bounded subject and signs entitlement claims. Subject possession is not proof of business authority. No change to the issuer. |

No authoritative enrollment system or named business-record custodian was
established by this inspection. A concrete source and custodian must be supplied
and accepted before execution. This does not assert that no such records exist
elsewhere or that an uninspected record is qualified.

Initial business enrollment and its recovery-contact record are a **new proposed
record system**, not a facility supplied by either inspected repository. The
**enrollment-record owner** is Juan, explicitly appointed in his subsequent
operator decision recorded in the enrollment work order and issue 101. The
storage location remains open. This owner would create
and maintain enrollment records, source-material custody and retention. The
**licensing owner** retains recovery-policy adoption and approval responsibility
and is proposed to own the administrator channel's account/role registry and
decision audit. That does not assign ownership of enrollment records to licensing.
Both roles require their explicit accepted procedures before operation. Proposed
placement is outside the licence service, preserving that service proposal's
no-identity-data boundary. An alternative inside that service would require an
explicit contract amendment; it is not authorized here. A payment-provider
dashboard or records held outside these repositories have not been inspected
and cannot be named as an established trust source.

Prior evidence alias `licensing-recovery-approval/contract/manifest.json`, SHA256
`455ce4f0a27cdcb922ea92412799d857bf64703e054e691ff672421247c8b469`, covers the
requirements proposal at `8a4513c4e9245e58cbf3703e8e74d66655ddd110`, not business
verification. Existing offline controller proofs remain unchanged. There is no
model, prompt, inference runtime or customer-document input in this slice.

Deliberate departure: recommend independently verified enrollment and a
dedicated administrator channel, with the restrictions and costs below. These
are proposed product choices, not established behavior or automatic extensions
of the entitlement service. Later executable work must inventory its actual
owners, list all differences and preserve existing offline proof parity.

## Recommended initial policy: independently verified business representatives

Require qualified business-authority enrollment before an affirmative recovery
verification result. Enrollment may already exist or be established during a
recovery case under the same separately accepted independent-evidence procedure.
An existing customer is not excluded solely because no enrollment predates the
case. A demo, subscription, paid invoice or offline licence alone is insufficient.

For recovery-time enrollment, the licensing verifier must obtain authority
sources and business contact routes independently of the requester. The sources,
authority relationship and routes must predate the case; the verifier retrieves
current status and initiates contact on that independently established route.
A source retrieved after case opening is not disqualified merely by retrieval
time, but its pre-case provenance and continuing authority must be established.
An independent authority record and the contact route in the original sale's
records are possible inputs only under an accepted method, not presumed existing
or sufficient evidence. A requester-supplied document, link, contact replacement,
key or verification flag is untrusted input, never a trust source merely because
it was submitted. Missing pre-case provenance, inaccessible required sources or
unverifiable current status blocks enrollment; no support override substitutes.

After independently verifying identity, current authority and the exact business
and entitlement binding, record the verified authority in a pending enrollment
with its provenance, source revisions, case reference, verifier and time. Only
then may the verifier initiate the accepted credential-registration ceremony
bound to that verified identity and enrollment. Enrollment becomes qualified
only after that ceremony succeeds. The registration key and its possession do
not authorize the enrollment; an arbitrary key in the recovery request cannot
be promoted to an enrolled credential. The later procedure must prove this binding and ordering.
Complete enrollment before the recovery challenge and verification sequence below;
initial evidence gathering cannot depend on possessing a not-yet-enrolled key.
No enrollment, contact replacement or credential registration is executed here.

A business is not ineligible merely because it has a single person with business
authority. The same independent-verification requirement applies to a person
acting under their own business authority and to a representative acting under
delegated authority. Eligibility does not establish that a supported verification
method exists or make recovery available.

The enrollment must bind an opaque business ID and entitlement lineage to a
named authorized representative, their authority basis (own business authority
or delegation), its scope and expiry or withdrawal conditions, a registered
public credential, and a pre-established business contact route.
Personal identity and contact details would stay in the enrollment-record owner's
new external record store; recovery receives opaque references and integrity
digests only.

The enrollment record must identify the representative's authority basis and
scope, link the business and entitlement, and retain evidence of how identity
and current business authority were independently established. For own business
authority, that independently verified evidence is the authority record; no
signed self-authorization document, self-delegation or second person is required.

For delegated authority only, require a business authorization document naming
the delegate and scope, linked to the business and entitlement, plus independent
verification of the authorizing person's authority and the delegation chain.
Its exact form and execution procedure need separate acceptance. During
recovery-time enrollment, the delegation instrument and authorizing relationship
must satisfy the same pre-case provenance and current-validity rules above;
creating a new delegation inside the case cannot bootstrap authority. A signature
or purchase payment alone is insufficient. In both authority paths, retain the
provenance of the independent evidence and contact route. If that chain cannot
be established, enrollment is not qualified and recovery remains blocked.

No enrollment record or contact is claimed to exist today. Before executable
work, Juan, the appointed record owner, must decide the storage location and
propose how to create the new system, independently check
business authority and enroll the representative; the licensing owner must adopt
the resulting policy, and Juan must accept the concrete source and procedures.
The concrete procedure must specify supported business forms and authority bases,
independent evidence sources, how identity is bound to current business authority,
and how source authenticity, revisions, expiry and withdrawal are checked. It
must cover own authority and delegated authority explicitly. Neither method is
selected or qualified by this amendment. Unsupported business forms, absent
accepted methods or unclear authority remain blocked, not guessed from a job
title, email domain or public listing. Sole-authority status alone is not an
unsupported business form. Apart from the proposed delegation document above,
no document template, government-ID upload or external identity vendor is selected.

For each recovery request, the licensing verifier must:

1. Load the current enrollment and authority basis from its authoritative store,
   independently of fields submitted by the requester. If no enrollment exists,
   complete the recovery-time enrollment procedure above first; do not interpret
   missing required history from an existing enrollment as a new enrollment.
   Match the exact business and entitlement lineage against licensing's consumed
   deployment.
2. Authenticate the requester with their enrolled credential and a fresh,
   single-use challenge bound server-side to the case revision, policy revision,
   predecessor receipt digest and exact replacement target digest. A credential
   proves continuity with enrollment, not business authority by itself.
3. Independently verify the representative's current business authority under
   the accepted procedure for their enrolled authority basis. The licensing
   verifier must be distinct from the requester and use the procedure's
   independently corroborated sources, not treat the requester's own assertion
   as proof. For own authority, verify that the identified requester currently
   holds that authority. For delegated authority, also verify the current
   authorizing authority and delegation chain. Record the evidence source and
   revision, authority basis and scope, verification method, verifier, time and
   result. A record holder's custody alone is not authority evidence; an
   enrollment-record owner or custodian may perform verification only if assigned
   the verifier role, distinct from the requester, and applying the same accepted
   evidence procedure. They cannot supply a substitute attestation merely because
   they hold the records.

   Initiate the required business contact through the pre-established route,
   never a replacement route supplied in recovery. Contact with a sole owner is
   permissible, but possession of the route, credential or a signed self-assertion
   is insufficient, individually or together, to establish business authority.
   Confirmation by another business-side authority may be evidence under the
   accepted procedure if that person's authority and scope were independently
   established; it is not universally required. Naming a bookkeeper, agent or
   contact does not itself establish that authority. Missing accepted evidence
   sources or methods, missing provenance, ambiguity, disagreement, an
   unresponsive required contact or unavailable current authority status blocks
   verification. A sole-authority business with qualified enrollment and
   independently verified current authority can obtain a verification result
   under these same rules; that result still does not approve recovery.
4. Write a case-bound verification record with the enrollment/authority and
   policy revisions, authoritative-source references, exact target binding,
   verifier identity and expiry. Recheck current versions and revocation before
   any later affirmative approval; a stored successful check is not permanent
   authority. Missing required stored history is corruption STOP.

Proposed freshness bounds: the authority confirmation expires 24 hours after
completion; a credential challenge expires after 5 minutes. Equality at expiry
is expired. Changing any bound case/target/policy/enrollment field invalidates
pending confirmation. These are proposed product limits, not standards claims.
Role withdrawal, credential revocation or a source revision change invalidates
the result immediately even inside its time window. Unavailable authoritative
status blocks approval; cached data cannot assert that no revocation occurred.

Representative changes and lost credentials require the separately accepted
enrollment/re-enrollment procedure, using the same independent verification and
pre-case source/contact requirements when performed during recovery. A new key is
registered only after that verification, through the bound ceremony above. Keep
the old enrollment and revocation history; invalidate pending verification and
never overwrite withdrawn authority or reinterpret corrupt history as absence.
Neither support email nor the recovery administrator may bypass missing
provenance or assign themselves as the business representative. No credential
enrollment or re-enrollment happens in this slice.

## Recommended licensing administrator channel

Use a dedicated, private licensing administration web application with an
explicit origin and relying-party identity, separate from customer application
and licence-acquisition surfaces. Select no host, domain, vendor or deployment
here. Under the ownership split above, the licensing owner is proposed to control
its server-side account/role registry and decision-audit writer; the operator
must explicitly approve its initial administrator roster and enrollment
ceremony. No public self-signup, shared administrator account,
customer-token promotion or client-supplied role is permitted.

For licensing administrators, require personally enrolled, user-verifying roaming
hardware credentials. Before enabling the initial roster, each administrator
must register and verify at least two credentials on distinct physical security
keys, with the spare stored separately. Two registrations on one key do not meet
the spare requirement. This supports a single operator; it does not require a
second administrator or a shared account. Platform and synced credentials remain
outside the administrator profile.

For business representatives, permit any user-verifying WebAuthn passkey usable
independently of the deployment being recovered: a roaming key, a synced passkey
available on another device, or a phone passkey. Reject a credential whose only
usable copy is bound to the failed deployment. A label such as "synced" or a
client-supplied device claim alone does not establish independent availability.
The later authentication work order must qualify an actual registration and
assertion path independent of the failed deployment, require and verify user
verification, and establish the identity/enrollment binding. A customer need not
buy a hardware key if a qualifying passkey is available. No administrator hardware
restriction is relaxed by this representative profile.

The later authentication work order must specify and qualify both profiles; a
browser attachment preference alone cannot prove hardware custody or independence
from a deployment. No authentication implementation or security-key purchase is
authorized. Native sign-in and Hello remain on hold; permitting a future customer
passkey profile does not authorize a native or Hello probe.

Use the standard registration and assertion verification procedures, including
expected origin, RP identity, challenge, signature and required user verification,
through a maintained verifier selected in the later work order. WebAuthn does
not establish the holder's business role; enrollment and current business
authority remain separate checks. See [W3C WebAuthn registration](https://www.w3.org/TR/2021/REC-webauthn-2-20210408/#sctn-registering-a-new-credential)
and [assertion verification](https://www.w3.org/TR/2021/REC-webauthn-2-20210408/#sctn-verifying-assertion).

Proposed administrator sessions expire after 12 hours absolute or 15 minutes
idle, whichever comes first. This removes both the unsupported five-minute idle
cutoff and the blanket 15-minute absolute cap; the latter would interrupt active
manual verification without adding decision-specific authentication. The proposed
bounds use the overall limit and inactivity recommendation in
[NIST SP 800-63B-4, AAL3 reauthentication](https://pages.nist.gov/800-63-4/sp800-63b/aal/#aal3reauth).
This is a timeout reference, not a claim that this unimplemented channel meets
AAL3. Activity never extends the absolute ceiling. Approval still requires a new
single-use authentication ceremony tied to that
exact decision, completed within 5 minutes of commit. Equality at either session
limit or the approval-ceremony expiry is expired. An open page does not keep
authority alive.
Each write derives the actor from the authenticated session, enforces its
server-side role and business scope, and revalidates after the writer wait.

Separate permissions for recording verification, approving recovery, and
maintaining administrator enrollment. A verifier may also be an approver if
explicitly assigned both roles, but cannot approve their own customer recovery
request. Role administration cannot grant the actor their own additional scope.
Roster changes require the separately accepted operator-controlled enrollment
procedure, not approval rights. If one key is lost, the remaining enrolled key
can authenticate the administrator under the existing role and enrollment rules;
revoke the lost credential and restore the separately stored spare through the
accepted procedure. No emergency password/email fallback is proposed: if all
authorized administrator credentials are lost, writes stop until that procedure
restores administration. Preserve operator console access; do not deploy access
restrictions before its recovery path is accepted and qualified.

The approval owner must serialize permission, enrollment and policy revisions
with the approval commit, using the same durable authorization boundary or a
specified fencing protocol. A remote check followed by an unguarded local write
is insufficient. Revocation and approval must have an explicit order: revocation
committed first prevents approval; approval committed first remains historical
and cannot grant fresh effects after revocation. The later storage/wire contract
must prove that ordering; no cross-service atomicity is claimed here.

The channel must also enforce authenticated state-changing requests, request
origin/CSRF protection, exact operation binding and replay prevention at the
server. No approval through GET, email links, a browser flag, support-ticket
status or an unsigned import. Runtime schemas and one semantic owner will enforce
the accepted fields and bounds; this prose proposal adds no alternate validator.

## Private records, audit and deletion boundary

Keep independent authority evidence, delegation documents where required, contact
details and human verification notes in the enrollment-record owner's proposed
external record store. Limit access to assigned verifiers and explicitly
authorized records custodians; an approver sees the necessary result/provenance,
not unrestricted source documents. No raw record,
identity document, credential secret, session token or contact detail enters a
Lead Intake packet, entitlement, PR, log or model prompt. Opaque references and
hashes are still access-controlled, not treated as public anonymization.

Keep the recovery lineage and decision audit immutable while authority or any
replacement derived from it remains in use. Source-material retention is a
separate policy, proposed below. Before executable work, the record owner must
supply the actual record obligations, accepted schedule and backup handling.
No cleanup job or permanent retention claim is authorized.
Authorized source deletion records a tombstone and provenance digest; it never
frees a consumed deployment. If required verification material is unavailable,
future approval blocks. A missing lineage/audit row is STOP, not routine deletion.

### Proposed source-retention schedule

Juan requested a default within 30–90 days with customer choice; this amendment
recommends **30 days from receipt for each retained source copy**. The exact
default, start event and rules here are proposed for review, not an already
accepted or legally qualified US-wide schedule. Record the receipt time and
effective policy revision. Reading, reviewing, opening a recovery case or
restoring a backup does not restart that clock. Verification still pending at
expiry does not silently extend it; new independent evidence may be needed.

The business's currently authorized representative can choose a shorter or
longer duration for its source copies through the authenticated business-scoped
channel. No 30-day minimum or 90-day maximum is inferred from the suggested
default range. Zero means no persistent source copy, using transient verification
or references where the qualified method supports that; it does not mean retain
forever or use a fallback default. A method needing a retained copy must state
the exact need and investigate a lighter alternative, not categorically exclude
the business. No silent coercion of a valid customer choice is permitted.

Make each change explicit about existing copies and future collection. Shortening
for existing copies makes already-overdue copies due immediately. An explicit
extension may update a still-retained copy, but cannot recreate deleted bytes.
Serialize setting changes with deletion and report which operation took effect;
if deletion won, an extension cannot claim to restore the copy or undo its
tombstone. A future form must show the effective expiry and the
scope of the change before saving it. Record who changed it and which revision
applies. An unauthenticated caller, another business or a revoked representative
cannot change this policy. This uses the canonical role boundary, not a new
credential or second-person approval requirement.

The setting must say plainly: **this duration governs raw source copies only**.
Both the setting surface, before saving, and every deletion receipt must list
each other retained class below: minimal enrollment/current-authority records,
consumed-deployment lineage/decision audit, and any remaining source-copy backups.
For each, show what remains, its concrete retention basis and its end condition
(or the backup's actual expiry), including when the selected source duration is
zero. Distinguish a class with no remaining records from one still retained.
Zero or completed source deletion must not be presented as deletion of all
business records. The selected operating policy must supply the unresolved
retirement/end conditions before real use; a generic "required records remain"
notice does not fulfill this disclosure or justify retention.

Use the following record classes; do not implement one account-wide TTL:

| Record class | Proposed handling |
| --- | --- |
| Raw source copies, including optional identity/delegation documents and captured source responses | Customer-configurable default above, subject only to a specifically established obligation for that record. Prefer independent references/minimal facts when sufficient; no universal ID copy. |
| Minimal enrollment/current-authority record | Retain only facts and provenance needed to manage current authority: opaque record/binding references, authority basis/scope, method and source revision, observation/verifier provenance, credential-registration reference and current withdrawal/supersession state. Contact and identity details stay external and are limited to the qualified method's needs. No document text disguised as audit metadata. |
| Consumed-deployment lineage and decision audit | Preserve original identifiers, association revisions and authorization/deletion decisions while authority or a derived replacement remains in use, as above. Source expiry cannot make consumption available. Retirement and eventual deletion require a separately specified condition proving this history no longer supports active authority; this is not a blanket forever policy. |
| Source-copy backups | Cover each copy in the custody inventory with a finite, disclosed expiry. Restrict ordinary access after primary expiry and reapply current deletion tombstones before any restore is exposed. Customer-visible deletion status distinguishes primary deletion from remaining backup expiry; do not claim immediate physical erasure of all copies. |

Juan owns deletion operations; the customer controls the source-copy preference.
On expiry, prevent further ordinary reads, delete through the store's supported
object API, and record completion or retryable failure without copying the
source into logs. Do not mark deletion complete on a failed/missing response.
Concurrent verification must recheck required-source availability at decision
commit; a stale open document cannot supply current evidence. Where a qualified
method can independently retrieve fresh evidence, use it and record new
provenance; deletion is not permanent ineligibility. Corrupt required history
remains STOP, not a cue to rebuild it as a new enrollment.

The selected custody plan must state the actual backup expiry bound and restore
procedure before collection. No provider-independent number is invented here.
If a selected source/jurisdiction imposes a conflicting obligation, record its
authority, affected record class, duration and customer-visible effect; justify
why a minimal reference or different evidence method cannot meet it. Do not
infer a nationwide legal minimum or indefinite hold from a generic compliance
label. The all-50-state target requires coverage research, not an extra document
from every customer.

The later schema owns non-negative duration and explicit zero semantics, UTC
instants, closed record classes and required policy revisions. Reject booleans,
empty strings and malformed values rather than defaulting them to 30. The one
retention owner computes expiry; the transactional writer enforces revisions,
authorization and deletion ordering. The same owner schedules pending source
records under the [custody creation order](LEAD-OWNER-ENROLLMENT.md#source-object-creation-and-reconciliation);
upload finalization never starts a second retention clock. This prose does not
add an executable schema, scheduler or source-cleanup implementation.

## Approval remains a separate decision

Verified business authority and a valid administrator session satisfy only their
respective prerequisites. The approval owner must still require determined
predecessor consumption, exact case/target binding, qualified old-host retirement
and fresh replacement native proof under the accepted recovery requirements.
Unreachable predecessors stay blocked under [issue 84](https://github.com/canfieldjuan/connect-automate/issues/84).
There is no ordinary-lead-operation licensing polling or background revocation
dependency. Business verification cannot repair the old-disk rollback problem.

The channel records a decision; it does not mint an executable recovery token or
publish a replacement administrator. Those require the separately accepted wire,
qualified host mechanism and explicit execution authority. Existing evidence
admission remains `EVIDENCE_RECORDED_ONLY`, and synthetic proofs remain
`OFFLINE_CONFORMANCE` with `qualification_pass=false`. Device replacement and
inaccessible-disk cases remain `BLOCKED`; native cases remain `NOT_RUN`.

## Why the retained restrictions are needed

The asset is a business's deployment authority, not possession of its licence.
The existing [offline fixture](../../qualification/owner_authority/licensing_fixture.py)
checks consumed bindings and receipts in `_recovery_predecessor`, preserves
corruption STOP in `_recovery_case`, and has no real business-identity verifier or
administrator session. The [approval requirements](LEAD-OWNER-RECOVERY-APPROVAL.md)
separate those missing owners from host retirement and publication. The reasons
below apply to the proposed channel; they do not claim those controls exist.
The customer is often the only business authority, and the licensor may have one
operator. No restriction below requires another business owner or another operator.

| Retained rule | Exclusion or cost | Concrete need; why the lighter rule is insufficient |
| --- | --- | --- |
| Independently establish identity, current authority and exact business/entitlement; verifier distinct from requester; no self-approval | Manual verification and waiting; a requester cannot verify or approve their own case. | Prevent takeover of another business's consumed deployment. Credentials, receipts and self-assertions establish neither current business authority nor an independent decision. One licensing operator may verify and approve a customer's case; a second business authority is unnecessary. |
| Independent pre-case authority/contact provenance for recovery-time enrollment, followed by current checks and verifier-initiated contact | Customers without independently recoverable provenance remain blocked; contact takes time. | Prevent an attacker from supplying both the proposed identity and its own confirmation route during the case. A current lookup alone cannot bind the person holding the new key to the existing business/entitlement. Existing qualified enrollment or independently obtained historical evidence supplies that link; prior enrollment itself is not mandatory. No route or source is accepted merely because it exists in a public listing. |
| Delegation instrument only for delegated authority | Delegates need a document establishing their scope; owners do not. | An employer/owner's identity does not establish a delegate's permission to move deployment authority. The accepted instrument can be an existing valid authorization; a new bespoke form is not universally required. A delegate's job title or own statement cannot establish the grant. |
| Complete verified enrollment and bound registration before using a new credential; preserve revisions and withdrawn/corrupt history | Registration or re-enrollment is an extra step; missing historical integrity blocks recovery. | A new key otherwise authorizes itself, and a missing record could reset an existing consumed lineage. Credential possession alone or recreating a record on error cannot preserve the original authority chain. Recovery-time enrollment supplies the needed path without requiring the dead PC's credential. |
| Customer passkey requires user verification and availability independent of the failed deployment | A customer needs a usable independent authenticator; no mandatory hardware purchase. | A failed PC cannot perform the recovery ceremony, and possession without user verification lets a lost unattended authenticator stand in for the person. A phone, synced copy on another device or roaming key meets the need; hardware-only custody for customers does not. |
| Individually enrolled administrator hardware keys, two distinct keys with separately stored spare; no shared account or self-assigned role | The operator buys and safeguards primary and spare keys and uses an approved roster procedure. | This role can move authority across customers and handle verification records. Hardware custody limits credential copying after account/device compromise; a synced credential does not provide that non-exportability boundary. Distinct keys avoid a single lost/broken key locking out the only operator. Two credentials on one device share the same failure, while requiring two operators excludes the actual operating model. |
| Authority confirmation at most 24 hours old; current source/revocation checks still mandatory | A delayed case may require another manual confirmation. | No qualified change-notification service exists for human authority evidence. A stored confirmation cannot certify indefinitely that the role/contact remains current. A one-day maximum age bounds reliance on that manual observation; relying solely on the absence of a recorded revocation would assume a missing notification service. This is a proposed freshness budget, not proof that a one-day-old observation is sufficient. Current evidence must also pass. |
| Single-use case-bound credential challenge and decision ceremony, each at most 5 minutes old | A delayed ceremony must restart. | Bound the usable life of an abandoned authentication result while an attacker tries to substitute a case or target. Single-use prevents a second use but not a delayed first use; binding prevents cross-target use but not stale presence. Five minutes is the proposed ceremony budget, not a measured guarantee. It does not cap the preceding manual investigation. |
| Administrator session at most 12 hours overall and 15 minutes idle, with fresh authentication for approval | Reauthenticate after inactivity or a long working session. | Bound unattended access and long-lived session theft. Idle timeout alone permits an attacker to keep a stolen session active indefinitely; an overall limit alone leaves an unattended session usable for hours. The cited NIST bounds supply the reference profile; the shorter blanket cap adds interruption without protecting the exact approval better. |
| Server-derived actor/scope, origin protection, exact decision binding, serialized revisions and revocation, one selected target | No unsigned import or email-link approval; competing decisions wait or fail. | Prevent forged roles, request substitution, revoked authority winning a writer race and duplicate replacement targets. A prior check followed by an unguarded write or a browser flag does not enforce the licensing writer's decision. The existing consumed-binding/corruption owners illustrate why caller claims cannot replace authoritative state. |
| No password/email/support bypass; all administrator keys lost means restore through the accepted enrollment procedure | Losing both keys stops writes until administration is restored. | An easier fallback would let an attacker bypass the privileged credential and roster boundary. A tested spare handles ordinary single-key loss; full loss requires restoring that same authority boundary, not asserting a support role. No permanent lockout or second-person requirement is introduced. |
| External restricted identity records, opaque references, protected audit history and explicit source-retention policy | Custody, access control, backup/restore and retention work for the named owner. | Source identity material must not spread through licences, logs, CI or model prompts; the proposed licence service has no identity store. Audit history is required to distinguish authorized deletion from corrupt consumption. Hashes alone cannot replace unavailable authority evidence; unrestricted copies or deleting lineage on cleanup defeat those boundaries. No indefinite source-retention duration is imposed. |
| Separate source-copy expiry from active authority/consumption history | Some minimal binding/audit facts remain beyond the customer's document-copy duration. | The existing recovery relation and consumed-state rules need original identifiers and withdrawals to avoid duplicate authority or false availability after cleanup. Longer retention of original documents is unnecessary for that purpose; deleting both classes loses the boundary. Keep only necessary facts and specify retirement before eventual removal. |
| Customer settings use authenticated business scope and serialized deletion handling | Authorized changes require the existing channel; deleted copies cannot be resurrected by an extension. | A cross-business or revoked actor could destroy another customer's proof, and a race/restore could silently retain private material contrary to the effective policy. A UI-only check or deleting metadata alone cannot enforce the boundary. Existing role controls, structured policy revisions and supported object deletion are sufficient; no second approver is needed. |
| Determined consumption, qualified predecessor retirement, fresh replacement proof and separate executable authorization | A dead/unreachable predecessor can still block publication even after successful business verification. | The current local-first host cannot prove an old disk image lost its authority merely because licensing approved a replacement. A signature or support decision does not fence the old host. Issue 84 owns the missing enforcement/product decision; this contract cannot disguise that gap. No ordinary-operation polling is introduced because it would change offline operation rather than prove the existing boundary. |
| Concrete methods, owner/custody and qualification before execution; native/live holds | This contract alone cannot perform recovery or collect real evidence. | Current code supplies synthetic evidence only. A fixture flag or accepted prose cannot authenticate a real business or retire a real host. The separately reviewed execution work order must provide those actual owners and proofs; the holds preserve Juan's explicit scope. |

## Acceptance examples and exit gates

These are future proof obligations, not executed tests:

| Case | Required outcome |
| --- | --- |
| Qualified enrollment, fresh enrolled-key proof, independently verified current own authority or delegation chain under an accepted method, same business/entitlement and target | One case-bound verification result; no automatic recovery approval or host write. |
| Licence, paid invoice, receipt, email, installer privilege or synthetic retirement packet alone | No business-verification success. |
| Existing customer without prior enrollment; verifier independently obtains pre-case authority sources and contact route, confirms current identity/authority/binding, records enrollment and completes bound credential registration | May proceed to the same fresh challenge and verification checks; no automatic recovery approval. |
| Missing independent authority evidence; only a new contact/key supplied in recovery; unsupported evidence method or business form | Block; no requester-supplied trust-root substitution. |
| Claimed pre-case source with no provenance, newly created delegation or contact route inside the case, or current authority withdrawn | Block recovery-time enrollment; historical existence alone is insufficient. |
| Existing enrollment with missing required history, presented as a first-time enrollment | Corruption STOP; do not bootstrap a replacement record. |
| Owner acting under independently verified own authority, with no signed self-authorization document | Admit that authority basis without the document; all other enrollment and recovery checks still apply. |
| Delegate without the required authorization document or with an unverified authorizing chain | Block; the owner's paperwork exemption does not apply to delegated authority. |
| Sole-authority business meeting the preceding qualified-enrollment, credential, independent current-authority and binding requirements | Eligible for the same verification result without a second business authority; all separate recovery approval gates still apply. |
| Sole-authority enrollment but no accepted independent verification method for that authority basis, or only self-assertion, route/key possession and a signed authorization | Block verification; eligibility and these items together do not establish authority. |
| Delegated representative with a missing or withdrawn authorizing authority or delegation link; named contact or custodian offered as authority without independent evidence | Block verification; neither a second person's presence nor custody substitutes for the authority chain. |
| Valid credential but withdrawn own authority or delegation, wrong entitlement, stale or mixed-validity evidence | No approval; credential possession does not rescue a failed authority check. |
| Representative uses a user-verifying phone, synced or roaming passkey through a qualified path independent of the failed deployment | Accept the credential profile; current business authority and exact case binding remain required. |
| Representative credential usable only on the failed deployment, no user verification, or only an unsupported claim of independent availability | Refuse authentication; no profile-label bypass. |
| Initial administrator roster has one key, or two credentials on the same physical key | Do not enable administration until distinct primary and spare keys are registered and verified. |
| Administrator loses one of the separately stored enrolled keys | Remaining key can authenticate under existing roles; revoke the lost key and restore the spare through the accepted procedure. No fallback or additional scope. |
| Administrator is idle beyond 5 but below 15 minutes, or active beyond 15 minutes but below 12 hours absolute | These elapsed times alone do not expire the session; decision-specific authentication and all role checks still apply. |
| Administrator reaches 12 hours absolute or 15 minutes idle, or approval ceremony reaches 5 minutes | Expired; activity cannot extend the absolute ceiling or rescue the decision ceremony. |
| Exact expiry, future confirmation time, zero/empty/false bounds or missing required fields | Refuse; no fallback to a permissive default. Numeric and temporal bounds belong to the future closed schema and semantic owner. |
| Forged actor/role, wrong origin, replayed challenge, expired session, wrong target or requester approving own recovery | No privileged write; server-owned identity and binding control the decision. |
| Permission or enrollment revoked while approval waits for the writer | Revalidate under serialized authorization ordering; revocation before commit prevents approval. |
| Lost reply or two concurrent decisions for different replacements | Existing exact retry/one-selected-target rules; preserve history, never duplicate approval or overwrite the target. |
| Valid business and admin checks, but unreachable predecessor or absent native/retirement qualification | Block replacement; no exemption from issue 84. |
| Missing source after authorized deletion versus damaged required audit lineage | Block new verification for unavailable source; STOP for corrupt lineage; neither makes consumption available. |
| Default receipt-based expiry, shorter/longer customer setting, zero, and a value above 90 days | Default is 30 days; valid choices are honored without an inferred 30–90 bound. Zero persists no source copy; no falsy fallback. Method-specific obligations must be explicit. |
| Zero selected, or positive duration expires while minimal authority/lineage records or backups remain | Setting and deletion receipt both identify the raw-copy-only scope and each retained class, its basis and end condition/backup expiry. Show absent classes accurately; never claim all records were deleted. |
| Boolean, empty string, missing required policy revision or mixed valid/invalid policy fields | Closed schema rejects malformed policy; no partial application or fallback duration. |
| Shortening an existing copy past its due time; extension before, at or after expiry | Due immediately on shortening; explicit extension can update a retained copy. If deletion wins the serialized race, no false restoration or undone tombstone. Check both operation orders and exact expiry. |
| Verification still open at expiry; deletion fails; stale backup restored after deletion | No clock reset or silent extension, no false completion; unavailable required evidence blocks decision until valid evidence exists. Restore reapplies tombstones and reports remaining backup expiry accurately. |
| Customer changes another business's policy or uses a withdrawn role | Reject under current business/role authorization without changing either policy. |

The proposed [enrollment, evidence and custody work order](LEAD-OWNER-ENROLLMENT.md)
develops the concrete inputs below. It does not establish an existing record
system or a qualified evidence method, and this policy remains their owner.

Before an executable work order can be accepted, Juan, the appointed
enrollment-record owner, must decide the external storage location and
supply the new enrollment-system design, concrete independent authority-check
methods and sources for own authority and delegation, representative
credential-enrollment procedures, and retention schedule. The later qualification
must demonstrate both prior and recovery-time enrollment, the owner without
self-authorization paperwork, delegated authority with its instrument, and the
independent-device passkey and administrator-spare cases. It must reject the
self-assertion-only, unsupported-method, broken-chain, requester-key substitution
and corrupt-history cases above; this contract supplies no such execution
evidence. The licensing owner must adopt the verification policy and supply its
administrator enrollment and recovery procedures, roster and channel design under
the ownership split above.
Juan must accept those concrete inputs. A later work order must pin the
authentication implementation and profile enforcement, closed wire/storage
models, atomic permission ordering and
qualification plan. No undeclared provider, trust root or policy placeholder may
be replaced with a fixture flag and called real verification.

Juan's exact acceptance of this amendment must cover sole-authority eligibility,
independently verified enrollment before or during recovery, authorization
paperwork only for delegation, the separate customer/administrator credential
profiles, two physical administrator keys and the revised session timeouts. These
changes retain independent identity/current-authority verification, pre-case
source and contact provenance for recovery-time enrollment, freshness/revocation
and blocked fallback behavior. Costs remain: the external record system, manual
verification, administrator hardware keys and spare custody, and recovery delays.
A representative's hardware-key purchase and an owner's self-authorization
paperwork are not mandatory costs. Concrete evidence methods, registration and
re-enrollment procedures, and independent-device authentication still need
acceptance and qualification; their availability and cost are unresolved.
Eligibility alone enables no recovery. Acceptance of this amendment selects no
concrete source or provider and does not authorize execution.

Submit this exact contract revision to independent oversight; then obtain Juan's
exact-revision acceptance before merge. Implementation, synthetic fixture runs,
account provisioning and any native/live qualification need separate explicit
authorization under accepted work orders. Native sign-in, Hello, Gmail and live
activation remain on hold.
