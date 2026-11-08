# Offline device-replacement recovery: evidence-admission work order

Status: **PROPOSED; CONTRACT ONLY.** This is the first bounded prerequisite
for offline device-replacement recovery, not a complete replacement protocol.
Juan authorized preparation of this contract-only work order. Independent
oversight and Juan's exact-revision acceptance are still required. Acceptance
and merge do not authorize implementation or fixture execution; those need a
separate go naming offline synthetic fixtures and temporary test keys only.

The [canonical failed-PC recovery contract](LEAD-OWNER-AUTHORITY.md#failed-or-replaced-pc-recovery)
owns product policy. This work order owns only the proposed offline evidence
format, admission rules and proof below. It supplies no recovery authorization,
replacement admin, native retirement, business-verification policy or licensing
service. The existing `device-replacement` catalog case stays `BLOCKED`, including
after this prerequisite is implemented. Native sign-in, Hello, Gmail and live
activation remain on hold. Having access to a PC supplies none of those gates.

## Root cause and required change surface

The consumed-binding invariant already refuses a new installation using an old
claim. The missing component is a separate evidence-admission owner: the harness
has no closed recovery case or predecessor-signed record bound to an exact case,
replacement and validity window. Treating an ordinary receipt, arbitrary signed
blob or a controller `retired=true` flag as that evidence would bypass the
canonical recovery prerequisites. This is a missing capability, not a reproduced
defect in the current consume endpoint. No compensating consume check is proposed.

This PR changes only this work order and a link at the canonical recovery owner.
Later implementation may change `qualification/owner_authority/protocol.py`,
`licensing_fixture.py`, the existing protocol/wire/recovery tests and README.
The existing closed model owner derives a new, separately named recovery-evidence
schema. The fixture identity/profile and existing derived run/result schemas
must advance together to the final accepted work-order commit; historical bytes
must not be relabeled. Controller recipes, catalog cases and host bootstrap APIs
remain unchanged. Split protocol and durable admission into separately reviewed
increments if necessary; no partially implemented recovery entry point is public.

### Validated-work inventory before design

Inspected baseline: `81d56684ce045f042145523eae39f341d7474417`, the merge of PR91.
References below are repository-relative at that revision. Recorded tests are
historical evidence, not tests rerun for this documentation change.

| Owner / evidence | Reuse and limit |
| --- | --- |
| `qualification/owner_authority/protocol.py:78-83,140-191,300-313` | Strict closed immutable models, canonical JSON with duplicate-member/non-finite rejection, derived schemas and real UTC parsing. Reuse these owners, not parallel parsing or regex admission. |
| `protocol.py:378-391,440-447,472-507` in that directory | Exact consumed binding, signed consumed receipt, explicit expected-type dispatch and shared signature verifier. Existing bootstrap purposes cannot authorize recovery. |
| `qualification/owner_authority/licensing_fixture.py:56-124,224-276` | Version/profile-bound disposable stores; one SQLite writer, validation after waits and before commit; immutable consumption and same-binding replay. Add recovery tables at this issuer owner, not a second ledger or cross-store SQL reader. |
| `qualification/owner_authority/host_fixture.py:25-46,299-342` | Local receipt/admin/audit transaction and selected-state renewal provide patterns, not a retirement mechanism. Do not add replacement publication or retirement to this host in this slice. |
| `tests/test_owner_harness_recovery.py:42-100,103-161,269-291,347-405,1257-1295` | SyntheticWire ephemeral signers, fixed January clocks, receipt/replay/conflict, restored-store denial, real-process races and fault hooks. Reuse the established test machinery and repetition policy. |
| `qualification/owner_authority/controller.py:436-563`, `cases.json` | Existing bounded real-process proof and truthful offline packets. No device-replacement recipe exists; the catalog entry is blocked. Do not manufacture a full-case PASS from evidence-only tests. |
| `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml:79-82` | Python >=3.13; locked cryptography 49.0.0, Pydantic 2.13.5, pytest 8.4.2, Ruff 0.16.8 and httpx 0.28.1. Existing Windows CI covers all four owner test files. No dependency or workflow change. |
| Alias `offline-manifest-renewal/controller/manifest.json`, SHA256 `6eacd8def742e2a2e551b844ba2c99bead1a2e92f8834309d43108fd76b95d82` | Sealed PR91 evidence, including final adjacent checks and fault controls; historical renewal proof only, not device recovery or retirement qualification. |

Dependency lock SHA256:
`ef00a5b983e507a66f1dcca1687bf1f6523f031a44e640e5d9ae380832ecc5e3`.
There is no model, inference runtime, prompt, chat template or private document
input in this port. Capture baseline source/schema/catalog/lock hashes before
later edits and preserve the prior receipt/conflict/replay results on identical
synthetic inputs before adding recovery behavior.

Intentional differences from that inventory: new recovery-only closed models,
domain-separated evidence signature, issuer-owned case/admission tables and
explicit offline calls; a versioned fresh fixture profile and derived schemas;
new tests and instructions. No existing bootstrap signature, claim, binding,
receipt, endpoint or host authority semantics change. No other difference is
authorized by this work order.

## Offline evidence contract

All new objects use the existing strict `Closed` base. Every field is required;
no extras, nulls, coercion, defaulted approval fields or caller-supplied verifier.
Reuse `UuidV4`, `Digest`, `PublicKey`, `Signature`, `Instant` and canonical JSON.
Schema-expressible restrictions belong in the decoded model and its derived
JSON Schema. Real date/key parsers own semantics. One named recovery validator
owns the cross-record relations below; callers and tests must not implement
parallel policy. The prefix/type registry selects the expected recovery type
before decoding, rather than trusting an input purpose to select its budget.

### Closed values and signature

Every new value has `version` const `offline-recovery-evidence/1`,
`evidence_class` const `OFFLINE_CONFORMANCE`, and `qualification_pass` strictly
boolean false (reuse `FalseOnly`, not a Literal that admits numeric zero).

| Value | Remaining required fields |
| --- | --- |
| `ReplacementTarget` | `operation_id`, `installation_id`, `host_id`, `organization_id`, `entitlement_id`: UUIDv4; `installation_public_key`: PublicKey; `principal_commitment`, `initialization_sha256`: Digest. This is not a ConsumeBinding, claim or authorization. |
| `RecoveryEvidenceCase` | `case_id`: UUIDv4; `predecessor_binding`: exact existing ConsumeBinding; `predecessor_receipt_sha256`: Digest; `replacement`: ReplacementTarget; `opened_at`, `expires_at`: Instant. |
| `RetirementEvidence` | `purpose` const `offline-predecessor-retirement-evidence`; `evidence_id`, `case_id`: UUIDv4; `case_sha256`, `predecessor_receipt_sha256`, `replacement_sha256`: Digest; `asserted_at`, `expires_at`: Instant; `assertion` const `SYNTHETIC_RETIREMENT_ONLY`. |
| `RetirementEvidenceEnvelope` | `payload_base64url`: canonical unpadded base64url; `signature_base64url`: Signature. No key ID, public key or trust material supplied in the envelope. |
| `RecoveryEvidenceSelection` | `case_id`: UUIDv4; `case_sha256`, `predecessor_receipt_sha256`: Digest. Derived from the issuer's read snapshot, rechecked in its writer; not a controller approval. |
| `RecoveryEvidenceAdmission` | `admission_id`, `case_id`, `evidence_id`: UUIDv4; `case_sha256`, `evidence_sha256`, `predecessor_receipt_sha256`, `replacement_sha256`: Digest; `admitted_at`: Instant; `state` const `EVIDENCE_RECORDED_ONLY`. This local receipt is not signed recovery authority. |
| `RecoveryEvidenceRefusal` | `case_id`: UUIDv4; `code` enum `RECOVERY_PREDECESSOR_UNAVAILABLE`, `RECOVERY_BINDING_CONFLICT`, `RECOVERY_EVIDENCE_INVALID`, `RECOVERY_EVIDENCE_EXPIRED`, `RECOVERY_CONFIGURATION_UNAVAILABLE`. No completion/authority claim or arbitrary diagnostic text. |

Digest definitions are SHA256 over canonical complete case/target bytes and over
exact signed evidence-envelope / consumed-receipt bytes respectively. No digest
may be computed from a subset of the named value. The existing consumed binding
keeps its existing version; nested new values include their new common fields.

Proposed offline bounds: a case's `opened_at < expires_at`, interval at most
86400 seconds; an evidence window has `asserted_at < expires_at`, at most 3600
seconds and lies wholly inside the case window. New admission requires
`opened_at <= asserted_at <= now < evidence.expires_at <= case.expires_at`.
These are synthetic evidence limits, not a production recovery-policy choice.
Use injected fixed January UTC time, never today's time or machine-clock edits.

Single recovery budget table (future models derive their limits from it):

| Expected value | Canonical bytes max | Base64url payload characters max | Complete envelope bytes max |
| --- | ---: | ---: | ---: |
| RetirementEvidence | 1536 | 2048 | 2560 |
| RecoveryEvidenceCase | 4096 | n/a | n/a |
| ReplacementTarget, RecoveryEvidenceSelection, RecoveryEvidenceAdmission, RecoveryEvidenceRefusal | 1536 each | n/a | n/a |

Retirement signature preimage is ASCII
`local-connect.offline-predecessor-retirement-evidence.v1` followed by one NUL
byte and canonical RetirementEvidence payload bytes. Reuse the existing Ed25519
verification primitive, with the verification key taken exclusively from the
verified predecessor binding in the issuer's consumption ledger. An ephemeral
test key signs only this synthetic assertion; its signature proves binding and
key possession, not that an actual PC, session or grant was disabled. Existing
bootstrap signing purposes and activation key allowlists stay unchanged.

## One admission owner and durable behavior

Proposed fixture API boundaries: `open_recovery_case`, `select_recovery_evidence`
and `admit_recovery_evidence` on `IssuerFixture`. All take explicit inputs; none
calls a host, network service, native API or ordinary consume as a side effect.

Case creation takes a case UUID, predecessor claim UUID and operation UUID,
ReplacementTarget, opened_at and expires_at. Both predecessor references must
resolve to the same consumed row through the issuer owner. It verifies the stored signed receipt through the
existing receipt owner and requires its complete binding to equal the stored
binding. Unknown, absent, malformed or conflicting predecessor evidence cannot
open a usable case. The owner constructs the case from that verified snapshot
and the proposed replacement; caller-supplied predecessor bytes are not trusted.
An active, release-verified fixture manifest supplies existing receipt trust;
missing/expired configuration refuses new work before effects. Do not weaken
receipt validation to accommodate an expired or corrupt trust configuration.
Case creation, including exact retries, requires `opened_at <= now < expires_at`.
Validate all creation relations against the actual issuer writer snapshot after
waits and before commit, just as for admission. Case opening does not accept an
unverified claim or caller assertion that consumption is known.

Replacement organization and entitlement equal the predecessor's; operation,
installation, host and installation public key must each differ from it. The
new principal commitment may equal or differ: a new installation can belong to
the same person, and this slice proves no person's identity. The target's shape
and binding never constitute business verification or fresh native proof.

The issuer writer reserves one immutable case/target per predecessor consumed
operation in this bounded fixture. Enforce unique case ID and unique predecessor
operation in SQL, with foreign-key ownership and closed table states. Exact
case-creation retries return identical case bytes. Reuse of a case ID for a
different predecessor, target or window conflicts. Another case for the same
predecessor conflicts, even after expiry; cancellation/reselection and successive
replacement chains are later work, not an implicit release or retry here.

Selection is owner-derived. Admission validates the full case, verified original
receipt/binding, selected digests, canonical evidence, expected signature and all
case/target/time relations before any write. The same validator runs against the
actual writer snapshot after waits and immediately before commit with fresh
synthetic time. Stale selection or changed/corrupt source state refuses; no
silent rebase or re-selection. No cross-store transaction or host database read.

Record exact signed evidence bytes and one admission receipt atomically, using
unique case ID and unique evidence ID. Exact evidence retry for the same case
returns the same receipt bytes and makes no write; it still requires intact
source records, signature and current windows. Expired retry refuses without
deleting the historical admission. A different evidence ID, envelope or target
after admission conflicts; the same evidence reused by another case conflicts.
After a lost response, the caller explicitly retries the same bytes. No automatic
retry, new case, replacement claim or authority publication occurs.

New case/admission tables are the only writes. Preserve byte-identical original
claims, consumptions, receipts and journal, and every host's configuration,
pending binding, receipt/admin/audit state. Use owner snapshot digests over all
relevant rows, not counts alone. The fixture identity owner advances storage
version and accepted contract pin; only fresh disposable roots are created.
Old, restored, wrong-owner/profile and corrupt stores refuse without migration.

Admission success is `EVIDENCE_RECORDED_ONLY`, never `COMMITTED` or replacement
eligibility. The refusal model above keeps unavailable predecessor/configuration,
binding conflict, invalid evidence and expired evidence separate. A malformed value with
no usable case ID is an uncorrelated protocol error, not an invented identity.
Store corruption and worker termination remain STOP/error paths, not an ordinary
refusal or PASS. Partial writes roll back; a durable commit followed by lost
reply remains uncertain to the caller until explicit same-evidence recovery.
Each ordinary refusal carries the already validated caller-selected case UUID;
it does not assert that a case exists. Missing/unknown consumption maps to
predecessor unavailable; mismatched known references map to binding conflict.
Missing/expired active configuration maps to configuration unavailable. Invalid
stored signatures or malformed/future configuration are corruption/input errors,
not unavailable. A well-formed but untrusted candidate signature or mismatched
evidence fields is invalid evidence; a valid expired window is expired evidence.
No code implies that an earlier ambiguous admission failed to commit.

This slice introduces no executable recovery authorization, revocation endpoint
or admission-to-admin consumer. Its receipt must be rejected by every existing
bootstrap claim/receipt decoder. Revocation of an authorization that does not
exist here is not simulated. Later authorization/publication work must specify
its own signing trust, revocation/replay protocol and all canonical prerequisites.

## Verification plan for a separately authorized implementation

| Gate | Required falsifiable proof |
| --- | --- |
| Baseline and parity | Existing signed consume, changed-binding conflict, same receipt replay, expired-claim recovery, restored-store denial and renewal tests on the pinned baseline, then unchanged inputs/results after the new fixture version. No claim that this establishes retirement or recovery authorization. |
| Fail first | Missing model/API/schema rejection is the declared initial failure class. No fixture/key generation for this contract PR. Later preserve the smallest failing reproduction before implementation. |
| Models and budgets | Positive canonical cases; missing/extra/null/coerced/falsy/mixed fields, duplicate members, non-finite values, wrong versions/purposes, alternate base64/JSON encodings, min/max/one-over and large valid inputs. Generated schema and runtime admission agree. |
| Binding and trust | Otherwise-valid wrong case, target, predecessor receipt, key, purpose, organization, entitlement and each required distinct target field; copied ordinary receipt/claim and arbitrary supplied verifier rejected. Equal principal commitments admitted. Each digest must be sensitive to every covered field. |
| Time | Before/equal/after each window boundary; exact maximum and one-over; future assertion, case expiry, evidence expiry and expiry after writer wait / before commit. Expired exact retry refuses while preserving history. |
| Durable replay | Exact open/admit retries after restart return byte-identical stored receipts without another row; lost reply recovered explicitly. Changed envelope/ID/target and evidence replay across cases refuse with complete state retained. |
| Concurrency | Real processes and existing deterministic barriers, both race winners: two case IDs for one predecessor; same case with two targets; identical admission retries; different evidence for one case. Prove one reservation/admission and no overwrite. No sleeps or process-state proxies. |
| Faults | Existing SQL/crash hooks at writes and before/after commit; actual stored binding/receipt/case corruption, missing store, restored store and stale selections. No partial admission, no erased uncertainty and no reinterpretation of corruption as unavailable. |
| Effects and boundaries | Owner digests prove original issuer rows and all host state unchanged; actual new tables show only the intended case/admission. Network/native/account/installed-trust/product sentinels prove no dispatch. Bootstrap decoders reject new evidence/receipts; `device-replacement` remains BLOCKED and native commands STOP. |
| Mechanism sensitivity | Each relation has an independent otherwise-valid negative plus a fresh-process removal/weakening probe. Identify exact assertion failures; setup/import errors, STOP and shared downstream failures do not count as detecting that rule. Preserve both sides of compound comparisons. |

Run the affected existing test files and applicable lint/schema/whitespace checks
incrementally; CI owns duplicated broad suites. Reuse current Windows coverage.
The later evidence packet must name actual exercised source/lock/schema hashes,
positive results, refusals, failures and unmeasured behavior. Store evidence under
alias `offline-device-recovery/` outside worktrees with directories 0700/files
0600. Retain no private test key, principal/salt bytes, credentials or real data.
Public reviews cite artifact aliases and SHA256, not private paths. Do not reuse
the full controller result model to claim this prerequisite is device recovery.

## Assumptions, blockers and explicit non-scope

The offline prerequisite can use fabricated case/target values and temporary
original-installation signing keys after a separate go. It does not assume an
approved business-verification policy, a qualified retirement API, or any real
predecessor's availability. No `approved=true` or mocked native assertion can
remove those production blockers.

The licensing owner must still supply its business-verification policy. Real
retirement, session/grant invalidation and supported restore/rollback resistance
remain unqualified. [Issue84](https://github.com/canfieldjuan/connect-automate/issues/84)
remains open: the unreachable-predecessor decision and older disk-image risk are
not resolved by a signature. No new polling/connectivity requirement is proposed.

No native/VM/account/service/boot/disk work, real key or trust provisioning,
licensing issuance/deployment, recovery authorization, replacement publication,
machine grant, receiver, Gmail/OAuth/message, UI, production source, dependency,
workflow or other-repository change. No PR91 P3 hardening is folded in. No
controller case promotion, new CLI, catalog change or device-replacement PASS.

## Contract checks, acceptance and gap audit

For this PR verify the two-document scope, canonical link, exact source/lock and
prior-evidence pins, closed-field/budget/time consistency, retained blocked case,
and unchanged executable/schema/test bytes. Read the final diff cold. Run no
application imports, tests, fixtures, key generation or native probes. There is
no fail-first runtime test for a prose-only work order; the table above specifies
the later implementation proof.

Publish the exact contract commit for independent oversight and Juan's final
acceptance. Merge only that accepted head after green CI, clean connector review,
zero unresolved threads/no CHANGES_REQUESTED, independent PASS and merge-tree
equality. Then stop for separate offline implementation authority. This work
order's acceptance cannot lift the native or live-work holds.

Implementation summary: proposal and canonical pointer only. Cold diff audit
must trace both files to this missing evidence-admission prerequisite and find
no restated or changed product policy. **DONE** applies only to checked contract
preparation/publication. **NOT DONE** for review, exact acceptance, merge,
implementation, recovery authorization, device replacement or qualification.
