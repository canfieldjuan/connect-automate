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

On acceptance, the sequence and proof provisioning below supersede the older
activation and native-authority prerequisites for the isolated V1e proof. They
also supersede the original V1b-before-V1c sequence, and distinguish synthetic V2
qualification from enabling personal-data reads. Existing source custody,
privacy, testing and shipping requirements continue to apply where they do not
depend on those superseded prerequisites. V1e proves isolation and privacy on
Juan's proof PC. Multi-platform native and installer qualification remains a
shipping requirement. The original PR 69 accepted text remains archived intact.

## Work order

| Order and owner | Scope and exit |
| --- | --- |
| V1c, Lead Intake with EW contract input | First executable slice after separate authorization. Define one closed versioned template and field schema, structural extraction and one canonical idempotent lead record. Use synthetic fixtures with the same expected template structure before Juan selects a message. This qualifies the modeled structure. The actual selected template and authenticating domain must be matched privately before a real lead can commit. Pin the lossless source representation and use existing custody and workflow owners. |
| V1d, Email Watcher | Prove the selected body-only source uses the existing queue and receiver prepare before capture. Bind the exact raw/selected content, DKIM evidence and template to the signed source artifact. Preserve attachment behavior, avoid a durable retry body, and prove reference-only retry using synthetic fixtures. Lead Intake owns the field parser. |
| V1e, joint Lead Intake and EW | On Juan's own PC, run the actual isolated EW queue, local receiver, signed no-action pack and Lead Intake writer for the single notification Juan selects. A pass means one durable canonical lead with authenticated status and exact replay/restart proof, before/after mailbox evidence and reviewed private evidence. The one proof provisioning step below replaces native bootstrap and admin delegation publication for this run. |
| V2, Lead Intake | Build and qualify the scoped local list and stage counts after the first lead. Qualify using synthetic records and a closed read contract. Enabling personal-data list reads still requires the accepted human and record-access authority. The V1e provisioning exception does not extend to V2. |
| Before shipping or adoption, V1b and V3 | V1b delivers and qualifies native verified-owner bootstrap, local sign-in and host sessions, Windows Hello and protected admin-delegated grants. V3 removes the proof provisioning path from the deliverable and qualifies the signed package and normal first launch. Preserve Decision C, exact delegation scope, native and installation evidence and the separate authorization for any adoption. |

Recovery after PC failure, recovery approval, business and US verification,
licensing and the register, enrollment revisions, grant history and restore
fencing are parked behind the first lead. PR 115 stays open and parked. Issues
84 and 101 remain open and do not gate this proof. The existing V1a custody
status behavior is already merged. Each new slice must move the first lead.
When none can advance, identify the actual blocker and what lifts it.

## Isolated V1e provisioning and execution boundary

One labelled **test-only provisioning** step may establish Juan as the owner
and set up the matching machine grant for the approved V1e proof on his own PC.
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
privacy boundaries. Provisioning stands in only for native human bootstrap,
sign-in and admin publication of the initial grant. It supplies no exception
to the host's existing entitlement check or pack signature verification.
Use existing licensed host eligibility. This work does not require a new issuer,
sale, grant register, recovery decision or customer purchase. If the existing
eligibility or isolated receiver cannot be exercised, identify that specific
blocker in the V1e work order.

Keep proof entry point, binding material and fixtures in the qualification
surface outside distributable packages. V1b replaces the provisioned authority
with verified native authority and protected admin delegation. V3 must inspect
the exact signed shipping artifacts and installed entry points for absence of
the provisioning code, credentials and configuration. Test a clean shipping
installation with proof inputs and the proof configuration. It must reject them
and require the ordinary verified-owner setup, with a valid normal setup as
control. No supported release flag may turn on proof provisioning.

## Prerequisite and restriction audit

| Requirement and cost | Need for the first lead and why a lighter rule fails |
| --- | --- |
| Juan selects one notification in one supported template | Limits exposure to the one message whose handling he approves and lets the proof isolate one deterministic form contract. Searching broadly or guessing fields could read unrelated mail and create a false lead. No new user document or business-verification step is needed. |
| Isolated EW, local receiver and scoped current machine/source authority | Dedicated configuration and processes keep tokens, raw data and state away from the live installation. A shared runtime or unrestricted bearer could route the wrong source, expose its results or mutate live state. The one-time proof setup suffices for this boundary. |
| Existing host entitlement and signed-pack policy | Use existing host eligibility and the signed pack pin. Ignoring either check would exercise a different admission path in a proof with real data. Proof provisioning changes who establishes owner authority. It does not alter entitlement validation or require a new licence purchase. |
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
   run on his PC, including its test-only provisioning, selected data boundary
   and cleanup plan.
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
evidence and cleanup. V1b/V3 supply separate native and release proof.

Implementation summary and cold diff: documentation only. Gap audit: **NOT
DONE** for review, exact-revision acceptance and implementation. The first
executable work order is V1c.
