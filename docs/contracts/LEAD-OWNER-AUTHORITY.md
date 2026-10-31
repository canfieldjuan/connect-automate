# V1b.1: owner bootstrap and native admin qualification

Status: **PROPOSED, CONTRACT ONLY. Owner authority and native mechanism pins are
unresolved. Not ready for executable acceptance. Stop for oversight review and
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
| CONFIRMED | `LI/_host_policy.py:1-7,35-66,97-158` validates supplied scope/actor/session/version facts and returns eligibility. Its machine actor is denied by the human policy catalog. It acquires no native identity and grants no execution authority. |
| CONFIRMED | `LI/custody_protocol.py:102-110` contains an enrolled-machine UUID and opaque proof reference. Neither verifies a credential. `LI/custody_handoff.py:124-191` revalidates runtime/route/store/request references, not the caller's native identity. |
| CONFIRMED | `LI/auth.py:82-109,151-195` validates source-trust snapshots and source signatures against host/org/namespace/mailbox/retention grants. It is not deployment-owner bootstrap, employee sign-in or a transport-control verifier. Keep that owner and signing preimage unchanged. |
| CONFIRMED | `LI/source_store.py:396-464` enforces current-process/private-path assumptions; its comment explicitly trusts same-user processes. Those checks do not isolate employees sharing the store account or establish encryption, owner authority or login state. |
| CONFIRMED | `LI/custody_store.py:135-196` already owns custody mutations and retained reads. `LI/source_store.py:551-592,604-624` owns source writer/commit and query-only snapshots. New host authority must not read/write these tables or duplicate these transactions. |
| CONFIRMED | `CA/connect.py:98-134,330-364` defines registry bearer transport, one hashed input artifact, bounded scalar parameters and output bytes. These are reusable transport contracts, not employee or business-owner identity. |
| INFERRED | The first missing owner in the accepted vertical is protected host authority acquisition. Adding another policy result type or trusting test-populated admin rows would leave that boundary missing. |
| UNKNOWN | An independently trusted business deployment-owner anchor, complete native sign-in/lock mechanism, protected service/keystore installation and native cross-account isolation are not qualified by these paths. No global claim about uninspected products is made. |

### Bounded reuse search and existing proof

Read-only searches of tracked local trees also covered `local-connect-status`
at `d94c84f4f6c49fa22273d693bc3e6fd36f61f8ec`, `local-connect-licensing`
at `9f9d1be530653300926315294ef1721ce3d4fc98`, and `local-connect-model-host`
at `f707665d801db2ff05759bea83be3e7d92080a53` for first-admin,
deployment-owner, native-identity, bootstrap and enrollment references. This
bounded search did not establish an implemented business-owner bootstrap.
It is not an audit of all branches, installed services or unpublished work.
The licensing checkout contains documentation, not a reusable identity service;
the model host remains inference infrastructure, outside this lane.

`connect-contracts` at `a168b9a67450556d95b4939a59ca36aa7aedfda5`,
`schemas/v2/registration.schema.json:7-35`, declares loopback/bearer registration,
not delegated business-owner or employee authority. No cross-repository change
or dependency/pin update is proposed here.

Retain these existing proof inputs and their limits:

| Inventory | What can be reused; what cannot be claimed |
| --- | --- |
| `tests/test_lead_host_policy.py:35-369` | Closed-policy matrix, scope/version/role checks, copied-value rejection and no-I/O tests. These test supplied facts; they do not authenticate a human. |
| `tests/test_automate_host.py:94-134`; `tests/test_windows_connect.py:138-426`; `tests/test_locking.py` | License, private-path and lock regression owners; preserve their existing behavior. Native employee isolation or session proof does not follow from their presence. |
| `protected-host-read-contract/linux-credential-probe.py`, SHA-256 `9c50cf68c94856e442e2a6b1e698cac79bbe7b82f27232b7e2622d1ff518b693` | Existing unnamed-socket credential probe; hash rechecked, not rerun. Reuse it rather than inventing a replacement identity simulation. |
| `protected-host-read-contract/linux-credential-result.json`, SHA-256 `5ecf067de3fc283471bfd31948ce9f59388ca6f1781d423a92f185b2ca327ef8` | Recorded same-account Linux primitive: actual sender differs from claimed/connection identity and forged credentials are refused. Explicitly not sign-in, separate-account isolation or Windows proof. |
| V1a receipt above | Completed custody vocabulary/recovery regression reference. No human, machine-control or transport qualification. |

There is no model, prompt, inference runtime or real-message fixture in this
port inventory. Proposed departures are native identity acquisition, protected
owner bootstrap and session qualification. Existing policy, source, custody,
retention and workflow behavior remains the parity reference. No application
tests or native probes are executed for this documentation PR.

## First-admin bootstrap: unresolved authority, one hardened recommendation

Oversight explicitly carried this forward in mailbox `289865d6`: pin a concrete
first-admin bootstrap needing no enrollment step, or bring the blocker to Juan.
The accepted plan did not select the underlying authority. Naming a protected
file, keystore or native API would not supply that missing trust source.

**BLOCKER B0 — operator decision:** what independently trusted, local ownership
record or provisioning process establishes the business deployment's owner
before the first application caller? No such record or process is assumed to
exist. Juan's acceptance of this prose is not itself a runtime credential.

**Recommended constraint:** bootstrap must require an independently authenticated
deployment-owner authorization already bound to this installation, immutable
organization and intended native person, plus fresh native verification of that
same person. The protected host alone consumes it and creates the initial admin
atomically. Integrate that proof into the normal trusted installation/first-use
flow; do not require enrollment commands, key copying or a parallel cloud identity
service. The provenance and delivery of the initial owner authorization must be
selected before this mechanism can be implemented or tested as authoritative.

The closed bootstrap binding must cover installation/host and organization,
owner/native-principal binding, authorization issuer/trust-anchor identity and
version, one-use operation identity, exact initialization payload digest and
validity/revocation policy. Bootstrap authority must not be issued by the same
unverified caller it is intended to authorize. Its verifier/trust-anchor delivery,
native identity representation and finite time/size bounds are acceptance inputs,
not fields an implementation may fill with permissive defaults.

This is a required mechanism shape, **not a claim that a concrete bootstrap
issuer/verifier exists**. Until B0 is resolved, return an explicit bootstrap
unavailable outcome; do not create an employee, grant or session. An administrator
of the OS, the installer process, an entitlement, an email address, an owner name
typed into setup, a UUID or a signed artifact from an untrusted key is insufficient.
No "first caller wins", implicit recovery enrollment or restored-empty-store reset.
An unrelated administrator must be denied through the supported bootstrap
interface. This is not a promise to withstand a compromised kernel or an attacker
who can replace the protected host and its trust anchor; pin that trusted computing
boundary rather than claiming ordinary process isolation defeats OS takeover.

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
| Trusted deployment provisioning | Establish and deliver the independently verified owner authorization selected under B0; preserve it across restart without caller substitution | Granting ownership from installer privilege or creating a new identity cloud service |
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

1. Verify installation and owner authorization before opening any bootstrap
   mutation. Authenticate the native person and bind the current request channel;
   reject unknown/locked/shared-account identities and unverified owner records.
2. A single authority owner serializes bootstrap. After any lock/store wait,
   reload owner authorization, revocation, validity and native state. Initialize
   immutable installation/org identity, individual owner/admin mapping, consumed
   operation identity and minimal audit in the same durable transaction. Concurrent
   callers cannot elect different owners or create partial admin state.
3. Recheck the relevant authority and native state before commit and before
   releasing a result. Define the adapter's observation point honestly: a host
   lock cannot control an independent OS lock/logout event. Unknown state denies;
   no claim of atomicity across OS state and SQLite.
4. Exact authenticated bootstrap replay may recover the same committed outcome;
   a changed scope/person/payload/operation is a conflict, never a new bootstrap.
   A lost response or post-commit crash does not justify deleting/reinitializing
   authority. Corrupt/missing-after-initialization state requires controlled
   recovery, not fallback to an empty store. Crash before commit leaves no partial
   identity, role, audit or consumed proof.
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
selected B0/B1 mechanisms, session/freshness/capacity/timeout values and secret-free
evidence schema. Pin all numeric bounds with boundary assertions in that revision.
Native account, service, dependency or VM setup requires its own explicit run
authority. This draft authorizes none on Juan's workstation or any other host.

| Required proof | Decisive assertions; evidence to retain |
| --- | --- |
| Owner authority | Valid independently verified owner succeeds; unrelated local employee and unrelated OS admin/installer cannot self-enroll. Forged, missing, revoked, expired, wrong-installation/org/person and swapped trust-anchor inputs fail without writes. Test the true provenance verifier, not a pretrusted fixture boolean. |
| Native identity | Real caller/person/session binding; claimed actor, inherited/transferred handle, sender change, process exit/reuse, account reuse and shared-account ambiguity cannot impersonate the owner. Fresh sign-in is independent of channel identity. |
| Bootstrap linearization | Separate native processes, exact barriers, both winner orders, repeated initialization, SQL fault between writes and forced exit before/after commit. Same authenticated replay recovers the same identity; conflicts never overwrite it. |
| Session lifecycle | Locked/unlocked/unknown, logout, expiry, disable/role change and restart; revocation during a busy wait and before release. Copied handles/results, false/zero/default windows and concurrent renewals fail according to pinned rules. |
| Isolation and secrets | Actual unrelated employee cannot directly read/replace authority, keystore or source paths, including indirect restore/reparse/symlink access. Encryption and backup protection are separate proofs, not inferred from ACLs. No raw credential in diagnostics or evidence. |
| No effects / parity | Existing policy/source/custody/runtime schemas and tests unchanged; no Connect registration, provider discovery, source authority publication, body read, Gmail, workflow dispatch, lead creation or external request. Assert denied attempted calls, not just an empty result. |
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

- B0 owner trust source chosen by Juan; B1 mechanisms and B2 run pins closed in a
  revised contract. If no compliant local owner-proof mechanism can be identified,
  report that product/setup blocker; do not silently add manual key copying or
  self-enrollment.
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

Non-scope: real users/credentials, installed host changes, receiver/transport
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
blocker carried from oversight; no changed accepted text or executable files.
Run documentation scope/link/citation/whitespace checks only. Do not rerun code
tests or represent historical primitive/custody results as native sign-in proof.

**NOT DONE:** B0 ownership authority, B1 native mechanisms, B2 exact run pins,
oversight/exact-revision acceptance, qualification, integrated enforcement and
all later V1b activation remain open. Publish this contract-only draft and stop
for review. No completion, adoption or implementation authority is implied.
