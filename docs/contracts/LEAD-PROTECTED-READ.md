# Protected host: one authorized source-content read

Status: PROPOSED contract and feasibility inventory. Documentation only; no
implementation acceptance, installed service, native-authentication qualification
or employee-facing access is claimed. This follows the private policy evaluator;
it does not reopen the accepted [application policy](LEAD-SOURCE-HANDOFF.md#decision-c-local-admin-and-user-roles-with-delegated-background-authority).

## Contract

### Problem, owner and bounded outcome

Employee applications must not turn a receipt identifier, a claimed employee ID
or an eligible policy result into access to protected source bytes. The next
vertical outcome is a real native employee signing in to a protected local host,
then reading one assigned admission through `source.content.read`. The host owns
identity, enrollment, sessions and assignments. Lead Intake remains the sole
owner of source custody, lifecycle, clocks and SQL. The policy evaluator remains
the sole owner of its closed eligibility catalog.

This document proposes that boundary and its proof obligations. Unresolved native
security facts below block an executable integration work order. Do not fill the
gaps with synthetic identities and call the result a protected read path.

### Pinned implementation and proof inventory

All repository citations in this document are relative to
`canfieldjuan/connect-automate` at
`ede79c022826ebc3ee650ab30a850c31a0a1473b`.
CONFIRMED means inspected source unless a row explicitly identifies a run.

| Status | Source / proof owner | Reuse and demonstrated limit |
| --- | --- | --- |
| CONFIRMED | `src/connect_automate/lead_intake/_host_policy.py:97-158` | Validates supplied facts and checks current/observed authority and assignment versions. No native identity acquisition or effect execution. Reuse unchanged. |
| CONFIRMED | `src/connect_automate/lead_intake/content.py:58-98` | A read records the clock and may commit expiry deletion. It takes no employee principal. Authorizing only byte return leaves writes unprotected. |
| CONFIRMED | `src/connect_automate/lead_intake/source_store.py:383-428` | Source-owned writer acquisition can wait before yielding; source commit occurs after the yielded operation. A pre-call authorization check is insufficient. |
| CONFIRMED | `src/connect_automate/locking.py:47-69`, `:111-139` | Existing private native file-lock machinery is available. It does not establish a transaction across authorization and custody stores. |
| CONFIRMED | `src/connect_automate/connect_windows.py:208-240`, `:388-455` | Current-process identity and protected-path helpers can support service-owned storage. Current service SID is not the named-pipe client's identity. |
| CONFIRMED | `tests/test_lead_source_content.py:69-111` | Existing fixtures distinguish expiry from signing-key revocation: removing a source grant does not revoke historical host content access. Preserve that behavior; employee revocation is a different authority. Tests inspected, not rerun here. |
| CONFIRMED | `tests/test_lead_host_policy.py`, `tests/test_automate_host.py`, `tests/test_windows_connect.py`, `tests/test_locking.py` | Existing policy, license, path and lock fixtures are regression inputs. Their presence is not proof of native employee authentication. |

There is no validated end-to-end employee sign-in/read harness in this inventory.
No model, prompt, inference setting or production authentication experiment is
being ported. The existing policy and source behavior are the parity reference.
Proposed departures are limited to native identity acquisition, protected host
state and the source-owned authorization seam needed for this single read. Each
requires new behavioral evidence; none may alter source signatures, retention,
contact identity, runtime actions or EOM operations.

### Platform feasibility: evidence versus proposal

CONFIRMED by a local Linux experiment: a child process sent a misleading identity
field through an unnamed Unix socket pair. Kernel ancillary credentials identified
the actual sending process/account, and the kernel rejected a forged credential
message. Connection-time credentials differed from the later child sender. The
probe used no real messages, credentials, installed listener or account changes.

Durable evidence aliases and SHA-256:

- `linux-credential-probe.py`:
  `9c50cf68c94856e442e2a6b1e698cac79bbe7b82f27232b7e2622d1ff518b693`
- `linux-credential-result.json`:
  `5ecf067de3fc283471bfd31948ce9f59388ca6f1781d423a92f185b2ca327ef8`

The packet lives outside worktrees under the operator's durable evidence root,
`connect-automate/protected-host-read-contract`. This is a same-account transport
primitive proof, not separate-account isolation, employee sign-in, lock-state
trustworthiness or Windows evidence. Reuse the probe in native qualification;
do not replace it with mocked credential fields.

Primary platform references (documentation evidence, not runtime qualification):

- Linux [Unix sockets](https://man7.org/linux/man-pages/man7/unix.7.html)
  distinguish connection-time peer credentials from message credentials.
  INFERRED recommendation: authenticate each bounded request using kernel
  credentials; reject absent/truncated ancillary data and sender changes. A
  client-supplied PID or UID is never authoritative.
- [Linux-PAM authentication](https://www.man7.org/linux/man-pages/man3/pam_authenticate.3.html)
  supplies an authentication operation and authenticated account result.
  UNKNOWN: an approved local PAM stack, account checks and protected conversation
  suitable for this application on the target distribution. Library presence is
  insufficient. Do not persist passwords or introduce remote authentication.
- [systemd login sessions](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html)
  expose a `LockedHint` set through `SetLockedHint`. UNKNOWN: a trustworthy lock
  boundary on the supported desktop. This hint alone is not accepted proof that
  employee processes cannot defeat locked-session denial. A native adversarial
  test and a defined supported desktop are prerequisites, not optional hardening.
- Windows [pipe-client impersonation](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient)
  uses the last message's client context; failure leaves the service context in
  place. INFERRED recommendation: local-only named pipes with explicit ACLs,
  per-request verified client tokens, and fail-closed impersonation/reversion.
  Never substitute the service token or trust an account name in the request.
- Windows [session state](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/ns-wtsapi32-wtsinfoex_level1_w)
  distinguishes locked, unlocked and unknown. UNKNOWN: complete native sign-in,
  token-to-interactive-session binding and lock behavior on supported Windows.
  No Windows runtime was exercised in this slice. Unknown state must deny.

INFERRED design direction: a protected OS service with platform-native local IPC
and native sign-in. Transport identity, fresh sign-in and current interactive
session state are separate checks. No loopback bearer-token substitute. Before
implementation, specify and prove the complete sign-in mechanism on both target
platforms, including account disablement, account identity reuse, inherited or
transferred handles, process exit/PID reuse, and shared-account rejection. This
document does not select an untested Windows sign-in API or pretend the Linux
lock-state question is settled.

### Host state and application interface requirements

PROPOSED requirements for the subsequent executable work order:

- Install under a dedicated service principal. Existing path checks run as that
  principal. Ordinary employees cannot read, replace, restore or impersonate its
  authority, source stores or keystore. Encryption remains a separate accepted
  deployment obligation. Never fall back to the employee's writable directory.
- Bootstrap the first admin only through verified deployment-owner control.
  Missing/corrupt authority fails closed; restarting cannot self-enroll a caller.
  Native account identity maps to a host-owned employee UUID and immutable
  organization. Account deletion/recreation must not inherit an old enrollment.
- Host-owned enrollment, role and record grants are durable and versioned.
  The exact record for this operation is the source `admission_id`; knowing it
  grants nothing. Admin reads also need assignment. Host methods own these facts;
  neither UI nor source-library code reads another owner's tables.
- Host sessions are short-lived, tied to verified native identity, interactive
  session and local channel. Logout, disablement, role/grant changes, expiry,
  lock and restart invalidate further use. A copied session handle or policy
  result is not authorization. Session lifetime, native proof exchange and
  bootstrap/admin mutation protocols must be pinned before executable acceptance;
  they are unresolved here, not permissive defaults.
- The read request carries a closed versioned operation, request correlation and
  admission identity. It carries no authoritative actor, role, organization,
  assignment or policy result. The host derives these and reevaluates policy.
  Wrong scope, malformed/unknown operations and mixed fields fail closed.
- Success releases the existing source envelope only to the authenticated channel.
  A denial is fixed and does not disclose record existence. Authorized expired or
  unavailable content has an explicit unavailable result; no invented empty body.
  No raw body, password, token or confidential narrative enters logs or audits.
  Minimal audits record host-owned actor, operation, authority/grant versions and
  outcome under the accepted metadata retention owner; no second business store.

### Transaction and revocation ordering

INFERRED proposed serialization protocol, requiring proof before adoption:

#### Canonical host gate requirements

This section owns ordering, mode, lifetime and fairness for the proposed host
gate; future effect contracts link here rather than restating a separate rule.

- **Order:** every operation needing both the source writer and the host authority
  gate acquires the source writer first, then the gate. Never acquire a source
  writer while holding the gate. Future purge, retirement and clock-reconciliation
  contracts inherit this order; no such effects are authorized here.
- **Mode and lifetime:** the proposed initial gate is exclusive across protected
  host operations. A read holds it through source commit, the entire response
  stream and bounded cancellation cleanup. This deliberately serializes protected
  reads host-wide; an active slow stream delays unrelated reads and revocation.
  Shared-reader concurrency is not silently implied by the word gate.
- **Fairness:** once authenticated revocation is queued, no read waiting for the
  gate or arriving later may acquire it ahead of that revocation. Revocations
  retain FIFO order among themselves. A primitive lock with unspecified wake-up
  order is insufficient; the host must enforce and test this admission rule
  across processes, including cancellation, owner death and queue recovery.
- **Bounds:** stop admitting reads to the gate when revocation queues. If `N`
  reads already hold it, their streaming-drain contribution is at most
  `N * (whole-response deadline + cancellation cleanup bound)`. The exclusive
  mode permits only its current holder. New read arrivals cannot extend this
  drain. This is not a complete acknowledged-revocation bound: remaining source
  transaction/commit work, earlier queued revocations, scheduling and revocation
  persistence also require explicit bounds or classified failure. Pin the finite
  queue/capacity and deadline behavior before executable acceptance. Restarting
  a per-chunk timeout indefinitely does not bound a whole response.

#### Read and revocation sequence

1. Authenticate the request and perform cheap host preflight. Do not pass a cached
   eligible result as a capability. Acquire the existing source writer through
   its owner without holding the host authorization gate during the busy wait.
2. After source writer acquisition, acquire the host's cross-process authority
   gate. Reload enrollment, session, role and exact assignment; verify native
   caller/session state and rerun the existing policy evaluator. No content fetch,
   clock recording or expiry deletion may precede this checkpoint.
3. The source owner performs its existing custody/lifecycle/clock checks and any
   expiry writes. Check authority, session expiry and native state again before
   source commit. On denial, roll back this operation's pending writes. Source
   commit failure or uncertainty releases no bytes and uses existing recovery.
4. Apply the [canonical gate lifetime](#canonical-host-gate-requirements).
   Perform a final native/session check before release of bytes and recheck before each response
   chunk; stop on expiry, lock, disconnect or failure. No success framing for a
   partial transfer. Bytes already released cannot be retracted; do not promise
   this or universal atomic read/delivery. Source lifecycle checks retain their current serialization.
5. Host revocation acquires that same authority gate, commits its version change
   and invalidates sessions before acknowledging completion. It never acquires a
   source writer while holding the gate. If revocation wins, the waiting read
   denies before source effects. If the read wins, its bounded authorized work
   precedes acknowledged revocation. Native OS state can change independently:
   prove the adapter's observation/linearization contract rather than equating a
   host gate with control of OS locking.

The guarded operation must be source-owned; do not reach into source SQL from a
transport wrapper or create an alternate reader. Preserve the trusted-host library
API and existing tests, but never expose that unguarded API through the service.
The source guard must encompass commit and be held by the host until release;
a callback invoked only before `read_content` cannot meet this contract.

UNKNOWN/blocking: trustworthy native lock observation at these checkpoints,
crash-safe host authority persistence and a guard implementation satisfying the
[canonical gate requirements](#canonical-host-gate-requirements), including its
mode, priority, queue recovery and full latency accounting. The deadline and
cleanup values remain unqualified. These require a focused executable work order
after native feasibility. No cross-store atomic transaction is claimed. A valid
expiry commit followed by a channel failure may remain committed; denial before
commit must roll back. Retrying a read never revives purged content.

### Proof sequence and acceptance gates

Every stage is required; later stages cannot substitute for an earlier failure.

| Stage | Reproducible proof required | Gate |
| --- | --- | --- |
| Native feasibility | Actual separate service/employee identities on Linux and Windows; successful native sign-in, failed/forged/disabled identity, locked/unknown session denial, ordinary-user direct-file denial; protected bootstrap and keystore failure | Prerequisite to executable integration acceptance / G0,G6 |
| Authority and policy binding | Real sign-in issues a scoped session; host reloads role and assignment; wrong host/org, unassigned admin/user, copied results/handles and machine identities deny; authorized assigned read succeeds | G2,G6 |
| Source enforcement | Existing source tests unchanged; no unauthorized clock/expiry mutation; valid expiry still purges; signing-key revocation remains distinct from employee revocation | G2,G6 |
| Concurrency and recovery | Separate processes exercise both revocation orders, busy writer, continuous arriving reads with queued revocation, gate owner death and queue recovery, session expiry during wait/send, lock/unlock, disconnect, process death, restart and commit uncertainty; assert bytes and stored state independently | G3,G6 |
| Release qualification | Required native Windows/Linux lanes from first executable push; exact revision, real fixtures, recorded failures and results, secure installation/retention evidence | G6; no automatic adoption |

Negative cases isolate one guard at a time. Include missing/mixed fields,
empty/null/false/zero, version boundaries, truncated framing/credentials and
large valid content. Tests must exercise the true owner and process boundary;
mock adapters supplement rather than establish native qualification. Reuse the
policy/source/path/lock fixtures; preserve the unchanged-library parity lane.

## Implementation summary and cold audit

This slice adds this proposed contract and a continuation pointer in the prior
work order. Its only executable evidence is the isolated Linux primitive probe
outside the repository. No application source, test, dependency, schema, workflow,
installer or production configuration changes. Validate pinned citations and
`git diff --check`; do not rerun broad application suites for documentation.

No new scheduler, mailbox poller, CRM, extraction, destination adapter, EOM
operation, source retention policy, privileged admin endpoint or production
activation is in scope. The eventual bootstrap and grant-administration mechanism
must be reviewed as a necessary dependency, not smuggled in as test scaffolding.
Rollback of this document is a documentation revert. A future runtime rollback
must stop employee access and preserve protected state, never restore direct SQL.

## Gap audit and next decision

DONE in this slice: source-owner inventory and bounded Linux credential evidence.
NOT DONE: native sign-in/lock proof, Windows feasibility, protected installation,
bootstrap/session/admin protocols, host state implementation, source enforcement,
review/acceptance and G6/adoption. These are explicit blockers to publishing an
employee read endpoint.

The next work order should first close the native platform feasibility blockers
using isolated native test accounts and real OS mechanisms, then pin the bounded
integrated read implementation. Operator acceptance of this document does not
waive those blockers or authorize changing the accepted locked-session policy.
