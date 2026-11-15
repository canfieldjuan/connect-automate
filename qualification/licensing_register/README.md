# Offline PostgreSQL register core

Implements the bounded synthetic grant → issuance → association → original
consumption path of `LEAD-OWNER-LICENSING-REGISTER.md`, accepted at
`0981a88f3d8eb2d081ed2b2c2cb8d50157c819ce`. Evidence is always
`OFFLINE_CONFORMANCE`, with `qualification_pass=false`. No output grants
recovery, host, customer or production authority.

Run with PostgreSQL 16 binaries installed:

```sh
uv sync --locked --all-groups
RUN_REGISTER_POSTGRES=1 uv run --group register pytest tests/test_register_postgres.py tests/test_register_protocol.py tests/test_register_enrollment_change.py
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

Not implemented: sale/provider ingestion, commercial/association corrections,
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
revision envelope is still to implement. Journal snapshots retain revisions here;
production revision tables, event timestamps/reasons and compact audit references
are still to implement. The fixture journal contains only closed opaque synthetic
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
