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
- Use the accepted work-order revision `ba7f7cf7db9b14c050d87021fddd7333ff149851`
  and the full harness commit of the checkout under review. Supply a fresh UUIDv4
  `run_id`. Pin `dependency_lock_sha256` to the actual bytes of `uv.lock`.
- Set `fixtures` to a single alias/digest pair with alias `cases` and the SHA-256
  of the actual shipped `cases.json` bytes. Select case IDs in `case_ids`.
  The caller declares the harness commit. The per-case receipts also hash the
  actual executing harness source and record the Python version.
- Runnable cases cover signed replay after a lost response, revoked claims and
  denial with no dispatch, and malformed-consume recovery. The latter performs
  three explicit exchanges: a committed but lost reply, a malformed recovery
  request with zero issuer-ledger entry, then fresh authenticated recovery of
  the original receipt. It proves complete pending-binding preservation and
  derived unresolved state (`UNKNOWN`), not a stored completion column.
  A cached invocation dispatches nothing. Metadata is canonical fixture IPC;
  it does not qualify HTTP/TLS or a live endpoint. Other issue #73 cases stay
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
assertion or code, and 2 for a refusal or stopped case. Per-case time is bounded
at 180 seconds within the serial 3600-second platform budget.

The native `preflight`, `run` and `collect` commands return a fixed STOP
diagnostic. Native sign-in, Hello, Gmail and live activation stay on hold.
Each run uses ephemeral test keys in the disposable processes and stores only
sanitized offline evidence. Native qualification and a later native run need
their own accepted work order.

The accepted [offline renewal work order](../../docs/contracts/LEAD-OWNER-MANIFEST-RENEWAL.md)
is being implemented in reviewed increments. The protocol increment supplies
the shared signed-manifest renewal validator, typed active-manifest availability
and closed selection value. Durable host configuration, selected publication,
writer/crash proof and controller adoption remain pending. These protocol APIs
do not renew storage or resume a pending operation. The `manifest-renewal` case
remains blocked, and the runnable packet profile above is unchanged until adoption.
