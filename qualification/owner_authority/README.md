# Offline owner-authority harness

H1c runs selected synthetic cases through disposable issuer and host ledgers in
separate spawned processes. The shipped catalog pins the runnable case IDs,
expected codes, assertion IDs and allowed capability. The broader H1a and H1b
wire, race and crash proof stays in its focused pytest lanes.

From the repository root with the locked development environment:

```sh
uv run python -m qualification.owner_authority.controller inspect --manifest <absolute-run-json>
uv run python -m qualification.owner_authority.controller offline --manifest <absolute-run-json> --output-root <absolute-fresh-directory>
```

Use a local regular manifest file and a fresh output directory under a private,
trusted local parent outside Git worktrees. On Windows select a private parent
with an appropriate ACL. The controller creates its output directory with
mode 0700 and uses mode 0600 for evidence files. It refuses indirect paths,
hard-linked inputs, UNC/device paths on Windows and existing output roots.

Create the manifest using the existing `run.schema.json`:

- Set `version` to `owner-harness/1`, `evidence_class` to `OFFLINE_CONFORMANCE`
  and `qualification_pass` to literal false.
- Use the accepted work-order revision `92fbc04b8ec9a195932a16c7d97e738ea352c164`
  and the full harness commit of the checkout under review. Supply a fresh UUIDv4
  `run_id`. Pin `dependency_lock_sha256` to the actual bytes of `uv.lock`.
- Set `fixtures` to a single alias/digest pair with alias `cases` and the SHA-256
  of the actual shipped `cases.json` bytes. Select case IDs in `case_ids`.
  The caller declares the harness commit. The per-case receipts also hash the
  actual executing harness source and record the Python version.
- Runnable cases cover signed replay after a lost response, revoked claims and
  denial with no dispatch, malformed-consume recovery, manifest renewal, and
  recovery-evidence admission.
  Malformed recovery performs
  three explicit exchanges: a committed but lost reply, a malformed recovery
  request with zero issuer-ledger entry, then fresh authenticated recovery of
  the original receipt. It proves complete pending-binding preservation and
  derived unresolved state (`UNKNOWN`), not a stored completion column.
  A cached invocation dispatches nothing. Metadata is canonical fixture IPC;
  it does not qualify HTTP/TLS or a live endpoint. Manifest renewal deliberately
  loses a committed reply, expires only its case-local synthetic manifest, and
  proves an explicit resume dispatches nothing while it is unavailable. Two
  selected forward renewals preserve complete pending state; separate issue-time
  and expiry regressions are refused. A restarted host then explicitly resumes
  and recovers the original receipt: two exchanges, one issuer consumption and
  one local triplet. Renewal and issuer adoption have no ledger/authority effects;
  cached recovery has no dispatch. Other issue #73 cases stay
  `BLOCKED`; native cases remain `NOT_RUN`.
- The closed models and derived schemas enforce this exact work-order profile.
  Historical evidence keeps its original schema/harness bytes and pin; do not
  relabel archived packets or feed an old profile to this controller.

Inspect validates the entire selection and prints it. Offline writes the
validated run, sanitized case receipts and `hashes.json`, then publishes
`result.json` last. Check the result against `result.schema.json` and verify all
listed hashes before using the evidence. The fixture digest binds the case and
its public synthetic recipe. Retain the directory and cite aliases and hashes
when sharing evidence. A directory without `result.json` is incomplete.
The offline exit status is 0 for a run with passing assertions, 1 for a failed
assertion or code, and 2 for a controller refusal or stopped case. Per-case time is bounded
at 180 seconds within the serial 3600-second platform budget.

The native `preflight`, `run` and `collect` commands return a fixed STOP
diagnostic. Native sign-in, Hello, Gmail and live activation stay on hold.
Each run uses ephemeral test keys in the disposable processes and stores only
sanitized offline evidence. Native qualification and a later native run need
their own accepted work order.

The accepted [offline renewal work order](../../docs/contracts/LEAD-OWNER-MANIFEST-RENEWAL.md)
is being implemented in reviewed increments. Shared protocol validation and the
versioned disposable host configuration now support explicit selection and
configuration-only renewal. The pending operation retains its original signed
manifest; restart reads the installed bytes from the store. A separate explicit
resume recovers the original receipt. The issuer fixture's explicit candidate
adoption changes its in-memory configuration without changing its ledger or signers.
Fresh roots bind `offline-fixture/4` and the accepted profile above; old or wrong
profiles are refused without migration. Constructor bytes never overwrite an
existing host configuration. The `manifest-renewal` case uses these owners and
records fixed assertions from stored digests and actual exchange/consumption
counts. Real worker fault controls require exact false assertion flags and a
recorded FAIL; stopped workers do not count as assertion-sensitivity proof.
A failed recovery never triggers the cached step as an implicit retry.

The accepted [device-recovery evidence work order](../../docs/contracts/LEAD-OWNER-DEVICE-RECOVERY.md)
is implemented in separately reviewed increments. The first increment supplies
closed recovery-only values and `recovery-evidence.schema.json`, bounded canonical
parsing, the predecessor-key signature check, complete case/target digests and
case/evidence time-window checks. The caller selects the expected type before
decoding. The issuer's durable admission owner establishes the original
consumption/receipt trust and revalidates the selected case in its writer; passing
a caller-constructed case to the pure validator grants no authority.

Durable issuer admission now implements `open_recovery_case`,
`select_recovery_evidence` and `admit_recovery_evidence`. Each returns a bounded
canonical recovery value or a typed refusal; corruption and restored-store
errors remain distinct. Only usable synthetic predecessor keys can sign its
fixtures. Such a signature proves key possession and exact evidence binding, not retirement of an actual host. The
unreachable/failed-PC path stays blocked under the canonical recovery policy.
`EVIDENCE_RECORDED_ONLY` is an evidence-admission result, never replacement
admin eligibility; the `device-replacement` catalog case remains BLOCKED.
The original claim/receipt purposes and host authority writers are unchanged.
The new fixture profile refuses old roots without migration; historical packets
retain their original bytes and profile. Native sign-in, Hello, Gmail and live
activation remain on hold.

Case opening derives predecessor trust from the issuer's consumed row and the
shared stored-receipt verifier, reserves one immutable case per predecessor,
and returns the same bytes on an exact retry. Selection is derived from that
stored case. Admission validates selection, signature and windows before writes,
again in the writer after waits, and before commit. It records evidence and its
local receipt atomically in recovery-only tables; explicit retries return the
same receipt. Expired retries refuse while preserving history. Changed cases,
competing targets and reused evidence IDs cannot overwrite an admission.
`recovery_snapshot` reports owner digests and counts; the original issuer
snapshot continues to cover only claims, consumptions and journal. No host
state or original consumption row is written by these recovery APIs.
New tables require fixture version4 and fresh roots; version3 protocol-only
roots are refused without migration. Business verification, qualified old-host
retirement and replacement authorization remain separate gates.

The accepted [controller proof work order](../../docs/contracts/LEAD-OWNER-RECOVERY-CONTROLLER.md)
adds `recovery-evidence-admission`, expected `EVIDENCE_RECORDED_ONLY`. A real
synthetic bootstrap establishes the predecessor consumption; its original key
signs evidence bound to the issuer-owned case and a fresh replacement fixture.
The case opens at consumption time. After admission the issuer withholds the
reply, reopens its store with its worker-local signers, and returns the identical
admission on an explicit retry. This is a store reopen, not a process restart.
A different signed evidence ID conflicts; replay at exact evidence expiry refuses
while retaining history. No private key crosses IPC or enters the evidence packet.

Closed recovery control messages are capped at 8192 canonical bytes and enforce
the smaller nested value budgets. Complete owner-read host row digests and actual
owner-entry counters prove unchanged predecessor/replacement authority and no
bootstrap, consume, exchange, renewal, or issuer adoption dispatch during recovery.
The receipt records thirteen fixed assertions with sanitized counts and digests.
Ordinary typed domain refusals yield FAIL; corruption, malformed IPC, worker
failure and deadlines yield STOP. Real worker fault controls must yield the exact
false assertion set and FAIL; STOP is separate evidence. The existing result-last
publication and source/catalog/lock hashes apply. Storage remains version4, with
the accepted profile advanced and old profiles refused without migration.
`device-replacement` remains BLOCKED and all native/live holds remain in force.
