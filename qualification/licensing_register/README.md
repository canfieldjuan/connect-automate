# Offline PostgreSQL register core

Implements the bounded synthetic grant → issuance → association → original
consumption path of `LEAD-OWNER-LICENSING-REGISTER.md`, accepted at
`0981a88f3d8eb2d081ed2b2c2cb8d50157c819ce`. Evidence is always
`OFFLINE_CONFORMANCE`, with `qualification_pass=false`. No output grants
recovery, host, customer or production authority.

Run with PostgreSQL 16 binaries installed:

```sh
uv sync --locked --all-groups
RUN_REGISTER_POSTGRES=1 uv run --group register pytest tests/test_register_postgres.py tests/test_register_protocol.py tests/test_register_enrollment_change.py tests/test_register_association_correction.py tests/test_register_grant_revisions.py
```

The tests create a fresh private cluster under pytest's managed base temp, with a private Unix
socket, SCRAM login passwords and no TCP listener. `REGISTER_PG_BIN` may point to
an absolute installed PostgreSQL binary directory. No ambient DSN is accepted.
Only its own cluster is stopped; the fixture issues no database drops or directory
deletions. Pytest owns directory cleanup under its configured retention policy
(the default keeps the last three runs). The socket sits directly below a short
cluster directory under that base, without long per-test names. Retained directories
are owner-only and contain temporary test passwords, never real credentials.
Durable review evidence is stored separately, outside pytest's disposable storage.

`Register` is a privileged test controller: it creates databases and imports
closed synthetic statements signed by an in-memory Ed25519 authority created for
that database. These signatures prove only fixture provenance, not human identity,
real entitlement issuance or real host retirement. The statement can describe a
synthetic issuance/receipt digest; it is not a production envelope adapter.

`Client` has only a scoped database login and no proof-import/signing capability.
The database derives actor and organization from `session_user`, not a caller
field or `SET ROLE`. Application roles receive EXECUTE on the command function,
not table access. The function has a fixed search path and a non-login owner.
The isolated cluster has no Data API, service-role credentials or hosted project.
This proves local PostgreSQL privileges only, not Supabase deployment settings.

The control row serializes a short transaction. It checks current heads and
`clock_timestamp()` after waits, then commits domain rows, projection snapshot,
journal chain and operation result atomically. Exact retry recovers the historic
result, labelled REPLAY; it is not a new current-authority decision. Application
withdrawals preserve consumption and old journal snapshots. Required-source
expiry is checked using the database clock; no source-object deletion worker is
implemented here.

Full retained projection snapshots make corruption probes explicit in this small
offline fixture. This is intentionally not a scalable production journal design.
Snapshots include referenced proof contents and signatures, so modifying imported
evidence after use is corruption. The unreferenced proof inbox is fixture-owned.
A complete jointly rolled-back snapshot cannot be detected by its own hash chain:
supported restore must impose the external lock. `lock_restored()` models that
interlock; there is no unlock command or claim of production continuity.

Not implemented: sale/provider ingestion, sale corrections,
business transfers, real enrollment verification/registration ceremony, source custody or
retention deletion, production authentication, deployment, continuity witness,
restore unlock, recovery approval or publication. Existing offline issuer and
recovery fixtures are unchanged. Later integration must preserve their parity.
Native sign-in, Hello, Gmail and live activation remain on hold.

## Contract coverage and porting boundary

This is a bounded mechanism implementation, not the complete logical record or
service command schema in the accepted contract. Its separate `offline-register/1`
version must not be accepted by a production licensing service. Fixture database
identity plus a fresh epoch isolates each run; the production register ID/schema
revision envelope is still to implement. Enrollment, association and synthetic grant
relations retain their revisions; sale history and real commercial adapters remain
unimplemented.
The full production schema, event timestamps and compact audit references remain
unimplemented. The fixture journal contains only closed opaque synthetic
command fields, never human notes or identity text.
Each fixture actor is bound to one organization; a real licensing operator's
multi-business authorization model is a separate porting requirement.

The imported enrollment proof asserts a synthetic completed decision. It does not
implement the contract's method/source branches, canonical registration ceremony,
external source currentness or private-store coordination. Nullable source expiry
models only whether the fixture has a time-limited required source. Similarly,
issuance and consumption statements are trusted fixture attestations; their real
envelope/receipt verification adapters and full provenance records remain future
work. This lane proves the database mechanisms below those adapters and grants no
permission to bypass them. No existing issuer or host algorithm is ported or replaced.

## Register-side enrollment changes

Implements the bounded register ordering work order accepted at
`8c4a883af29f340cd2df5322f5cdbe451498ba8a`. `begin_change` publishes a non-current
revision before a synthetic evidence change; `finish_change` requires the exact
pending revision/change plus a candidate decision and bound completion proof.
The canonical candidate digest is computed at the existing verified Python import
boundary; SQL compares that trusted digest, without a second JSON canonicalizer.
Private revision/digest remain signed fixture assertions, not independently verified
store facts. Tests produce completion facts only after begin commits.

Enrollment heads select retained revisions through relational constraints. An
enrollment-specific state enum and CHECK branches prohibit completed decision fields
on non-current revisions. Change IDs are register-wide primary keys; associations
reference the exact retained enrollment revision. Initial enrollment, begin, finish
and withdrawal share one SQL transition owner. Existing `withdraw_enrollment` uses
its operation ID as its internal change ID, and cannot leave an old finish eligible.
Replay returns historical evidence and never restores a withdrawn head. A fresh,
evidenced begin/finish can restore currentness from any non-current state.

The fixture has no deployed migration, real private-store adapter, cleanup worker,
source-currentness proof, new identity method or recovery permission. The existing
restore lock remains closed. Tests reuse the PostgreSQL process barriers and managed
temporary retention, and keep review evidence outside that disposable storage.

## Register-side association correction

Implements the offline work order at `87755f367a5d3f3c8d39f79b03623faa3b82803c`.
`correct_association` takes an exact expected head and an imported, signed synthetic
`ASSOCIATION_CORRECTION` proof binding that head, the original entitlement and exact
grant/enrollment revisions. A current supporting grant and enrollment, checked
after lock waits, are required to publish a new current decision. This checks
fixture facts; it does not authenticate a person or real sale/issuance/receipt.

Creation, correction and withdrawal share one SQL transition owner. The head retains
the original association identity and points to a retained revision; a separate
constant original-revision FK preserves its initial decision. Each revision's
decision-revision FK targets a `CURRENT` decision using a constrained constant
target-state column. Current rows reference themselves; withdrawals reference their
last current decision and carry no current proof or supporting fields. These are
relational guarantees, not a second mutable decision projection.

A correction can restore a withdrawn association, keep the same supporting facts
and verification reference, or select another current enrollment of the same
business. Original entitlement/organization and consumption stay fixed. Withdrawal
does not require current support; consumption attachment remains historical evidence
and can follow correction or withdrawal. Grant retention is covered below; real
adapters remain unimplemented. No fixture result is recovery or host authority.


## Register-side grant revisions and issuance history

Implements the offline work order accepted at
`86e67bc02a8a173fd06ff952598cf23b4ea2c73a`. `revise_grant` requires an exact expected
head and a distinct signed synthetic `GRANT_REVISION` proof bound to that head,
grant and organization. It can correct a current decision or restore a withdrawn
grant while retaining the same provenance reference and policy revision. Initial
grant creation, revision and withdrawal share one SQL transition owner.

Grant heads select retained revisions. State/reason CHECK branches and scoped
decision-state FKs retain the original and prior decisions without presenting a
withdrawal as current authority. Snapshot history covers all retained grant proofs.
Both issuance and association references use a constrained `CURRENT` target-state
FK, so a withdrawal revision cannot serve as their grant decision.

Every synthetic issuance producer now supplies a required `grant_revision`; old
proofs without it fail closed, with no inferred initial/latest revision. An attested
issuance can be recorded against an older retained decision after correction or
withdrawal. This does not issue a licence or qualify actual issuer chronology.
New association decisions still check current grant/enrollment heads, but can use a
newer grant decision than the original issuance. Issuance and consumed bindings
remain immutable; grant restoration does not mutate a withdrawn association.

The unchanged fixture version strings describe disposable offline inputs only.
Fresh databases are required for this changed fixture schema; no deployed database
conversion or production API compatibility is claimed. Sale/provider policy,
real grant provenance and all four live/identity holds remain outside this work.
