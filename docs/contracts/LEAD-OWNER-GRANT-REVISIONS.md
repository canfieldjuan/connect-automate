# Offline grant revisions and issuance-binding work order

Status: **PROPOSED — contract only**. This narrows the next offline implementation
under the [accepted register contract](LEAD-OWNER-LICENSING-REGISTER.md).
Independent exact-revision review and Juan's explicit acceptance precede contract
merge; implementation requires separate authorization. Synthetic records and
temporary test keys only. Native sign-in, Hello, Gmail and live activation remain
on hold.

## Root cause, inventory and differences

At merged revision `476a56b814e4af8ac6eb1babbfe6e80043f9c6d3`, grant creation and
withdrawal in `qualification/licensing_register/core.sql:339-360` write one mutable
`grants` row. Withdrawal replaces its state/revision; there is no evidenced revision
command. The `issuances` relation at `core.sql:66-70` binds only grant identity,
not the decision revision. Association revisions already record `grant_revision`,
but their foreign key at `core.sql:88` binds only grant identity/organization.
Journal snapshots preserve old projections, but are not retained decision relations
that issuance and association can reference. These are bounded fixture gaps in the
parent's `revise_commercial` and `register_issuance` requirements, not a production
incident or a claim that a real licensing register exists.

| Existing owner at that pin | Reuse and limit |
| --- | --- |
| `qualification/licensing_register/protocol.py`, `Grant`, `Issuance`, `Command`, `Evidence` | Closed Pydantic unions, strict positive revision/UUID/digest types, synthetic signed evidence. `Grant` has provenance/policy references; `Issuance` has a grant ID and envelope digest, but no grant revision. |
| `core.sql`, enrollment and association heads/revisions | Reuse the retained identity/head pattern, branch constraints and scoped FKs; do not import enrollment-only states into grants. |
| `core.sql`, `apply`, `snapshot`, `assert_history`, `transition_association` | Reuse control-row serialization, session-derived scope, exact replay, current supporting-head checks and corruption/restore admission. Replace grant create/withdraw branches with one grant transition owner. |
| `qualification/licensing_register/fixture.py` | Reuse verified temporary-key proof import, canonical serialization, execute-only clients, pytest-managed PostgreSQL and CHECKPOINT/finally-stop cleanup. No fixture client can sign/import proofs. |
| `tests/test_register_postgres.py`, `tests/test_register_protocol.py`, `tests/test_register_enrollment_change.py`, `tests/test_register_association_correction.py` | Reuse synthetic lifecycles, SQL fault injection, independent-process barriers, both-order races, retained-history and locked-restore tests. Prior implementation evidence recorded 270 passing register tests; that is baseline evidence, not verification of these proposed commands. |
| `qualification/owner_authority/` | Existing issuance/consumption/recovery algorithms remain unchanged. This work does not establish real issuer-adapter or recovery integration parity. |

There is no model, prompt or inference runtime. Differences from the inventory are
the grant revision command/proof, retained grant relations and transition owner,
required issuance grant-revision binding, stronger association grant-revision FKs,
and directly affected fixtures/tests/CI/docs. The existing fixture versions
`offline-register/1` and `offline-register-evidence/1` remain fixture-only; the
new required issuance field is an intentional fixture input change, not a compatible
production API change. Update every synthetic issuance producer explicitly. There
is no default to revision 1 or the latest head and no conversion of persisted old
databases: use fresh disposable databases. No deployed migration is proposed.

## Closed commands and evidence

Keep initial `grant` and `withdraw_grant` command shapes. Add `revise_grant` with
the existing operation, epoch and record ID, required strict positive
`expected_revision`, and `proof_id`. Actor and organization remain session-derived;
the command belongs to the existing licensing lane.

Add a distinct closed `GRANT_REVISION` proof branch, carrying the common version,
offline markers, proof ID, grant record ID and organization plus:

- `expected_revision`, the grant head this decision revises;
- `provenance_ref`, the opaque attributable grant-decision reference;
- `policy_revision`, the strict positive adopted grant-policy revision.

The privileged importer validates the existing closed model and temporary-key
signature. The signed decision must bind the actual expected head; an initial
`GRANT` proof cannot serve as a revision proof. A new decision may retain the same
provenance reference and policy revision. Neither a changed reference nor a higher
policy number proves new authority, so neither is required as a proxy. The exact
head-bound decision is the evidence. The fixture signature asserts synthetic
provenance only; real grant-policy adoption/authentication remains unqualified.

Extend the closed `ISSUANCE` proof with required `grant_revision`, using the shared
strict revision type. Together with its existing record/organization/grant IDs and
envelope digest, this signed statement attests that this synthetic issuance was
made under that retained grant decision. It is not permission to issue a licence.
No caller `verified` flag, optional-everything branch, guessed revision, new
signature format or production timestamp/issuer adapter is introduced.

## Retained grant identity and transition owner

Keep a stable grant identity and organization with a head pointing to a retained
revision. Each revision has the scoped grant ID, revision, closed state/reason
and decision lineage. Retain initial revision and all subsequent decisions,
withdrawals and their referenced proof contents in `snapshot`.

Use the fixture's `CURRENT`/`WITHDRAWN` states. A `CURRENT` branch references its
initial `GRANT` or `GRANT_REVISION` decision, with `INITIAL` or `RECORD_CORRECTION`
respectively. A `WITHDRAWN` branch uses `COMMERCIAL_WITHDRAWAL` and retains a
reference to its preceding current decision, without presenting its proof as
current authority. Repeated withdrawals against the actual head remain representable
and preserve the last decision lineage. Enforce identity, organization, head,
initial revision, decision-state and branch relations with existing SQL
PK/FK/UNIQUE/CHECK/enum mechanisms. A head-selected `grants` view can preserve current
readers, without a second mutable copy of decision fields.

One named SQL grant transition owner handles create, revise and withdraw through
the existing privileged `apply` boundary. Remove the old separate mutation branches.
Cross-record semantics not expressible by constraints belong here, not in a later
reader filter. Keep fixed search paths and execute-only application permissions.

For a new revision, preserve control lock → epoch/mode → actor/lane → history →
replay admission. Resolve the scoped grant head under the existing locking order,
require command expected revision to equal the actual head, and require the signed
revision proof to bind that same head, grant and organization. Append a `CURRENT`
revision from either `CURRENT` or `WITHDRAWN`; advance the head and commit journal,
snapshot and immutable result atomically. Existing initial `grant` remains creation
only, including after withdrawal; operation replay never recreates or restores it.

Withdrawal requires its existing exact expected head and licensing role, without
a new affirmative decision proof or current enrollment/association. Append a
withdrawal through the same owner. This records reduced reliance on the grant;
it must remain possible when other authority is expired, unavailable or withdrawn.
Grant correction does not rewrite issuance, associations or consumption, and does
not itself approve recovery, renew a licence or reactivate a withdrawn association.

## Issuance history versus current association authority

Issuance stores its proof's exact grant revision. A scoped FK binds it to a retained
`CURRENT` grant decision, not a withdrawal revision. Use a constrained target-state
column or equivalent existing relational mechanism; do not leave decision-state
integrity to reader conventions. Validate the proof/record/organization/grant/revision
bindings at the issuance writer. Preserve entitlement uniqueness and immutable
envelope/proof binding. Multiple entitlements may reference the same grant decision.

An independently attested earlier issuance may be registered after the grant head
has advanced or been withdrawn, provided its exact supporting decision remains
retained. Do not require that historical decision to equal the current head. This
records historical evidence, not fresh issuance under withdrawn authority. A new
issuance claim bound to a withdrawal revision fails. Without the required signed
historical binding, leave registration unresolved; do not infer it from a latest
head, matching organization, caller date or envelope digest alone. The fixture
cannot prove real-world chronology: qualifying actual issuer evidence is later work.

Association creation/correction still checks the current grant and enrollment
heads in its locked transaction. Its grant must match the issuance's stable grant
identity and organization. Its selected current grant revision may be newer than
the issuance's original supporting revision; requiring equality would unnecessarily
strand legitimately issued licences after an evidenced grant correction. Upgrade
the association revision FK to the exact retained grant decision, while keeping
issuance's original decision immutable. Existing enrollment expiry checks remain.
Historical issuance registration while the grant is withdrawn does not make a new
association eligible. Once an evidenced revision restores the grant, a separately
validated association operation can use the new head. No automatic association
mutation or approval follows from restoring the grant.

Preserve original consumption identity, binding, receipt, claim, entitlement and
operation across all transitions. Historical consumption attachment remains available
after withdrawal when its existing binding checks pass. Missing consumption remains
unresolved linkage, not evidence of an unconsumed deployment.

## Refusal, replay, crash and restore

Use existing result/refusal vocabulary. Malformed new input is `INPUT_INVALID`;
wrong lane/actor is `UNAUTHORIZED`; a stale/missing expected grant head is
`REVISION_CONFLICT`; a mismatched existing proof, scope, record or referenced
grant/revision relation is `BINDING_CONFLICT`. Missing new proof is
`SOURCE_UNAVAILABLE`; referencing a retained withdrawal as issuance authority, or
using a non-current supporting head for an affirmative association, is
`AUTHORITY_NOT_CURRENT`. History validation precedes these business checks: missing
or altered established revisions/proofs/issuance/consumption is `HISTORY_CORRUPT`,
never new-evidence unavailability. Preserve `REGISTER_LOCKED` and old-epoch denial.

Refusals and STOP leave domain snapshots unchanged and expose no successful result.
Rollback before commit includes head/revision, issuance, journal and result writes;
commit precedes success bytes. Lost committed replies replay the immutable old
result. Changed operation content/actor/scope conflicts. Old create/revise/withdraw
replay cannot advance heads, restore authority or retarget issuance. Revocation,
scope, corruption and restore admission still precede affirmative replay.

Concurrent grant revisions/withdrawals serialize: the loser using the old expected
head conflicts and must reselect before reporting a new decision effective. Historical
issuance can commit in either order with withdrawal because it references the retained
decision, while an affirmative association observes current supporting state.

## Required change surface and verification plan

Separately authorized implementation touches `protocol.py` closed branches,
`core.sql` grant relations/owner, issuance and association bindings, snapshot proof
reachability, and their direct callers. Add a focused grant-revision test module;
update existing issuance fixture builders and grant-table fault/corruption probes
only where the new required field or retained storage changes their target. Keep
their prior assertions and behavior coverage. Add that module to the existing
register-postgres CI job and update the fixture README's implemented/gap inventory.
No new framework, dependency, public endpoint or independent parser is needed.

| Proof group | Required observations |
| --- | --- |
| Fail first and positive history | Reproduce missing revision command and missing issuance revision binding at the baseline; retain minimal fail-before/pass-after tests. Create, revise, withdraw repeatedly, restore by evidenced revision, revise with unchanged provenance/policy, and issue multiple entitlements. Every decision/withdrawal retained, original issuance/consumption unchanged. |
| Closed input and direct SQL | Missing/unknown/mixed fields, old initial proof used as revision, caller actor/scope/verified flags, zero/negative/boolean/string/overflow revisions fail; minimum/maximum representable inputs decode. Direct SQL cannot bypass command shape or scoped writes. Revision increment at the storage maximum cannot wrap or partially commit. |
| Binding both sides | Independently mismatch existing grant, organization, proof kind, record, expected proof head, issuance grant revision, envelope/entitlement identity and association support. Include same-business wrong-ID cases and valid controls so scope rejection cannot mask the tested guard. Probe retained decision-state/FK/CHECK constraints directly. |
| Historical registration | Register an attested issuance against an older current decision after correction and after withdrawal. Bind to a withdrawal/nonexistent/wrong-business revision and refuse unchanged. New association while withdrawn refuses; after evidenced restoration it may use the new current grant revision while issuance retains the old one. |
| Existing authority paths | Association correction/withdrawal, enrollment begin/finish/expiry, historical consumption attachment and unchanged consumed-binding semantics still pass. Withdrawal of a grant does not need current enrollment or another person's confirmation. |
| Real races | Independent PostgreSQL processes and deterministic barriers, both orders using the existing three-repeat policy: revise/revise, revise/withdraw, issuance/revise, issuance/withdraw, and revise or withdraw versus association creation/correction. Assert exact serial head/revision/issuance outcomes, including stale proof refusal; no lost history. |
| Retry and failure | Inject each affected write failure and pre-commit failure; no partial revision/head/issuance/journal/result. Lost reply replays exactly; old replay after later revisions cannot restore authority. Changed payload and revoked actor tests remain. |
| Corruption and restore | Remove/re-key/alter retained head, initial/prior revision, referenced proof, issuance or consumption; STOP before replay/mutation. Old proofs remain in snapshot coverage after correction/withdrawal. Complete rollback remains externally locked; no invented continuity/unlock mechanism. |
| Guard strength | Remove each new semantic guard and demonstrate its named regression; classify equivalent/constraint-dominated mutants explicitly. A setup error is not proof of detection. Reuse actual PostgreSQL and temporary-key importer, not mocks of transactions or signature admission. |

Run the focused regressions and adjacent register modules, applicable Ruff checks
and SQL integration proofs. CI owns duplicated unrelated broad suites; preserve
required high-risk local register proof. Record exact tested head, commands, outputs
and cold diff audit in durable evidence outside worktrees. No tests run for this
prose-only proposal, and no native/live or real identity qualification is claimed.

## Restriction audit, non-scope and exit

| Constraint and cost | Concrete need and why a lighter rule fails |
| --- | --- |
| Same grant identity, organization and grant basis; this command does not transfer a licence | Existing issuance/consumption binds original identities. Rewriting them would change who historical receipts describe. Retained same-business corrections meet the current need without moving consumed authority or requiring a new purchase. |
| Exact expected head and signed revision decision; internal reselection after a conflict | A delayed initial/old decision could undo a withdrawal. A current state label or newly supplied command revision alone does not bind what the evidence approved. Same provenance/policy references are allowed; no extra customer document, account or person is required. |
| Required exact issuance decision revision; old synthetic producers must add it | Grant identity alone cannot distinguish which retained decision supported issuance. Guessing latest/initial revision fabricates history. Signed explicit binding admits delayed genuine history without imposing current-head equality or a new sale. |
| Current supporting heads for new association decisions; withdrawn authority delays that operation | An association could otherwise rely on withdrawn authorization. Historical issuance/consumption recording and grant withdrawal remain available; evidenced grant restoration and separately checked association operations provide recovery without permanent exclusion. |
| Existing SQL role separation and retained lineage | An application caller must not mint proof or overwrite issuance history. Existing importer/execute-only privileges and relational constraints provide that boundary; no second operator or commercial provider is added. |

Sale/provider ingestion, commercial terms, real grant-policy/source authentication,
business transfer, identity/contact records, hosted Supabase provisioning, production
migrations, custody/retention workers, continuity witness, restore unlock and
recovery approval remain outside this bounded offline work. This adds no blanket
production retention period. Non-blocking proof follow-ups remain in
[issue 107](https://github.com/canfieldjuan/connect-automate/issues/107).

Assumptions/blockers: the existing signed synthetic GRANT path is sufficient to
exercise database mechanisms; it does not settle real licensing adoption or evidence
authenticity. No new operator policy choice is needed to draft this work order.

Implementation summary for this revision: this document and its parent link only;
no source, tests, dependencies, workflow or generated schema changes. Cold diff
audit must confirm that boundary and the inventory against the pinned source.

Gap audit: **NOT DONE** as an executable slice. This proposal requires independent
exact-head oversight, connector review and CI, then Juan's explicit acceptance of
the reviewed revision before contract merge. Implementation and its verification
remain separately authorized work. All fixture evidence must stay
`OFFLINE_CONFORMANCE` with `qualification_pass=false`; all four holds remain.
