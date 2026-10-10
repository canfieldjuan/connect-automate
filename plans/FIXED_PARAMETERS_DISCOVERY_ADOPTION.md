# Negotiated fixed-parameter discovery adoption

Status: PROPOSED. Planning only. Acceptance is required before dependency implementation. No app adoption or checking-pipeline START is granted.

## Root cause

At connect-automate main d68b25f8390a449126ae54bda2b156c836be7418, generic discovery always decodes the strict legacy v2 manifest (src/connect_automate/connect.py:1212-1214). _ParameterDeclaration (:167-172) and CapabilityParameter/public_dict (:417-435) have no fixed_value presence/value. The capability converter (:1054-1061) consequently cannot retain fixed identity. _validated_parameters (:1333-1389) validates caller values only, and is used by both new request construction and persisted restoration (:1517). Simply extending that shared validator with current-declaration fixed binding would risk rejecting or rebinding an already frozen request after rotation.

These are missing adoption surfaces, not proof that today's legacy paths are broken. The shared contract is landed; the dependency must implement its own real discovery and construction paths without redefining provider idempotency.

## Validated inventory and differences

- Shared owner: connect-contracts landed 8a9a44c5d4a040c75849a93ded82e6c98ff242e9 (PR64). Full landed tree equals reviewed b6a75d65eb9fe6ee9a5dd2544b4eb200a18d557d. ADR0013 and schemas/v2/features/fixed-parameters-v1 are canonical.
- Existing proof: 53 shared static tests, 127 vectors, 18 mutations; the provider independently verified direct refusal schema behavior. These are static proofs, not production HTTP, authentication, transactions or classifier qualification.
- Dependency baseline: main d68b25f; frozen Watcher dependency a3e2667741d9b06608e8a0b9689ea5f4fb75fc48. The planning checkout isolates work from that frozen dependency.
- Production differences to prove: authenticated streamed HTTP requests/headers, strict Pydantic decoding, bounded duplicate-safe JSON, public DTO serialization, new request binding, frozen request restoration and actual error propagation. No model, prompt, sampling settings or corpus applies to this protocol slice.
- Replay identity is the existing owner's. Shared typed fixed-value equality does not authorize numeric-spelling identity normalization, digest rewrites or legacy migration.

## Required change surface

1. src/connect_automate/connect.py: keep the strict legacy decoder; derive a separate negotiated decoder from the same legacy declaration/validation owners. Preserve all existing type, identifier, boundedness, unique-member, identity-attribution and closed-object checks. A fixed member requires required=true, its declared primitive type and the canonical request bounds. Presence preserves empty string, zero and false; null/nested values reject. No second copy of legacy validators.
2. _discover_capabilities and its public discovery wrappers: add explicit caller opt-in for fixed-parameters-v1, default off for compatibility. Opted-in v2 discovery sends the exact feature request header. Select the extended decoder only on exact requested+acknowledged token; otherwise select the legacy decoder. Unsolicited/wrong/ambiguous acknowledgments reject. Auth, registered identity matching, time budgets, limits, registration safety, endpoint validation, conflicting-instance handling and entitlement behavior remain owned by their existing paths. v1 discovery and registered GET-only reconciliation stay unchanged.
3. Opted-in discovery consumes the canonical response rules: no-store and feature Vary, with case-insensitive header names, existing Vary preservation, no response reuse and a fresh authenticated request on rediscovery. The dependency does not cache manifests today; preserve that fact rather than inventing a cache. Legacy default discovery stays unchanged. In opted-in discovery an older provider lacking the required response headers is incompatible; do not silently weaken the shared rules or claim every old provider already implements them. Feature-capable providers must retain invoice/certificate in their negotiated and legacy variants under their separately accepted advertisement slice.
4. CapabilityParameter and _generic_capabilities/public_dict: retain fixed-member presence separately from value. A legacy public dictionary omits fixed_value; a negotiated one preserves its exact admitted value, including falsy values. Internal absence representation must never leak into the public dictionary or request. Metadata transport is generic; no hardcoded Invoice Processor provider, bundle algorithm or classifier policy enters this dependency.
5. New request preparation: one binding owner consumes the explicitly selected declaration, fills an omitted fixed value before freezing, preserves ordinary required/editable parameters and rejects a wrong-typed or conflicting supplied value under the existing PARAMETERS_INVALID contract. No prompt is needed for a fixed parameter. Declaration matching uses typed value equality. All preparation entry points route through the same owner; do not bypass existing source/media/hash/confirmation gates. Existing new-request normalization for ordinary integer parameters is preserved; it does not rewrite persisted requests.
6. Persisted request restoration: never inject missing fixed values, compare with the newly advertised bundle or reserialize stored request_json. Restore validates existing wire integrity and capability/source identity through the inherited owners, preserving the frozen bytes and old admitted parameter identity. Where declaration-specific validation is needed, use the recorded admission declaration supplied by the caller, never a replacement live manifest. Persisting that declaration belongs to the caller adoption; GET-only registered reconciliation does not acquire a new declaration. Provider admission still decides replay versus conflict or failed restart under its recorded/current identity. A stale declaration is not permission to create new work. Caller selection/generation persistence belongs to Watcher adoption, not this library.
7. Existing ConnectV2Client error decoding propagates the canonical FIXED_PARAMETER_MISMATCH code and retryable=false without parsing message text, blind same-request retry or fabricating a document result. If it already does so, prove and preserve it rather than changing it. Watcher's deferred/classifier_bundle_unavailable mapping remains its separately reviewed I-state amendment.
8. Tests: tests/test_connect.py for decoder/DTO/preparation/restore; tests/test_windows_connect.py for shared discovery on Windows; tests/test_automate_connect.py for the preparation boundary where applicable. Consume immutable shared artifacts through a verified pin or checked copies with full hash receipts. A compact ownership guard proves decoder differences are limited to the extension. Generic conformance consumes generic schema/vector rules; classifier-specific declaration policy and provider admission events remain with their named owners, not a vendor-specific generic-library validator.

## Explicit non-scope

No provider advertisement/admission implementation, Watcher selection/state/queue/UI changes, classifier/model/runtime/OCR work, entitlement changes, new job origins, database migrations, digest policy changes, stored request rewrites, legacy shared schema edits, dependency-version bump in Watcher, v1/v3 feature changes, deployment or future merge authority. No blanket cleanup or new unrelated robustness work.

## Assumptions and blockers

- This is a dependency adoption contract proposal, not accepted implementation. Existing session owns preparation of this plan; implementation ownership and acceptance must be explicit.
- Shared pin is the landed PR64 tree, not a mutable main snapshot. Generic validation delegates to canonical owners; classifier-specific semantic qualification remains outside the dependency.
- Provider and Watcher adoption contracts must separately pin this dependency's reviewed implementation and prove their actual paths. Fixed-value presence transported to a public DTO does not prove an app renders it without a prompt.
- Legacy default discovery is intentionally preserved. Opted-in caller adoption must handle providers not satisfying the negotiated response rules visibly through existing unavailable outcomes, not fabricate compatibility.

## Verification plan

Before implementation, record exact baseline/source pins and shared artifact hashes. Declare each fail-first regression and expected failure before running it. Use public synthetic manifests/artifacts and isolated entitlement fixtures; no live licence or documents.

- Decoder: valid fixed declarations; unknown fields; mixed valid/invalid capabilities; required=false; null/nested values; type crossovers; empty string/zero/false; string1000/1001; integer +/- (2^53-1) bounds; integral/nonintegral numbers; undeclared/missing/duplicate names; legacy decoder still rejects fixed_value.
- HTTP: exact token/ack, no request, unsupported/mixed-case token, missing/unsolicited/wrong/duplicate ack, header-name case; both request orders; no-store/Vary preservation; stale rediscovery after bundle replacement; response app/instance mismatch; bounded/duplicate JSON and existing entitlement/timeout paths. Count actual requests, not mock dictionaries alone.
- DTO/preparation: omitted fixed value is filled once from selected declaration, falsy values survive public serialization and request creation, matching typed integral values admitted, wrong-type/conflicting values rejected, nonfixed required inputs remain required, extra caller keys reject; inspect actual frozen request bytes.
- Restore: unchanged accepted-job requests before/after advertised rotation restore exact bytes and old bundle; no new discovery value is substituted. Test changed request identity through the existing owner without introducing a universal numeric-spelling decision. Missing required frozen values remain malformed; restoration never repairs them. Registered GET-only reconciliation continues without a manifest.
- Refusal: direct canonical schema accepts exact refusal and rejects wrong code/retry policy; actual client propagates the code and false retryability. Watcher mapping is not exercised or claimed here.
- Mutations: disable ack gate, erase falsy fixed value, allow supplied override, compare restored request to current bundle, reserialize or normalize stored bytes, remove either refusal constraint. Each must be caught at its actual relevant owner; static-only mutations are not substitutes for client path tests.
- Run focused affected tests and Ruff first. Preserve Windows discovery tests and existing tests/test_connect_automate_boundary.py. Broader required checks follow the repository workflow if configured; record absence honestly. Shared suite evidence may be reused only with verified identical artifact hashes.

## Implementation summary

None. This change contains the proposed plan only. It does not build a negotiated consumer or authorize app adoption.

## Cold diff audit

Only this planning document is new. Source, tests, package pins, schemas, stored requests and frozen app heads remain unchanged. Source anchors were read at d68b25f before drafting. No test run is claimed for documentation alone.

## Gap audit

NOT DONE: operator acceptance; dependency implementation and real-path proofs; independently reviewed dependency pin; provider advertisement/admission and Watcher adoption acceptance AND builds. All three must be complete before checking-pipeline code. Scanned lineage remains independently gated.
