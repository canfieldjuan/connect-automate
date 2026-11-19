# Offline licensing register restore fence

Status: **Proposed, contract only.** This work order narrows the restore qualification
in the [licensing register contract](LEAD-OWNER-LICENSING-REGISTER.md). Independent
review and Juan's explicit acceptance of the reviewed revision are required before
contract merge. Implementation requires separate authorization. Use synthetic
records, disposable PostgreSQL and temporary test keys. Native sign-in, Hello,
Gmail, live activation and restore unlock are held.

## Root cause and existing evidence

At `eceab38ecb4bf54b596c11fdcc347e3da05c6450`, the `control` row, journal tail,
operation results and retained grant, enrollment, issuance, association and
consumption facts all live inside the same register database. An internally valid
older backup can roll them back together. `assert_history()` establishes internal
consistency and `apply()` refuses a locked or wrong-epoch request ahead of replay.
The current test calls `lock_restored()` on the original fixture database. It
starts from an already established lock and provides no evidence of restore
ordering, source writer fencing or comparison with current committed history.
The owning gap is the absence of a restore controller outside the restored state.

| Existing owner | Reuse and limit |
| --- | --- |
| `qualification/licensing_register/core.sql` | Reuse the shared `apply` control-row lock and pre-replay denial for both licensing and enrollment roles, and validate journal/projection consistency with `assert_history()`. Its local digest cannot establish freshness. |
| `qualification/licensing_register/fixture.py` | Reuse the private socket-only PostgreSQL 16 fixture, restricted clients, privileged test controller and managed teardown. `lock_restored()` remains a unit-level modeling helper. |
| `tests/test_register_postgres.py` and the grant, enrollment and association suites | Reuse real PostgreSQL, temporary proofs, independent process barriers, lost-reply checks and unchanged-domain assertions. PR 114 closes retained grant coverage gaps. |
| Existing register protocol and canonical serialization | Reuse existing opaque IDs, strict revisions, digests and canonical encoder. This work adds no licensing or enrollment command. |

## Required change surface

Add one qualification-only restore controller with a durable SQLite control store
under the fixture controller's ownership, in a location excluded from PostgreSQL
backup and restore. Reuse Python's existing SQLite support and closed typed models.
The store is independent of the register database's rollback domain within this
fixture. Joint rollback or replacement of the control store itself requires a
trusted operating baseline beyond this experiment.

The control store binds a logical register ID, source fixture identity and epoch,
one restore operation ID, a fresh target identity and epoch, and the immutable
continuity checkpoint. The checkpoint binds the source sequence, journal tail and
digest of the retained domain projection. Use strict UUID and digest types,
nonnegative sequence with the existing empty-journal sentinel, and closed phase and
result types. Use SQLite keys, checks and transactions for phase shape, unique
identity and checkpoint publication. A unique index over active restore intents
enforces one active operation per logical register. One transition owner checks
progression and exact identity binding. Read the PostgreSQL cluster identifier
from `pg_control_system().system_identifier` and database OID from `pg_database`
over the fixture's private socket. Use the pair for source and target identity.
No secrets, proof payloads or private-source copies
belong in the checkpoint. A missing control store in a resume path cannot mean
that the operation starts over.

The implementation may change the fixture helpers needed to create an isolated
target and run the controller, plus a focused integration test and the existing
PostgreSQL CI job and README. Reuse the existing SQL admission owner. Any SQL
change must serve that boundary and preserve existing command behavior on the
ordinary active fixture. No separate application-side restore check can substitute
for database enforcement.

## Restore sequence

1. **Begin.** Persist a restore intent outside the source before taking any
   restore action. The controller stops its own source-side provisioning and
   proof imports. Keep the source and its control history intact. A persisted
   intent alone is pending. Acknowledge fencing only after the PostgreSQL
   fence and independent checkpoint have committed.
2. **Fence and capture.** After verifying the source identity and epoch, durably
   set its locked state under the same control-row lock used by `apply`. Validate
   retained history while that fence is held and capture the checkpoint only for
   a valid history. A validation failure must leave the source locked and the
   checkpoint unpublished. If the source lock cannot be established, halt before
   target import. An in-flight writer
   can commit before the fence or roll back. Include all commits ordered before the
   fence. Requests ordered after it refuse, including replays with valid credentials.
   A reply already committed before the fence may arrive later and remains a
   historical result. Persist the checkpoint outside the source only after the
   fence commits. After an interruption, resume from the same intent and verify
   the expected source's committed lock before capturing or confirming a checkpoint.
   If the source or checkpoint state cannot be established, leave the operation
   pending or stopped. Never derive a replacement checkpoint from the restore.
3. **Restore in quarantine.** Use PostgreSQL 16 dump and restore tooling on an
   actual fixture-generated logical backup. Restore only into a fresh private
   target created by the controller. Bind the generated archive digest to its
   source identity and epoch in controller-owned metadata when taking the backup.
   Verify that binding before import, and check the restored source epoch before
   rotating it. Create the target with
   [`ALLOW_CONNECTIONS false`](https://www.postgresql.org/docs/16/sql-createdatabase.html)
   so a crash immediately after creation cannot expose the default `PUBLIC`
   access. From the maintenance database, revoke `CONNECT` from `PUBLIC` and
   withhold it from all scoped roles. Grant access only to the fixture roles
   needed for import and verification. Verify the target's identity and
   `pg_database.datacl`, including effective scoped-role access, and check
   `pg_stat_activity` for no target sessions before enabling connections for
   import. A target left unbound by a crash stays closed.

   [Restore into the precreated database](https://www.postgresql.org/docs/16/app-pgrestore.html)
   with archive ownership and object grants preserved. Use a non-superuser
   fixture login with membership in the source object owner role and the
   target privileges needed to restore its objects. Keep database creation and
   connection grants under the controller's ownership outside the import.
   Before opening scoped connections for denial tests, compare source and target
   schema, relation and function ACLs (`nspacl`, `relacl`, `proacl`) and owners
   (`nspowner`, `relowner`, `proowner`) by object identity and role name.
   Use PostgreSQL's `aclexplode` and `acldefault` to compare normalized grants,
   including grantor, grantee, privilege and grant option. An explicit owner-only
   ACL and its equivalent catalog default can represent the same privileges.
   Verify the restored `apply` still runs as the source's restricted owner.
   Keep scoped `CONNECT` withheld until the new epoch and locked state commit
   and these checks pass. Preserve the locked source in its original location.
4. **Compare while locked.** Validate the target's retained history and identity
   against the source binding in the independent restore record. Compare sequence,
   journal tail and retained domain projection without comparing the deliberately
   rotated epoch and lock state as business history. The comparison records a
   closed diagnostic result: consistent with the captured checkpoint, history
   mismatch, or unavailable/unverifiable. A consistent result leaves writes and
   affirmative replays denied. An older valid prefix with lost withdrawals or
   consumption is a mismatch. No reconstruction from a caller receipt or automatic
   empty-store bootstrap is permitted.

A retry must revalidate the operation, source/target binding and actual committed
barriers. It can finish an interrupted fence or report a previously verified result.
It cannot regress the phase, replace the checkpoint, renew the old epoch or publish
a writable target. A partially loaded target stays quarantined. If a clean retry
needs a new target, retain the abandoned one in quarantine and bind its replacement
explicitly to the same source checkpoint. No destructive cleanup is needed.

## Verification for separately authorized implementation

| Proof | Required observations |
| --- | --- |
| Fail first and positive control | With the fixture's current local history check, an honest earlier snapshot validates internally despite a later committed withdrawal or consumption. An unfenced active fixture remains usable for normal commands and exact replay. |
| Real backup and continuity | Restore an older genuine dump after those later commits. Independently captured sequence/tail/projection reject history loss. Restore a current genuine dump and report parity while locked. Include a same-sequence digest mismatch and an altered/non-head retained decision. Preserve source and target domain snapshots on denied attempts. |
| Source ordering | Exercise licensing and enrollment through scoped clients and direct SQL. Independent processes and deterministic barriers cover both orders of a write or replay racing the fence. Show the last pre-fence commit is captured and later operations generate no new successful result. |
| Target quarantine | Probe actual connections with valid scoped credentials at creation, during import and before lock commit. After lock and ownership/ACL parity are verified, open controlled scoped connections and require `apply` to raise `REGISTER_LOCKED` for fresh writes and exact replays at both epochs. A connection, schema or function privilege error fails the post-lock test. Show the same roles reach `apply` successfully on the active source before fencing. |
| Crash and retry | Interrupt before the SQL fence commits, after it commits but before checkpoint publication, after target creation but before the `CONNECT` revoke, during import and after target lock commit. Resume the same operation using a fresh controller process. Neither ambiguity nor a lost reply opens the target or clears the source fence. |
| Witness and role boundaries | Missing, unreadable, wrong-register or stale-operation control records cannot produce a satisfactory result. Wrong identity/epoch, another fixture's genuine archive, an altered archive and mixed or missing checkpoint fields fail. Probe direct scoped-role writes to fence state and compare protected results with valid controls. |
| Isolation and regressions | Restore only controller-owned synthetic backups and prove that import cannot reach the external store. Use real PostgreSQL transport and transactions, not mocked admission. Preserve existing command/epoch/replay tests and exercise removal of each new fence or comparison protection against its named regression. |

## Restrictions, assumptions and exit

| Constraint and cost | Concrete need and why a lighter rule fails |
| --- | --- |
| Restore pauses both scoped write lanes | The register and enrollment writers share authority and the journal. A lock around only one lane or around a client wrapper permits the other lane or direct SQL to change the captured source. A brief source transaction establishes the boundary without adding a new approval role. |
| Independent checkpoint and target quarantine | A restore needs controller storage and an isolated target. A same-backup marker misses rollback. A post-creation revoke alone leaves a crash window before revocation. Preserve object ownership and grants so the real register boundary remains testable. |
| One active restore per register | A second restore must resume the active operation or wait for its resolution. Concurrent operations could give the same fenced source competing checkpoints and target identities. A retry under the existing operation ID and a SQLite unique index cover this fixture without adding a separate coordinator. |
| Locked diagnostic exit | The fixture can test register continuity. It has no independent private evidence and deletion-tombstone reconciliation or proven production authority handoff. Publishing a writable target based on matching register hashes would bypass those prerequisites. |

The fixture assumes the privileged controller and its external storage are outside
the restored payload and trusted by the test. Real custody, independent witness
operation, reconciliation of private evidence/deletion tombstones, provider or
hosted deployment, live migrations, service rollout and an unlock protocol are
separate work. The test's checkpoint may establish parity only for this synthetic
register and epoch. No new customer requirement, retention period or second
operator is introduced. Evidence stays `OFFLINE_CONFORMANCE`, with
`qualification_pass=false`.

Implementation summary: this proposed work order and its parent link. Cold diff
audit verifies the inventory and the documentation-only scope. No executable tests
are required for the prose diff. Gap audit: **NOT DONE** for implementation,
independent exact-revision review, CI and Juan's acceptance.
