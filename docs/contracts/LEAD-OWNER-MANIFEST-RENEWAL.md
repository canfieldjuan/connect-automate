# Offline manifest renewal and pending recovery work order

Status: **PROPOSED; CONTRACT ONLY.** This slice prepares the next bounded
owner-bootstrap recovery work within V1b. Its two-document PR proposes the
installed-state comparison refinement at the canonical renewal owner and this
offline implementation work order. Both need independent review and Juan's
exact-revision acceptance. Acceptance/merge do not start implementation, generate
keys or run fixtures. A subsequent explicit go must name offline synthetic
fixtures and temporary test keys only.

Native sign-in, Hello, Gmail and live activation remain on hold. Machine grants,
receiver work and later vertical contracts do not advance past the native gate
in [the owner acceptance sequence](LEAD-OWNER-AUTHORITY.md#proof-matrix-and-executable-acceptance-gates).
This is a recovery prerequisite packet, not completion of V1b or native proof.

## Contract and root cause

The [canonical pending-renewal contract](LEAD-OWNER-AUTHORITY.md#expired-activation-manifests-during-pending-recovery)
owns interval policy, user initiation, immutable binding and publication rules.
PR82 accepted `5d22b4bb9b407c5f8cee4164b20c32395cf6ab80` and merged as
`d840068dbc1890e954cd68f5bc696d7d8bcb4cfd`. Its original comparison used only
the manifest retained with the pending operation. That retained-only comparison
originated in my accepted PR82 revision above (confirmed by git blame). After a successful renewal,
another candidate can pass that comparison while regressing installed state.
Issue73 records this deferred contract gap, missing interval examples and the
activation-configuration ownership row. They become concrete prerequisites for
this proposed renewal implementation; this PR proposes resolving them at that
one canonical owner, without another policy copy here.

Contract arithmetic at baseline: original interval January 1--2; installed
renewal January 2--4; candidate January 1 noon--3; observation January 2 noon,
all in UTC in the synthetic January 2026 fixture calendar. The candidate is
current and later than the original but regresses the installed interval.
This is a prose-relation reproduction, not an endpoint execution or proof of a
production defect. The new canonical comparison closes it; later independent
faults must isolate issue-time and expiry checks rather than fail on both.

The current harness also has no persisted installed/retained manifest owner.
`HostFixture` receives manifest bytes in memory, and `check_consume_request`
uses the current-window check. Expiry currently becomes generic protocol input
failure. Thus changing an object attribute or passing a fresh constructor value
cannot prove durable, selected, serialized configuration renewal.

### Source and validated-work inventory

All source references in this table are at merged baseline
`90c0aba6365cd4c6a79efa3afd3d389c3ded6779`. Inspected source and historical
results are distinguished; no executable test, import, key or fixture runs for
this documentation PR.

| Class | Existing owner and limit |
| --- | --- |
| CONFIRMED | `protocol.py:336-353` owns closed `ActivationManifest`, real origin/time parsing, unique key IDs and the maximum interval. `:458-493,496-533` verifies signed manifests, requests and receipts; current-window failure is generic `ProtocolInputError`. |
| CONFIRMED | `host_fixture.py:26-63,126-177,193-266` owns configuration IDs, durable pending binding and the original receipt/admin/audit transaction. It has no durable manifest columns/table. `:268-279` exposes complete pending-binding and receipt digests. |
| CONFIRMED | `licensing_fixture.py:192-256` owns metadata exchange and immutable consumption/replay. Its shared transaction/read-store helpers are the existing serialization boundary. Neither fixture is a licensing service. |
| CONFIRMED | `controller.py:23-33,132-162,203-294` supplies the accepted-profile reference, frozen clocks, separate real issuer/host processes and malformed recovery proof. `cases.json` keeps `manifest-renewal` BLOCKED. |
| CONFIRMED | `tests/test_owner_harness_recovery.py:42-100,973-991,1254-1276,1453-1476` supplies SyntheticWire, ephemeral signing material, expired-claim receipt recovery, real recovery barriers and writer-time revalidation. Reuse these owners. |
| CONFIRMED | Closed run/result models and derived schemas enforce accepted profile `ba7f7cf7db9b14c050d87021fddd7333ff149851`. CLI structured mismatch classification and mixed-invalid handling already exist. |
| CONFIRMED | Python >=3.13; locked Pydantic 2.13.5, cryptography 49.0.0, pytest 8.4.2, Ruff 0.16.8, httpx 0.28.1. Lock SHA256 `ef00a5b983e507a66f1dcca1687bf1f6523f031a44e640e5d9ae380832ecc5e3`. No dependency change. Windows CI already lists all four owner-harness files at `.github/workflows/ci.yml:79-82`. |
| RECORDED, NOT RERUN | PR87 reviewed head `e1bf8368d0370696353f88cc8f70de04f9897618`, merged as this baseline with tree equality. Alias `offline-malformed-recovery/round1/adjacent.txt`, SHA256 `a704424b52643e2972d04f64828604845d4d322aaabc823367f89c4b250036d1`, records 402 adjacent tests. Oversight review 5810105120 independently reports 560 four-file controls, 23/23 mutations and 3/3 second-side probes. These are malformed/recovery regression evidence, not renewal proof. |
| UNKNOWN | Production renewal publication, licensing-owner acceptance, protected native configuration, host enrollment, native proof and installed-product qualification remain unavailable evidence. |

Retain baseline source/schema/catalog/test/lock hashes with the later parity
packet. There is no AI model, prompt or inference-runtime migration in this
lane. Existing native evidence is not an input to execute.

### Intentional departures from the baseline

1. Amend the canonical interval comparison and selected-state writer checks;
   add the ownership row and independent regression/max-interval examples there.
   This requires operator acceptance of the proposed behavior, not silent adoption
   of a previously deferred suggestion.
2. Persist signed installed configuration and immutable original retained
   configuration in the disposable host fixture, through its existing owner.
   Constructor arguments or a mutable attribute cannot replace persisted state.
3. Add explicit fixture-only renewal and selected-state read APIs, reusing the
   original host writer, observations, signature verification and receipt replay.
   Classify unavailable active manifest at its verifier/configuration owner;
   do not reuse malformed-wire classification or catch every input error as expiry.
4. Add the real-process renewal recipe and its fixed assertion inventory; only
   `manifest-renewal` becomes runnable after all proof passes.
5. Advance the new run/result profile to this work order's final accepted commit,
   at the existing closed-model/schema owner. Preserve the remaining packet
   shape, typed mismatch vocabulary and historical evidence bytes.
6. Update only affected tests and offline instructions. The existing Windows
   test list already covers them. Split a large implementation into reviewed
   protocol/fixture work before controller adoption; do not activate a partial case.

## Ownership and later implementation surface

Only `docs/contracts/LEAD-OWNER-AUTHORITY.md` and this document change now.
Later candidate files are `qualification/owner_authority/protocol.py`,
`host_fixture.py`, the shared fixture-store helpers in `licensing_fixture.py`,
`controller.py`, `cases.json`, derived run/result schemas, README and the four
existing owner-harness test files. A workflow change needs a justified new test
file; no production source or other repository is included.

### Single policy and configuration owner

Keep the [canonical renewal relations](LEAD-OWNER-AUTHORITY.md#expired-activation-manifests-during-pending-recovery)
at one named protocol validator. Reuse closed manifest/envelope models, wire
budgets, canonical JSON, real signature/time parsing and installed fixture trust.
Schema-expressible constraints remain in those models; cross-manifest/time
relations belong in the one validator. No controller equality check, parallel
regex, second parser or duplicated interval rule.

Historical signature/policy verification of the original retained and installed
manifests does not make expired bytes current authority. Candidate key-ID policy
is compared as sets; otherwise-valid array reordering is not a policy change.
Preserve all signed bytes exactly. No trust installation, endpoint migration,
claim/receipt key-policy change or arbitrary caller-selected verifier.

Use a closed, bounded selection value derived by the host read owner. It binds
the operation, actual complete pending-binding digest, original retained signed
manifest digest and currently installed signed manifest digest. No approval flag
or expected values supplied by the controller stand in for store evidence.

Persist the original manifest when preparing the pending operation. Keep it
immutable across renewals. Store the active signed manifest through one host
configuration interface; all renewal/replay readers use that interface. A restart
must reload its actual current bytes and must not replace them from constructor
input. Fresh disposable roots only: version changed fixture storage at its
existing identity owner and refuse old/wrong profiles. Do not migrate, relabel or
modify historical fixture databases or production storage.

### Explicit renewal, serialization and failure truth

A fixture caller explicitly selects the operation/configuration and separately
submits a candidate. Verify before effects and revalidate all canonical rules,
selection digests, time and fresh synthetic observation after writer waits and
before commit. Compare actual stored configuration in that writer snapshot.
If another renewal or pending-state change wins, refuse the stale selection;
no silent rebase, automatic retry, fallback or replacement operation.

Publish only the installed manifest in that transaction. Do not rewrite the
claim, binding, retained original manifest, salt/principal, receipt, admin or
bootstrap audit. Inspect each store through its own owner; no cross-store SQL
or cross-store transaction. Reuse existing writer/fault/barrier machinery.

An absent/expired active manifest produces the parent's unavailable outcome
before consume dispatch. Preserve the complete pending state and derived UNKNOWN
when prior dispatch is ambiguous. Verification/trust/corruption, authenticated
clock refusal and malformed-request wire remain separate paths. A generic worker
failure or an unchanged operation ID is not proof of this outcome.

Renewal never resumes consumption itself. A later explicit resume obtains a
fresh synthetic observation and signs a fresh attempt for the same binding.
Issuer replay and local publication remain at the existing owners. An expired
claim may recover a stored receipt, but cannot publish local authority. Candidate
expiry during waits and SQL/crash failures preserve the last complete config.

The issuer fixture may explicitly adopt the same signed replacement through its
fixture configuration boundary, retaining its original ledger and in-memory
signers. This models release-owner publication only; no renewal endpoint, HTTP
client, activation call, issuer claim write or service deployment is introduced.
No hidden exchange is permitted while obtaining or installing the candidate.

## Later offline recipe and independent controls

Use the existing real spawned issuer/host pattern, synthetic identities and
January clocks. A case-local short manifest interval is an intentional fixture
change so it expires while the original claim remains valid. Old cases keep
their original times, claim/manifest settings and behavior. Never change the
machine clock or depend on today's date.

1. Prepare the original binding and persist its manifest. Issuer commits once;
   deliberately lose its first reply. Host retains pending with no local triplet.
2. Advance only the synthetic clock past manifest expiry. An ordinary explicit
   resume without renewal reports unavailable and dispatches nothing. Preserve
   actual pending, original-manifest and receipt evidence.
3. Explicitly select and install a same-policy replacement. Prove the installed
   digest changed and all pending/original/claim/receipt/authority evidence did
   not. Renewal alone performs no consume exchange or authority publication.
4. Separately resume with a fresh attempt/observation. Recover the original signed
   issuer receipt; publish one local receipt/admin/audit triplet. Cached invocation
   dispatches nothing. Record two consume exchanges and one issuer consumption.

Additional controls exercise successive valid renewals and an otherwise-valid
regressing candidate against actual installed state. Isolate issue-time and
expiry regressions separately. Include absent explicit renewal, invalid native
fixture observation, expired claim, another lost reply and missing/corrupt
retained or installed configuration. Record real failure outcomes, not just the
final successful state.

The fixed controller assertions must cover unavailable-without-dispatch,
renewal-only-config-effects, unchanged complete pending/original/claim evidence,
no implicit resume/retry, installed-state monotonicity, same receipt, one triplet,
cached no-dispatch and issuer effects. Measurements are actual owner snapshots
and call counts, with private material excluded. Each assertion also needs an
injected real fault that turns it false and makes the recorded case FAIL; a
positive all-true run alone does not establish its sensitivity.

## Verification plan after separate offline execution go

| Gate | Falsifiable evidence |
| --- | --- |
| Baseline/parity first | Run the existing affected owner files at the pinned source before edits. Carry valid receipt/refusal, malformed exchange, expired-claim recovery, lost reply and cached controls through the persisted configuration owner before new renewal behavior. Preserve archived packet bytes. |
| Fail first | Declare the missing renewal/persistence/classification failure before its minimal probe. Existing unavailable/pending checks may already pass; do not manufacture a failure. Any mismatch is isolated at its first changed owner. |
| Models and verification | Valid control and missing/extra/falsy/partial/mixed/over-cap inputs; wrong signature/release/purpose/origin/claim or receipt key policy; reordered equal key-ID sets admitted. Direct models and derived schemas remain closed and in sync. |
| Interval second sides | Before/equal/after current-window and comparison boundaries; maximum interval and just over it; issue-time regression with advancing expiry; expiry regression with valid issue time; later-than-original but older-than-installed candidate; repeated forward renewals. |
| Writer/state proof | Stale pending, original or installed selection rejects. Two renewals and renewal-versus-resume races use real processes, both winners and the existing repetition policy. Revalidation after waits/at commit, restart, SQL faults and crash boundaries preserve one complete config and no partial authority publication. No sleeps or process-state proxies. |
| Actual effects | Configuration-only renewal, no issuer consume/revoke/reissue/journal write, same signed receipt, exact exchange/consumption counts, pending and original digests, derived UNKNOWN and cached no-dispatch. Inject extra exchange and extra consumption separately; assert the exact false flags and recorded FAIL. |
| Denial/native holds | All other blocked/native selections refuse before fixture effects. Exercise network/installed-trust/native/account/product-call sentinels in real workers. OFFLINE_CONFORMANCE and literal false qualification flag; no aggregate/native qualification claim. |
| Guard-removal proof | Each new rule has a matching positive, independent negative and fresh-process removal/weakening receipt. Prove both halves of compound comparisons; do not count a shared downstream failure, import error or timeout as independent detection. |
| Incremental verification | Focused new and adjacent owner tests, applicable Ruff/whitespace and schema drift. CI owns duplicated broad suites. Existing Windows invocation applies from first push; one grouped repair push per review concept. |

Keep the existing case/platform deadlines and path/output/child-exit/assertion
truth gates unchanged. Proposed evidence alias root is
`offline-manifest-renewal/`, retained outside worktrees under
`~/Desktop/codex-evidence/connect-automate/`, directories 700/files 600.
Store sanitized raw outputs, source/lock/catalog hashes, before/after and selected
fault receipts plus a SHA256 manifest. Keep no temporary private key, credentials,
real messages or principal/salt bytes in durable evidence. Public PRs cite aliases
and digests, not private paths or names.

## Explicit non-scope and acceptance sequence

No entitlement-v1, source/auth/custody/runtime behavior, real stores, product APIs,
UI, dependency/pin, other repository, native helper, VM/account/service/boot/disk,
Gmail/OAuth or shared-model work. No production signing, issuer/service renewal,
provider registration, machine-grant/receiver work, lead creation or activation.
PC replacement and disk-isolation execution remain blocked. Issue73's other
follow-ups and issue84's product decision are not resolved by this slice.

For this documentation PR, verify only its exact two-document scope, preserved
text outside the renewal/ownership surface, canonical policy links, pinned
source/lock/prior-evidence hashes, interval arithmetic, whitespace and committed
bytes. Run no application tests, imports, fixtures, key generation or probes.

Publish the exact contract revision for independent oversight and Juan's final
acceptance. Merge requires exact-head green CI, clean connector/reconciled
review, zero unresolved threads/no CHANGES_REQUESTED and the accepted head,
with merge-tree equality. Then stop for a separate offline fixture/test-key go.
Acceptance of this packet grants no native or live authority.

## Implementation summary, cold diff audit and gap audit

Current change: one canonical contract refinement and this work order. No
executable path or catalog entry changes. Cold audit must confirm every change
traces to the renewal owner/current-state gap and that future implementation
scope is explicit.

DONE for documentation preparation only after its checks/publication are
recorded. NOT DONE for independent review, exact-revision acceptance, merge,
offline implementation/proof, native qualification or activation. Rollback of
this proposal is a documentation revert; no reset, state deletion or evidence
cleanup is authorized.
