# Lead Intake first-proof plan amendment

**Proposed, contract only.** This amends the order and isolated-proof boundary in
the [Lead delivery plan](LEAD-VERTICAL-DELIVERY.md), accepted in PR 69 at
`8639491e2b692c6a43efdbce42f02753b9ad8a29`. Juan directed this change after the
November 24 status review. Oversight relayed the requested amendment in
`ccbf8f87`. Independent review and Juan's acceptance of the exact revision are
required. The accepted plan remains in force until then.

## Root cause and affected requirements

The accepted plan's **Receiver activation and machine authority**, **Automatic
setup inventory**, and **Bounded work sequence and verification gates** put native
owner bootstrap and admin delegation ahead of the first real lead. Those steps
remain held. Offline work on bootstrap, recovery and licensing advanced, but main
at `eceab38ecb4bf54b596c11fdcc347e3da05c6450` still has no proof of a selected Gmail
form notification becoming a canonical lead. The host entry point in
`src/connect_automate/automate/host.py` checks a licence and reports its result.
The existing private custody owners provide storage and reconciliation primitives.
They do not supply the missing receiver, form parser or canonical lead record.

On acceptance, this amendment replaces the original V1b-before-V1c order and
the native activation and human-authority prerequisites for isolated V1e and its
V2 list observation. In the archived plan's **Automatic setup inventory**, the
production entitlement requirement in the pack-signature row applies to shipping.
Pack signature and fixed route checks apply to the proof as well. The
**activation blockers** paragraph and **Later lead list and configurable stages**
retain native sign-in and record-access authority for personal-data list use
outside the proof. The proof list uses the scoped owner and record-access checks
below. Existing custody, privacy and test requirements still apply. V1e proves
isolation on Juan's PC. Multi-platform native and installer qualification
remains a shipping requirement. The original PR 69 text remains archived intact.

## Work order

| Order and owner | Scope and exit |
| --- | --- |
| V1c, Lead Intake with EW contract input | First executable slice after separate authorization. Define one closed versioned template and field schema, structural extraction and one canonical idempotent lead record. Use synthetic fixtures with the same expected template structure before Juan selects a message. This qualifies the modeled structure. The actual selected template and authenticating domain must be matched privately before a real lead can commit. Pin the lossless source representation and use existing custody and workflow owners. |
| V1d, Email Watcher | Prove the selected body-only source uses the existing queue and receiver prepare before capture. Bind the exact raw/selected content, DKIM evidence and template to the signed source artifact. Preserve attachment behavior, avoid a durable retry body, and prove reference-only retry using synthetic fixtures. Lead Intake owns the field parser. |
| V1e, joint Lead Intake and EW | On Juan's own PC, run the actual isolated EW queue, local receiver, signed no-action pack and Lead Intake writer for the single notification Juan selects. A pass means one durable canonical lead with authenticated status and exact replay/restart proof, before/after mailbox evidence and reviewed private evidence. The single proof provisioning step below supplies the scoped authorities for this run. |
| V2, Lead Intake | Build and qualify the closed scoped local list and stage counts after the first lead using synthetic records. Under the reviewed isolated proof scope, Juan performs one authenticated list observation of that proof's own records using the same provisioned authority. It is an evidence item, with safe retries of the scoped read permitted. Personal-data reads outside this profile require V1b human and record-access authority. |
| Before shipping or adoption, V1b and V3 | V1b delivers and qualifies native verified-owner bootstrap, local sign-in and host sessions, Windows Hello and protected admin-delegated grants. V3 removes the proof provisioning path from the deliverable and qualifies the signed package and normal first launch. Preserve Decision C, exact delegation scope, native and installation evidence and the separate authorization for any adoption. |

Recovery after PC failure, recovery approval, business and US verification,
licensing and the register, enrollment revisions, grant history and restore
fencing are parked behind the first lead. PR 115 stays open and parked. Issues
84 and 101 remain open and do not gate this proof. The existing V1a custody
status behavior is already merged. Each new slice must move the first lead.
When none can advance, identify the actual blocker and what lifts it.

## Isolated provisioning and execution boundary

One labelled **test-only provisioning** step may establish Juan as the owner
and set up the matching machine grant for the approved proof on his own PC.
Use a qualification-only entry point, a dedicated isolated profile and data roots,
and one immutable proof configuration binding the organization, host and stable
instance, selected mailbox and message, sender/rule/version, pack and route, and
allowed operations. The privileged step seeds the scoped proof authority once
and records the reviewed configuration and origin in private evidence. A caller
cannot self-enroll, request a wider grant or use the provisioned authority against
the live installation. The proof owner uses OS-protected key storage and
Juan-controlled consent. Agents do not handle keys, credentials or tokens.

V1e exercises the actual machine and source authentication and current-scope
checks, artifact binding, custody fencing, replay protection, stable restart
identity and authenticated status reads. It exercises the lead writer and
privacy boundaries. The approved V2 observation uses the same owner binding
and closed read contract. Enforce identity, organization, proof instance and
record scope at the read owner. Machine transport by itself grants no personal
read access. Refuse foreign actors, records outside the proof, expired grants
and access from the live profile. The proof grants no edit authority.

The V1e work order schedules a read-only entitlement check on the proof PC early
in V1c, when authorized host access is available. Record only whether the PC is
eligible, absent a valid entitlement, or unverified. Collect no licence bytes or
credentials. If eligibility cannot yet be verified, synthetic V1c continues and
the V1e plan covers both branches. Use an existing entitlement if valid for the
proof. If absent or ineligible, the same labelled step supplies a signed
proof-scoped automations entitlement bound to the isolated instance and approved
proof duration. Validate it at the existing entitlement owner with trust material
available only to the qualification profile. Keep installed trust, entitlement
files and production validation unchanged. The pack signature and exact route
binding still pass through their normal checks. A production issuer, purchase,
sale, register and recovery decision are outside the first-lead path.

Keep proof entry point, binding material and fixtures in the qualification
surface outside distributable packages. V1b replaces the provisioned authority
with verified native authority and protected admin delegation. V3 must inspect
the exact signed shipping artifacts and installed entry points for absence of
the provisioning code, proof entitlement and trust material, and proof list
authority. A clean shipping installation must reject the proof entitlement,
provisioned list authority and proof configuration. Use valid shipping
entitlement and verified-owner setup as controls. No supported release flag may
turn on proof provisioning.

## Prerequisite and restriction audit

| Requirement and cost | Need for the first lead and why a lighter rule fails |
| --- | --- |
| Juan selects one notification in one supported template | Limits exposure to the one message whose handling he approves and lets the proof isolate one deterministic form contract. Searching broadly or guessing fields could read unrelated mail and create a false lead. No new user document or business-verification step is needed. |
| Isolated EW, local receiver and scoped current machine/source authority | Dedicated configuration and processes keep tokens, raw data and state away from the live installation. A shared runtime or unrestricted bearer could route the wrong source, expose its results or mutate live state. The one-time proof setup suffices for this boundary. |
| Proof-scoped entitlement and signed-pack policy | Production entitlement protects commercial access outside the proof. Requiring it in the isolated proof would block first-lead evidence when the PC lacks a licence. A signed and locally validated proof entitlement keeps the existing admission path exercised without a new issuer or purchase. The signed pack protects real data from unsigned behavior and still needs verification. |
| Authenticated V2 observation of the proof's own records | A local list contains personal data. A machine bearer alone cannot establish who may read it. Juan's scoped proof authority and record checks protect the isolated data without requiring the shipping sign-in path. The observed read adds no general list access. |
| Juan performs read-only OAuth and separately authorizes the run | The provider grant limits what the isolated client can do. Verify only permitted reads and unchanged selected-message labels/read state before and after. A scope label alone cannot prove the observed mailbox was untouched. |
| Valid DKIM for the expected sender and exact structural template | DKIM authenticates the form system and signed content. One closed schema and real structural parser prove which fields were actually submitted. An email header, heuristic, or matching sender name alone could admit spoofed or misparsed input. Unknown templates fail closed. |
| Signed no-action pack and idempotent canonical lead | The proof permits storing and reading status for one lead. Reusing an action-bearing pack risks customer contact or writes. Replaying the same physical source must resume the existing path and keep one canonical record. |
| Private local evidence kept until recorded review completion | Access controls and retention protect personal content while preserving enough evidence to verify the flow. Public logs, CI artifacts or cleanup before review would expose or destroy that evidence. Use existing retention rules and tested cleanup after review. |

## What Juan supplies and when

1. **For the V1e input**, Juan picks the form-notification email himself. The
   selection stays private. V1c and V1d can proceed with synthetic inputs under
   their own accepted work orders before this selection. Actual template match is
   verified only during the authorized V1e run.
2. **Before V1e setup or access**, Juan gives a separate go for the exact isolated
   run on his PC, including its test-only provisioning, selected data boundary,
   the scoped list observation when its V2 work order is ready, and cleanup.
3. **During authorized V1e setup**, Juan performs read-only OAuth himself in the
   isolated EW profile. The application uses the grant. Agents never receive it.

The amendment authorizes no implementation, preflight, mailbox access, OAuth,
key provisioning, receiver activation or live work. Native sign-in and Hello
remain held. The Gmail and activation holds apply until Juan separately authorizes
V1e within its reviewed scope. Restore unlock and live adoption remain separate.

## Verification and exit

This contract PR changes this amendment and a pointer outside the archived PR 69
text. Verify that the accepted bytes are intact and that the superseded sections
cannot be interpreted as active first-proof blockers after acceptance. Check all
owner, scope and link references. Later work orders must prove correct and
malformed structures, authenticated wrong sender/template and messages outside
Juan's selection, forbidden mailbox writes and action dispatch, isolation and
foreign-scope access denial, restart/replay with one canonical lead, private
evidence and cleanup. Cover existing eligible, absent and ineligible
entitlements, refusal of proof trust on the shipping path, and authenticated
list observation with wrong actor, instance and record-scope refusals. V1b/V3
supply separate native and release proof.

Implementation summary and cold diff: documentation only. Gap audit: **NOT
DONE** for review, exact-revision acceptance and implementation. The first
executable work order is V1c.
