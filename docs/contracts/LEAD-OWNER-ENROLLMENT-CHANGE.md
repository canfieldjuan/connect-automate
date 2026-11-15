# Offline register-side enrollment change work order

Status: **PROPOSED — contract only**. This narrows the next implementation step
under [the accepted register contract](LEAD-OWNER-LICENSING-REGISTER.md); it does
not amend business-verification policy or authorize code, infrastructure or live work.
Native sign-in, Hello, Gmail and live activation remain on hold. Later implementation
requires separate authorization and uses synthetic records and temporary test keys only.

## Problem, inventory and boundary

At merged revision `88dde8ed01f81b6f0578a7244bd7b0f5c54aaf22`, enrollment is
created directly as `CURRENT` or changed to `WITHDRAWN`. There is no pending change
identity, completion operation or proof that a delayed completion cannot overwrite
a newer withdrawal. An enrollment evidence change therefore has no executable
register-side ordering protocol yet.

| Existing owner at that revision | Reuse and limit |
| --- | --- |
| `qualification/licensing_register/protocol.py`, `Command`, `Enrollment`, `Proof` | Closed command/evidence branches, strict revisions, UUID/digest/instant types and offline evidence markers. Existing enrollment proofs assert synthetic completed decisions; they do not verify people. |
| `qualification/licensing_register/core.sql`, `apply`, `assert_history`, `snapshot` | Control-row serialization, session-derived actor/scope, exact replay, journal/projection integrity and currentness checks. `enroll` creates an initial head; `withdraw_enrollment` advances it. |
| `qualification/licensing_register/fixture.py`, `Register`, `Client`, `temporary_cluster` | Privileged temporary-key proof import, scoped execute-only clients and isolated PostgreSQL. Pytest owns temporary-directory retention. |
| `tests/test_register_postgres.py`, lifecycle, binding, process race, expiry, fault and restore tests | Retain the real PostgreSQL harness and deterministic lock barriers. The merged focused gate recorded 70 passing tests; the binding-guard removals each fail their new existing-record negative. |
| `qualification/owner_authority/` and its existing recovery tests | Original consumption/issuer/host behavior stays unchanged. Do not claim integration parity from this register-only extension. |

This work adds only the **register-side enrollment change fence**. A fence is the
committed transition to non-current before supporting evidence is changed. The
fixture imports signed synthetic completion facts after that commit; it does not
implement a private evidence store, identity method, retention worker or network
adapter. A synthetic import is proof of fixture provenance, not proof of real
source currentness. Full external-store coordination remains a later qualification.

No model, prompt, inference runtime or production port is involved. Differences
from the proven fixture are the enrollment state branches, change lineage and
completion binding described below. Existing grant, issuance, association and
consumption identities, actor scopes, restore lock and historical replay semantics
remain intact. Fresh disposable databases suffice; no deployed migration is proposed.

## Closed transitions and their owner

Keep the existing `offline-register/1` fixture boundary. Add closed `begin_change`
and `finish_change` command branches to its canonical command owner; no public API
or generic update command. Both carry the existing operation/epoch/record identity
and a strict positive expected revision. Actor and organization still come from
the authenticated enrollment database session, never request fields.

`begin_change` additionally carries a fresh opaque change ID and a closed reason:

| Reason | New head state | Meaning |
| --- | --- | --- |
| `SOURCE_UPDATED` | `PENDING` | A replacement decision/evidence revision is being prepared. |
| `SOURCE_UNAVAILABLE` | `UNAVAILABLE` | Required supporting evidence cannot currently be established. |
| `AUTHORITY_WITHDRAWN` | `WITHDRAWN` | The enrollment owner has withdrawn authority. |

The command locks and checks the exact scoped head, appends its next revision and
change lineage, and atomically commits the non-current head, journal and operation
result. No external work occurs while the SQL lock is held. A later independently
evidenced recovery from non-current is allowed: start a new `SOURCE_UPDATED` change
against the actual head. A new begin may supersede an unfinished change using that
same exact-head rule; it cannot silently finish or reuse the old change ID.

The existing `withdraw_enrollment` command remains supported. Route it and the new
withdrawal reason through one enrollment transition owner so neither can leave a
pending completion eligible. Both preserve historic decisions and original
consumption. `enroll` remains initial fixture creation only, never replacement or
reactivation of an existing enrollment ID.

`finish_change` carries the change ID and references to two imported fixture proofs:
the candidate `ENROLLMENT` decision and a closed completion statement. The completion
statement binds its kind/version, offline markers, proof ID, organization, enrollment
ID, change ID, pending register revision, candidate decision proof ID and digest,
registration reference, private evidence revision and private evidence digest.
Private revisions use the existing strict positive revision type as a fixture-only
ordinal, without selecting a production store's revision format; references and
digests reuse existing protocol types. No customer text or source bytes enter this
statement. Its temporary-key signature is verified by the existing privileged
import boundary, not accepted as an application-supplied `verified` assertion.
Compute the candidate digest from the validated `ENROLLMENT` proof using the
existing canonical serialization and SHA-256, not a second JSON formatting rule.

The completion statement is an immutable synthetic receipt for the separately
completed evidence change. The test driver produces it only after the matching
begin committed. The SQL owner verifies the corresponding fields against the retained
begin, candidate decision and current pending head. The private revision/digest are
signed fixture assertions: they have no independent private-store comparator in
this slice. Admission validates their closed shape and signature, and history binds
them immutably. Real-store authenticity/currentness must later be qualified by that
adapter; these assertions cannot stand for that proof. Merely knowing an enrollment ID,
holding an earlier proof or uploading a receipt cannot substitute for those checks.
Missing new completion evidence is unavailable; missing or altered established
lineage is corruption. Neither outcome changes domain state or creates success.

Only the matching `PENDING` head may finish. Check its revision, change ID, scope,
proof kind/identity, registration and candidate digest independently; an existing
but mismatched record must fail even when all foreign keys exist. Recheck canonical
authority and required-source expiry with the database clock after lock waits and
immediately before publishing `CURRENT`; equality is expired. Commit the new
current revision, proof lineage, snapshot, journal and immutable result together.
The signed completion's historical pending revision remains immutable after finish.

Express the state/command branches with closed models and SQL constraints. Completed
decision fields belong only to `CURRENT`; non-current heads carry change/reason and
explicit prior-decision lineage where present, not fabricated current evidence.
Retain historical proof/revision references so changing the current head neither
erases prior audit nor makes old consumption look absent. One named SQL transition
owner handles cross-record rules that relational constraints cannot express.
Use an enrollment-specific closed state type; do not accidentally admit enrollment
pending/unavailable states into commercial or association records.

## Replay, withdrawal and ordering

Preserve control lock → epoch/mode → actor/lane → history → replay ordering. Exact
retry returns the original committed `RECORDED` result labelled `REPLAY`, without
performing another transition. Replay is historical evidence, not current authority.
Changed command content/actor conflicts; revoked actor, corrupt history and locked
restore cannot retrieve an affirmative replay by bypassing the existing checks.

A new association cannot use `PENDING`, `UNAVAILABLE` or `WITHDRAWN` enrollment.
An association committed before begin remains a historic fact bound to its original
revision; it is not silently upgraded when finish publishes another revision.
Preserve existing consumption even if begin or withdrawal wins a race. No host or
recovery authorization is issued by any register result.

Withdrawal/new begin wins over an older finish if it commits first. If finish
commits first, a withdrawal using the old pending revision conflicts; the enrollment
owner must reselect and commit withdrawal against the actual current revision before
reporting it effective. Do not acknowledge an uncommitted withdrawal as applied.
A replayed old finish after withdrawal cannot reactivate the enrollment.

Failure before begin commit leaves the original state and no effective change.
Failure after begin commit leaves a non-current head. Missing completion or a lost
external reply cannot manufacture `CURRENT`; resolve/reimport the exact immutable
completion or leave the head non-current. An old completion cannot finish a new
change, even when its business, registration and evidence contents otherwise match.

## Verification for separately authorized implementation

| Proof | Required observations |
| --- | --- |
| Valid lifecycle | Initial current enrollment; begin makes it pending; new association refuses; matched completion finishes; a new association pins the new revision. No history or consumption disappears. |
| Other non-current branches | Unavailable/withdrawn deny new association; a fresh evidenced begin/finish can restore currentness. No permanent customer exclusion or implicit reinstatement. |
| Closed input and role | Reject partial/mixed branches, unknown fields, caller actor/scope, malformed IDs/digests, absent/zero/negative/boolean/string/overflow revisions. Probe direct SQL and licensing-role calls; enrollment-role controls pass. |
| Binding second side | Existing-but-wrong enrollment, organization, change ID, pending revision, decision proof/kind/digest and registration fail independently, with unchanged snapshots and valid controls. Altering private revision/digest after signing fails import; corrupting retained values fails history validation. Do not claim an external comparator exists. Remove each new semantic guard to prove its test detects the bypass. |
| Replay | Lost begin/finish reply recovers the same result; changed body conflicts. Old begin/finish replay after a newer withdrawal/change remains historical and cannot move the head. Revoked actor still refuses. |
| Crash and missing proof | Inject failure at each SQL write and before commit: no partial journal/head/result. After begin, missing completion keeps non-current. A completion for a superseded change cannot finish. |
| Real races | Begin versus association, finish versus withdrawal, competing begins, and competing finishes in both serial orders with the existing three-repeat process/lock-barrier policy. A stale withdrawal must reselect before it can become effective. |
| Clock | Valid, expired and required-source-expired candidates; writer waiting across each expiry; no cached transaction-start clock. Preserve optional-copy versus required-source distinction from the parent policy. |
| Corruption and restore | Remove/re-key retained change, decision or completion lineage; STOP before replay or mutation, unchanged snapshots. Restored and old-epoch requests remain locked; no unlock path. |
| Regression and retention | Existing focused register gate still passes on the same synthetic inputs. Use pytest-managed cluster retention and durable separate review logs; do not recreate unmanaged clusters. CI owns duplicated broad suites. |

## Restrictions, remaining gaps and exit

| Constraint and cost | Concrete need and lighter-rule assessment |
| --- | --- |
| Non-current while required evidence changes; temporarily blocks new associations for that enrollment | A cached CURRENT pointer could otherwise admit a decision against changing or withdrawn proof. Fence only required changes; optional source-copy deletion does not require this transition. |
| Exact head/change and paired decision/completion proof; internal bookkeeping/retry work | A delayed finish could undo withdrawal or publish another enrollment's decision. The existing enrollment proof alone lacks change/pending-revision bindings; the additional completion supplies them without changing its identity semantics or requiring another customer document. |
| Enrollment-role-only writes; licensing operator cannot self-verify | Licensing issuance authority does not establish business authority. Reuse the existing role split; no second person or additional customer credential is required. |

This proposal does not select a real source/currentness method, private-store
implementation, multi-business administrator policy or retention duration. It does
not implement sale ingestion, commercial/association correction, transfer, full
production record schemas, source deletion during outages, continuity witness,
restore unlock or recovery approval. These parent-contract obligations remain
unqualified, not waived. Non-blocking proof follow-ups remain in
[issue 107](https://github.com/canfieldjuan/connect-automate/issues/107).

Exit for this document: independent exact-revision oversight, clean connector/CI,
then Juan's contract acceptance. This prose-only work order changes no executable
code and runs no fixtures. Implementation needs a separate bounded request after acceptance; evidence
must remain `OFFLINE_CONFORMANCE` with `qualification_pass=false` throughout.
