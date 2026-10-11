# fixed-parameters-v1 shared conformance slice

## Contract and origin

ADR-0013 landed at d2d3b7baf053377e2e4b78ee3569bde7a389da94.
This slice supplies the negotiated manifest schema and canonical declarative
response/request/admission vectors that do not yet exist. Without them each
app could implement a private fixed-parameter dialect or bypass replay rules.

## Required surface and one owner

- An extended manifest schema derived from the unchanged legacy schema;
  a derivation guard rejects divergence outside the parameter extension.
- Closed fixture-context schemas for exchange, admission and ordered event
  traces. These envelopes describe test inputs, not additional wire fields.
- A canonical golden fixture index with expected validity and decision output.
- A feature conformance oracle under tests, composing the existing
  tests.test_contracts.semantic_errors and primitive-type owner. It does not
  copy their legacy validation rules. One admission oracle also owns event
  trace submission decisions.
- Focused fixture, mutation, boundary and derivation checks, plus the existing
  shared conformance suites. Public README links the executable command.

## Observable behavior

Decoder, acknowledgment, freshness, legacy compatibility and reuse policy are
owned by ADR-0013, Negotiated manifest. Exchange fixture context explicitly
names `producer_conformance` or `consumer_admission`; an omitted role retains
the original producer-conformance interpretation. This is test metadata,
not a wire feature or a guess about provider age. The revised consumer vectors
exercise the accepted PR65 amendment; application behavior is not proven.

Fixed declarations require required=true and their declared primitive type
and existing request-parameter bounds. Presence preserves empty strings,
zero and false; booleans are not integers. Missing/wrong caller values are
invalid requests, not invented fixed-mismatch refusals. Well-typed conflicting
fixed values yield the exact FIXED_PARAMETER_MISMATCH/409/retryable=false
refusal when starting new or failed-restart work.

Admission context resolves immutable job identity before comparing against
a newly rotated bundle. Identical accepted/processing/completed work replays
its admitted identity. A changed request conflicts. Failed restarts and new
jobs use the current declaration; serialized rotate/admit orders have distinct
expected decisions. Header, equality, ordering and conflict mutations must
change golden outcomes or validity. Existing legacy schemas/fixtures remain
byte-identical; a manifest-schema derivation check guards their single owner.

## Frozen request identity and fixed-value equality

Fixed-parameter validation uses typed value equality, admitting integral
numeric forms. Replay identity remains with the existing idempotency owner;
this feature does not normalize requests or migrate stored digests. Replay
vectors resend an unchanged frozen request. They do not assert a universal
replay/conflict decision for requests differing only in numeric spelling.
The oracle compares frozen fixture snapshots through deterministic JSON
serialization, preserving numeric forms and booleans; this test mechanism
is not a production canonicalization or digest requirement. Expected outputs
also preserve the admitted snapshot, rather than normalizing its values.

## Non-scope and proof limits

No app, HTTP server/client, connect-automate implementation, model, database,
queue, entitlement, scanned extraction, deployment or existing app contract
change. Ordered event traces are a deterministic conformance model, not a
running transaction or thread scheduler. Request-invalid is a model decision,
not a new HTTP error code. Existing canonical request/error bodies retain
their wire owners. These fixtures do not prove authorization, semantic
classification, real cache behavior or runtime concurrency. Both app owners
must independently replay the published pin and later prove their real paths.

## Gates and plan

Commit this contract before conformance implementation. First run a declared
fail-first schema probe for a valid required fixed value; it must initially
fail with the legacy additional-property rejection. Then derive the extension,
exercise golden fixtures and negative/mutation checks, and run the repository's
existing documented conformance suites. Record exact commit and content hashes
outside worktrees. Publish a separate reviewable PR; no merge is authorized by
this start. Dependent app work stays blocked on shared review/landing, joint
declarations, a later assigned connect-automate owner/pin and accepted app slices.

Status: static conformance implemented; independent review/landing and
application/runtime proof remain pending.

## Accepted legacy compatibility amendment implementation contract

PR65 accepted proposal f08c87d supplies the exact ADR freshness replacement.
Required surface: exchange context role, one role-aware exchange policy owner,
separate canonical producer/consumer vectors, direct header boundary and role
mutation guards. Retain old producer outcomes, fixed-value/request identity
separation, no cached response reuse and unchanged legacy protocol inventory.
No application, provider server, persisted request or classifier changes.
Fail-first consumer role/header regressions precede the implementation; run
focused feature tests and the documented shared suites. Publish for independent
review only; no merge authorization or application adoption is implied.

## Sender and recipient rule table

This table is the executable policy source read by the oracle. Grammar definitions
remain in `tests/fixed_parameters.py`; role rules are not duplicated there.
`optional-fields` validates field-name list syntax, not cache behavior. For
`no-cache` and `private`, producer certification follows the RFC's SHOULD NOT
recommendation against token form; consumer parsing permits both forms.
Unknown extension directives retain generic token/quoted-string argument syntax.
Vector entries are exact name prefixes spanning both roles and outcomes.

<!-- freshness-rule-table -->
| Member | Sender rule | Recipient rule | RFC citation | Vector prefix |
| --- | --- | --- | --- | --- |
| Cache-Control-list | empty-limit:0 | empty-limit:16 | RFC9110 5.6.1 | list-rule-Cache-Control- |
| Vary-list | empty-limit:0 | empty-limit:16 | RFC9110 5.6.1 | list-rule-Vary- |
| max-age | required-delta-token | required-delta-token-or-quoted | RFC9111 5.2.2.1 | directive-rule-max-age- |
| must-revalidate | forbidden | forbidden | RFC9111 5.2.2.2 | directive-rule-must-revalidate- |
| must-understand | forbidden | forbidden | RFC9111 5.2.2.3 | directive-rule-must-understand- |
| no-cache | optional-fields-quoted | optional-fields-token-or-quoted | RFC9111 5.2.2.4 | directive-rule-no-cache- |
| no-store | forbidden | forbidden | RFC9111 5.2.2.5 | directive-rule-no-store- |
| no-transform | forbidden | forbidden | RFC9111 5.2.2.6 | directive-rule-no-transform- |
| private | optional-fields-quoted | optional-fields-token-or-quoted | RFC9111 5.2.2.7 | directive-rule-private- |
| proxy-revalidate | forbidden | forbidden | RFC9111 5.2.2.8 | directive-rule-proxy-revalidate- |
| public | forbidden | forbidden | RFC9111 5.2.2.9 | directive-rule-public- |
| s-maxage | required-delta-token | required-delta-token-or-quoted | RFC9111 5.2.2.10 | directive-rule-s-maxage- |
<!-- /freshness-rule-table -->

References: https://www.rfc-editor.org/rfc/rfc9110.html#section-5.6.1
and https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2 .
