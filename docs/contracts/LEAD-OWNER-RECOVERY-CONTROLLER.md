# Offline recovery-evidence controller proof work order

Status: **PROPOSED; CONTRACT ONLY.** Juan authorized this work order's drafting
and independent oversight submission. It needs Juan's exact-revision acceptance
before merge. Acceptance or merge does not authorize implementation, fixture
execution or key generation; those require a separate explicit go for offline
synthetic fixtures and temporary test keys only.

The [canonical recovery policy](LEAD-OWNER-AUTHORITY.md#failed-or-replaced-pc-recovery)
and the accepted [evidence-admission work order](LEAD-OWNER-DEVICE-RECOVERY.md)
remain the policy and admission owners. This work order specifies an auditable
controller proof of that prerequisite, not replacement authorization. Native
sign-in, Hello, Gmail and live activation remain on hold. `device-replacement`
and `inaccessible-disk-evidence` stay `BLOCKED`; native cases stay `NOT_RUN`.
No PC access or offline PASS supplies business verification or actual retirement.

## Root cause and required change surface

PR93 and PR94 provide closed recovery values and durable issuer case/admission
APIs. The controller's closed runnable-case vocabulary has no recovery-evidence
case, and its recipes exercise host-bootstrap outcomes. There is no controller
packet proving the new admission lifecycle. Reusing `COMMITTED`, promoting
`device-replacement`, or writing expected assertion flags without exercising
those owners would claim more than the implementation proves. This is a missing
proof capability, not a reproduced defect in the reviewed admission code.

This PR changes only this work order and its canonical pointer. A later,
separately authorized implementation may change controller.py, protocol.py's
runnable-case/packet-profile and bounded IPC models, cases.json, derived
run/result schemas, README, host_fixture.py's read-only snapshot, and the
existing owner-harness tests. Unqualified source paths below are under
qualification/owner_authority/; test paths are repository-relative. Domain models,
recovery signature purposes, issuer admission rules/tables, host authority writes,
dependencies and workflows remain unchanged. No separate fixture SQL reader,
alternate validator, signing trust, public CLI command or production endpoint
is needed.

## Validated-work inventory and deliberate differences

Pinned baseline: `d333caf866263c1b4df263a050f3330a5e9b22e8` (PR94 merge), tree
`8d566e039c10c0304f8cfd2a3f8099487d809c11`. Source references below are at that
revision. Results are recorded prior evidence, not rerun for this prose PR.

| Owner | Reuse and limit |
| --- | --- |
| `protocol.py:78-137,165-204` | Strict closed models, bounded canonical parsing, offline run/result packets, literal false qualification flag and derived schemas. No new qualification claim. |
| `protocol.py:592-605,615-808` | Shared stored receipt verification and recovery-only models, budgets, signature, digest, selection and UTC window owners. Controller must call these owners rather than duplicate policy. |
| `licensing_fixture.py:97-124,323-534` | Existing writer/read boundaries; issuer-owned case, selection, admission and full-row recovery snapshot. Explicit same-input retry and corruption STOP already implemented. |
| `controller.py:118-187,376-473` | Temporary worker-local keys, separate spawned issuer/host processes, bounded communication, deterministic synthetic clocks and cleanup. Current recipes have no recovery-evidence branch. |
| `controller.py:489-563`, `protocol.py:840-882`, `cases.json` | Exact assertion-set comparison, PASS/FAIL/STOP separation, sanitized receipts, source/catalog hashes, result published last. Runnable case IDs are closed; device replacement is blocked. |
| `host_fixture.py`, `tests/test_owner_harness_recovery.py:2249-2789` | Real synthetic initialization/consumption and recovery/replay/refusal/race/fault fixtures. Host snapshot at `host_fixture.py:344-363` covers counts and selected hashes, not all configuration/admin/audit columns; extend this read owner for complete proof, preserving authority behavior and test inputs. The F1 test at `:2408-2434` proves missing/re-keyed predecessor under an existing case is corruption. |
| `tests/test_owner_harness_controller.py:857-879` | Real worker fault injection and exact false-assertion comparison. Reuse this proof pattern; a stopped worker does not prove assertion sensitivity. |
| `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml` | Python >=3.13; locked Pydantic/cryptography and existing Linux/Windows owner-harness CI. No dependency, framework or workflow addition. |

Lock SHA256: `ef00a5b983e507a66f1dcca1687bf1f6523f031a44e640e5d9ae380832ecc5e3`.
Prior durable evidence aliases and manifest SHA256:

- `offline-device-recovery/admission/manifest.json`:
  `5908d782d5d74962babd294a24cf2276ac7ff936193d982dc9d0e980eb5bcc38`.
  At the original implementation head: 956 adjacent tests and 22 assertion-based
  weakening probes. This packet proves fixture admission, not a controller case.
- `offline-device-recovery/admission/f1/manifest.json`:
  `173c27d0613f9d53152bbc7279bea6a93e4f961dbcdac7dd35d27f6445745978`.
  Four new cases pass against the owner and fail against pass-through corruption;
  adjacent recovery exits 0. Exact final head was independently passed in review
  5820068271; CI run 42532557938 passed both jobs before merge.
- `offline-manifest-renewal/controller/manifest.json`:
  `6eacd8def742e2a2e551b844ba2c99bead1a2e92f8834309d43108fd76b95d82`.
  Reuse packet/fault methodology only, not renewal outcomes as recovery proof.

There is no model, inference runtime, prompt, chat template or real document in
this lane. Before later implementation, inventory source/schema/catalog/lock
hashes and prove prior admission and existing controller cases on unchanged
inputs. Preserve historical packets and their original profile pins.

Intentional differences: one new prerequisite case and recipe, typed bounded
fixture-only control messages, its assertions and tests, a read-only full-row
host snapshot extension, and advancement of the
single accepted contract pin with derived run/result schemas and documented
fresh-root profile. The pin becomes the final accepted revision of this work
order; fixture identity already binds that pin and refuses old roots. Keep
`offline-fixture/4` and its schema unchanged: the storage layout does not change.
Do not relabel old evidence, migrate stores or relax mismatched-profile refusal.
No other behavioral departure from the validated owners is authorized here.

## Case identity, worker ownership and truthful outcomes

Add the separately named `recovery-evidence-admission` runnable catalog case:
kind `OFFLINE_CONFORMANCE`, requirement `issue-73`, capability
`disposable-fixtures`, expected code `EVIDENCE_RECORDED_ONLY`. Extend the existing
closed RunnableCase vocabulary, not the deferred device-replacement entry.
Keep the exact fixed assertion IDs below in the shipped catalog. Existing case
IDs, recipes, expected codes and assertion sets retain their behavior.

Use the existing bounded real spawned-worker lifecycle. The issuer alone opens
its database and invokes its admission APIs; host fixture roots remain owned by
the host worker. The original installation key signs the synthetic retirement
assertion in that host worker. New target keys are temporary and distinct.
No cross-owner database read, arbitrary SQL/path command, supplied verifier,
private-key serialization or mock `retired=true` decision is permitted.

The host snapshot owner must additionally return a digest covering complete rows
of configuration, pending, receipts, admins and audit, using the existing
snapshot_digest helper. It also returns a complete configuration-row digest and
owner-read public installation/host/organization IDs and public key for binding
the replacement target. Do not export private pending principal/salt contents.
Validate transmitted snapshot data in a closed protocol model. Only sanitized
digests/counts reach persistent case receipts; public binding fields stay in
bounded worker IPC. Extend this one read owner instead of re-reading SQLite in
the controller. Existing authority writers and table layouts are unchanged.

New IPC payloads use closed typed models at the existing protocol owner, with
fixed command tags and explicit fields/budgets. Reuse canonical recovery bytes,
existing UUID/digest/time/key types and real parsing; schema-expressible limits
belong in models, not parallel regex checks. Cap each new complete IPC message at 8192 canonical bytes on send and receive,
while enforcing the existing smaller per-value recovery budgets inside it. Use
bounded counters (0 through 2147483647), fixed fields and no arbitrary lists or
diagnostics. Unknown/missing/extra/mixed commands fail closed. Extend only the recovery-case
branch; existing bootstrap IPC and recipe behavior must retain parity.

The common controller packet already permits a bounded code and PASS/FAIL/STOP.
Use that packet with the recovery admission code directly; do not wrap the
admission in FixtureHostResult, set `committed=true`, or invent a host receipt.
All packets retain `OFFLINE_CONFORMANCE` and `qualification_pass=false`.
An offline PASS means assertions passed, never actual retirement or authority.

## Proposed deterministic recipe

Use fixed January 2026 UTC fixture times, never wall-clock changes. Keep the
original claim/manifest active through the normal sequence. One concrete plan:
case window 00:00--03:00, evidence asserted at 01:00 and expiring at 01:30; normal
calls at 01:00, final expiry probe at 01:30. These satisfy the accepted bounds.

1. In disposable roots, create an actual original installation and valid signed
   consumption through existing owners. Complete its synthetic bootstrap, then
   capture the original issuer and host snapshots. Create a separate replacement
   host fixture and capture its initial configuration/zero-authority snapshot.
   This setup is explicit and excluded from recovery-phase dispatch counters.
2. Construct ReplacementTarget from the replacement owner's returned public
   deployment IDs/key, a fresh operation UUID and the original entitlement.
   Use its complete configuration-row digest as initialization_sha256. Use a
   fixed synthetic principal commitment (which may equal the predecessor's);
   this asserts no person identity. Organization/entitlement must match the
   predecessor. This initialization digest is a controller-fixture convention,
   not a new native initialization or authority policy.
   Open the case through IssuerFixture using both original consumption references;
   parse the returned case, select through the issuer, and sign exact synthetic
   evidence with the original installation key. Do not fabricate source receipts.
3. Admit once. Deliberately suppress the committed response at the fixture
   transport boundary, after the owner completes. Preserve an unresolved caller
   outcome and the actual stored recovery snapshot. Do not retry implicitly.
4. Explicitly reopen the issuer fixture on the same root and request the exact
   same case/evidence. Return the stored case/admission bytes with the same
   digests and exactly one case/admission. Reopening keeps the worker's temporary
   signer objects in memory; this is a store-reopen proof, not process restart,
   durable signing-key custody, installed restart or restore qualification.
5. Submit otherwise-valid, differently identified signed evidence for that case.
   Require `RECOVERY_BINDING_CONFLICT` and unchanged full recovery snapshot.
   Then advance only synthetic time to evidence expiry and retry the original
   bytes. Require `RECOVERY_EVIDENCE_EXPIRED`, retaining the complete history.
6. Collect owner snapshots and recovery-phase call counters. Original issuer
   claims/consumptions/journal and original host state are unchanged. Replacement
   configuration stays unchanged, with no pending/bootstrap receipt/admin/audit
   publication. Return the actual validated admission's evidence-only code plus
   measured assertions. No successful admission means no fabricated expected code;
   record the actual refusal/failure or STOP, and never continue dependent steps.

The lost reply must hide the response from the caller. The issuer may retain a
sanitized digest for proof; the recipe must not use that digest as a substitute
response or privately complete/retry the caller's unresolved operation.

## Fixed assertions and independent controls

| Assertion ID | Observation that must be true |
| --- | --- |
| `source-bound-case` | Returned case matches the actual original consumed binding/receipt digest and the actual replacement target. |
| `same-case-on-reopen` | Explicit same-input open after store reopen returns byte-identical case and no new reservation. |
| `admission-evidence-only` | Parsed actual admission has the exact case/evidence/target digests and state EVIDENCE_RECORDED_ONLY. |
| `lost-reply-retained` | Suppressed response leaves caller unresolved while one complete stored admission exists. |
| `explicit-replay-only` | Measured owner calls show no automatic retry between loss and the explicit replay. |
| `same-admission-on-reopen` | Recovered admission digest equals the issuer's first committed admission digest. |
| `one-recovery-pair` | One case and one admission, with unchanged full recovery snapshot across exact retries. |
| `changed-evidence-conflict` | Otherwise-valid changed evidence gets BINDING_CONFLICT and leaves recovery state unchanged. |
| `expired-replay-preserves-history` | Exact expiry gets EVIDENCE_EXPIRED and retains the complete admission snapshot. |
| `issuer-original-preserved` | Complete original issuer snapshot remains equal throughout recovery. |
| `predecessor-host-preserved` | Complete original host snapshot remains equal throughout recovery. |
| `replacement-host-unpublished` | Complete replacement snapshot remains equal to its fresh zero-authority baseline. |
| `recovery-no-bootstrap-dispatch` | Recovery phase calls no ordinary consume/exchange/bootstrap/renew/reissue/revoke or authority publication. |

Compute flags from actual owner responses, complete snapshots and call counts.
The controller must not patch response codes, stored records or assertion maps
to manufacture observations. Retain exact measured call counts and sanitized
digests in a bounded closed diagnostic model if additional per-case evidence is
needed; never export keys, raw identity commitments, salts or database contents.
Any diagnostic model belongs at the same protocol owner with schema validation.

Each assertion needs a fresh-process, otherwise-valid real fault in its controlling
input/owner that makes the exact expected assertion set false and the packet
FAIL. Do not count hardcoded false flags, import/setup failures, crashes or STOP
as detecting an assertion. Separate compound relations so one failed comparison
cannot conceal an untested sibling. Keep positive controls and raw failure proof.

Separate error-path runs inject a missing or re-keyed predecessor under an
existing case (both select and admit), corrupt stored evidence, malformed IPC,
worker termination and timeout. Actual FixtureCorrupt or an unexpected exception
must produce sanitized STOP, never ordinary unavailable/refusal, PASS or an
assumed uncommitted outcome. Deliberate corruption stays in disposable test
controls, never a normal recipe command. Retain STOP packets, but do not count
them as false-assertion sensitivity. Preserve the existing broader issuer race,
SQL/crash, signature and boundary suites; no duplicate recovery implementation.

## Verification, artifacts and boundaries

Later implementation proof: declared missing-case/schema fail-first; baseline
parity; new positive recipe; exact refusal and corruption controls; each fixed
assertion fault; mixed selections and unavailable case refusal; result/schema
round-trip and artifact hash checks; original case parity; applicable lint and
CI. Probe both sides of guards and exact window boundaries. Keep the current
180-second per-case and 3600-second serial platform budgets, sanitized STOP,
no-live sentinels, output path defenses and publish-result-last behavior. Do not increase budgets to make a slow case pass.

Retain source/profile/catalog/lock pins, tested revision, Python/platform details,
positive and failing receipts, STOPs and unmeasured behavior under durable alias
`offline-recovery-controller/` outside worktrees (directories 0700/files 0600).
Use appropriate private Windows ACLs when exercised there. No private temporary
key, credential, real identity or raw principal/salt bytes survive worker cleanup.
A recorded Windows CI pass is not native sign-in or installed-product proof.

Business-verification policy, real predecessor disablement, session/grant
invalidation, rollback resistance, unreachable-PC policy and executable recovery
authorization remain separate blockers under the canonical contract. No licensing
service, native/VM/account/boot/disk work, real key provisioning, Gmail/OAuth,
receiver, UI, product store, production source or other-repository change.
No deferred PR91/PR93 hardening is folded in. Device replacement remains BLOCKED.

## Contract verification and acceptance gates

For this documentation PR: inspect source and prior evidence without importing
application code or running tests/fixtures/key generation; check references,
hashes, exact two-document scope, profile implications, schema-first mechanisms,
recipe/assertion correspondence and cold diff. No runtime proof is claimed here.

Publish the contract revision for independent oversight and Juan's exact-revision
acceptance. Merge only that accepted head after green CI, clean connector review,
zero unresolved threads/no CHANGES_REQUESTED, independent PASS and reviewed-tree
equality. Then stop for separate implementation authority. Do not interpret this
work order or its future evidence packet as retirement, replacement or activation.

Implementation summary: this PR adds the work order and canonical pointer only.
Gap audit: **NOT DONE** for exact acceptance, review, merge, implementation or
qualification until their separate gates are satisfied. The current contract
proposal does not change the accepted recovery admission behavior.
