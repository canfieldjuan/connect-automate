# Offline association correction and withdrawal history work order

Status: **PROPOSED — contract only**. This narrows the next implementation step
under [the accepted register contract](LEAD-OWNER-LICENSING-REGISTER.md), without
changing business-verification policy. Implementation requires separate authorization
after exact-revision review and Juan's acceptance. Synthetic records and temporary
test keys only; native sign-in, Hello, Gmail and live activation remain on hold.

## Problem, inventory and boundary

At merged revision `1e591be5447bc89e45d825f79fa85b61d3097bed`, enrollment changes
retain revisions and fence stale completions. Associations still occupy one mutable
row: `associate` creates it, `withdraw_association` updates it, and there is no
`correct_association`. Old decisions survive in journal snapshots, but there is no
retained association revision relation or executable evidenced correction path.

| Existing owner at that revision | Reuse and limit |
| --- | --- |
| `qualification/licensing_register/protocol.py`, `Command`, `Association`, `Consumption` | Closed commands/proofs, strict revisions and shared UUID/digest/instant types. Association verification and consumption receipts are signed synthetic facts, not real verification adapters. |
| `qualification/licensing_register/core.sql`, `apply`, `snapshot`, `assert_history` | Control-row serialization, session-derived scope, exact replay, history checks and association currentness checks. Replace the separate association create/withdraw mutation branches with one transition owner. |
| `core.sql`, enrollment head/revision relations and `transition_enrollment` | Proven retained-head pattern and post-wait expiry checks. Reuse the mechanism without changing enrollment semantics or admitting enrollment-only states into associations. |
| `qualification/licensing_register/fixture.py`, verified proof import and scoped clients | Existing temporary-key signature verification, canonical serializer, execute-only clients and disposable PostgreSQL. No application proof-signing/import privilege. |
| `tests/test_register_postgres.py`, lifecycle, withdrawal, consumption, binding, process, fault and restore tests | Reuse actual PostgreSQL, existing synthetic inputs, scoped clients, lock barriers and pytest-managed temporary storage. |
| `tests/test_register_enrollment_change.py`, retained history, both-order races and clock tests | Reuse the process/barrier and corruption proof patterns. PR109's register-postgres, test and windows-placement CI jobs passed; this is existing evidence, not a run of the proposed commands. |
| `qualification/owner_authority/` | Existing consumed-binding model is reused unchanged. No issuer/host/recovery algorithm is ported, and register-only tests do not establish integration parity. |

No model, prompt or inference runtime is involved. Differences from that inventory
are limited to the new correction command/proof, retained association identity and
revisions, a shared association transition owner, and their tests/CI/documentation.
Fresh disposable databases suffice; this does not propose a deployed migration.
Commercial/grant revision storage, sale ingestion and real proof adapters remain
separate obligations, not silently implemented by association history.

## Closed correction command and evidence

Keep `offline-register/1` and the existing fixture `CURRENT`/`WITHDRAWN` association
states; do not imply adoption of the parent's full production schema or API.
Add a closed `correct_association` command with the existing operation, epoch and
record identity, a strict positive `expected_revision`, and `proof_id`. Actor and
organization are derived from the authenticated licensing database session. This
does not give the licensing role enrollment-verification privileges.

Add a distinct closed `ASSOCIATION_CORRECTION` proof branch at the existing evidence
owner. In addition to the common version, offline markers, proof ID, association
record ID and organization ID, require:

- `expected_revision`, the association head this decision corrects;
- `entitlement_id`, `grant_id` and `grant_revision`;
- `enrollment_id` and `enrollment_revision`;
- `verification_ref`, the opaque reference to the synthetic correction decision.

Reuse existing strict positive revision and UUID types. No optional branch fields,
free-text identity, caller-supplied `verified` flag or second signature format.
The existing privileged importer validates the closed model and temporary-key
signature. The fixture's signed proof asserts an independently evidenced decision;
it does not establish actual requester identity, authority or source currentness.
No new customer document or second person is implied by this internal receipt.

The proof must bind the exact association revision and supporting revisions. A
caller cannot make an old proof authorize a new correction merely by changing the
command's expected revision. Reuse of a verification reference is not itself a
reason to refuse: the signed revision/scope bindings and current supporting heads,
not an arbitrary fresh-reference rule, determine eligibility. Initial `ASSOCIATION`
proofs remain unchanged and cannot be used as correction proofs.

## Retained identity, revisions and one owner

Preserve stable association identity separately from its current revision. The
original association ID, organization and entitlement remain fixed, with the
existing one-association-identity-per-entitlement uniqueness. This does not limit
the number of entitlements a business can hold. A correction may select another
current enrollment for that same business, or a new revision of the same enrollment.
It may also keep the same supporting references while correcting its verification
decision; do not require a changed enrollment ID as a proxy for a valid correction.
`associate` remains initial creation only: a new operation cannot recreate or replace
an existing association identity, including a withdrawn one. Exact replay remains
historical evidence; restoration uses the evidenced correction path.

Use primary/foreign keys to bind retained association revisions and the head to
that identity and organization, and each decision to its scoped proof and retained
enrollment revision. Keep all prior revisions and their proof references reachable
from `snapshot`. The head selects a retained revision, rather than duplicating its
mutable decision fields. Consumption references the stable original association
identity, whose initial revision remains retained; it is never retargeted to a
correction's new enrollment. A current-head view may preserve existing readers.

Use closed revision branches: a `CURRENT` revision identifies its initial or
correction decision and supporting revisions; a `WITHDRAWN` revision records the
withdrawal and explicitly retains its prior decision lineage without presenting
that decision as current authority. Initial, correction and withdrawal reasons
are closed to `INITIAL`, `RECORD_CORRECTION` and `AUTHORITY_WITHDRAWN` respectively.
Enforce expressible relations/state branches with the owner's existing SQL
PK/FK/UNIQUE/CHECK and enum mechanisms, not parallel regex or reader-side repairs.

One named SQL association transition owner handles creation, correction and
withdrawal. The existing privileged `apply` entry remains its only application
route; fixed search path and table/function permissions remain enforced. Replace
the old separate association mutation branches. Cross-record rules that constraints
cannot express belong in this owner; all readers use the retained identity/head.

For a new correction, under the existing control-row transaction:

1. Preserve control lock → epoch/mode → actor/lane → history → replay admission.
2. Resolve and lock the scoped association and supporting heads in stable order.
   Check the actual association revision against both command and correction proof.
3. Check proof kind/record/scope and original organization/entitlement independently.
   The entitlement's existing issuance must belong to that organization and grant;
   correction cannot relabel issuance or replace its original commercial basis.
4. Require the proof's exact grant and enrollment revisions to match current heads.
   Both must be `CURRENT`. Check enrollment authority and required-source expiry
   with the database clock after waits and immediately before the mutation;
   equality is expired. The fixture grant model has no new invented expiry.
5. Append the next association revision, advance its head, and record snapshot,
   journal and immutable result atomically. Commit before exposing success bytes.

Existing grants still use the bounded fixture's mutable head and journal history;
record the checked grant revision without claiming a retained commercial-revision
foreign key exists. Full commercial revision relations remain a later slice.
Missing new proof is `SOURCE_UNAVAILABLE`; stale expected heads are
`REVISION_CONFLICT`; a proof/command association-revision disagreement or mismatched
existing proof/identity relations is `BINDING_CONFLICT`; non-current or expired supporting authority is
`AUTHORITY_NOT_CURRENT`. Missing/altered established history is `HISTORY_CORRUPT`,
not missing new evidence. Refusals/STOP leave domain snapshots unchanged and create
no successful result. Preserve the existing locked-restore behavior.

## Withdrawal, recovery, replay and consumption

`withdraw_association` still accepts its existing command shape and exact expected
association revision, without a correction proof. It appends a withdrawal revision
through the same owner, preserving prior decisions and consumption. It must remain
possible when supporting enrollment/grant authority is expired or withdrawn:
withdrawal reduces reliance on authority and must not depend on its currentness.

An evidenced correction may publish `CURRENT` from either `CURRENT` or `WITHDRAWN`
when its actual head and current supporting facts pass the checks. This allows a
mistaken withdrawal to be corrected without erasing it. There is no permanent
withdrawal lock, new purchase requirement or automatic reinstatement. A real
business transfer changes whose authority is recorded and remains separate from
this same-business correction; no existing consumption is reassigned here.

If withdrawal commits first, an older correction conflicts. If correction commits
first, withdrawal with the old expected revision conflicts; the caller must reselect
the actual head before reporting withdrawal effective. A new correction against
that withdrawn head needs evidence bound to that revision. Replaying an old initial
association, correction or withdrawal returns historical evidence only and never
moves the current head. Changed payload/actor/scope conflicts; revoked actors and
corrupt/locked stores cannot obtain affirmative replay by bypassing admission.

Preserve the original consumed binding, claim, consumed operation, entitlement and
receipt byte-for-byte across correction and withdrawal. Existing consumption can
be attached as historical evidence before or after these transitions when its
original binding passes the existing checks; do not add a current-authority gate
to historical consumption recording. Missing consumption means unresolved linkage,
not proof of an unconsumed deployment. Removing or re-keying established consumption
remains corruption. A correction result grants no recovery or host permission.

## Verification for separately authorized implementation

| Proof | Required observations |
| --- | --- |
| Positive correction | Initial association, correction to a new current revision of its enrollment, correction to another enrollment of the same business, and correction keeping the same support references. Every revision retained; original consumption unchanged. |
| Withdrawal and recovery | Withdraw appends history even with expired/withdrawn supports. Fresh evidenced correction can restore a withdrawn association when supporting heads are current. Stale proof cannot restore it; no permanent exclusion. |
| Closed inputs/permissions | Partial/mixed/unknown fields and caller scope/verified flags refuse; missing/zero/negative/boolean/string/overflow revisions refuse; valid boundaries pass. Probe direct SQL and wrong-role access; scoped licensing controls pass. |
| Binding second side | Existing-but-wrong association, organization, entitlement, issuance/grant relation, proof kind, expected association revision and each supporting ID/revision fail independently, with valid controls and unchanged snapshots. Same-organization wrong-entitlement cases must not be masked by scope rejection. |
| Guard strength | Remove each new semantic guard and show the named regression detects its lost guarantee. Classify equivalent or constraint/history-dominated mutants honestly. Probe relational identity/revision/state constraints directly; no hidden setup failure counts as a killed mutant. |
| Currentness | Pending/unavailable/withdrawn enrollment and withdrawn grant refuse correction; valid supports with and without required-source expiry pass. Expired and equality boundaries and real lock waits across authority/required-source deadlines. No expiry is invented for optional source copies. |
| Races | Real independent PostgreSQL processes, deterministic lock barriers, both orders and the existing three-repeat policy: correction/correction, correction/association withdrawal, correction/enrollment begin or withdrawal, correction/grant withdrawal, and correction/original consumption attachment. One serial outcome; no erased history or duplicated/moved consumption. |
| Retry/crash | Failure at each applicable SQL write and before commit rolls back revision/head/journal/result together. Lost committed reply replays exactly. Changed operation content conflicts; old replay after newer corrections/withdrawals cannot reactivate or retarget anything. |
| Corruption/restore | Remove/re-key retained identity, head, revision, proof or established consumption; STOP before replay or mutation. Snapshot includes all retained association evidence. Restored/current and old-epoch requests remain locked; no unlock path. |
| Regression/retention | Existing register and enrollment-change fixtures pass unchanged; reusable consumption/issuer models are unchanged. Use pytest-managed clusters and durable separate review logs. CI owns duplicated broad suites; run necessary local PostgreSQL evidence without claiming native/live qualification. |

## Restrictions and exit

| Constraint and cost | Concrete need and why a lighter rule fails |
| --- | --- |
| Preserve original organization/entitlement; this command cannot transfer a consumed licence | Consumption already binds those identities. Allowing an overwrite would silently assign an existing receipt to another business or entitlement; retaining only the latest row would lose the original meaning. Retained revisions permit same-business corrections without a transfer. |
| Exact association/support revisions and signed correction evidence; internal reselection/retry work | A delayed decision could otherwise undo withdrawal or use changed enrollment. Checking only the latest state label, or accepting the old creation proof with a new command revision, does not bind what was actually evidenced. No extra customer document or person is required. |
| Current supporting authority for affirmative correction; temporarily prevents publishing current association from missing/expired evidence | Otherwise a new association decision could rely on withdrawn or changing support. Check only the referenced support and actual expiry; withdrawal and historical consumption recording remain available, and later evidenced correction can restore currentness. |
| Existing licensing-role writes and one identity per entitlement | Prevents an enrollment-only credential or duplicate association from relabelling licensing evidence. Reuse existing scoped permissions and relational uniqueness; no new operator account, second person or one-licence-per-business cap. |

No sale/provider work, commercial correction, business-transfer policy, private-store
coordination, identity method, custody/retention worker, Supabase provisioning,
production migration, continuity witness, restore unlock or recovery approval is
included. Those requirements remain unqualified. Non-blocking proof follow-ups stay
in [issue 107](https://github.com/canfieldjuan/connect-automate/issues/107).

Exit for this document: independent exact-revision oversight and clean connector/CI,
then Juan's contract acceptance. No fixtures run for this prose-only work order.
Implementation needs separate authorization; all resulting fixture evidence must
remain `OFFLINE_CONFORMANCE` with `qualification_pass=false`.
