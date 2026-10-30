# Lead delivery: first real notification, local list, automatic setup

Status: **PROPOSED PLAN. Contract only; not accepted for implementation or live use.**

This is the next product lane after read-only custody composition. It defines
both sides of the Email Watcher (EW) handoff. It does not authorize a mailbox
read, OAuth, service activation, installation, model call, or production change.
The EW session owns EW implementation after acceptance; lead-intake owns the
receiver and canonical leads. No parallel implementation is started here.

## Direction and acceptance boundary

The operator directions relayed in `b5c362f1`, `fdcf8b70`, `5ffcbd47`,
`c92fe544`, and correction `042f4eca` establish the following plan requirements.
Later decisions `37ad85bf` (corrected by `2f0e8aec`) and `30aba361` settle
proof-evidence retention, Lead Intake ownership and the default stage labels;
they do not accept this entire technical revision:

- Use a real Gmail **web-form notification selected by Juan**, not an arbitrary
  customer email. Agents must not search the inbox to select it.
- Keep the selected mailbox read-only, the live EW installation untouched, and
  the workflow free of replies, CRM writes, or any outbound customer contact.
- EW identifies and routes sources. Lead Intake owns leads. No dashboard or new
  lead-management application is included.
- Deliver the real-lead path, then a read-only local lead list, then automatic
  setup, as small separately reviewed changes. Plan all three now.
- Stages are user-configurable data with stable IDs, not a fixed product enum.
  Automatic runtime/setup provisioning must not remove useful user settings.

Peer mail is evidence of the requested direction, not technical acceptance.
Juan's exact-revision acceptance and oversight review remain required. This
plan cannot authorize every later implementation merely by naming it. Each
bounded executable work order must pin its actual schemas, owners, tests,
non-scope and rollback before code. No new library-only expansion is proposed
unless it is a demonstrated prerequisite of this vertical path.

## Contract: root cause and source inventory

The completed private custody library is not an installed receiver or a canonical
lead store. A successful workflow receipt is not evidence of extracted lead
fields, employee authorization, Gmail retrieval, or automatic setup.

Source pins (all paths and line references in this inventory use these revisions):

- **CA:** `canfieldjuan/connect-automate`,
  `b5ce216139f8dd11f2e71746f791279181374a70` (merged custody composition).
- **EW:** `canfieldjuan/eom-email-watcher`,
  `a63339b2f74f2bd450bd08781668b999c66eac42` (remote main verified).
- **CC:** `canfieldjuan/connect-contracts`,
  `9ef8a3760ebb1d2f216f6a704fec2343ba4ea6bc` (local origin/main inventory;
  not a claim of current remote main).

CA `LI/` abbreviates `src/connect_automate/lead_intake/`; EW paths begin
`src/eom_email_watcher/`. Documentation is an accepted constraint or a proposal,
never substitute evidence that an implementation exists.

| Classification | Source-grounded finding |
| --- | --- |
| CONFIRMED | CA `LI/custody_handoff.py:113-180,211-217,269-359` validates runtime, route, scope, machine reference and store pins, then composes submit/resume/status. Its module warning at `:1-5` explicitly excludes receiver authentication. |
| CONFIRMED | CA `automate/host.py:70-89` starts with an entitlement check; its executable entry point is a license-reporting skeleton. CA `pyproject.toml:14-15` points there. This is not receiver activation. |
| CONFIRMED | CA `connect.py:98-132,330-364,873-892` provides loopback registration, bearer transport, one hashed input artifact, bounded parameters and byte outputs. CC `schemas/v2/registration.schema.json:7-35` declares the same transport/bearer boundary, not delegated organization or employee authority. |
| CONFIRMED | CA `LI/custody_protocol.py:102-110` calls `proof_reference` an opaque reference. CA `LI/_host_policy.py:97-104,124-129` evaluates supplied facts and denies machine actors in its human operation policy. Neither is a machine credential verifier. |
| CONFIRMED | EW `gmail.py:53` requests `gmail.readonly`; `:1048-1085` fetches exact messages with metadata/full GET requests. `:1087-1134` checks folder evidence and extracts body content. This verifies source behavior, not the scope of any existing token or an unchanged live mailbox. |
| CONFIRMED | EW `gmail.py:455-457,515-520,569-589` selects ordinary metadata headers and normalizes them. It supplies no authenticated DKIM verdict in this path. The header dictionary collapses repeated header names; it must not become a DKIM input. |
| CONFIRMED | EW `automation/rules.py:228-241,401-421` requires an attachment media-type condition and emits a fire for each matching attachment. This cannot deliver a body-only notification unchanged. |
| CONFIRMED | EW `body_state.py:38-56,77-100` gates ordinary durable body storage on followed messages. EW `mime.py:46-74` reduces HTML to text; `:10-13` imposes body/input/structure limits. That text is not a lossless form template or raw signed MIME. |
| CONFIRMED | CA `LI/source.py:77-91,94-115,129-154` has physical source identity, body admission, completeness metadata and a signed payload whose only snapshot representation is `normalized-text`. Its closed models (`:67-74`) forbid extra fields. A MIME envelope cannot be smuggled into this version. |
| CONFIRMED | CA `LI/auth.py:151-195` authenticates signed-source authority, including mailbox/policy scope. Source signing and DKIM are distinct checks. |
| CONFIRMED | CA `LI/custody_handoff.py:327-359` projects an open unbound intent as prepared. CA `LI/custody_protocol.py:203-207,279-292` rejects a prepared reservation at/after expiry. This explains the conservative unknown covered by issue #66. |
| CONFIRMED | CA `LI/custody_store.py:141-192` already owns intent registration, upload binding, closure, admission, revalidation and retained reads. Reuse these owners; do not build another custody database or writer. |
| UNKNOWN | The selected message, authenticating form domain, exact notification template, field schema and valid DKIM evidence have not been inspected. No real-data fixture or extraction accuracy is claimed. |
| UNKNOWN | An installed protected machine-control verifier, encrypted isolated proof deployment and zero-touch enrollment have not been established by this inventory. A bearer token or UUID cannot fill that gap. |
| INFERRED | The smallest product path is an EW body-source extension plus a thin authenticated Connect receiver over the existing custody/runtime owners, followed by a separate Lead Intake record owner. |

### Existing proof and intentional departures

Retain the current synthetic fixtures, source/auth/custody tests and no-action
pack. In particular, `tests/test_lead_custody_status_process.py:148-200,336-418`
covers process ordering/crash scenarios; `tests/test_lead_custody_status.py:1167-1231`
contains the repaired inconsistent-observation proof. These are regression inputs,
not live Gmail or transport qualification. No tests were rerun for this plan.

Prior evidence manifests, re-read and hashed during this plan:

| Alias | SHA-256 | Reuse limit |
| --- | --- | --- |
| `custody-status-composition/manifest.json` | `689544ac39fcce45d6bdc46c4f734cc4088a611f5752b1b56cd58f543eb6293f` | Original private composition proof. |
| `custody-status-composition/review-g1-20261030/manifest.json` | `f7cf8bfbfce8a0ae3acf8300002a19c01252b532f6cafc5bb1c5e75ec9b3705a` | Isolating guard tests; production bytes unchanged in the repair. |
| `custody-status-composition/merge-20261030T174117Z/manifest.json` | `499ee6b8f254b9c4ff8c55a370fc93f3d4c702edc8f374b11ef780b9bb06036b` | Reviewed merge-tree and CI/review receipt; no application proof. |

Explicit departures requiring subsequent accepted contracts:

1. Private caller-supplied machine references become authenticated transport
   control. This is a missing enforcement boundary, not removal of an existing one.
2. Add explicit expired-unfenced vocabulary before transport exposure. Preserve
   existing version behavior; do not reinterpret old `unknown` replies.
3. Structural form extraction needs a versioned lossless notification representation
   and authenticated provenance. The current normalized-text schema remains valid
   unchanged. Never store HTML or MIME under its normalization label, or put extra
   fields in signed metadata without a versioned schema amendment.
4. EW admits eligible unfollowed body-only notifications through its existing
   source/queue owners. No fake attachment, implicit thread-follow, new poller or
   body retry spool.
5. Lead Intake adds canonical extracted records and user-owned stage configuration.
   Custody receipts and workflow records retain their separate purposes.
6. The later protected read surface and package provisioning are new qualification
   work; neither is inferred from a pure policy evaluator or a developer harness.

## Ownership and end-to-end path

```text
Juan-selected Gmail notification (read-only, isolated OAuth grant)
  -> isolated EW source owner: selected-message and sender eligibility
  -> EW existing queue: receiver prepare, capture once, verify form sender
  -> signed artifact handoff; Lead Intake validates the exact template
  -> Connect v2 loopback receiver: current machine/route authorization
  -> existing source custody writer -> existing no-action PackRuntime result
  -> Lead Intake structural extraction + canonical lead record
  -> authenticated custody status; later authorized lead-list read
```

EW retains source/reconciliation references, not a second lead record. Lead Intake
owns the form parser, extracted fields, record identity, review state, stage set and
stage history. Connect Automate owns workflow execution/history. The protected host
owns authentication and enforcement. Each owner exposes APIs; sharing a SQLite
deployment does not permit cross-owner SQL. EOM and the shared AI runtime are
untouched. This deterministic template path needs no inference or model download.

**Operator ownership decision:** Juan said "lead intake not atlas" (relayed in
`30aba361`). Lead Intake is the lead system. This plan does not route leads to,
feed or integrate with the Atlas funnel. It changes nothing in Atlas, EOM,
eom-timetracker or eom-connect-provider and does not replace their existing
business workflows.

### First vertical delivery

**Selection and isolation.** Juan supplies exact Gmail message IDs or applies a
dedicated selection label himself. Resolve only his selected set; do not search
other messages to find examples. Start with one template. Record before/after
labels and read state for those IDs, with observed concurrency limitations. Use
an isolated EW profile, state root, processes and OAuth grant; do not copy the
live profile/token or change live settings. Juan performs OAuth himself. Agents
never read, print, copy or transmit credentials. Read-only scope is necessary but
not proof: deny Gmail mutation APIs in the qualified client path and assert that
only permitted reads occurred. Provider requests, logs and responses are private.

**Form authentication and structure.** The sender is the form system, not the
submitted email or Reply-To. Pin From, Return-Path, DKIM signing domain, template
identity/version and the exact selected MIME structure in a private discovery
receipt. Authenticate the expected domain with valid DKIM covering the relevant
content; a displayed `Authentication-Results` string supplied in an email is not
authority. Duplicate singleton identity/form fields, partial-body signatures,
malformed MIME, ambiguous parts, conflicting templates or absent authentication
fail closed. Legitimately repeatable MIME/header fields must retain their order
and multiplicity for the real parser; do not reject all repeated header names.
Use an audited
DKIM/MIME implementation with explicit provenance and key policy, not regex or
handwritten crypto. No such verifier is established in the inspected EW path;
its owner/dependency/retained authentication evidence need a separate EW work order.
Historical key loss is a typed refusal, never permission to trust a spoofable
header. Do not render HTML, load remote images, follow links or execute content.

The EW-owned DKIM verifier fetches the signing selector's public key by DNS at
verification time. This is explicit network egress to the configured DNS resolver,
in addition to Gmail retrieval; the selector/domain query discloses that lookup,
not the message body or submitted customer fields. The EW work order must bound
DNS timeouts, response sizes and failures. It cannot use an email-supplied key or
silently substitute a historical key. If a delivery-time key has been replaced or
removed and the current selector cannot verify the signature, refuse the message.
Juan should select a **recent lead**; recency is guidance, never proof of validity.
The private proof records the provider-reported delivery time, verification time,
selector/domain, verifier version and verification result. No DNS or Gmail call
is authorized by this contract draft.

The selected template determines a closed versioned field schema and a real
MIME/HTML or structured label-value parser at the Lead Intake owner. Unknown or
duplicate fields, extra/missing structural elements and changed templates are
typed refusals. Missing, absent and unknown values stay distinct; do not invent
fields. Express types, lengths, formats and closed properties in that schema,
then validate with the same schema at admission. Cross-field constraints have one
named validator. No parallel regex over free text or model-selected identity.
Make the public fixture structurally identical using entirely synthetic values.
The schema cannot be finalized before the selected template is known; this is a
gate on that work order, not a reason to browse the mailbox now.

Sender selection is provisional until authentication and template validation
succeed. EW verifies the form sender; Lead Intake owns the structural validator
and invokes it on the exact received representation before custody acceptance.
The transport must not maintain a second field parser. Successful parsing is
neither source-signature authentication nor permission to write: all existing
source-writer authority, scope and fence checks still execute. Derived fields
are committed only by the Lead Intake record owner after source custody; recovery
reuses that same parser/version against the retained authenticated representation.

**Lossless handoff.** Reuse the existing `lead.source.custody` capability proposal
and Connect v2 POST/GET job transport in
[the custody contract](LEAD-RECEIVER-CUSTODY.md#proposed-application-contract).
Do not add bespoke HTTP routes or a second dispatch system. Each operation keeps
one hashed artifact. Prepare/status/resume/settle carry closed control metadata;
upload carries the signed source artifact. The notification-format amendment
must bind the exact selected part, template and authentication evidence to the
source payload digest, without increasing existing limits by accident. Its
precise wire model, media type, limits and compatibility fixtures are acceptance
inputs, not decided by implementation convenience. Unavailable or incomplete
content may be recorded truthfully but cannot produce a complete lead. An
attachment-bearing message is outside this first proof; no attachment extraction.

Receiver readiness and bounded quota reservation precede content capture. EW
keeps no durable intake body, input artifact, logs-with-body or retry cache. A
transient capture lost before custody is a recorded loss. A committed capture is
resumed by reference without Gmail reread. Existing full physical message
identity, event ID, payload digest, envelope hash and capture cutoff survive
replay. Changed event IDs or rotated signing keys must not create a second lead
for the same physical message. A changed signed payload is a conflict, not a
silent overwrite. Do not merge distinct messages merely because contact fields
match. Delivery deduplication remains a later, separate concern.

**Receiver activation and machine authority.** A thin provider in the existing
Connect host/installation loads the signed no-action pack and fixed organization,
namespace, route and source-store configuration. Do not launch it in this plan.
The provider registers only after entitlement, private storage, encrypted-volume,
keystore, grants and exclusive instance ownership are qualified. Persistent
installation identity must survive restart; a per-process registration identity
must never silently select a replacement provider for a pending request.

Reuse Connect bearer transport, but additionally enforce a protected current
machine delegation scoped to organization, host, namespace, mailbox/rule/version,
route/pack and operation. Bind proof to the exact job/control/handoff IDs,
artifact digest/size, capture pair and generation. Freshness, replay consumption,
rotation, revocation/commit ordering and authenticated GET-result access must be
specified in the machine-boundary work order. Never turn `proof_reference`, a
registry bearer, OS username/PID, or a copied eligibility result into authority.
No credential bytes in params, results or audit records. Current authorization is
checked even when returning cached historical results. The current code supplies
no qualified verifier for this contract: **real-data activation is blocked until
that boundary is implemented and independently proven**.

**Truthful results and canonical lead.** Custody acknowledgement follows the
source commit; workflow acceptance follows its separate commit. The no-action
pack must reject any action-bearing configuration. Neither result constitutes
business approval, delivery or a client relationship. Lead Intake validates the
form against its pinned schema and idempotently commits one canonical record
with immutable organization/source identity, extraction/schema version and review
requirement. Source custody, workflow history and the lead record are separate
commits: a restart must resume the missing step without fabricating a completed
one. Use existing workflow/reconciliation owners, not a new scheduler.
Only metadata references enter workflow receipts. Raw fields stay in the private
lead store and later authorized read result. Initial intake state is
`NEEDS_REVIEW`; configurable business stage is independent of intake approval,
delivery status and custody status. No automatic contact resolution, CRM write,
approval, customer outreach or legal conflict-clearance decision is included.

### Issue #66: required pre-transport amendment

Propose a new status schema version with `capture_phase=expired_unfenced` and
`reason=settlement_required`, only for a validated open, never-custodied,
capture-absent snapshot whose reservation deadline is at or before observation.
It includes the actual scope, generation, state revision and deadline; it has no
receipt or workflow. It reports no committed custody at that snapshot, **not a
fence or future absence guarantee**. Existing versions retain conservative
unknown behavior. Put the combination constraints in the versioned owner model;
the transport must not reclassify `unknown` by inspecting clocks or text.

The caller may request a separately authenticated `settle` at the observed
generation. Only the existing writer can close/fence admission and resolve a race
with upload. A stale observation cannot renew a reservation, recapture bytes,
create another event or claim cancellation. Status remains read-only and never
settles. Require before/equal/after-deadline, both race orders, stale generation,
replay, clock-floor, unauthorized access and downgrade tests. This proposal
requires its own accepted schema/implementation slice before the receiver is exposed.

## Later lead list and configurable stages

**Accepted default stage labels:** New, In progress, Closed. Juan said
"defaults for stages are fine", relayed in `30aba361`. These are the shipped
defaults; users retain the ability to add, rename, reorder and remove stages
under the rules below. Each user has a non-empty ordered
stage set with stable UUID IDs, owner and organization scope, schema version and
revision. Labels are bounded user data. Stage IDs are unique by ID (not merely
unique whole objects); enforce that cross-item rule in one owner validator. The
closed schema handles structure, size and label bounds. A lead references a stage
set and stage ID, never an arbitrary label. Preserve stage-set ownership so later
multi-user access does not confuse configuration ownership with record access.

New leads enter the configured initial stage. Renaming/reordering a stage keeps
its ID and every lead association. Empty stages can be removed. Removing a stage
with leads is refused until an authorized explicit migration names the destination
and expected revisions; never silently reassign or erase history. No stage-edit
or lead-movement interface ships in the read-only slice. Later user-authorized
changes append old/new IDs, actor, time, reason and configuration revision in the
same transaction as the stage change. The initial assignment is also recorded.
Workflows may not move stages automatically in this lane. Review/approval and
delivery lifecycles remain independent even if a user names a stage Pending approval.

The later versioned, closed JSON Schema lead-list response contains scoped lead
IDs, extraction schema/version and fields, intake review state, stage ID plus
current label, configured-stage counts including zero, configuration revision,
and bounded pagination/snapshot metadata. Do not expose raw MIME or secrets.
Counts and rows use the same authorized scope and consistent snapshot, including
across pagination; a changed/expired snapshot fails explicitly. A named validator
at Lead Intake verifies every stage ID against that user's configured set.
Labels cannot be an enum compiled into code. Schema evolution uses a versioned
contract, not free-form added keys.

Reuse Connect loopback and current machine authorization. Personal-data reads
also require the accepted human/record-access policy; machine transport alone
does not establish an employee's right to view a lead. No cloud copy, direct SQL,
GUI, dashboard, editor or deletion endpoint. The precise read capability/schema,
byte budgets and authorization implementation must pass a separate work order
before this surface is enabled. Custody's reference-sized status remains separate
from the bounded personal-data list response.

## Automatic setup inventory

These are **proposed owners and proof obligations**, not claims that a package
installer currently performs them. Infrastructure setup should require no user
enrollment commands. Gmail consent and business settings remain explicit user
choices. The first proof may use documented test-only provisioning; none can
silently become a shipping manual step.

| Setup requirement | Proposed provisioning owner | Evidence needed / later removal of proof-only setup |
| --- | --- | --- |
| Runtime binaries, dependencies, model assets if another feature needs them | Shared package installer and shared AI runtime owner | Signed/pinned assets, resumable verified downloads, offline/error behavior; no second model runtime or lead-specific model installation. This form path uses no model. |
| Private encrypted roots, service principal and OS keystore | Package installer | Native Linux/Windows access/encryption checks, denied unauthorized reads, upgrade/uninstall behavior; never infer protection from a private filename. |
| Immutable organization/host/user scope and provider identity | Connect first-launch host | Single deployment scope, atomic restart-safe initialization, no NULL/global fallback; qualification provisioning remains test-only until this slice passes. |
| First-admin bootstrap under verified deployment-owner control | Installer plus protected Connect first-launch host | Verify the deployment owner's authority and bind that owner's verified native identity to the initial employee/admin record. Installer privilege, a claimed owner ID or the first local caller is not owner proof. Test an unrelated local user, repeated/concurrent initialization, restart and attempted takeover; no self-enrollment or reinitialization fallback. |
| Owner sign-in and short-lived host-issued session | Protected host's native identity/session adapter at first use | Verify native identity, map it to the enrolled employee, immutable organization and current role, then issue a host session and enforce assigned record access. Prove lock/logout/expiry/role revocation and checks after store waits; reject claimed webview identities and shared-account ambiguity. Session acquisition is a normal sign-in flow, not manual enrollment or token copying. |
| Admin authorization of the chosen sender/rule/route delegation | Protected host after the enrolled admin's authenticated configuration choice | Fresh native verification and audience/operation/payload-bound one-use proof authorize publication of the exact scoped machine grant. Host/keystore code performs publication without user commands. Prove unauthorized publication fails, exact rule/version/mailbox/route/retention binding, replay and revocation/commit ordering; never infer a grant from possession of a machine key or installer privileges. |
| Source signing key and machine credential | Protected host using OS keystore | Keys generated without operator copy/paste; scoped grants, rotation/revocation and crash recovery. Agents never handle secret material. |
| Pack signature trust, no-action pack and fixed route binding | Installer plus Connect host | Verified pack install, fixed binding/digest, fail-closed downgrade/replacement; no bypass of entitlement or trust in fixtures used for real data. |
| Receiver activation and private registry | Connect host lifecycle | Exclusive ownership, restart identity and current result authorization, unavailable/quota handling; reuse registry/job transport. |
| Gmail isolated account and selection | EW first-launch/account owner plus Juan's consent | Narrow read-only grant; no reuse of the live token/profile. OAuth consent is not an enrollment command to automate away. |
| Body rule and template policy | EW configuration with Lead Intake template registry | Safe disabled/default configuration, explicit chosen source/template, no automatic broad mailbox capture. |
| Initial lead stage set | Lead Intake on scoped first use | Idempotent defaults, stable IDs, migration and authorized custom settings; no required settings before a lead can be stored. |
| Retention, cleanup and recovery metadata | Each existing data owner, provisioned by host | Exact deadlines and no-revival proof; no cross-application table access or a second cleanup scheduler. |

If service identity, keystore or encryption cannot be qualified automatically on
a supported platform, record that platform's blocker. Do not weaken authentication
or require users to copy keys. The zero-touch slice must remove each test-only
provisioning step before any shipping claim. Preserve business configuration
controls; zero-touch does not mean unconfigurable.

These human-authority steps preserve
[accepted Decision C](LEAD-SOURCE-HANDOFF.md#decision-c-local-admin-and-user-roles-with-delegated-background-authority),
whose acceptance is recorded at
[the policy acceptance record](LEAD-SOURCE-HANDOFF.md#current-acceptance-and-work-order-status).
Admin and user roles and individual enrollment must be supported from first
adoption; adding further employees is an optional authorized business setting. Automatic setup
must not turn the installer, any local user or a background machine into an admin,
skip sign-in, or delegate a sender/rule/route without admin authorization.

**UNKNOWN / activation blockers:** the inspected library does not establish a
qualified verified-owner bootstrap, native sign-in/session adapter or admin
delegation-publication flow. Their exact native mechanisms and evidence must be
pinned before activation. V1e cannot authorize its machine principal until the
bootstrap and admin delegation are proven; V2 cannot expose personal records
until sign-in/session and record-access enforcement are proven. If any supported
platform cannot automate provisioning while preserving these guarantees, bring
that specific platform/mechanism blocker to Juan. Do not offer self-enrollment,
shared-account identity, pretrusted fixture authority or manual key copying as
an alternative. Test-only provisioning still has to exercise the real authority
checks and be removed by V3 before shipping.

## Private proof and retention

No real-message access occurs under this plan. Before a real run, pin the selected
IDs/template, isolated profile identity, authenticated source/receiver versions,
encrypted evidence location and the retention decision below. The private evidence
root is outside repositories/worktrees under the operator's private corpus area;
directories are mode 700 and files mode 600, with equivalent native ACL proof.
No real content, addresses, names, headers, message IDs or low-entropy field hashes
in public repos/issues/CI/oversight mail. Publish only safe aliases, counts and
whole evidence-manifest hashes; reviewers of public PRs see synthetic fixtures.

**Operator retention decision:** Juan directed "keep until reviewed" in the
oversight conversation, relayed in `37ad85bf` and clarified by `2f0e8aec`.
Keep the planned private proof set, including raw material needed for review,
receipts, before/after mailbox records, extracted test records and proof summary,
in the private evidence root until review is complete. There is **no pre-review
deadline** and no advance-expiry exception. The earlier evidence-expiry proposal
is withdrawn. This settles the evidence-retention decision only; all selection,
OAuth, authentication, qualification and exact-revision acceptance gates remain.

The accepted product policy remains independent: receiver custody raw source
expires seven days after original capture during the proof, and its metadata
policy remains ninety days after original admission. Evidence retention neither
extends a receiver deadline nor revives an expired admission. Expiry is product
behavior under test; the original message remains in Juan's Gmail. This plan
does not claim the still-pending production metadata-retention mechanism exists.
No evidence goes into public repos, ordinary backups/caches, crash dumps,
external tracing or CI artifacts. EW never persists an intake retry body.

Record review completion in a private receipt naming the reviewed code revisions,
evidence-manifest aliases and digests, required reviewer verdicts, disposition of
every finding and completion timestamp. Pending or unresolved review does not
complete this receipt or trigger cleanup. After recorded completion, delete the
private proof set through each owner's APIs, inventory WAL/temp/export copies,
and perform an observed post-deletion check. Keep only a non-personal cleanup
receipt identifying the proof alias, review completion and deletion result; no
customer fields or message identifiers. Then Juan revokes the isolated grant.
Encrypted-volume disposal/deletion does not imply physical secure erasure on SSDs.
Existing immutable workflow metadata needs owner-supported retention or a
separately approved disposable-deployment teardown; do not drop triggers or edit
tables to manufacture cleanup. A failed cleanup blocks qualification/adoption.

## Bounded work sequence and verification gates

The first deliverable remains the real lead; list exposure and automatic setup
follow it. Within that deliverable, the smallest prerequisite PRs are ordered by
dependency. Each implementation PR has a prior accepted work order, keeps Windows
coverage from its first push, and carries its own rollback and evidence packet.

| Slice / owner | Required result and proof | Gate / rollback |
| --- | --- | --- |
| V0: this cross-app plan, lead-intake | Source inventory, ownership, departures, privacy and setup map; operator acceptance of exact revision. Message/template and machine verifier still unresolved. | G0; docs only. |
| V1a: expired-unfenced, CA | Accepted issue #66 versioned contract and owner implementation; boundary, clock, race and legacy-version parity tests. | G0/G3; capability remains disabled; old private versions retained. |
| V1b: machine control and activation, CA/Connect owner | Accepted machine-proof schema/verifier, verified-owner bootstrap, native admin session and exact admin-delegated grant; durable replay/revocation, authenticated result reads, stable installation identity and thin v2 provider. Synthetic native tests first. | G1/G3/G6 prerequisite; disable new capability, preserve custody/history. No production host adoption. |
| V1c: selected template and source representation, lead-intake + EW | After separately authorized selected-message discovery, exact synthetic template/closed schema, DKIM owner and versioned lossless source amendment. Structural extraction and canonical idempotent lead record include stage-set references from inception. Preserve all old source/auth tests. | G0/G2; disable new source version/template; never reinterpret or erase old records. |
| V1d: EW body handoff, EW session | Existing source/queue extended to unfollowed body-only input, prepare-before-fetch, no body spool, reference recovery, capture-cutoff removal and unchanged attachment paths. Source/transport auth and limits proven before real data. | G1/G3/G6; disable lead rule, keep reconciliation references. |
| V1e: isolated real-lead proof, joint owner evidence | Juan-selected read-only Gmail input through actual EW queue/receiver, no-action workflow and one canonical lead; authenticated status readback, restart/replay and before/after mailbox evidence. No fake success and no real data in CI. | G1/G2/G3/G6 qualification only; stop isolated instance, retain evidence until recorded review completion, then qualified cleanup. No production readiness claim. |
| V2: lead list, Lead Intake | Closed read contract, record access, consistent scoped rows/counts, configured stages and bounded outputs. No display or edit UI. | G2/G6; disable read capability, retain canonical records. |
| V3: zero-touch, package/Connect/EW owners | Replace every proof-only provisioning step with verified install/first-run ownership; upgrade/restart/uninstall, offline/download and native privacy evidence. | G6/G7 before adoption; disable activation or restore qualified installation, never reset lead identities. |

Do not combine these into one broad refactor. Split an executable slice further
at its owner boundary if the review surface is too large, without inventing
another engine/store/poller. No simultaneous EW changes from this session.

Verification must include valid body-only and unavailable sources; failed DKIM,
changed/ambiguous templates, duplicates, conflicting fields, truncation, replay
after key rotation, several event IDs for one physical message, SQL fault between
commits, separate-process races, crash before/after custody and lost response.
Prove reference-only recovery does not reread Gmail or double-create a lead.
Probe each new guard independently, including valid/bad/partial/boundary inputs
and schema defaults; remove each guard to show the intended assertion catches it.
Prove unverified-owner enrollment, forged sessions and unauthorized delegation
are refused, including both revocation/commit orders and initialization races.
Exercise DKIM DNS/key absence, changed selector keys and timeouts alongside a
valid recent signed notification; record delivery/verification time separately.
Prove mailbox writes, outbound contact, action dispatch and unauthorized personal
reads are absent through exercised negative tests, not assertions of intent.
Native Windows and Linux evidence are mandatory; no real-message fixture in CI.

## Change summary, cold audit and gap audit

This plan adds one contract document and a navigation pointer from the receiver
roadmap. It changes no code, tests, schemas, dependency pins, services, secrets,
settings, data or workflows. Verification for this docs-only change is citation
resolution against the pinned trees, direction-to-plan coverage, a cold diff read
and whitespace/scope checks. Existing executable test evidence is historical;
tests are not rerun solely for this prose change.

**NOT DONE:** exact-revision operator acceptance; selected-message discovery
authorization and actual template; precise machine authentication/activation
contract; versioned notification and expired-status schemas; private proof
encryption/cleanup qualification (retention direction is settled); all executable
vertical, lead-list and automatic-setup work. None of these gates is satisfied
by this plan or by a green documentation PR. Stop at contract review; do not
begin implementation or live use.
