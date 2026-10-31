# V1b.1: owner bootstrap and native admin qualification

Status: **PROPOSED, CONTRACT ONLY. B0 selects the licensing issuer for owner
bootstrap; claim lifecycle and native mechanism/run pins remain unresolved.
Not ready for executable acceptance. Stop for oversight review and
Juan's exact-revision decision; no implementation or native run is authorized.**

## Ordering, completed work and bounded outcome

The accepted [vertical plan](LEAD-VERTICAL-DELIVERY.md#acceptance-record) orders
V1a before **V1b: machine control and activation**, then the selected template,
EW body handoff and isolated real-lead proof. Its work-sequence table permits
splitting at an owner boundary. It does not authorize implementation merely by
naming a slice.

V1a is complete in the private library: [PR #71](https://github.com/canfieldjuan/connect-automate/pull/71)
merged as `c44091fe038223bcd43f5a86da07c5548569095e`, with reviewed/merged tree
`177bff42dfc9662db1f1167a6a9e2428fb635248`. Issue #66 closed under its accepted
completion procedure. Exact-head Linux/Windows CI, oversight and connector
review passed. This is recorded evidence, not a new test run or live qualification.
Evidence alias `lead-custody-expiry-implementation/merge-20261031T142956Z/receipt.json`,
SHA-256 `44607d94124910e11f891b75b576eadfc1837c3aca3f1900601ab8f153527147`.

**Proposed bounded next outcome:** qualify how the protected local host verifies
the deployment owner, bootstraps that owner's initial admin record and obtains
a native admin session. Use synthetic identities on separately authorized
disposable native environments. Deliver a reproducible feasibility packet and
the precise subsequent enforcement work order, not a receiver or another pure
eligibility model. An unproven prerequisite is a typed blocker, not a fixture
grant that permits the next step.

This split is necessary because V1b's machine grant must be published by an
authenticated enrolled admin. The accepted plan requires owner bootstrap and
native session proof before that authority can exist. It explicitly disallows
installer privilege, a claimed owner ID and the first local caller as owner
proof (`LEAD-VERTICAL-DELIVERY.md:355-395,440-460`).

## Contract: root cause and exact source inventory

All CA source citations below use `canfieldjuan/connect-automate` at
`c44091fe038223bcd43f5a86da07c5548569095e`. `LI/` means
`src/connect_automate/lead_intake/`; `CA/` means `src/connect_automate/`.
Documentation supplies constraints and leads, not implementation evidence.

| Label | Evidence and demonstrated limit |
| --- | --- |
| CONFIRMED | `CA/automate/host.py:34-89` is an entitlement-gated host skeleton. Starting it checks licensing; it does not bootstrap employees, verify native sign-in or run a protected receiver. |
| CONFIRMED | `CA/entitlement.py:138-166,175-188,199-240` supplies strict signed-envelope/claim models, installed public-key authority, license evaluation and installation. `:402-418` is the shared Ed25519 verifier; `:435-469` checks signature, feature and validity. The existing issuer trust chain is reusable. The claims lack organization, installation, native-principal and one-time consumption/revocation binding; a valid license alone is not owner proof. |
| CONFIRMED | `LI/_host_policy.py:1-7,35-66,97-158` validates supplied scope/actor/session/version facts and returns eligibility. Its machine actor is denied by the human policy catalog. It acquires no native identity and grants no execution authority. |
| CONFIRMED | `LI/custody_protocol.py:102-110` contains an enrolled-machine UUID and opaque proof reference. Neither verifies a credential. `LI/custody_handoff.py:124-191` revalidates runtime/route/store/request references, not the caller's native identity. |
| CONFIRMED | `LI/auth.py:82-109,151-195` validates source-trust snapshots and source signatures against host/org/namespace/mailbox/retention grants. It is not deployment-owner bootstrap, employee sign-in or a transport-control verifier. Keep that owner and signing preimage unchanged. |
| CONFIRMED | `LI/source_store.py:396-464` enforces current-process/private-path assumptions; its comment explicitly trusts same-user processes. Those checks do not isolate employees sharing the store account or establish encryption, owner authority or login state. |
| CONFIRMED | `LI/custody_store.py:135-196` already owns custody mutations and retained reads. `LI/source_store.py:551-592,604-624` owns source writer/commit and query-only snapshots. New host authority must not read/write these tables or duplicate these transactions. |
| CONFIRMED | `CA/connect.py:98-134,330-364` defines registry bearer transport, one hashed input artifact, bounded scalar parameters and output bytes. These are reusable transport contracts, not employee or business-owner identity. |
| INFERRED | The first missing owner in the accepted vertical is protected host authority acquisition. Adding another policy result type or trusting test-populated admin rows would leave that boundary missing. |
| UNKNOWN | A license-backed owner claim and its durable consumption/revocation, complete native sign-in/lock mechanism, protected service/keystore installation and native cross-account isolation are not qualified by these paths. No global claim about uninspected products is made. |

### Bounded reuse search and existing proof

Read-only searches of tracked local trees also covered `local-connect-status`
at `d94c84f4f6c49fa22273d693bc3e6fd36f61f8ec`, `local-connect-licensing`
at `9f9d1be530653300926315294ef1721ce3d4fc98`, and `local-connect-model-host`
at `f707665d801db2ff05759bea83be3e7d92080a53` for first-admin,
deployment-owner, native-identity, bootstrap and enrollment references. This
bounded search did not establish an implemented business-owner bootstrap.
It is not an audit of all branches, installed services or unpublished work.
The licensing checkout contains a proposed issuing-service contract, not evidence
of an implemented service. That does not negate the existing entitlement verifier
and issuer below. The model host remains inference infrastructure, outside this lane.

`connect-contracts` at `a168b9a67450556d95b4939a59ca36aa7aedfda5`,
`schemas/v2/registration.schema.json:7-35`, declares loopback/bearer registration,
not delegated business-owner or employee authority. Its
`tools/entitlement_issuer.py:359-450` validates feature/time/subject inputs, loads
the issuer key, signs and self-verifies a license, then writes a new envelope.
`entitlements/v1/claims.schema.json:5-40` forbids extra properties and fixes the
existing claim vocabulary. Neither path implements owner-claim consumption or
per-claim revocation. These are **CONFIRMED source findings**, not a claim that
production issuance or key custody was exercised. No private key was accessed.

**C1 correction:** my initial inventory searched for bootstrap/native identity
but omitted the existing entitlement chain. That omission originated in this
contract's reuse inventory, not the license implementation. The correction
credits the issuer/verifier and narrows the missing capability to scoped owner
authorization and consumption. It does not create a parallel signing system.

**Licensing owner/change:** the licensing/release owner must own business-scoped
claim issuance, revocation/reissue and any authoritative consumption interface.
The existing concrete issuer lives in `connect-contracts/tools/entitlement_issuer.py`;
its schema/fixtures and the CA consumer would need separately accepted changes.
The inspected `local-connect-licensing` proposal names a release-session owner
at `docs/contracts/LICENCE-SERVICE.md:3-16` and preserves entitlement v1 at
`:46-51`. Those are unverified ownership/service claims requiring coordination,
not authority to change that repository or evidence of a running API. No
cross-repository code, dependency/pin or production issuing change is made here.

Retain these existing proof inputs and their limits:

| Inventory | What can be reused; what cannot be claimed |
| --- | --- |
| `tests/test_lead_host_policy.py:35-369` | Closed-policy matrix, scope/version/role checks, copied-value rejection and no-I/O tests. These test supplied facts; they do not authenticate a human. |
| `tests/test_automate_host.py:94-134`; `tests/test_windows_connect.py:138-426`; `tests/test_locking.py` | License, private-path and lock regression owners; preserve their existing behavior. Native employee isolation or session proof does not follow from their presence. |
| CA `tests/test_entitlement.py:91-115,205-224,250-285`; connect-contracts `tests/test_entitlement_issuer.py:97-124` | Existing signature/feature/time, duplicate-member, installed-authority and issued-envelope conformance tests. Inspected, not executed here. Preserve unchanged v1 behavior; these do not test an owner claim or native sign-in. |
| `protected-host-read-contract/linux-credential-probe.py`, SHA-256 `9c50cf68c94856e442e2a6b1e698cac79bbe7b82f27232b7e2622d1ff518b693` | Existing unnamed-socket credential probe; hash rechecked, not rerun. Reuse it rather than inventing a replacement identity simulation. |
| `protected-host-read-contract/linux-credential-result.json`, SHA-256 `5ecf067de3fc283471bfd31948ce9f59388ca6f1781d423a92f185b2ca327ef8` | Recorded same-account Linux primitive: actual sender differs from claimed/connection identity and forged credentials are refused. Explicitly not sign-in, separate-account isolation or Windows proof. |
| V1a receipt above | Completed custody vocabulary/recovery regression reference. No human, machine-control or transport qualification. |

There is no model, prompt, inference runtime or real-message fixture in this
port inventory. Proposed departures are a separate owner-authorization claim and
its lifecycle at the licensing boundary, native identity acquisition, protected
bootstrap and session qualification. Existing license, policy, source, custody,
retention and workflow behavior remains the parity reference. No application
tests, issuer commands or native probes are executed for this documentation PR.

## First-admin bootstrap: license-backed direction, unqualified mechanism

Oversight explicitly carried this forward in mailbox `289865d6`: pin a concrete
first-admin bootstrap needing no enrollment step, or bring the blocker to Juan.
The accepted plan did not select the underlying authority. Oversight has now
[relayed Juan's B0 decision](https://github.com/canfieldjuan/connect-automate/pull/72#issuecomment-6546119928)
on 2026-10-31, verbatim:

> use the license for owner bootstrap

**B0 direction selected, not technical acceptance.** The relay says Juan answered
the recommendation to issue a signed, one-time owner authorization with the
license; at first launch its holder signs in with their computer account and
becomes admin. No enrollment command, key copying or setup beyond license
activation. Reuse the existing signed entitlement verification and issuing trust
chain, with no second signing system or cloud identity service. This record
attributes the decision to that relay; it is not a new acceptance of this revision
or permission to operate the issuer, native accounts or a VM.

**Trust limit:** the issuer authorizes the named business deployment. The first
valid holder who completes native authentication consumes the authorization;
the issuer has not preidentified that human. A leaked authorization could be
claimed by another valid holder. Native sign-in proves the local account, not
civil identity or entitlement to represent the business. This replaces this
draft's earlier proposed prebinding to an intended native person. An ordinary
license, installer privilege, OS administration or being first to call the host
still grants no bootstrap authority. After successful consumption, the owner
mapping is immutable through ordinary bootstrap and cannot be replaced by a
second holder. Native principals are bound at consumption, not inferred from
the license's `subject` or a typed owner name.

### Proposed claim and verifier boundary

Add a versioned, purpose-specific **owner-bootstrap companion claim**, delivered
with the existing entitlement during normal activation. Preserve the entitlement
v1 schema and feature behavior; do not insert new fields into its closed payload
or repurpose `subject` as a native identity. Reuse `CA/entitlement.py:402-418`
for signature verification and the installed public-key trust distribution.
The licensing owner must explicitly authorize which trusted issuer keys may
issue this purpose; not every valid signed pack/license is a bootstrap claim.
No private signing key belongs in the app or this qualification session.

The closed schema must bind claim/version/purpose, issuer/key identity, linked
entitlement identity, immutable organization, installation/host identity and its
protected key binding, unique claim identity, issuance/not-before/expiry and
revocation/reissue generation. Installation identity needs proof of possession
from the protected host, not a caller-supplied UUID. The issuer controls the
business-to-installation assignment; arbitrary setup text cannot mint it.
Native-person identity is added only by a verified consumption request, bound to
a stable operation identity and digest of the exact initialization payload.
Replays must match claim, installation, organization, native principal, operation
and payload. Changed bindings are conflicts. Schema-expressible constraints
belong in closed models/schema; semantic checks have one owner, no parallel regex.
Exact wire schemas, numeric bounds and approved key-purpose policy remain
acceptance inputs, not permissive implementation defaults.

### One-time consumption, revocation and reissue

**Recommended lifecycle owner:** place the new authoritative claim lifecycle
with the licensing owner; the protected local host owns the resulting employee/admin
state. A signed file plus a local consumed flag alone cannot prove one-use after
rollback, restore or reinstallation, or that a remote revocation is current.
No such lifecycle/status interface exists in the inspected issuer. A new
licensing interface and its availability/retention costs must be qualified and
accepted separately; do not silently treat the proposed online licensing service
as implemented or impose a new network dependency through this document.

Required semantics for that interface are a durable, serialized claim transition:
an eligible claim may be consumed once, revoked, expired or superseded. Exact
authenticated operation replay returns its same bound receipt; another principal
or payload cannot consume it again. Revocation winning before consumption denies
bootstrap. Consumption winning first preserves that owner binding: revoking or
reissuing an owner claim cannot elect a replacement admin. Reissue of an unconsumed
claim revokes/supersedes it before making a new claim eligible, with a new claim
identity and generation. Recovery of an already consumed claim is a separate
owner-authorized process, never implicit enrollment or an empty-store reset.

The protected host must durably record a bound pending operation before requesting
consumption, then commit the verified receipt, owner/admin mapping and minimal
audit in its own transaction. It must recover a lost response from the same
authoritative operation. Do not claim a transaction across issuer and host.
After an ambiguous consumption result, retain pending state and reconcile that
operation; never try a new owner or claim automatically. Recheck native identity
and validity after waits before local publication; a consumed claim with interrupted
local completion remains reserved to its original binding, not newly available.
The issuer receives only the necessary business/installation references and an
opaque commitment to the local consumption binding, never native credentials,
account names or lead content. Pin retention and recovery of that commitment in
the licensing work order; it must not become an employee directory.

**BLOCKER B0-I — issuer interface and freshness:** pin how the existing licensing
owner provides current consumption/revocation state, authenticates installation
and recovery requests, proves resistance to rollback and delivers a bound receipt.
The authorization and path for revoke/reissue must be independent of possession
of the leaked claim. If reaching authoritative state requires a licensing network
call, disclose and obtain acceptance of that dependency before implementation;
local lead operations must not gain a continuous licensing-status dependency.
Stale, unavailable or unverifiable state refuses bootstrap with an explicit
unavailable result. No disconnected client may claim instant remote revocation.
License renewal/expiry must not erase or reset the established owner; existing
feature gating remains separate. B0's trust-source choice is settled; B0-I is not.

This mechanism is **PROPOSED and unqualified**. No employee, grant or session may
be created on the strength of this prose. An unrelated administrator without a
valid scoped authorization must be denied through the supported bootstrap
interface. This does not promise protection from a compromised kernel or an
attacker replacing the protected host/trust anchor; pin that computing boundary.

## Native mechanism pins and protected ownership

**BLOCKER B1 — native feasibility:** before executable acceptance, identify exact
supported Linux desktop/distribution and Windows versions, service principal,
local authentication broker, verified per-request caller binding, fresh sign-in
and current interactive-session/lock APIs. Pin the API/library versions, approved
local authentication configuration, IPC framing/ACL policy and public upstream
references. Do not choose an API solely because it reports an account name.
Individual employees need distinct verified native principals. Refuse mapping
one principal to multiple employees. People sharing the same native credentials
are not distinguishable by that credential; shared-account use is unsupported,
not something these tests may claim to detect automatically.

The existing [protected-read feasibility inventory](LEAD-PROTECTED-READ.md#platform-feasibility-evidence-versus-proposal)
names candidate native primitives and their unresolved limits. It is a proposal,
not an accepted native adapter. In particular its same-account credential proof
does not establish employee identity, and its Linux lock-state question and
Windows sign-in/session binding remain qualification obligations. This contract
does not bless those candidates by repetition or claim they were rerun.

| Owner | Required boundary in this qualification | Excluded responsibility |
| --- | --- | --- |
| Licensing/release owner, using existing issuer trust chain | Authorize business/installation binding; issue companion claim; own authoritative consumption, revoke/reissue and bound receipts under B0-I | Native employee authentication, lead data, granting ownership from installer privilege or a new identity cloud service |
| Existing Connect/Automate protected host seam | Own installation identity, immutable org scope, employee enrollment/role, bootstrap consumption, host sessions and authority versions | Source/custody/workflow SQL or a second scheduler/lead store |
| Native adapter under that host | Verify current caller/person/session and perform fresh native authentication using pinned mechanisms | Trusting webview JSON, an account name/PID alone, a copied result or a transport bearer |
| Existing policy evaluator | Evaluate the existing closed human-operation catalog using host-acquired facts | Becoming a native credential verifier or accepting a machine as an employee |
| Existing source/custody/runtime owners | Remain unchanged regression references | Being exposed to employee clients during this qualification |

The protected host owns its authority state through one access interface. Its
physical placement and any authority-only tables/schema must be pinned in the
subsequent implementation work order. No second custody store or cross-owner SQL
is permitted. Normal employee processes must be unable to read, replace, restore
or impersonate protected state/keystore. Test same-user exposure explicitly;
private filenames or file modes under the employee's own identity are insufficient.

Machine grants remain absent in V1b.1. Successful owner bootstrap/sign-in does
not publish source keys or authorize a sender, rule, route, content read or
custody operation. Do not extend `_host_policy`'s catalog to disguise enrollment
or machine delegation as an existing human operation.

## Required qualification behavior and failure/recovery contract

These are proof obligations for a later, explicitly authorized disposable run;
they are not implemented APIs or approval to run now.

1. Verify installation and the purpose-specific license-backed authorization
   before opening a bootstrap mutation. Authenticate its holder natively and bind
   the request channel; reject unknown/locked/shared-account identities and
   ordinary licenses presented as owner claims.
2. The licensing owner serializes claim consumption against revoke/reissue; the
   protected host serializes local bootstrap. Follow the pending-operation and
   receipt protocol above. After waits, recheck claim, validity and native state.
   Initialize immutable installation/org identity, individual owner/admin mapping,
   consumed receipt and minimal audit in the same local transaction. Concurrent
   callers cannot elect different owners or create partial local admin state.
3. Recheck the relevant authority and native state before commit and before
   releasing a result. Define the adapter's observation point honestly: a host
   lock cannot control an independent OS lock/logout event. Unknown state denies;
   no claim of atomicity across OS state and SQLite.
4. Exact authenticated bootstrap replay may recover the same committed outcome;
   a changed scope/person/payload/operation is a conflict, never a new bootstrap.
   A lost response or post-commit crash does not justify deleting/reinitializing
   authority. Corrupt/missing-after-initialization state requires controlled
   recovery, not fallback to an empty store. Crash before commit leaves no partial
   identity, role, audit or locally consumed proof. Issuer-side consumption may
   already have committed; recover its receipt rather than declaring rollback
   across the application boundary or making the claim reusable.
5. Native sign-in maps a verified person to the existing individual employee,
   immutable org and current role. Session handles are opaque, host-issued and
   bound to person, native interactive session, channel and host incarnation.
   Possession of a copied handle is insufficient. Pin absolute session lifetime,
   fresh-verification window, clock behavior and finite request/queue limits
   before acceptance; no sliding/default-unbounded session.
6. Logout, disablement, role change, expiry, lock and restart deny further
   interactive use. Check after waits and before any response. Test both orders
   of revocation versus session issuance/validation. A locked human session does
   not erase a future already-delegated machine grant; that separate authority is
   not created or exercised here.
7. No personal-data response or privileged business effect is reachable. The
   qualification result contains only synthetic references, selected native
   mechanism, outcome and evidence identity. Keep secrets and authentication
   conversations outside ordinary records, logs, command lines and public CI
   artifacts. Agents never read or copy real credentials.

Do not borrow the source database lock as employee authorization or claim a
cross-store transaction. This first qualification touches no source transaction.
Later cross-owner enforcement must explicitly adopt or supersede the proposed
[protected-read host-gate ordering](LEAD-PROTECTED-READ.md#canonical-host-gate-requirements)
in its own accepted contract, including busy waits, finite queues, fairness,
response bounds and owner death. That proposed gate is not implemented here.

## Proof matrix and executable acceptance gates

**BLOCKER B2 — reproducible run pin:** before running, record disposable environment
and native account ownership, exact scripts/revisions, permitted setup/teardown,
selected B0-I/B1 mechanisms, session/freshness/capacity/timeout values and secret-free
evidence schema. Pin all numeric bounds with boundary assertions in that revision.
Native account, service, dependency or VM setup requires its own explicit run
authority. This draft authorizes none on Juan's workstation or any other host.

| Required proof | Decisive assertions; evidence to retain |
| --- | --- |
| Owner authority | Valid scoped issuer claim plus fresh native holder succeeds; unrelated employee/admin/installer without that claim cannot self-enroll. Ordinary license, wrong-purpose/key, forged, missing, revoked, expired and wrong-installation/org/key-binding inputs fail without authority writes. Test actual signature/provenance verification with disposable issuer keys, not a pretrusted boolean. A valid leaked claim can be won by another eligible holder before consumption/revocation: preserve that disclosed trust limit. |
| Claim lifecycle | Both consumption/revocation orders, atomic supersession/reissue, claim copied to another installation, restored local state, competing native holders and unavailable/stale status. Same operation resumes after issuer or host crash/lost response; changed principal/payload fails. Already consumed claims cannot create replacement admins. Compromise recovery requires independent licensing authority. Pin and exercise the real B0-I mechanism before claiming one-use or current revocation. |
| Native identity | Real caller/person/session binding; claimed actor, inherited/transferred handle, sender change, process exit/reuse, account reuse and shared-account ambiguity cannot impersonate the owner. Fresh sign-in is independent of channel identity. |
| Bootstrap linearization | Separate native processes, exact barriers, both winner orders, repeated initialization, SQL fault between writes and forced exit before/after commit. Same authenticated replay recovers the same identity; conflicts never overwrite it. |
| Session lifecycle | Locked/unlocked/unknown, logout, expiry, disable/role change and restart; revocation during a busy wait and before release. Copied handles/results, false/zero/default windows and concurrent renewals fail according to pinned rules. |
| Isolation and secrets | Actual unrelated employee cannot directly read/replace authority, keystore or source paths, including indirect restore/reparse/symlink access. Encryption and backup protection are separate proofs, not inferred from ACLs. No raw credential in diagnostics or evidence. |
| No effects / parity | Existing entitlement-v1/policy/source/custody/runtime schemas and tests unchanged; no production issuance, Connect registration, provider discovery, source authority publication, body read, Gmail, workflow dispatch or lead creation. Only an expressly authorized disposable B0-I harness may exercise claim lifecycle; deny all unapproved external calls. Assert denied calls, not just an empty result. |
| Two-platform qualification | Native Linux and Windows result packets use the same invariants and retain platform-specific blockers. Linux mocks do not pass Windows; a green existing Windows custody suite does not prove the new native boundary. |

Each new security guard needs otherwise-valid independent negative fixtures,
valid/invalid/partial/falsy/boundary probes and a deliberate fault that the
intended assertion catches. Record equivalent or unreachable mutations honestly.
Reuse the existing Linux credential probe and existing regression owners; native
adapters must be tested through real process/account/session boundaries. No
sleep-based race proof, synthetic admin grants presented as genuine authority,
or undocumented provisioned state. Record ordinary failures and ambiguous commit
outcomes as well as successes; do not count a missing test environment as a pass.

Acceptance sequence:

- B0 trust source selected through the relayed operator decision above; B0-I
  issuer mechanism, B1 native mechanisms and B2 run pins closed in a revised
  contract. Agree the licensing-side owner/work order and preserve unchanged v1
  behavior. Report any activation/connectivity or recovery tradeoff before
  acceptance; do not silently add manual key copying or self-enrollment.
- Oversight review of the exact revision, explicit operator acceptance of that
  bounded work/run order, and contract CI/connector/merge gates. Docs acceptance
  alone does not authorize unspecified account/service setup.
- Separately authorized native qualification, then recorded independent review of
  its exact evidence. A failed platform blocks its dependent enforcement.
- Only then propose the bounded executable host-authority work order. Subsequent
  V1b contracts pin admin-delegated machine grants, proof wire formats and durable
  replay/revocation at owning operations, authenticated GET results and the thin
  Connect v2 provider. No receiver activation is granted by this work order.

## Required change surface, non-scope and rollback

This PR changes only this proposed contract and the receiver roadmap's completed
V1a/next-work pointer. It preserves the entire accepted vertical plan and V1a
work order, all source/tests, schemas, dependency pins, workflows and runtime
configuration. The existing malformed `handoff_id` negative-test gap noted on
PR #71 stays deferred until that test file is next touched; no incidental test
change belongs in this contract PR.

Future qualification evidence belongs outside worktrees in the durable evidence
root, with private directory/file permissions and equivalent native ACL proof.
Its precise runnable harness/files are B2 acceptance inputs, not an instruction
to add placeholder code now. Stop before implementation or running any probe.

Non-scope: production signing keys, license issuance or issuer/service changes,
real users/credentials, installed host changes, receiver/transport
activation, account or service provisioning, Gmail/OAuth, source capture or lead
extraction, canonical lead records, UI, CRM/EOM, automatic package adoption and
the shared AI inference runtime. No new workflow engine, polling/dispatch service,
public API or cloud identity dependency. No parallel EW or shared-runtime work.

Rollback of this proposal is a documentation revert. A future qualification must
have an accepted disposable-environment teardown plan. Do not reset a protected
identity, alter current stores or remove retained proof to make a run repeatable.
For future executable authority, disabling exposure must preserve identity and
audit/replay state; its recovery/rollback is a separate acceptance input.

## Implementation summary, cold diff audit and gap audit

**Contract preparation only.** The concrete next slice is the authority
prerequisite of V1b, not V1c template discovery or another custody expansion.
Cold-audit checks: ordering against the accepted plan; source citations at the
pinned merge; prior evidence hashes; owner/native trust separation; first-admin
decision attributed to oversight's operator relay; entitlement reuse and strict
v1 compatibility; claim lifecycle's new dependency stated honestly; no changed
accepted text or executable files.
Run documentation scope/link/citation/whitespace checks only. Do not rerun code
tests or represent historical primitive/custody results as native sign-in proof.

**NOT DONE:** B0-I claim lifecycle/interface, B1 native mechanisms, B2 exact run pins,
oversight/exact-revision acceptance, qualification, integrated enforcement and
all later V1b activation remain open. Publish this contract-only draft and stop
for review. No completion, adoption or implementation authority is implied.
