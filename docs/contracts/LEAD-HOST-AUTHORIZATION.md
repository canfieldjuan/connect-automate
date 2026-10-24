# Lead host authorization: protection-and-roles work order

Status: PROPOSED work order; documentation only. The operator's instruction to
start the next slice starts this contract. It does not accept this technical
decomposition, authorize executable changes, or qualify employee access.

The [accepted application policy](LEAD-SOURCE-HANDOFF.md#decision-c-local-admin-and-user-roles-with-delegated-background-authority)
owns the admin/user/machine permissions and protected-host requirement. This
document owns the proposed implementation boundary and proof sequence. It does
not replace that policy with another permission matrix.

## Contract

### Root cause and pinned source inventory

CONFIRMED: the existing source library trusts its embedding host and private OS
user. Its license, signed-source authority and storage protections do not establish
which employee may invoke an operation. Exposing these APIs to employee processes
without the accepted protected-host boundary would promote caller-supplied identity
into authority. This is an adoption gap, not a claim that the library violates its
existing contract.

All CA citations below are repository-relative at
`9cc984f952a7fb06774cbc94068bcde7e3b94142`. They are source evidence, not claims
about an installed application. Each row is CONFIRMED by reading that revision.

| Existing owner | Evidence | Reuse and limit |
| --- | --- | --- |
| License gate | `src/connect_automate/automate/host.py:34-89` | Keep `AutomateHost.require_license`; construction/startup and the entry point check entitlement, not employee identity. |
| Signed-source admission authority | `src/connect_automate/lead_intake/auth.py:151-195` | Keep receiver, organization, key, mailbox, retention and signature checks. These authorize a source, not a human role. |
| Deployment and source transaction | `src/connect_automate/lead_intake/source_store.py:239-277`, `:383-420` | Keep immutable deployment scope and the existing writer transaction. No cross-application table access or second source store. |
| Private filesystem | `src/connect_automate/lead_intake/source_store.py:279-308`; `src/connect_automate/connect_windows.py:388-479` | Reuse path/ownership/ACL checks under the eventual service principal. They do not encrypt data or verify a different employee. |
| Authority administration | `src/connect_automate/lead_intake/source_store.py:535-591`, `:594-641` | Preserve publication CAS/history and clock reconciliation identity. These entry points do not take an employee principal. |
| Content and lifecycle | `src/connect_automate/lead_intake/content.py:74-98`, `:123-166` | Preserve source-owned read, expiry, message purge and namespace retirement. A content read can commit expiry cleanup; it is not a transaction-free read. |
| Historical workflow outcome | `src/connect_automate/automate/runtime.py:356-394` | Keep historical metadata lookup separate from content authority. Knowing a binding/event/digest is not employee record access. |
| Connect transport identity | `src/connect_automate/connect.py:98-132` | Keep existing transport ownership. Process registration and bearer transport authentication are not employee sessions. |

CONFIRMED adjacent inventory: `canfieldjuan/connect-contracts` at
`f00aad8aa3d53285c5b96afd34ecc5ec59030991`,
`schemas/v2/registration.schema.json:7-35`, describes process/loopback/bearer
registration, not an employee assertion. `canfieldjuan/local-connect-licensing`
at `9f9d1be530653300926315294ef1721ce3d4fc98` contains only `README.md` and
`docs/contracts/LICENCE-SERVICE.md` in its tracked tree. That checkout supplies no
executable employee-authentication implementation. This bounded inventory does not
establish that every repository or installed native component has been audited.

### Existing proof inventory and departures

CONFIRMED by inspection, not execution in this docs-only slice:

- `tests/test_automate_host.py:94-143` exercises entitlement behavior.
- `tests/test_lead_source_store.py:128-147` rejects identity rebinding while
  preserving published authority. The store tests also contain concurrency and
  crash fixtures; they are regression inputs, not employee-authentication proof.
- Existing source parser/authentication, content, host composition and joined
  recovery/lifecycle fixtures live in `tests/test_lead_source.py`,
  `tests/test_lead_source_auth.py`, `tests/test_lead_source_content.py`,
  `tests/test_lead_host_composition.py`, `tests/test_lead_joined_recovery.py` and
  `tests/test_lead_joined_lifecycle.py`. Preserve them unchanged.
- `.github/workflows/ci.yml` pins Python 3.13 and runs Linux tests plus an explicit
  Windows selection. `pyproject.toml` owns dependencies and test/lint settings.
  The new policy tests must enter the Windows selection on the first executable
  push. No dependency, model, prompt, inference or application-pin change is needed.

INFERRED implementation choice: introduce a private, deterministic policy evaluator
before wiring platform identity or effects. No validated employee-authentication
harness was established by this inventory. Synthetic policy contexts are new proof
of policy logic only; they are not a port of a proven sign-in implementation.
This is the sole proposed behavioral departure in the first executable increment.
Existing library behavior and fixtures remain the parity reference.

### Required change surface

This PR changes this document and adds a current acceptance/work-order pointer to
`LEAD-SOURCE-HANDOFF.md`. No executable change is included.

After review and a separate implementation instruction, the first executable
increment is bounded to proposed new files
`src/connect_automate/lead_intake/_host_policy.py` and
`tests/test_lead_host_policy.py`, plus the Windows test selection in
`.github/workflows/ci.yml`. These paths are planned, not existing interfaces.
The private policy owner has no imports from source stores, runtime dispatch,
network, filesystem, native authentication or secret storage. Existing model
validation dependencies may be reused; do not add a framework or dependency.

It evaluates an explicit operation against a validated snapshot of host-owned
facts. It performs no I/O, signs nothing, issues no session and executes no effect.
It must not be wired into current public APIs in this increment.

### Policy input and result contract

Proposed internal version `1.0`; this is not a wire protocol. Use closed, immutable
models that validate on every evaluation, including previously constructed model
instances. Unknown fields, unsupported versions, missing fields and type coercions
fail closed. Never accept a serialized client context as authenticated evidence.

The request specifies version, operation, host and organization; record operations
also specify the exact record identity. Deployment scope is supplied separately by
the host. Host, organization, enrolled employee and internal record identities use
the existing canonical UUID-v4 representation; native account names are not employee
IDs. Do not case-fold or invent fallback scopes.
Human facts identify the enrolled employee, host, organization, active/disabled
enrollment, current admin/user role, and session state (active/locked/expired/revoked).
They include observed and current authority versions as strict integers in
`1..2147483647`; the versions must match. This compares supplied facts; it cannot
prove they are current without a protected authoritative reader.

For record reads, require a resource fact with the exact host, organization, record
and employee identities, explicit active read assignment and matching observed/current
grant versions with the same integer bounds. There is no implicit admin record-read
bypass. Non-record operations
reject stray record facts. Machine identities are a distinct actor kind and cannot
be converted to an employee, assigned a human role, or use a human session.

The initial catalog maps only these operations to existing owners:

| Operation | Policy eligibility and required later enforcement |
| --- | --- |
| `source.content.read` | Active enrolled admin/user with active session and exact read assignment; host must enforce current authority before `SourceContent.read_content`, including its expiry writes. |
| `source.outcome.read` | Same human/record requirements; host resolves the exact authorized record to the workflow owner's lookup arguments. Content access does not follow from the outcome. |
| `source.authority.publish` | Active enrolled admin with active session; fresh native verification and one-use operation/payload proof required before publication. |
| `source.clock.reconcile` | Same admin requirements; bind reconciliation operation identity, expected sequence and corrected instant. |
| `source.message.purge` | Same admin requirements; bind full source-message scope and the accepted capture cutoff. |
| `source.namespace.retire` | Same admin requirements; bind exact deployment and namespace. |

This is a closed catalog, not authority to expose those APIs. Unsupported operations
(including lead approval, export, enrollment, policy editing and machine submission)
are denied by this evaluator. Their absence does not remove accepted responsibilities
or change current machine/library paths: later increments must specify their own
authenticated bindings before enabling them. In particular machine submit/resume/status
needs the receiver protocol's delegated sender/rule/version/route contract; do not
fake it by granting the machine a human role.

Return either `policy_denied` with reason `policy_mismatch`, or `policy_eligible`
with reason `policy_match` and the required enforcement class
(`session_record_read` or `fresh_admin_effect`). Denied results have no enforcement
class. The result carries no raw body, token, caller-supplied error
text or reusable authorization proof. Malformed inputs produce a fixed validation
failure; a well-formed but ineligible request produces `policy_denied`. Neither
path executes anything. No `allowed`, `authenticated=True`, signing API or dispatch
callback is provided. A copied eligible result cannot authorize an operation.

### Ownership and later enforcement obligations

The protected host must acquire identity, role, session and assignment facts from
its own verified native identity and protected state. A caller's employee ID, claimed
role, receipt ID, transport bearer token or license cannot supply those facts.
The first increment intentionally does not implement that acquisition. An eligible
result is a necessary policy calculation, never sufficient execution authority.

Before an operation is exposed, its subsequent work order must define:

- Native session verification, service-principal installation, first-admin bootstrap,
  keystore failure behavior, role/access administration and backup/restore authority.
  Reuse existing filesystem checks; do not confuse them with encryption or sign-in.
- Revocation linearization relative to each owning read or mutation, including a
  busy-store wait. Checking once before a lock is insufficient. Specify lock ordering
  or an equivalent serialization protocol across authority and resource owners;
  no direct cross-application database access or invented cross-store atomicity.
- Fresh privileged verification bound to employee, organization, audience, operation,
  exact payload, nonce and versions. Durable consumption and operation recovery must
  handle crash/lost response without permitting a second effect or losing a committed
  effect. Consuming a proof and then calling a non-atomic API is not that guarantee.
- Separate machine delegation and human authority, minimal actor/version/operation
  audit records, and release of data only after the final authorization checkpoint.
  Denials must not reveal whether a restricted record exists.

These obligations remain mandatory even if all policy-core tests pass. Native
platform adapters, authority persistence and operation enforcement require separate
bounded contracts and proofs; this work order does not preselect a native mechanism
without testing it on Linux and Windows.

### Explicit non-scope

Do not modify existing source schemas, signatures, stores, clocks, purge rules,
workflow/action identities, runtime methods, Connect transport, entitlements,
mailbox polling, EOM behavior, fixtures or dependency pins. No public endpoint,
service installation, SQLite migration, enrollment, new workflow engine, user UI,
live mailbox, external provider, canonical lead, delivery or production adoption.
Do not add an audit database or a second copy of business records to the pure core.

### Assumptions and blockers

CONFIRMED: A/B/C acceptance is recorded in the linked handoff acceptance note.
UNKNOWN: native employee identity/session mechanism, protected installation and
keystore availability on target machines, authoritative role/grant persistence,
and the per-operation concurrency/recovery protocol. These block employee-facing
integration and G6 qualification, not review of this isolated policy proposal.
The decomposition and internal policy contract remain proposed until reviewed;
passing review does not itself authorize the next executable increment.

### Verification plan

For this docs-only PR: validate every cited path/range against its pin, inspect the
complete diff and run `git diff --check`. Do not rerun code suites for prose changes.
Record inventory, citation checks and cold audit outside the worktree. No runtime
or security claim follows from that check.

For the future policy increment:

- Fail first on the absent evaluator with named synthetic fixtures; then positive
  and negative cases for every catalog operation and actor/role combination.
- Isolate each rejection: wrong host/org/employee/record, absent/inactive assignment,
  disabled enrollment, locked/expired/revoked session, stale authority/grant version,
  unsupported operation/version and machine-to-human confusion. Each fixture must
  satisfy all earlier checks so its intended guard alone catches the corruption.
- Probe missing/mixed/extra fields, empty strings, `0`, `False`, null, positive
  version boundaries and wrong types without default coercion. Unknown operations
  and malformed model instances fail closed. A valid assigned user read remains
  eligible; a valid admin effect remains only eligible with its proof requirement.
- Confirm deterministic results, input immutability, no I/O/dispatch side effects,
  fixed non-sensitive errors and no public export/wiring of policy decisions.
  Do not label supplied-fact tests forged-credential, one-use-proof or race proof.
- Run the new policy file, adjacent host tests and Ruff locally; preserve old source
  tests unchanged and let required Linux/Windows CI run the regression lanes. Include
  the new file in Windows CI from the first push. Record exact tested revisions.

Before employee access: reproduce real forged-caller denial, privileged proof replay,
both revocation/wait orders, locked-session reads, service/keystore failures and
ordinary-user direct-file denial on both native platforms. Exercise the real owners,
including expiry writes during reads, and prove authorized operations still work.
G0 work-order review and policy fixtures do not pass G6 or adoption.

Rollback for this document is a documentation revert. The isolated core can later
be removed without data migration because it creates no state or integrations.
After any future service activation, rollback must stop new employee operations and
preserve protected authority/history; never restore direct database access.

## Implementation summary and cold diff audit

This change writes the proposed work order and links the accepted parent policy.
No code or tests are added or altered. The cold audit must confirm that each changed
document traces to that scope and that accepted policy has not been silently revised.

## Gap audit

NOT DONE: technical work-order review, executable policy implementation, native
identity, protected-host installation, real authorization enforcement and adoption
qualification remain outstanding. This document is not an employee-access feature.

## Protected-read continuation

The private evaluator is present in the pinned source inventory of the
[protected-host read proposal](LEAD-PROTECTED-READ.md). That proposal owns the
next native-identity and single-read feasibility boundary. It does not broaden
this work order or qualify native authentication, employee access or adoption.
