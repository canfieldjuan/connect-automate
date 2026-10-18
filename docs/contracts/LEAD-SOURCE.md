# Lead Intake source contract: parser slice

Status: implementation started on operator direction, library only. This is not
source admission, deployment authorization, or a claim that G1 passes.

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
models, `canonical_payload` and `payload_digest`. Package exports explicitly name
the untrusted boundary. Synthetic tests exercise the actual parser and its output.

An envelope requires `payload` and `authorization`. All objects are closed, all
fields required, all types strict. The payload schema is `lead.source.admission`
version `1.0`. Identifiers are lowercase UUIDv4; digests are lowercase SHA-256.
Opaque source identifiers are nonempty, at most 256 UTF-8 bytes, never truncated
or normalized. Revisions are integers from 1 through 2147483647; booleans fail.
Timestamps are real UTC dates, seconds precision with a literal Z.

Raw and canonical envelopes are limited to 2097152 bytes. Body text is limited
to 200000 Unicode scalar values, with no silent trimming or normalization. Body
SHA-256 covers its exact UTF-8 bytes; stored_chars counts scalar values. Complete
bodies require source_chars == stored_chars; truncated bodies require a known
larger source_chars; unknown completeness requires null source_chars. Unavailable
body states carry a reason and no invented content. Attachments are explicitly
not processed; count may be unknown. Capture precedes or equals firing time,
which strictly precedes recovery_deadline. This does not check the current time.

Canonical JSON sorts keys, uses UTF-8 without ASCII escaping, no insignificant
spaces, no floats or nonfinite numbers. Unicode normalization is forbidden. All
required nulls are retained. Digest covers payload only, excluding authorization,
so re-signing does not change business payload identity. Full canonical envelope
also receives the size check. Duplicate keys at any depth, invalid UTF-8, lone
surrogates, excess nesting and unknown fields fail. Errors expose no input data.

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

This slice implements the source envelope from the proposed architecture, not
the full G1 gate. Authenticated pairing and organization enforcement must precede
any future admission. A durable snapshot/receipt transaction and replay policy
are still required. Approval of this parser does not approve those implementations.

## Verification plan

Fail first on the missing parser using a valid synthetic envelope; then verify
positive and negative inputs, byte/scalar limits, null/false/type confusion,
duplicate members, unavailable states, time order, canonicalization and immutable
outputs. Confirm malformed input errors do not include confidential content.
Run the focused test file and Ruff; preserve output outside the checkout.
No broad suite duplicates the event-runtime session's existing work.

## Recovery and regression risk

The module is opt-in and has no callers in production. Removing the new module
and tests rolls back this slice without changing stored data. The main risk is
a future caller mistaking validation for authentication; naming, documentation
and a test accepting a shape-valid forged signature make that boundary explicit.
