# Lead source authentication and organization scope

Status: PROPOSED. Contract-only; not accepted and not implementation authorization.
The next implementation, if separately authorized, is a library verifier with
synthetic fixtures. No enrollment service, receiver, persistence or application
adoption is authorized by this document. The source handoff gate remains open.

## Root cause and verified reuse inventory

CONFIRMED: the source parser validates structure and signature encoding, but
returns an explicitly untrusted model. Treating that return as permission to
read a receipt or create an intake would skip the missing authorization owner.
There is no deployed failure being repaired here; this is a prerequisite for
the proposed intake boundary.

Evidence pins below describe source presence, not runtime qualification:

| Alias | Repository | Inspected revision |
| --- | --- | --- |
| CA | `canfieldjuan/connect-automate` | `69e8a278695ae7ec78c58e0bc54370cd41c9842b` |
| EW | `canfieldjuan/eom-email-watcher` | `9fc701e157cad3de91a2207dca02551a21937bb0` |
| EP | `canfieldjuan/eom-connect-provider` | `93a73e6844eb5005a13669395a438b50cf1aa5c5` |

Paths are relative to each pinned repository. All rows marked CONFIRMED were
read from source; test inspection is not test execution.

| Finding | Evidence | Reuse decision |
| --- | --- | --- |
| CONFIRMED: shared canonical encoding and payload digest exclude authorization | CA `src/connect_automate/lead_intake/source.py:206-269` | Keep this owner and existing vectors; do not invent another JSON encoding |
| CONFIRMED: common Ed25519 verification accepts a caller-provided key map | CA `src/connect_automate/entitlement.py:402-418`; existing caller `src/connect_automate/automate/pack.py:121-139` | Reuse `verify_signature`; supply a separate source-authority key map, never entitlement or publisher keys |
| CONFIRMED: discovery and submission use registration bearer tokens, with process/app matching and artifact hash checks | CA `src/connect_automate/connect.py:103-134`, `1029-1054`, `2028-2059` | Keep transport and artifact validation; these paths do not establish an organization/mailbox grant |
| CONFIRMED: Watcher selection snapshots omit tokens and endpoints | EW `src/eom_email_watcher/connect_selection.py:9-24` | Keep capability selection separate from source authority |
| CONFIRMED: Watcher's paired-deployment tests check service definitions and executable identity | EW `tests/test_paired_deployment.py:14-41`, `78-91` | This is installation qualification, not sender-key enrollment |
| CONFIRMED: provider proofs bind a context, device, request target, body digest and timestamp | EP `src/eom_connect_provider/proof.py:27-59`, `79-92` | Preserve domain separation and exact target/content binding as a pattern; do not import the EOM HTTP proof format |
| CONFIRMED: provider enrollment uses tracker admin endpoints, an office bearer and a generated key signing a challenge | EP `src/eom_connect_provider/enrollment.py:24-25`, `45-77` | Reference only; not generic Lead Intake enrollment |
| CONFIRMED: provider stores raw private-key bytes without encryption; Windows publication delegates to Connect | EP `src/eom_connect_provider/store.py:70-105`, `107-116` | Do not claim encrypted storage or copy this store as the generic secret owner |
| CONFIRMED: Windows private storage primitives already exist | CA `src/connect_automate/connect_windows.py:388-468`, `539-563` | Candidate infrastructure for a later storage slice; this contract does not qualify storage |

INFERRED: no reusable business-source enrollment was found in these inspected
boundaries. Searching EW source for `Ed25519`, `organization_id`, `host_id` and
`public_key` found no matches. This is a bounded search, not proof about every
repository, branch or deployed installation.

UNKNOWN: deployed key custody, employee authentication, deployment organization
configuration and retention-policy enrollment. No live credentials, mail,
customer records or databases were inspected. No production pairing is claimed.

Existing parser vectors in CA `tests/fixtures/lead_source/vectors.json` and its
named ASCII, Unicode, control-character, maximum-body and unavailable-body
fixtures are the compatibility baseline. Existing crypto caller tests include
CA `tests/test_entitlement.py:111-115` and `tests/test_automate_pack.py:108-138`;
they cover changed payloads and untrusted/unknown keys in their own domains,
not source authorization. They were inspected, not rerun for this document.
This slice has no
model, inference runtime or prompt. Differences from existing behavior are
explicit: a new signing preimage, a separate source trust configuration, and
authorization checks after parsing. Existing source wire fields, payload
digests, parser outputs, Connect transport and EOM protocols do not change.

## Required change surface and ownership

This PR changes only this document. A subsequent accepted implementation would
add `src/connect_automate/lead_intake/auth.py`, explicit package exports, focused
`tests/test_lead_source_auth.py` and synthetic signing vectors in
`tests/fixtures/lead_source_auth/`. It must reuse `source.py` and
`entitlement.verify_signature` without changing their existing behavior.

Lead Intake owns the source authentication policy and verifier. The deployment
operator owns authorization to install, revise and revoke trust configuration.
Watcher owns its eventual signing key and mailbox assertions. Connect owns
transport; Automate owns orchestration. None may infer business authority from a
license, pack signature, local bearer token or EOM device enrollment.

The first library API accepts bytes and an already locally supplied, validated
trust snapshot. It does not load configuration from an envelope, fetch public
keys, enroll a sender or read another application's tables. A production caller
and the administrative configuration writer require later contracts. There is
no default trust snapshot and no trust-on-first-use path.

## Identity and trust contract

Proposed meanings fix previously unspecified authentication semantics without
changing the source envelope schema:

- `authorization.host_id` is the stable **receiving deployment** identity. It is
  neither the sender machine nor a Connect provider process `instance_id`.
- `payload.source.namespace_id` is the stable Watcher installation namespace.
- `authorization.key_id` selects an explicitly enrolled source signing key.
- `payload.organization_id` must equal the receiving deployment's sole configured
  organization. It is checked, not copied into a new deployment configuration.
- Event identity, message identity and later delivery identity remain distinct.
  A valid signature proves a permitted key made assertions, not that an email's
  sender, narrative or business facts are truthful.

The locally supplied `SourceTrustSnapshot` has exactly `version` (literal string
`1.0`), receiver `host_id`, non-null `organization_id`, positive `generation`,
`key_grants` and `retention_policies`. The latter collections contain the records
specified below; empty top-level collections are valid deny-all configuration.
All configuration objects are closed and all fields required. There must be
exactly one host/organization pair. IDs and
revision types reuse the source contract's UUID and strict positive revision
rules; booleans and coercion fail. Missing or malformed configuration fails
closed before authorization. Snapshot collections and nested records are copied
to immutable values; caller mutation must not alter a verification in progress.

Each key grant contains:

| Field | Rule |
| --- | --- |
| `key_id`, `namespace_id` | UUIDs; key ID unique throughout the snapshot |
| `public_key` | Exactly 32 raw Ed25519 public-key bytes; no remote key reference |
| `status` | Explicit `active` or `revoked` |
| `valid_from`, `valid_until` | UTC timestamps; a nonempty half-open validity interval |
| `mailboxes` | Nonempty immutable set of exact `(provider, account_id, mailbox_identity_key)` tuples using source field types |
| `retention_policies` | Nonempty immutable set of explicitly permitted `(policy_id, policy_version)` pairs |

Duplicate key IDs, duplicate public keys under different key IDs, duplicate
mailbox tuples within a grant and dangling/duplicate policy references within a
grant invalidate the snapshot. Shared mailbox permission across distinct keys
is permitted for rotation. Duplicate policy pairs in the top-level policy
collection also fail. Detect duplicates before converting sequences to sets.
No wildcards, NULL-organization fallback, case folding or account-only matching.
Mailbox identity is compared as the whole tuple, within the granted namespace
and the snapshot's organization. Rule/selector identifiers remain signed
provenance, not proof that a particular sender filter was applied correctly.

Each retention policy identifies `policy_id`, `policy_version` and an explicit
`max_recovery_seconds`, a strict positive integer no greater than 2147483647.
Grant validity timestamps use the source contract's exact UTC timestamp type.
There is no product default duration in this slice. A supplied duration limits
authentication age; it does not promise that content is stored or deleted on
schedule. Choosing production durations and implementing deletion remain open.

Grant identity is immutable: a key ID cannot acquire another public key,
namespace, host or organization. Administrative grant changes, revocation and
policy changes must advance the snapshot generation. An old generation cannot
overwrite a newer one. The verifier validates one snapshot; it cannot enforce
monotonic publication across calls without a durable owner. Those publication
and concurrent-revocation guarantees block production admission until qualified.

## Exact signature contract

Use Ed25519 directly over the following ASCII bytes. Join the four lines with
one LF byte; there is **no trailing LF**:

```text
connect-lead-source-auth-v1
<authorization.host_id>
<authorization.key_id>
<payload_digest(source)>
```

IDs and digest use their already validated canonical lowercase representations.
`payload_digest` is the existing SHA-256 over canonical payload bytes; this
preimage is not a second JSON serializer. The fixed context selects this signing
protocol. The verifier has no fallback to raw JSON, body-only signatures,
entitlement/pack signatures or EOM request proofs. A later algorithm/preimage
needs an explicit new protocol; do not infer it by trying several verifiers.

`source_signing_bytes(source)` exposes this deterministic preimage for independently
qualified producers. It revalidates the model through the existing source owner.
The sender can prepare it with a shape-valid placeholder signature because the
signature itself is excluded; after signing, the sender replaces that field and
uses `canonical_source` to emit the complete validated envelope. No private-key
generation or storage is added to Connect by this slice.

The receiver parses raw bytes, selects only the declared grant, decodes the
already validated signature and calls the existing crypto verifier with that
grant's public key. Receiver and key IDs are signed; organization, namespace,
mailbox, event, content, timestamps, trigger and retention are all covered by the
payload digest. Re-signing an unchanged payload with a newly authorized key
preserves its payload digest, but requires a new valid signature.

## Verification, time and replay semantics

`authenticate_source(raw, *, trust, now)` returns an immutable
`AuthenticatedSource` or a fixed public `SourceAuthenticationError`.
It performs no filesystem, network or database access. `now` is a required
timezone-aware UTC datetime supplied by the trusted host clock, not the request;
naive values, strings and non-UTC offsets fail. Comparisons retain subsecond
precision; timestamps from the source remain second-precision UTC.

Before returning, the single verifier must establish all of the following:

1. The raw source and trust snapshot are valid; the expected host and organization
   match exactly; the named key exists, is active and grants the source namespace.
2. The whole mailbox tuple and retention-policy pair are allowed by that grant.
3. `valid_from <= now < valid_until`; revocation is checked in the current snapshot.
4. The signature verifies over the exact preimage above.
5. `captured_at <= occurred_at <= now < recovery_deadline` and
   `recovery_deadline - occurred_at <= max_recovery_seconds` for the granted policy.

No clock-skew allowance is implicit. A future-dated event waits until eligible;
an expired event is rejected even if a receipt already exists. A host clock that
cannot be trusted must block admission. This library does not detect OS clock
rollback; that is a deployment qualification requirement, not a claimed guarantee.

An older captured event may be re-signed after key rotation; current key validity
is checked at verification time, not retroactively at the event's occurrence.
Rotation never extends the original recovery deadline. A revoked/unknown key
cannot retrieve a receipt. A newly enrolled active key with the same namespace
and permissions may sign the unchanged payload during its original recovery
window. Retired keys are not retained as a signature fallback.

Successful authentication is deliberately replayable during that window; it is
not admission or deduplication. The later admission owner must authenticate and
authorize **before** any business receipt lookup, including a duplicate lookup.
Source event replay must compare payload digests and reject conflicting payloads;
new events for the same message require a separately defined intake policy.

`AuthenticatedSource` carries the parsed source, payload digest, receiver and
organization, namespace, key ID, trust generation, policy pair, verification time
and `valid_until = min(key.valid_until, recovery_deadline)`. It is an in-process
result, not a serialized credential or an unforgeable Python object. Consumers
must not accept caller-constructed instances as proof of authority.

For future durable admission, the boundary itself must call the verifier, check
the current generation and time again, and serialize that check with the commit
against administrative revocation. A stale result cannot authorize a later
write. Merely checking a generation and then writing without coordination is
insufficient. The transaction/publication owner and its race tests belong to the
durable-admission contract; this verifier cannot close that race on its own.

## Errors and privacy

All input, trust, scope, time and cryptographic rejection paths expose the same
fixed public message and args. Do not attach source bytes, validation errors,
keys, identifiers or a retained internal exception chain. Raise after leaving
the handling block, following the parser's existing error boundary. No logs or
telemetry are emitted. Tests inspect exception attributes and chains.

This is not memory erasure and does not protect caller-owned frames, active
exceptions or debugger locals. The returned source contains sensitive content;
its representation must omit body text, signature and key material. Public
errors must not reveal whether a key, organization, mailbox or receipt exists.

Signing is not encryption. Source transport remains the existing local Connect
path; cross-machine delivery is not authorized. Key custody, encrypted storage
and backups, multi-user administration, retention enforcement and resistance to
a compromised same-user process are not provided by this library. The configured
OS user is a trust boundary, not an employee-role authorization system.

## Verification plan and acceptance gates

Contract verification: inspect every cited pinned source range, check the final
diff contains only this document, and obtain review and operator acceptance of
the exact contract revision. No behavioral tests are warranted for this doc-only
change. Inspection of existing tests does not qualify the proposed behavior.

After separate implementation authorization, first record the missing API as a
fail-first test, then implement only the verifier/encoder boundary above:

- Reuse existing parser fixtures unchanged. Freeze independently calculated
  signing preimage, public key, signature and payload digest vectors with a
  clearly synthetic test-only key. Check both ASCII and Unicode payloads.
- Verify valid signatures and every signed-field mutation; reject signatures
  made over raw JSON, another context, another host/key or only the body.
  Distinguish malformed parsing from a shape-valid forged signature in tests.
- Probe valid and invalid scope combinations, mixing a provider from one allowed
  tuple with an account/mailbox from another. Include missing/empty scope lists,
  duplicate/dangling trust records, revoked and unknown keys, and another org.
- Probe before/at/after validity starts and ends, occurrence and deadline; include
  subsecond values, equal endpoints, maximum recovery duration and its neighbors,
  `0`, `False`, empty strings, negative values and naive/non-UTC clocks.
- Show identical authenticated replay is allowed, while expired/revoked replay
  fails. Show a permitted rotation preserves the payload digest without extending
  the deadline. Do not claim this proves durable duplicate prevention.
- Mutate supplied configuration/models after validation; the result cannot change.
  Crafted model construction must not bypass schema checks. Test errors and repr
  with sentinel sensitive values and inspect internal exception chains.
- Remove each controlling check in a temporary mutation and require its focused
  regression to fail. Run the focused file, parser and signature-helper callers,
  and applicable lint/type checks; CI owns duplicated broad suites. No app pin,
  live mailbox, database or service is needed. Store proof outside worktrees.

Production adoption remains blocked on trusted configuration publication and
enrollment, sender custody, clock qualification, durable admission/revocation
coordination, source availability and retention. Native Windows storage must be
qualified in the later storage slice before that deployment is supported.

## Explicit non-scope, recovery and gap audit

No change to the accepted `LEAD-SOURCE.md`, parser wire format, EOM behavior,
Watcher polling, Connect transport, provider selection, Automate runtime,
workflow vocabulary, databases, migrations, dependencies or application pins.
No new workflow engine, dispatcher, remote pairing service, employee-role system,
extraction, CRM routing, local Inbox UI or durable receipts in this slice.

The prospective module is opt-in and has no production caller. Rollback removes
that integration without migrating business data. Main regression risks are
authority confusion, an independently divergent encoder, and treating a stale
authentication result as commit permission; the contracts and probes above
target those owners directly. Existing EOM proof and enrollment remain intact.

Implementation summary: this change specifies a proposed boundary only.
Cold diff audit: the intended change surface is this document alone.
Gap audit: NOT DONE for acceptance, implementation and handoff qualification.
Commit this contract separately and stop for exact-revision acceptance before
implementing. Contract acceptance does not authorize app adoption or waive the
later enrollment, persistence, recovery and retention gates.
