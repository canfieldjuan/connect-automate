# Lead Intake source contract: parser slice

Status: ACCEPTED at revision `8d453b6be525c7f1a1b1069269a79a8b92b3d088`.
This commit records acceptance only; the behavioral requirements below are
unchanged. No parser code or tests are included in this contract-only branch.
The existing parser on draft PR #7 still requires correction and exact-head review.
This is not source admission, deployment authorization, or a claim that G1 passes.

## Operator acceptance and execution boundary

On 2026-10-18, Juan selected **"Accept (Recommended)"** for this exact contract
revision. Oversight relayed the selected option verbatim in
[the acceptance record](https://github.com/canfieldjuan/connect-automate/pull/10#issuecomment-6254877248):

> I relay this word for word. The session applies this contract to the parser branch (#7) as a docs-only commit, then makes the parser and test corrections as separate commits and requests review of that exact head. #10 merges as the contract record. No app changes, no version-pin bump.

Merge the contract record only after the published head has green required checks
and no unresolved review threads. Then apply this accepted document to the parser
branch as a docs-only commit before implementation/test corrections. Acceptance
does not waive the must-fail regression proofs or authorize application adoption.

## Root cause and existing work

The proposed lead source envelope existed only as a chat schema/check harness.
The base library has no Lead Intake contract owner. The separately developed
pack-trigger work at `3056cc1a15f34fa6d8720fc0a35579968e71c148` adds generic
mail events in `automate/events.py` carrying sender/subject, not the protected
body snapshot needed by intake. This parser does not depend on that work. Do not
enlarge that event or store bodies in its immutable receipts.

The prior chat harness is reference work, not a deployed implementation. Preserve
its closed objects, version, source/fire identities, body completeness, hash/count
checks and timestamp ordering. Use the installed Pydantic dependency instead of
adding jsonschema. No model, prompt, inference runtime or production data applies.

## Required change surface

`lead_intake/source.py` owns `parse_untrusted_source(bytes)`, immutable parsed
models, `canonical_source`, `canonical_payload` and `payload_digest`. Package
exports name the untrusted boundary. Synthetic tests exercise the actual parser and its output.

An envelope requires `payload` and `authorization`. All objects are closed, all
fields required, all types strict. The payload schema is `lead.source.admission`
version `1.0`. Identifiers are lowercase UUIDv4; digests are lowercase SHA-256.
Opaque source identifiers are nonempty, at most 256 UTF-8 bytes, never truncated
or normalized. Revisions are integers from 1 through 2147483647; booleans fail.
Timestamps are real UTC dates, seconds precision with a literal Z.

### Complete envelope shape

Every listed field is required, including nullable fields; no extra fields.

| Object | Required fields and types |
| --- | --- |
| Envelope | `payload`, `authorization` |
| Payload | `schema="lead.source.admission"`, `schema_version="1.0"`, `organization_id` UUID, `event_id` UUID, `watcher_event_id` digest, `occurred_at` timestamp, `source`, `trigger`, `snapshot`, `retention` |
| Source | `namespace_id` UUID, `provider` opaque string, `account_id` opaque string, `mailbox_identity_key` digest, `message_id` opaque string |
| Trigger | `rule_id` UUID, `rule_version` revision, `admission_kind="exact_sender"`, `selector_id` opaque string, `input_kind="message_body"`, `part_id="body"` |
| Snapshot | `snapshot_id` UUID, `representation="normalized-text"`, `normalization_version` opaque string, `captured_at` timestamp, `body`, `attachments` |
| Available body | `state="available"`, `text` string, `sha256` digest, `stored_chars` bounded stored-body count, `source_chars` nullable metadata count, `completeness` complete/truncated/unknown |
| Unavailable body | `state="unavailable"`, `reason` source_gone/outside_scope/retrieval_failed/not_captured; no content fields |
| Attachments | `count` nullable metadata count, `processing="not_processed"` |
| Retention | `policy_id` UUID, `policy_version` revision, `recovery_deadline` timestamp |
| Authorization | `host_id` UUID, `key_id` UUID, `signature` canonical unpadded base64url of 64 bytes |

The Watcher firing UUID is `event_id`; `watcher_event_id` is separately preserved
source provenance, not a substitute firing identity. This parser does not perform
identity resolution, deduplication, sender verification or policy lookup.

### Size and count ownership

Raw and canonical envelopes are limited to 2097152 bytes. Body text is limited
to 200000 Unicode scalar values, with no silent trimming or normalization. Body
SHA-256 covers its exact UTF-8 bytes; stored_chars counts scalar values. Complete
bodies require source_chars == stored_chars; truncated bodies require a known
larger source_chars; unknown completeness requires null source_chars. Unavailable
body states carry a reason and no invented content. Attachments are explicitly
not processed; count may be unknown.

Both metadata counts (`source_chars`, `attachments.count`) use one shared
strict integer type from 0 through 9007199254740991 inclusive, or explicit null.
This maximum is a proposed transport representation bound: exactly representable
by common binary64 JSON consumers and within signed 64-bit database integers.
It is not a claim about provider capacities or an authorization to allocate that
many records. Values beyond it are rejected, never clamped or converted to null.
`stored_chars` remains bounded by the stored-body limit, not this metadata limit.

Do not import Watcher's rule-configuration limits as source-message facts. At
Watcher revision `c7196dd5338cb0fe9e12f2c9fbedd0651beae09d`,
`automation/rules.py:221-224` bounds the configured `attachment.count` comparison
value, not the actual attachment collection. `mime.py:11` defines an input
character bound, not a generic multi-provider intake schema. Domain-specific
provider limits remain the provider adapter's responsibility.

Capture precedes or equals firing time, which strictly precedes recovery_deadline. This does not check the current time.

### Sender encoding and shared serialization owner

Senders MUST use `canonical_source` (or an independently qualified byte-equivalent
implementation) to emit the complete envelope, including authorization. It is
compact UTF-8 JSON, not Python's default ASCII-escaped JSON. The receiver may
accept noncanonical formatting within the raw byte cap; that tolerance does not
promise acceptance of arbitrary whitespace or escape expansion. An over-cap
ASCII-escaped envelope is rejected before decoding; the raw cap is not increased.

`canonical_source` returns complete canonical envelope bytes. It and
`canonical_payload` share one serialization implementation, rather than having
separate sender and receiver encoding rules. The producer API revalidates the
supplied model and applies the envelope byte limit; model construction/copy APIs
must not bypass the public encoder's validation. It does not sign or authorize.

Canonical JSON sorts keys, uses UTF-8 without ASCII escaping, no insignificant
spaces, no floats or nonfinite numbers. Unicode normalization is forbidden. All
required nulls are retained. Digest covers payload only, excluding authorization,
so re-signing does not change business payload identity. Full canonical envelope
also receives the size check. Duplicate keys at any depth, invalid UTF-8, lone
surrogates, excess nesting and unknown fields fail. JSON depth is bounded by 16
and arrays by 64 entries as defensive pre-validation limits; this schema has no
valid array-valued fields. The resource limits apply before schema validation.

### Error ownership and privacy guarantee

`parse_untrusted_source` owns error translation. A rejected input produces
`SourceInputError` with fixed message/args and no attached input, raw decoder
exception or Pydantic validation exception. Raise after leaving the internal
exception handler so the internal exception is not retained via `__context__`.
Do not treat `from None` or Pydantic's hidden input string as data removal.
Tests inspect the object and exception chain, not only its printed message.

This guarantee covers parser-added exception fields and its internal exception
chain. It is not memory erasure: caller input references, caller-active exceptions,
and traceback/frame-local capture by debuggers or telemetry are outside this
library contract. Integrations must not capture sensitive locals. Normal direct
calls must have `__context__ is None` and `__cause__ is None` for decoder and
validation errors; no raw input is included in exception notes or custom fields.

Difference from the chat harness: signature representation is checked for
canonical unpadded base64url encoding of 64 bytes, rather than just its character
pattern. This does NOT verify Ed25519, key possession, enrollment, organization,
mailbox grants, destination host, revocation, replay, expiry or freshness.
Successful parsing must never be treated as authorization or persisted admission.

## Explicit non-scope

No changes to Automate event/runtime/store/locks, Watcher, EOM, dependencies,
services, workflow vocabulary, databases, application pins or existing fixtures.
No provider receiver, worker, pairing registry, lead record, approval or delivery.
The separately developed runtime work is excluded from this branch.

## Assumptions and blockers

The proposed slice implements the source envelope from the architecture, not
the full G1 gate. Authenticated pairing and organization enforcement must precede
any future admission. A durable snapshot/receipt transaction and replay policy
are still required. Approval of this parser does not approve those implementations.

## Verification plan

Fail first on the missing parser using a valid synthetic envelope; then verify
positive and negative inputs, byte/scalar limits, null/false/type confusion,
duplicate members, unavailable states, time order, canonicalization and immutable
outputs. Confirm malformed input errors do not include confidential content.
Add root-bound regression proofs before implementation corrections:

- Error class: digest mismatch, overlong identifier, invalid UTF-8 and malformed
  JSON all leave no internal exception context or cause. Include recursion and
  duplicate-member rejection as sibling paths; assert fixed message/args.
- Decoder exhaustion: input of `b"[" * 1048576 + b"]" * 1048576` is exactly at the
  raw cap and must become `SourceInputError`. Confirm removing `RecursionError`
  handling in a memory-only mutation makes the new regression fail. Keep a
  separate shallower fixture for the explicit shape-depth guard.
- Encoding: the public canonical envelope encoder round-trips an available
  200000-emoji body and a control-character body at the limit; default
  ASCII-escaped over-cap bytes fail with the documented size error. Sender and
  payload canonicalization retain the existing canonical vector. Test invalid
  constructed/copied models at the public encoder boundary.
- Metadata counts: exercise both nullable fields with null, zero, maximum-minus-one,
  maximum, maximum-plus-one, negative, false, empty string, float and a huge integer.
  Use a truncated available body where needed to isolate the source-count bound
  from completeness rules. Removing the common upper bound must fail both fields'
  regressions. Values at the maximum survive canonicalization unchanged.

These tests must fail when their owning rule is removed, not merely when an
unrelated guard rejects the same input. Informational redundant guards are not
claimed as separately proven invariants. No new downstream filters or database
coercion compensate for missing boundary checks.

Run the focused test file and Ruff; preserve output outside the checkout.
No broad suite duplicates the event-runtime session's existing work.

## Recovery and regression risk

The module is opt-in and has no callers in production. Removing the new module
and tests rolls back this slice without changing stored data. The main risk is
a future caller mistaking validation for authentication; naming, documentation
and a test accepting a shape-valid forged signature make that boundary explicit.

## Root repair and approval sequence

All review findings originate in the initial parser commit
`257705e557e7c36d76671fe2178f3ccc3c8b44ed`:

| Finding | Origin at that revision | Required correction after acceptance |
| --- | --- | --- |
| Input retained in error context | `source.py:228` raises while handling the raw exception | Translate outside the internal handler; replace the suppression-only privacy assertion, keeping all malformed-input siblings under the same owner |
| Recursion catch not regression-protected | `tests/test_lead_source.py:229` uses nesting accepted by the decoder | Add a real decoder-exhaustion fixture and mutation proof, separate from shape depth |
| Encoding rule omitted | `LEAD-SOURCE.md:33` couples scalar/raw limits without a sender encoding | Specify canonical wire bytes and expose the existing serializer through one validated envelope encoder |
| Unbounded metadata integers | `source.py:63` defines lower-bound-only `Count`, used by both metadata fields | Add the portable upper bound at that shared owner, with tests for both readers |

This contract-only branch is based on main and preserves published history.
PR #7 remains draft; no force push, deletion or rewriting of its original commit.
After contract review and operator acceptance, apply this contract to the parser
branch in a docs-only commit, then make implementation/test corrections separately
and request review of the exact published head. No finding is marked resolved
until the accepted correction and its regression proof are pushed. The broader
source-handoff gate remains incomplete even after these parser repairs pass.
