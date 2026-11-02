# V1b.1-H1: offline owner-authority harness preparation

Status: **PROPOSED WORK ORDER; DOCUMENTATION ONLY.** Juan authorized drafting
this work order and sending it to oversight. He has not authorized harness
implementation, native proof, preflight, setup, accounts, keys, issuer changes or
live work. Review, CI, merge and acceptance of the parent plan grant none of those.

## Contract and root cause

The [owner-authority plan](LEAD-OWNER-AUTHORITY.md) was accepted as a plan at
`314b43a6a8d4860fd6ca0f17bab1427059f7dea7` and merged by PR #72 as
`b8ad3da2f0bc14451da1a5fbe833a70885e03ae9`. Its B0-I, B1 and B2 sections define
proposed interfaces, native mechanisms and qualification obligations. They are
the requirements, not proof that an implementation exists.

**Broken assumption to prevent:** supplied policy facts, a simulated issuer
receipt or hosted CI could be mistaken for verified deployment ownership or
native authentication. Preparation must make their evidence classes distinct
before a native run is possible. This work order proposes a runnable offline
transaction/recovery harness, not another eligibility-only model and not a new
product authority store.

### Source and proven-work inventory

All repository source references below are pinned to
`b8ad3da2f0bc14451da1a5fbe833a70885e03ae9`; `CA` means `src/connect_automate/`.

| Label | Inventory and actual limit |
| --- | --- |
| CONFIRMED | `CA/automate/host.py:34-89` implements an entitlement-gated skeleton. `start()` checks licensing; it does not bootstrap an admin or expose a native receiver. |
| CONFIRMED | `CA/entitlement.py:138-166` has closed entitlement-v1 models; `:402-418` owns shared Ed25519 verification. Reuse that verifier with explicit synthetic keys; do not extend entitlement v1 into an owner claim. |
| CONFIRMED | `CA/lead_intake/_host_policy.py:1-6,25-32,35-77` declares eligibility over supplied immutable facts, not credentials. `tests/test_lead_host_policy.py:332-376` covers copied-result refusal and no-I/O policy evaluation, not sign-in. |
| CONFIRMED | `CA/lead_intake/custody_protocol.py:102-110` carries an opaque proof reference; `custody_handoff.py:124-145` validates composition/configuration. Neither is native verification. Preserve these boundaries. |
| CONFIRMED | `pyproject.toml` pins Python >=3.13 and existing dependency ranges; `.github/workflows/ci.yml` runs Python 3.13 on Linux and Windows. These are portable regression lanes, not desktop qualification. |
| CONFIRMED | Retained evidence alias `protected-host-read-contract/linux-credential-probe.py`, SHA-256 `9c50cf68c94856e442e2a6b1e698cac79bbe7b82f27232b7e2622d1ff518b693`, creates an unnamed AF_UNIX socketpair, reads kernel message credentials and attempts a forged credential. Its source was inspected and hash rechecked; it was not executed for this work order. |
| CONFIRMED | Alias `protected-host-read-contract/linux-credential-result.json`, SHA-256 `5ecf067de3fc283471bfd31948ce9f59388ca6f1781d423a92f185b2ca327ef8`, records same-account primitive results only. It explicitly excludes sign-in and service isolation. No Windows, lock-state or distinct-account success follows from it. |
| UNKNOWN | Protected-service verification of first-use Hello/passwordless enrollment, actual licensing-service consumption, native isolation and native session revocation remain unqualified. No current harness result exists for this profile. |

The retained probe uses Python's standard library, a fresh child process and
no model, prompts or message content. Preserve its exact bytes and original
result as reference inputs. Running it again requires separate native-run
authority. No model/runtime migration or AI extraction belongs here.

### Intentional departures from the inventory

- Add a harness-only protocol adapter, disposable issuer/local ledgers and
  adversarial transaction tests. They simulate B0-I consumption/local recovery;
  they are not the licensing owner's implementation or genuine owner enrollment.
- Add an offline controller and evidence manifest that distinguish portable
  assertions from native obligations. They cannot call installed host entrypoints.
- Defer native helper implementations and process/account/session experiments
  to their own bounded work order and go. Retain the parent's proposed helper
  paths as future inventory; do not replace them with successful fake adapters.
- Do not port the retained native probe into ordinary pytest collection. Only
  hash/read its approved reference during offline preparation.

Parity with existing license, policy, source, custody and workflow behavior
precedes any future production port. A simulator result is never parity with an
unimplemented service. Every later departure needs its own inventory and review.

## Ownership, established contracts and smallest change

| Owner | Established seam and why it needs preparation | Proposed bounded change | Preserved invariant |
| --- | --- | --- | --- |
| Lead Intake qualification harness | Parent B0-I wire/lifecycle requirements have no harness at this baseline | Build isolated fixtures, offline adapter, temporary ledgers, controller and evidence checks | No simulator result grants authority or invokes product operations |
| Licensing/release owner | Parent B0-I names a new consume interface, not an implemented service | Review its own contract separately; no changes in that repository in H1 | Issuance, consumption and revocation remain that owner's responsibility |
| CA entitlement verifier | Existing `verify_signature` already verifies Ed25519 bytes | Call it from fixture conformance tests with explicit test key mappings | Installed trust, environment lookup and entitlement-v1 contracts unchanged |
| Existing CA source/custody/runtime owners | Existing private APIs already own their records | Preserve source and tests unchanged; no owner-DB reads by the harness | No new source keys, machine grants, content reads, workflow dispatch or lead records |
| Native qualification owner/operator | B1 verification and B2 environment/run controls are unproved | Describe pending cases; do not install/build/run native helpers in H1 | Unknown native trust fails closed and blocks dependent enforcement |

Logical ownership is unchanged. Separate disposable issuer and host stores model
the application boundary; neither reads the other's tables. Use explicit
test-only APIs and receipt exchange, never cross-database SQL or a claimed
transaction spanning both stores. No Connect provider, scheduler or dispatch
mechanism is added.

## Required change surface and stacked implementation slices

Propose these stacked PRs in dependency order, each about 1,000 changed lines
including tests, fixtures and generated schemas. Split further by concern before
exceeding that budget; do not omit tests to fit. Each slice needs its own review
and CI gates and adds its own portable tests to the existing Windows invocation
from its first push. Naming the stack authorizes no implementation.

| Slice | Bounded concern and owned paths from the inventory below |
| --- | --- |
| H1a: protocol and schemas | `protocol.py`, derived `run.schema.json`/`result.schema.json`, and `tests/test_owner_harness_protocol.py`; schema-level offline-only results and literal non-qualification first |
| H1b: disposable ledgers and recovery, stacked on H1a | `licensing_fixture.py`, `host_fixture.py`, and `tests/test_owner_harness_recovery.py`; independent issuer/local transactions, race ordering and crash/replay assertions |
| H1c: controller and evidence, stacked on H1b | `controller.py`, `cases.json`, `README.md`, and `tests/test_owner_harness_controller.py`; offline commands, native refusal, immutable case inventory and bounded evidence collection |

Each slice may update only its necessary shared model/schema seam and Windows
test entries in addition to those owned files. Preserve one protocol/schema
owner across the stack; do not duplicate it to make a slice standalone. H1 is
complete only after the full stack's requirements and evidence are reconciled.

This document is the entire current change surface. The following paths are
**proposed future files**, not files created or execution authorized here:

| Proposed path | Responsibility |
| --- | --- |
| `qualification/owner_authority/controller.py` | Offline manifest inspection, case selection and evidence collection only; no shell evaluation, privileged commands, installed-config discovery or native dispatch |
| `qualification/owner_authority/protocol.py` | One closed model/validator owner for the parent B0-I wire profile, canonical encoding and per-type budgets; test-only adapter, no published API |
| `qualification/owner_authority/licensing_fixture.py` | Disposable issuer emulator: issue/consume/revoke/reissue and receipt lookup through its own API, isolated from all real issuer state |
| `qualification/owner_authority/host_fixture.py` | Disposable local pending/receipt/admin/audit transaction model; accepts synthetic observations only in offline cases |
| `qualification/owner_authority/cases.json` | Closed case inventory: each case's evidence class, requirement, expected result, assertion and allowed capabilities |
| `qualification/owner_authority/run.schema.json`, `result.schema.json` | Derived schema artifacts from the single model owner, checked for drift; no separately handwritten duplicate validation |
| `qualification/owner_authority/README.md` | Offline commands, evidence limits, freeze process, current blockers and the later separately authorized native handoff |
| `tests/test_owner_harness_protocol.py`, `test_owner_harness_recovery.py`, `test_owner_harness_controller.py` | Portable adversarial schema, process/transaction and controller tests using synthetic fixtures and private temporary roots |
| `.github/workflows/ci.yml` | In each later implementation slice, append that slice's new portable tests to the existing Windows focused pytest invocation from its first push; preserve existing jobs, platform pins and test entries |

No new dependency or native compiler/SDK installation is assumed. The baseline
Linux job discovers new tests; the Windows job has an explicit file list, so
the narrow invocation addition above is required from the first implementation
push. No new CI job or native platform qualification is introduced. Any dependency
or other workflow change needs a stated scope revision before editing. Native helper
sources/builds, protected-service adapters and actual licensing clients are not
part of H1. Shared wire publication belongs to its owning cross-repo contract,
not an accidental export from this private harness.

### Schema and evidence rules

The parent B0-I table is the specification for claim/manifest/request/receipt
fields, purpose separation, clocks, canonical bytes and type-selected wire
budgets. Do not copy its constants into multiple independent validators. Use
closed types, schema constraints and one named cross-field validator where
necessary; an origin is parsed as a URI, never checked with ad hoc substring
tests. Preserve duplicate-member rejection before model admission.

H1's closed `result.schema.json` admits only the evidence class
`OFFLINE_CONFORMANCE` (`const`), and every packet requires
`qualification_pass: false` (`const`). It has no overall PASS field or aggregate
PASS outcome. Schema admission rejects `NATIVE_QUALIFICATION`, a copied native
PASS, a true/missing qualification flag and any extra overall-PASS field, even
when the controller is bypassed. Per-case offline PASS/FAIL/STOP records describe
only the individual offline assertions; none is qualification success. A later
native work order must revise the schema under its own acceptance.

Native cases exist only as `NOT_RUN` entries in `cases.json`; that inventory
branch cannot carry an execution result. A requested native execution returns
an offline STOP refusal before I/O with a fixed harness reason. Never infer
trust from a copied policy result or mark a required case optional. Parent
per-case PASS/FAIL/STOP semantics remain unchanged; `NOT_RUN` is inventory
metadata, not a new execution outcome.

H1's offline interface is `controller.py inspect --manifest <absolute-path>`
and `controller.py offline --manifest <absolute-path>`. Both read only the
explicit synthetic input allowlist and use a caller-selected private temporary
output root. Do not create runnable native `preflight`, `run` or `collect`
entrypoints in H1. If those names are requested, refuse before opening paths,
enumerating accounts, loading installed configuration or creating output.
The parent's native commands remain reserved for separately accepted work.

All artifacts identify the parent contract commit, harness commit, case ID,
evidence class, expected/actual codes, assertion IDs and public fixture digests.
Record environment/version hashes from the actual later build, not invented
values. No credentials, private signing material, user profiles, email bodies
or personal narratives enter logs or public artifacts. Temporary test signing
keys may be generated only in a later explicitly authorized offline test run;
they stay in that private temporary root, are never installed and are never
retained in evidence. This work order creates none.

## Verification plan for later H1 implementation

| Gate | Required assertions and evidence; no success is claimed now |
| --- | --- |
| Portable protocol | Valid samples for every wire type; wrong purpose/signature/key, duplicate/extra/missing fields, mixed/partial input, malformed encoding and independent otherwise-valid corruptions. Every individual guard must catch its own fixture. |
| Limits and time | Parent per-type budgets and maximal field-derived manifest; intended early cap catches over-limit input before decode/verification. Cover min-1/min/max/max+1, false/zero/empty/default defeats, wrong types and unreachable boundaries honestly. Reuse the parent's exact clock-window and activation/expiry cases without clock changes on the host. |
| Consumption and replay | Separate issuer and host processes, immutable binding, exact authenticated-request replay, changed organization/principal/key/payload conflict, revoke/consume in both orders and reissue supersession. Synthetic native observations are explicitly labelled. |
| Recovery and atomicity | Explicit barriers, both race winners, SQL failure between each local row write, lost response and process death before/after issuer and local commits. Inspect each store through its own API. Same receipt resumes; no partial admin, replacement owner, duplicate consumption or claim reuse. |
| Harness denial | Native/platform case requested through every controller path, forged evidence-class override, copied native-success fixture and unknown case all refuse before effects. Place forbidden-call sentinels at the actual owner for account/service/key-store/native/network/product access; assert they were not invoked. |
| Evidence integrity | Changed/missing input digest, out-of-root/reparse/symlink path, mixed-case inventory, oversize artifact, secret-bearing unexpected field and partial write cannot publish a valid offline evidence packet. The result schema rejects native evidence, overall PASS and any qualification flag other than literal false without depending on controller refusal. No directory/profile/drive enumeration or environment-derived fallback. |
| Portable parity | Existing entitlement, policy, source/auth/custody/runtime tests and fixtures remain unchanged. Run focused new tests and applicable lint first; CI owns broad repetition. Explicit Windows invocation and UTF-8 reads, short stable test IDs and real fresh child processes from the first push. No native/platform result inferred from hosted CI. |

Each new guard requires a valid control, an invalid counterpart and a deliberate
fault proving the intended assertion fails. Declare expected fail-first failures
before execution. A child-process boundary must be real, not a process-inspection
proxy. Use barriers, not sleeps, for race ordering. Follow parent case/platform
deadlines; a timeout records failure/STOP honestly, never silent retry to green.

The parent's barrier, repetition and assertion rules
(`LEAD-OWNER-AUTHORITY.md:1036-1044`) apply in full to every applicable offline
case: each two-way race exercises both winners, three repetitions per order,
using separate processes and explicit barriers; assertions include no publication
while denied and no hidden licensing call during subsequent synthetic host
operations, as well as the transaction/recovery assertions above.

Future evidence goes outside worktrees under
`~/Desktop/codex-evidence/connect-automate/lead-owner-harness/<packet-id>/`,
directories 0700/files 0600 (equivalent Windows ACLs). Keep raw sanitized outputs,
fixture/model digests, fail-before/pass-after receipts and a SHA-256 manifest.
Public PRs use alias plus digest. Never claim production licensing, local admin
enrollment or native isolation from disposable reference-ledger results.

## Assumptions, blockers and authorization checkpoints

1. Current authorization ends at this document's publication and oversight
   request. H1 implementation requires exact-revision review and Juan's separate
   explicit go, naming offline fixture/test-key scope. No acceptance is recorded
   here for him and no native authority is implied by an implementation go.
2. Licensing-service implementation, signed endpoint/key-purpose publication and
   its owner's accepted work order remain separate blockers for genuine bootstrap.
   A test emulator neither settles them nor changes existing licence behavior.
3. Hello trusted first-use enrollment and passwordless Microsoft accounts remain
   UNKNOWN. Parent typed blockers and no-weaker-fallback rules apply. Do not build
   an enrollment mechanism from an untrusted client key or a UI Verified result.
4. Linux VM and Windows 11 dedicated-account/dev-drive safeguards remain as in
   the parent. Windows 10 remains required for first release. Oversight mail
   `df1538cb` relays deferred proof until Juan's licensed local installation;
   the eventual venue remains unsettled. No VM or native-boot preparation now;
   resolve the venue and any parent amendment before its frozen native work order.
5. [Issue #73](https://github.com/canfieldjuan/connect-automate/issues/73) remains
   open for malformed-request refusals, manifest renewal, device replacement and
   inaccessible-disk evidence. H1 must not invent an operation ID for a malformed
   request, a hidden refresh, replacement ownership or an isolation proxy. Record
   those cases as blocked pending the respective bounded contract decisions;
   this order neither resolves nor excludes those items. Their release status is
   Juan's to decide at their respective contract reviews.
6. Review the exact later H1 code and evidence independently before proposing
   native helpers, a frozen run or enforcement. Parent Linux fake-user-bus gate
   remains the FIRST native Linux case; defeat stops dependent native work.
   No host-authority enforcement, machine-grant or receiver work advances through
   a blocked native prerequisite.

## Explicit non-scope, regression risk and rollback

Do not edit the accepted parent text, entitlement v1, installed trust, production
host/authority/policy/source/custody/runtime APIs or tests, dependency lock, EOM,
Email Watcher, shared inference runtime or other repositories. No real message
selection, Gmail, source authority publication, body reads, machine grant,
provider registration, dispatch, Lead Inbox or lead creation. No live endpoints,
issuance, account/VM/service setup, native preflight, Hello enrollment, key
installation or current-user credential probe. No cleanup runs.

H1 should have no product runtime import side effect or installation entrypoint;
regression risk is test collection/import leakage and misleading evidence.
Prove isolation and evidence labels at the controller/fixture owner. Removal or
disablement of a later harness preserves production state and all retained
evidence. Clean up only explicitly owned temporary resources through the later
reviewed cleanup path; no resets, wildcard deletion or real-machine rollback.

## Implementation summary, cold diff audit and gap audit

Current change: this documentation file only. It pins the H1 owner, candidate
paths, portable verification scope, explicit native blockers and next acceptance
checkpoint. It creates no harness, schemas, fixtures, keys, accounts or services.

Documentation verification: inspect source citations and retained-probe hashes,
check relative links, whitespace and the final diff; verify no change to source,
tests, dependencies, configuration or accepted parent. No application tests or
native probes run for this docs-only revision. Record that evidence durably and
send the exact published commit to oversight; do not poll before the recorded
review deadline absent an operator update or exact-head notification.

**DONE only for drafting/publication when those documentation checks are recorded.**
**NOT DONE for H1 acceptance/implementation, native qualification, licensing
service acceptance, integrated enforcement, activation or release.** Oversight
review is not operator acceptance. Stop after sending this proposal; existing
implementation and native-proof holds remain in force.
