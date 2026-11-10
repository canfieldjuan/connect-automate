# Business-verification policy and licensing administrator channel proposal

Status: **PROPOSED; CONTRACT ONLY.** Juan authorized drafting and oversight
submission. This is a Lead Intake recommendation for the licensing owner to
adopt, not a claim that licensing supplied or implemented this policy. It needs
independent oversight and Juan's exact-revision acceptance before merge. Neither
acceptance nor merge provisions an account, enrolls a business, generates keys,
collects customer evidence or authorizes implementation.

Pending amendment to the accepted proposal at
`f219d016577d737676bdbc0338cef025e3a07fbc`: remove categorical exclusion of
sole-authority businesses. Independent verification of business authority remains
required; confirmation by a second business authority is no longer a universal
prerequisite. This amendment needs its own exact-revision acceptance and does
not inherit acceptance from that earlier revision.

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

This amendment changes only this proposal; the approval work order is unchanged.
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
**enrollment-record owner** means the accountable owner Juan must name; that
owner and the storage location remain open decisions. This owner would create
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

Deliberate departure: recommend a pre-enrolled-representative policy and a
dedicated administrator channel, with the restrictions and costs below. These
are proposed product choices, not established behavior or automatic extensions
of the entitlement service. Later executable work must inventory its actual
owners, list all differences and preserve existing offline proof parity.

## Recommended initial policy: pre-enrolled business representatives

Support recovery only after the enrollment-record owner creates and verifies
the business-authority enrollment through a separately accepted enrollment step,
before any recovery case. An existing demo, subscription, paid invoice or
offline licence alone is ineligible. No just-in-time enrollment or contact/key
replacement may be admitted through an open recovery case. This deliberately leaves
legacy businesses without qualified enrollment blocked until a separately
accepted enrollment process supplies the prerequisite.

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

The proposed authority source must be created during that enrollment step: a
business authorization naming the representative, their authority basis and
scope, and linking the business and entitlement, plus evidence of how the
representative's identity and business authority were independently established.
For delegated authority, this includes the authorizing person's independently
verified authority and the delegation chain to the representative. For own
business authority, this includes independent evidence that the identified
representative holds that authority; self-delegation or appointing a second
person is not required and cannot substitute for that evidence. The executed
business authorization is a **new enrollment-time document requirement proposed here**;
no existing commercial agreement or authorization is presumed. Its exact form
and execution procedure require separate acceptance before enrollment is enabled.
A signature on a document or a purchase payment alone is insufficient. The
record must include the provenance of the independent authority evidence, the
verified authority basis and an independently obtained business contact route,
not merely data supplied by the later recovery requester. If that chain cannot
be established, enrollment is not qualified and recovery remains blocked.

No enrollment record or contact is claimed to exist today. Before executable
work, Juan must name the enrollment-record owner and decide the storage location.
That owner must propose how to create the new system, independently check
business authority and enroll the representative; the licensing owner must adopt
the resulting policy, and Juan must accept the concrete source and procedures.
The concrete procedure must specify supported business forms and authority bases,
independent evidence sources, how identity is bound to current business authority,
and how source authenticity, revisions, expiry and withdrawal are checked. It
must cover own authority and delegated authority explicitly. Neither method is
selected or qualified by this amendment. Unsupported business forms, absent
accepted methods or unclear authority remain blocked, not guessed from a job
title, email domain or public listing. Sole-authority status alone is not an
unsupported business form. Apart from the proposed new business authorization
above, no document template, government-ID upload or external identity vendor is
selected.

For each recovery request, the licensing verifier must:

1. Load the current enrollment and authority basis from its authoritative store,
   independently of fields submitted by the requester. Match the exact business
   and entitlement lineage against licensing's consumed deployment.
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
enrollment/re-enrollment procedure. The old enrollment remains in history;
pending verification is invalidated. Neither support email nor the recovery
administrator may bypass missing provenance or assign themselves as the business
representative. No credential enrollment or re-enrollment happens in this slice.

## Recommended licensing administrator channel

Use a dedicated, private licensing administration web application with an
explicit origin and relying-party identity, separate from customer application
and licence-acquisition surfaces. Select no host, domain, vendor or deployment
here. Under the ownership split above, the licensing owner is proposed to control
its server-side account/role registry and decision-audit writer; the operator
must explicitly approve its initial administrator roster and enrollment
ceremony. No public self-signup, shared administrator account,
customer-token promotion or client-supplied role is permitted.

Propose personally enrolled, user-verifying roaming hardware credentials for
both this administrator channel and representative authentication. Platform
credentials, Hello and synced credentials are outside the initial profile.
The later authentication work order must specify and qualify how this profile
is enforced; a browser attachment preference alone cannot prove hardware
custody. No authentication implementation or security-key purchase is authorized.

Use the standard registration and assertion verification procedures, including
expected origin, RP identity, challenge, signature and required user verification,
through a maintained verifier selected in the later work order. WebAuthn does
not establish the holder's business role; enrollment and current business
authority remain separate checks. See [W3C WebAuthn registration](https://www.w3.org/TR/2021/REC-webauthn-2-20210408/#sctn-registering-a-new-credential)
and [assertion verification](https://www.w3.org/TR/2021/REC-webauthn-2-20210408/#sctn-verifying-assertion).

Proposed administrator sessions expire after 15 minutes absolute or 5 minutes
idle, whichever comes first. Approval requires a new single-use authentication
ceremony tied to that exact decision, completed within 5 minutes of commit.
Equality at either limit is expired. An open page does not keep authority alive.
Each write derives the actor from the authenticated session, enforces its
server-side role and business scope, and revalidates after the writer wait.

Separate permissions for recording verification, approving recovery, and
maintaining administrator enrollment. A verifier may also be an approver if
explicitly assigned both roles, but cannot approve their own customer recovery
request. Role administration cannot grant the actor their own additional scope.
Roster changes require the separately accepted operator-controlled enrollment
procedure, not approval rights. No emergency password/email fallback is proposed:
if all authorized administrator credentials are lost, writes stop until that
procedure restores administration. Preserve operator console access; do not
deploy access restrictions before its recovery path is accepted and qualified.

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

Keep enrollment-time business authorization, contact details and human
verification notes in the enrollment-record owner's proposed external record
store. Limit access to assigned verifiers and explicitly authorized records
custodians; an approver sees the
necessary result/provenance, not unrestricted source documents. No raw record,
identity document, credential secret, session token or contact detail enters a
Lead Intake packet, entitlement, PR, log or model prompt. Opaque references and
hashes are still access-controlled, not treated as public anonymization.

Keep the recovery lineage and decision audit immutable while authority or any
replacement derived from it remains in use. Source-material retention is a
separate policy: this proposal intentionally sets no deletion duration without
the enrollment-record owner's actual record obligations. Before executable work
that owner must supply an accepted retention/access schedule, deletion owner and
backup handling. No cleanup job or permanent retention claim is authorized.
Authorized source deletion records a tombstone and provenance digest; it never
frees a consumed deployment. If required verification material is unavailable,
future approval blocks. A missing lineage/audit row is STOP, not routine deletion.

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

## Acceptance examples and exit gates

These are future proof obligations, not executed tests:

| Case | Required outcome |
| --- | --- |
| Qualified pre-enrollment, fresh enrolled-key proof, independently verified current own authority or delegation chain under an accepted method, same business/entitlement and target | One case-bound verification result; no automatic recovery approval or host write. |
| Licence, paid invoice, receipt, email, installer privilege or synthetic retirement packet alone | No business-verification success. |
| Record with no independently established authority basis; new contact/key supplied in recovery; unsupported business form | Block; no enrollment or trust-root substitution inside recovery. |
| Sole-authority business meeting the preceding qualified-enrollment, credential, independent current-authority and binding requirements | Eligible for the same verification result without a second business authority; all separate recovery approval gates still apply. |
| Sole-authority enrollment but no accepted independent verification method for that authority basis, or only self-assertion, route/key possession and a signed authorization | Block verification; eligibility and these items together do not establish authority. |
| Delegated representative with a missing or withdrawn authorizing authority or delegation link; named contact or custodian offered as authority without independent evidence | Block verification; neither a second person's presence nor custody substitutes for the authority chain. |
| Valid credential but withdrawn own authority or delegation, wrong entitlement, stale or mixed-validity evidence | No approval; credential possession does not rescue a failed authority check. |
| Exact expiry, future confirmation time, zero/empty/false bounds or missing required fields | Refuse; no fallback to a permissive default. Numeric and temporal bounds belong to the future closed schema and semantic owner. |
| Forged actor/role, wrong origin, replayed challenge, expired session, wrong target or requester approving own recovery | No privileged write; server-owned identity and binding control the decision. |
| Permission or enrollment revoked while approval waits for the writer | Revalidate under serialized authorization ordering; revocation before commit prevents approval. |
| Lost reply or two concurrent decisions for different replacements | Existing exact retry/one-selected-target rules; preserve history, never duplicate approval or overwrite the target. |
| Valid business and admin checks, but unreachable predecessor or absent native/retirement qualification | Block replacement; no exemption from issue 84. |
| Missing source after authorized deletion versus damaged required audit lineage | Block new verification for unavailable source; STOP for corrupt lineage; neither makes consumption available. |

Before an executable work order can be accepted, Juan must name the
enrollment-record owner and decide the external storage location. That owner must
supply the new enrollment-system design, concrete independent authority-check
methods and sources for own authority and delegation, representative
credential-enrollment procedures, and retention schedule. The later qualification
must demonstrate the positive sole-authority and delegated cases and reject the
self-assertion-only, unsupported-method and broken-chain cases above; this
contract supplies no such execution evidence. The licensing owner
must adopt the verification policy and supply its administrator enrollment and
recovery procedures, roster and channel design under the ownership split above.
Juan must accept those concrete inputs. A later work order must pin the
authentication implementation and profile enforcement, closed wire/storage
models, atomic permission ordering and
qualification plan. No undeclared provider, trust root or policy placeholder may
be replaced with a fixture flag and called real verification.

Juan's exact acceptance of this amendment must cover removing the categorical
sole-authority exclusion while retaining independent identity and current
business-authority verification. Pre-enrollment, the enrollment-time authorization
document, credential requirement, session/freshness bounds and blocked fallback
behavior remain required. Costs remain: creating and operating the enrollment
system, hardware credentials, manual independent verification and recovery
delays. Supporting sole-authority businesses requires a concrete accepted and
qualified evidence method; its availability and cost are still unresolved. Some
businesses will remain blocked until their enrollment and verification method
are qualified. No second business authority is required solely to make a sole
owner eligible. Acceptance of this amendment does not accept a concrete evidence
source or enable execution; those inputs need separate review and acceptance.

Submit this exact contract revision to independent oversight; then obtain Juan's
exact-revision acceptance before merge. Implementation, synthetic fixture runs,
account provisioning and any native/live qualification need separate explicit
authorization under accepted work orders. Native sign-in, Hello, Gmail and live
activation remain on hold.
