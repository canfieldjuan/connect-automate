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
- Use the parent contract revision `314b43a6a8d4860fd6ca0f17bab1427059f7dea7`
  and the full harness commit of the checkout under review. Supply a fresh UUIDv4
  `run_id`. Pin `dependency_lock_sha256` to the actual bytes of `uv.lock`.
- Set `fixtures` to a single alias/digest pair with alias `cases` and the SHA-256
  of the actual shipped `cases.json` bytes. Select case IDs in `case_ids`.
  The caller declares the harness commit. The per-case receipts also hash the
  actual executing harness source and record the Python version.
- Runnable cases cover signed replay after a lost response, revoked claims and
  denial with no dispatch. The catalog lists native cases as `NOT_RUN` and
  the outstanding issue #73 decisions as `BLOCKED`.

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
