# Bounded action-lock lifecycle — issue #9

## Root cause and validated inventory

At baseline `8326d4ab8121ffd044372786bf5a14ecb931f574`, fifty synthetic
`ActionRunner.run` calls settle fifty actions and retain fifty native lock
files. Durable evidence alias `action-lock-lifecycle/reproduce-before.json`.
Commit `3056cc1` introduced this defect in `ActionRunner._deliver`: each
persisted action ID maps to a permanent SHA-256 pathname. Native POSIX locks
retain that pathname after release. I introduced that mapping in the intake
implementation; cleanup belongs at its lock-lifecycle owner, not in the store
or a later action sweep.

Reuse the existing native `operation_lock` and private directory preparation in
`locking.py`, shared `_deliver/_deliver_locked` entry point, and persisted
request/status reload. Existing direct-run, dispatch, recovery, stale-reader,
unsafe-replay and soft-fallback tests remain applicable. The pinned filelock
version is 3.32.7; use only its existing constructor/acquire/release interface,
compatible with the unchanged dependency range. No pre-production alternative
lifecycle has been validated. No model, prompt or live service is involved.

## Required change surface

Add an opt-in ephemeral lifecycle to `locking.operation_lock`. Its default
behavior remains unchanged for Connect lane/source and all other callers.
`ActionRunner._deliver` opts into it at the origin, retaining its current hashed
path and zero-timeout per-action acquisition. A focused new test module is added
to the existing native Windows lane; update PACK-TRIGGERS only to reference this
replacement for the deferred retention behavior.

## Protocol and observable behavior

1. Prepare the existing private action-lock directory. Use one fixed
   `.namespace.lock` there as a native gate. Never explicitly unlink that gate.
   Its acquisition waits for the metadata critical section; the gate must never
   span adapter execution, store reads/writes or waiting for a held action lock.
2. Every ephemeral participant acquires the gate **before opening** any action
   lock. Under the gate, inspect only names matching the existing lowercase
   SHA-256 `.lock` format. Try each native lock nonblocking: retain held files;
   release an idle probe and remove its pathname before releasing the gate.
   Unknown filenames are not owned and must be left alone. This also reclaims
   existing idle files and files left by an interrupted process.
3. Still under the gate, acquire the requested per-action native lock with one
   nonblocking attempt. If held, return the existing busy outcome: pending and
   no adapter invocation or terminalization. Release the gate before yielding
   to the action runner. Two distinct actions never share an action lock.
4. On every normal or exceptional body exit, reacquire the gate, release the
   action lock and remove its idle pathname, then release the gate. A failed
   cleanup must release the held descriptor, propagate the error and leave any
   orphan for the next successful gated sweep; it must not run an adapter again.
   No contender can retain an unopened/unacquired action handle across a gate
   boundary. This invariant prevents split-inode exclusion during cleanup.
5. A process exit/crash releases native ownership. Its pathname may remain until
   the next successful ephemeral entry, which reaps it. Do not infer ownership
   from PID, age, clock, row status or file existence. Cleanup never changes
   persisted actions, requests, IDs or recovery eligibility.

The resource bound concerns managed lock files: in crash-free operation, after a
successful metadata transition there is at most one gate plus one file per
currently held action. At idle after successful completion, no per-action files
remain. An interrupted participant may leave one orphan; the next successful
entry beginning after its exit reclaims it. Concurrent interruptions can leave
one orphan per interrupted participant, rather than per historical settled
action. Unsupported locking or I/O failures fail closed. Ephemeral acquisition
requires the existing hashed action filename and accepts only timeout zero;
waiting for a held action while holding the namespace gate would deadlock its
releaser. The generic lock's other timeout behavior is unchanged.

## Explicit non-scope and assumptions

No app repository/pin, adapter behavior, persisted request, stable action ID,
schema, public workflow format, license rule, adapter-idempotence policy,
dependency, package version, kit, Connect lane/source lock lifecycle or release
catalogue changes. No background janitor, time-based lease, hash bucket pool,
global delivery lock, exactly-once promise or retry of ambiguous external sends.

The private namespace is used by one protocol version. As with adopting this
library generally, stop older hosts before upgrading; do not run old ungated
callers concurrently with ephemeral cleanup. This revision has no app adoption.
Do not remove an inode with a live native owner, even if its action is terminal.

## Verification plan

- Fail first: the existing fifty-action reproduction retains files; turn it into
  a runner regression. Probe successful settlement, adapter failure, same-action
  contention, unsupported native locking and unrelated action progress.
- Real spawn-process tests pause participants before open, after acquire and
  between release and unlink. Force contenders to reach the namespace gate;
  show they cannot open an action file during cleanup, cannot overlap on one
  action and can run distinct non-idempotent actions concurrently.
- Crash/exit probes leave locks at entry, adapter execution and cleanup. The
  next entry reclaims idle leftovers without redelivering an unsafe pending
  action. Existing idle legacy files are reclaimed, live files preserved, and
  unknown files untouched.
- Boundary probes cover an empty namespace, one and many historical actions,
  invalid ephemeral timeouts, default persistent locking, same and different
  action IDs, native errors and a soft-lock fallback. Preserve existing tests.
- Causal mutants must expose retention without opting in/reaping/exit cleanup,
  the missing namespace gate, unlinking a held action and a gate spanning
  adapter delivery. Keep each observed causal failure.
- Run focused/adjacent action, event, review and locking tests with strict
  resource warnings, Ruff, wheel/source isolation and a cold diff audit. Required
  Linux CI and native Windows process tests, exact-head independent review and
  zero unresolved findings are merge gates. Do not duplicate broad CI locally.

## Implementation summary, cold diff audit and gap audit

NOT DONE: contract recorded before implementation. Source, fail-first regression,
native interleaving/crash proof, exact-head CI/review and merge remain. Issue #9
continues to block app adoption and pin changes until these gates pass.
