# V1b.1: owner bootstrap and native admin qualification

Status: **PROPOSED, CONTRACT ONLY. B0-I licensing interface, B1 native mechanisms
and B2 disposable qualification plan are specified below for review. They are not
implemented or qualified. Licensing-side acceptance, oversight of this revision,
Juan's exact-revision acceptance, harness freeze and separate run authorization
remain gates. No implementation, native run or merge is authorized by this draft.**

## Ordering, completed work and bounded outcome

The accepted [vertical plan](LEAD-VERTICAL-DELIVERY.md#acceptance-record) orders
V1a before **V1b: machine control and activation**, then the selected template,
EW body handoff and isolated real-lead proof. Its work-sequence table permits
splitting at an owner boundary. It does not authorize implementation merely by
naming a slice.

V1a is complete in the private library: [PR #71](https://github.com/canfieldjuan/connect-automate/pull/71)
merged as `c44091fe038223bcd43f5a86da07c5548569095e`, with reviewed/merged tree
`177bff42dfc9662db1f1167a6a9e2428fb635248`. Issue #66 closed under its accepted
completion procedure. Exact-head Linux/Windows CI, oversight and connector
review passed. This is recorded evidence, not a new test run or live qualification.
Evidence alias `lead-custody-expiry-implementation/merge-20261031T142956Z/receipt.json`,
SHA-256 `44607d94124910e11f891b75b576eadfc1837c3aca3f1900601ab8f153527147`.

**Proposed bounded next outcome:** qualify how the protected local host verifies
the deployment owner, bootstraps that owner's initial admin record and obtains
a native admin session. Use synthetic identities on separately authorized
disposable native environments. Deliver a reproducible feasibility packet and
the precise subsequent enforcement work order, not a receiver or another pure
eligibility model. An unproven prerequisite is a typed blocker, not a fixture
grant that permits the next step.

This split is necessary because V1b's machine grant must be published by an
authenticated enrolled admin. The accepted plan requires owner bootstrap and
native session proof before that authority can exist. It explicitly disallows
installer privilege, a claimed owner ID and the first local caller as owner
proof (`LEAD-VERTICAL-DELIVERY.md:355-395,440-460`).

## Contract: root cause and exact source inventory

All CA source citations below use `canfieldjuan/connect-automate` at
`c44091fe038223bcd43f5a86da07c5548569095e`. `LI/` means
`src/connect_automate/lead_intake/`; `CA/` means `src/connect_automate/`.
Documentation supplies constraints and leads, not implementation evidence.

| Label | Evidence and demonstrated limit |
| --- | --- |
| CONFIRMED | `CA/automate/host.py:34-89` is an entitlement-gated host skeleton. Starting it checks licensing; it does not bootstrap employees, verify native sign-in or run a protected receiver. |
| CONFIRMED | `CA/entitlement.py:138-166,175-188,199-240` supplies strict signed-envelope/claim models, installed public-key authority, license evaluation and installation. `:402-418` is the shared Ed25519 verifier; `:435-469` checks signature, feature and validity. The existing issuer trust chain is reusable. The claims lack organization, installation, native-principal and one-time consumption/revocation binding; a valid license alone is not owner proof. |
| CONFIRMED | `LI/_host_policy.py:1-7,35-66,97-158` validates supplied scope/actor/session/version facts and returns eligibility. Its machine actor is denied by the human policy catalog. It acquires no native identity and grants no execution authority. |
| CONFIRMED | `LI/custody_protocol.py:102-110` contains an enrolled-machine UUID and opaque proof reference. Neither verifies a credential. `LI/custody_handoff.py:124-191` revalidates runtime/route/store/request references, not the caller's native identity. |
| CONFIRMED | `LI/auth.py:82-109,151-195` validates source-trust snapshots and source signatures against host/org/namespace/mailbox/retention grants. It is not deployment-owner bootstrap, employee sign-in or a transport-control verifier. Keep that owner and signing preimage unchanged. |
| CONFIRMED | `LI/source_store.py:396-464` enforces current-process/private-path assumptions; its comment explicitly trusts same-user processes. Those checks do not isolate employees sharing the store account or establish encryption, owner authority or login state. |
| CONFIRMED | `LI/custody_store.py:135-196` already owns custody mutations and retained reads. `LI/source_store.py:551-592,604-624` owns source writer/commit and query-only snapshots. New host authority must not read/write these tables or duplicate these transactions. |
| CONFIRMED | `CA/connect.py:98-134,330-364` defines registry bearer transport, one hashed input artifact, bounded scalar parameters and output bytes. These are reusable transport contracts, not employee or business-owner identity. |
| INFERRED | The first missing owner in the accepted vertical is protected host authority acquisition. Adding another policy result type or trusting test-populated admin rows would leave that boundary missing. |
| UNKNOWN | A license-backed owner claim and its durable consumption/revocation, complete native sign-in/lock mechanism, protected service/keystore installation and native cross-account isolation are not qualified by these paths. No global claim about uninspected products is made. |

### Bounded reuse search and existing proof

Read-only searches of tracked local trees also covered `local-connect-status`
at `d94c84f4f6c49fa22273d693bc3e6fd36f61f8ec`, `local-connect-licensing`
at `9f9d1be530653300926315294ef1721ce3d4fc98`, and `local-connect-model-host`
at `f707665d801db2ff05759bea83be3e7d92080a53` for first-admin,
deployment-owner, native-identity, bootstrap and enrollment references. This
bounded search did not establish an implemented business-owner bootstrap.
It is not an audit of all branches, installed services or unpublished work.
The licensing checkout contains a proposed issuing-service contract, not evidence
of an implemented service. That does not negate the existing entitlement verifier
and issuer below. The model host remains inference infrastructure, outside this lane.

`connect-contracts` at `a168b9a67450556d95b4939a59ca36aa7aedfda5`,
`schemas/v2/registration.schema.json:7-35`, declares loopback/bearer registration,
not delegated business-owner or employee authority. Its
`tools/entitlement_issuer.py:359-450` validates feature/time/subject inputs, loads
the issuer key, signs and self-verifies a license, then writes a new envelope.
`entitlements/v1/claims.schema.json:5-40` forbids extra properties and fixes the
existing claim vocabulary. Neither path implements owner-claim consumption or
per-claim revocation. These are **CONFIRMED source findings**, not a claim that
production issuance or key custody was exercised. No private key was accessed.

**C1 correction:** my initial inventory searched for bootstrap/native identity
but omitted the existing entitlement chain. That omission originated in this
contract's reuse inventory, not the license implementation. The correction
credits the issuer/verifier and narrows the missing capability to scoped owner
authorization and consumption. It does not create a parallel signing system.

**Licensing owner/change:** the licensing/release owner must own business-scoped
claim issuance, revocation/reissue and any authoritative consumption interface.
The existing concrete issuer lives in `connect-contracts/tools/entitlement_issuer.py`;
its schema/fixtures and the CA consumer would need separately accepted changes.
The inspected `local-connect-licensing` proposal names a release-session owner
at `docs/contracts/LICENCE-SERVICE.md:3-16` and preserves entitlement v1 at
`:46-51`. It already proposes online issuance at first launch (`:26-29`) and
retains hand-signed offline licences through the existing issuer (`:35-36`).
The selected first-launch consumption call fits that proposed activation point;
the proposal is neither accepted here nor evidence that the service exists.
Those ownership/service claims require coordination, not authority to change
that repository or evidence of a running API. No
cross-repository code, dependency/pin or production issuing change is made here.

Retain these existing proof inputs and their limits:

| Inventory | What can be reused; what cannot be claimed |
| --- | --- |
| `tests/test_lead_host_policy.py:35-369` | Closed-policy matrix, scope/version/role checks, copied-value rejection and no-I/O tests. These test supplied facts; they do not authenticate a human. |
| `tests/test_automate_host.py:94-134`; `tests/test_windows_connect.py:138-426`; `tests/test_locking.py` | License, private-path and lock regression owners; preserve their existing behavior. Native employee isolation or session proof does not follow from their presence. |
| CA `tests/test_entitlement.py:91-115,205-224,250-285`; connect-contracts `tests/test_entitlement_issuer.py:97-124` | Existing signature/feature/time, duplicate-member, installed-authority and issued-envelope conformance tests. Inspected, not executed here. Preserve unchanged v1 behavior; these do not test an owner claim or native sign-in. |
| `protected-host-read-contract/linux-credential-probe.py`, SHA-256 `9c50cf68c94856e442e2a6b1e698cac79bbe7b82f27232b7e2622d1ff518b693` | Existing unnamed-socket credential probe; hash rechecked, not rerun. Reuse it rather than inventing a replacement identity simulation. |
| `protected-host-read-contract/linux-credential-result.json`, SHA-256 `5ecf067de3fc283471bfd31948ce9f59388ca6f1781d423a92f185b2ca327ef8` | Recorded same-account Linux primitive: actual sender differs from claimed/connection identity and forged credentials are refused. Explicitly not sign-in, separate-account isolation or Windows proof. |
| V1a receipt above | Completed custody vocabulary/recovery regression reference. No human, machine-control or transport qualification. |

There is no model, prompt, inference runtime or real-message fixture in this
port inventory. Proposed departures are a separate owner-authorization claim and
its lifecycle at the licensing boundary, native identity acquisition, protected
bootstrap and session qualification. Existing license, policy, source, custody,
retention and workflow behavior remains the parity reference. No application
tests, issuer commands or native probes are executed for this documentation PR.

## First-admin bootstrap: license-backed direction, unqualified mechanism

Oversight explicitly carried this forward in mailbox `289865d6`: pin a concrete
first-admin bootstrap needing no enrollment step, or bring the blocker to Juan.
The accepted plan did not select the underlying authority. Oversight has now
[relayed Juan's B0 decision](https://github.com/canfieldjuan/connect-automate/pull/72#issuecomment-6546119928)
on 2026-10-31, verbatim:

> use the license for owner bootstrap

**B0 direction selected, not technical acceptance.** The relay says Juan answered
the recommendation to issue a signed, one-time owner authorization with the
license; at first launch its holder signs in with their computer account and
becomes admin. No enrollment command, key copying or setup beyond license
activation. Reuse the existing signed entitlement verification and issuing trust
chain, with no second signing system or cloud identity service. This record
attributes the decision to that relay; it is not a new acceptance of this revision
or permission to operate the issuer, native accounts or a VM.

**B0-I connectivity decision, limited scope.** Oversight separately
[relayed Juan's answer](https://github.com/canfieldjuan/connect-automate/pull/72#issuecomment-6546300612)
to whether one online check at first launch is acceptable, on 2026-10-31:

> yes to both

That answer also covered an unrelated question. The relay attributes only this
licensing decision here: **one authoritative call to the licensing owner at first
launch to consume the claim, with a clear typed refusal if the service is
unavailable. Lead operations gain no continuing licensing dependency.** This
does not accept `LICENCE-SERVICE.md`, authorize service/issuer changes, or accept
this contract revision. B1/B2 and exact-revision acceptance stay open. The relay
does not authorize code, native/VM/account work or key access.

**Trust limit:** the issuer authorizes the named business deployment. The first
valid holder who completes native authentication consumes the authorization;
the issuer has not preidentified that human. A leaked authorization could be
claimed by another valid holder. Native sign-in proves the local account, not
civil identity or entitlement to represent the business. This replaces this
draft's earlier proposed prebinding to an intended native person. An ordinary
license, installer privilege, OS administration or being first to call the host
still grants no bootstrap authority. After successful consumption, the owner
mapping is immutable through ordinary bootstrap and cannot be replaced by a
second holder. Native principals are bound at consumption, not inferred from
the license's `subject` or a typed owner name.

### Proposed claim and verifier boundary

Add a versioned, purpose-specific **owner-bootstrap companion claim**, delivered
with the existing entitlement during normal activation. Preserve the entitlement
v1 schema and feature behavior; do not insert new fields into its closed payload
or repurpose `subject` as a native identity. Reuse `CA/entitlement.py:402-418`
for signature verification and the installed public-key trust distribution.
The licensing owner must explicitly authorize which trusted issuer keys may
issue this purpose; not every valid signed pack/license is a bootstrap claim.
No private signing key belongs in the app or this qualification session.

**Issued claim:** its closed schema binds claim/version/purpose, issuer/key
identity, linked entitlement identity, immutable organization/business, unique
claim identity, issuance/not-before/expiry and revocation/reissue generation.
It does not name an installation, host key or native person that may not yet
exist. The licensing owner issues the online owner claim only during successful
first-launch licence activation, not at purchase. A Friday purchase followed by
a Monday installation therefore starts claim validity on Monday's activation.
The claim is delivered with that activation response; no separate bootstrap
claim-fetch or host-key handshake is introduced. The 86400-second cap starts at
activation issuance, as the existing first-launch proposal describes at
`local-connect-licensing/docs/contracts/LICENCE-SERVICE.md:26-29` (proposal only).
The issuer authorizes the business; arbitrary setup text cannot change it.

For an unconsumed claim that expires after activation, the user message is:
"Your owner setup authorization expired. Resume licence activation to obtain a
fresh authorization." That explicit normal-activation action verifies entitlement
and business and atomically supersedes the unconsumed claim under the existing
licensing-owner generation rule; no key copying or admin-enrollment command.
An unresolved consume is reconciled first with its original binding: do not
reissue or discard pending state because its response was lost. If consumption
already committed, keep that owner and use controlled recovery, never a fresh
claim to replace it. Expiry is not an invalid-licence message.

**Consumption operation:** at first launch the protected host supplies its
installation/host identity and proves possession of its protected key, alongside
the freshly verified native-person binding, stable operation identity and exact
initialization payload digest. The licensing owner atomically binds the issued
claim to that installation/key and opaque native/payload commitment in the same
consumption operation. The signed receipt and durable consumed state preserve
those bindings. A caller-supplied UUID alone is not installation proof.
Before consumption another eligible holder may win the claim, as disclosed
above. After consumption a copied claim from another installation/key or person
must fail, not rebind. Exact replay must match all consumed bindings; changed
bindings are conflicts. Schema-expressible constraints
belong in closed models/schema; semantic checks have one owner, no parallel regex.
The wire vocabulary, bounds and key-purpose policy are pinned in the B0-I
profile below. They require review and conformance fixtures before adoption.

**C2 correction:** my revision `06087b110736b69d41ebfdc53bf2acc8cfbe3a4f`
incorrectly put installation/key binding in the issued claim. Its origin was
this claim-boundary section. Separating issue-time fields from consumption-time
bindings removes the impossible pre-existing-key requirement; it does not relax
binding after consumption or add a pre-activation handshake.

### Hand-signed offline licences and typed refusal

Hand-signed offline licences remain valid under the unchanged entitlement-v1
rules. **Given only such a licence, owner bootstrap returns
`OWNER_AUTHORIZATION_REQUIRED`: the licence does not provide the companion owner
claim.** This is an explicit blocker for that input class, not an invalid-license
result. Keep the licence and its existing behavior unchanged; do not create an
admin, fall back to a local consumed flag or silently convert the licence.

A valid companion claim, if separately issued for that business/entitlement,
still requires the same authoritative first-launch online consumption call.
There is no disconnected bootstrap route in this proposal. If that call cannot
produce a verified authoritative outcome, return `LICENSING_UNAVAILABLE` and
publish no owner/admin authority. If consumption may have happened before the
response was lost, preserve the bound pending operation and explicitly report
its unresolved status; unavailable is not evidence that nothing was consumed.
Recovery replays that same operation, never a replacement claim or owner.

A hand-signed customer obtains a companion claim only through explicit online
licence activation with that licence, after the licensing owner verifies the
issued entitlement and business. The owner claim is issued at that activation,
not with an earlier hand-signing/purchase date; the hand-signed licence itself
stays unchanged. A fully disconnected customer has no owner-bootstrap path here.
Do not assume the service implements this offline-entitlement activation path:
it needs separate licensing acceptance and qualification. Until available, keep
`OWNER_AUTHORIZATION_REQUIRED` with "This licence is valid; owner setup requires
online activation and a business-scoped owner authorization." No local flag or
manual key-copy fallback is permitted. No claim means `OWNER_AUTHORIZATION_REQUIRED`;
a claim with unavailable online consumption means `LICENSING_UNAVAILABLE`.
These outcomes derive from verified inputs and availability, not a guessed
offline label or issuer-key naming convention. **C3 correction:** the same prior
revision that introduced C2 omitted this licence class. These explicit outcomes
close that contract gap without claiming disconnected bootstrap support exists.

### One-time consumption, revocation and reissue

**Recommended lifecycle owner:** place the new authoritative claim lifecycle
with the licensing owner; the protected local host owns the resulting employee/admin
state. A signed file plus a local consumed flag alone cannot prove one-use after
rollback, restore or reinstallation, or that a remote revocation is current.
No such lifecycle/status interface exists in the inspected issuer. The relayed
decision accepts the first-launch online dependency and typed unavailable
refusal. The licensing interface, retention and recovery behavior still need
qualification and separate acceptance; the proposed online service is not
thereby implemented or authorized for changes.

Required semantics for that interface are a durable, serialized claim transition:
an eligible claim may be consumed once, revoked, expired or superseded. Exact
authenticated operation replay returns its same bound receipt; another principal
or payload cannot consume it again. Revocation winning before consumption denies
bootstrap. Consumption winning first preserves that owner binding: revoking or
reissuing an owner claim cannot elect a replacement admin. Reissue of an unconsumed
claim revokes/supersedes it before making a new claim eligible, with a new claim
identity and generation. Recovery of an already consumed claim is a separate
owner-authorized process, never implicit enrollment or an empty-store reset.

The protected host must durably record a bound pending operation before requesting
consumption, then commit the verified receipt, owner/admin mapping and minimal
audit in its own transaction. It must recover a lost response from the same
authoritative operation. Do not claim a transaction across issuer and host.
After an ambiguous consumption result, retain pending state and reconcile that
operation; never try a new owner or claim automatically. The ordinary path uses
the accepted first-launch consumption call. Recovery may replay only that same
unresolved operation with the same bindings; it adds no periodic status polling
or licensing call on lead operations. Recheck native identity
and validity after waits before local publication; a consumed claim with interrupted
local completion remains reserved to its original binding, not newly available.
The issuer receives only the necessary business/installation references and an
opaque commitment to the local consumption binding, never native credentials,
account names or lead content. Pin retention and recovery of that commitment in
the licensing work order; it must not become an employee directory.

### B0-I: licensing interface profile, version `owner-bootstrap/1`

**PROPOSED contract pin, not implemented API.** The licensing/release owner owns
this profile and its claim ledger; CA owns the client and local authority store.
It is a new bounded addition to the licensing proposal, not an acceptance or
implementation of `LICENCE-SERVICE.md`. No app accesses the issuer database.

**Endpoint:** `POST /v1/owner-bootstrap/consume`, HTTPS, no redirects, cookies,
query parameters or browser invocation. Resolve the single allowed origin and
claim/receipt key-purpose allowlist from a release-signed activation manifest
installed through normal activation. Verify it with the existing installed trust
chain; do not accept an origin/key from email, request JSON or environment
variables. No production origin or service existence is asserted here. Production
adoption requires the licensing owner to publish the signed endpoint/key manifest
and pass this profile; absent configuration returns `LICENSING_UNAVAILABLE`.
The disposable harness uses only its own loopback TLS origin and ephemeral CA.

**Encoding owner:** closed JSON Schema 2020-12 models, every listed field required,
`additionalProperties: false` at every object, no null/default/coercion, duplicate
members or non-finite numbers. Payload fields are ASCII identifiers, bounded
integers and fixed UTC strings. Canonical bytes are UTF-8 JSON with sorted keys,
compact separators, no NaN; reject any alternate signed encoding. This preserves
the bounded canonicalization pattern at `LI/source.py:206-210`, not its source
schema/preimage. Use existing Ed25519 `CA/entitlement.py:402-418`; do not duplicate
crypto or import lead/source business models into licensing. Sign domain prefix
plus canonical payload; domain prefixes are the ASCII strings below followed by
a NUL byte. New strict models and fixtures belong to a later licensing/CA work
order; this Markdown defines their conformance obligations, not generated code.

| Type | Closed required fields and constraints |
| --- | --- |
| `ActivationManifest` payload | `version` const `owner-bootstrap/1`; `purpose` const `owner-bootstrap-activation`; `origin` canonical ASCII HTTPS origin, JSON Schema minLength 1/maxLength 255, parsed as a URI with an A-label DNS host or bracketed IPv6; no userinfo/path/query/fragment, control characters, escaped host or Unicode, port 443 outside the isolated test build; `claim_key_ids`, `receipt_key_ids` arrays of 1..16 unique bounded key identifiers, all present in the installed keyring; `issued_at`, `expires_at` fixed UTC, ordered validity at most 2592000 seconds. Signed envelope must use an installed release-authority key, not an arbitrary pack key. No active manifest means unavailable. |
| `OwnerClaim` payload | `version` const `owner-bootstrap/1`; `purpose` const `owner-bootstrap`; `claim_id`, `organization_id`, `entitlement_id` UUIDv4; `generation` integer 1..2147483647; `issued_at`, `not_before`, `expires_at` UTC `YYYY-MM-DDTHH:MM:SSZ`. Enforce `issued_at <= not_before < expires_at`, at most 86400 seconds of validity starting at first-launch activation issuance, never purchase. No installation, host key or native identity at issuance. |
| Signed envelope | `version` const `owner-bootstrap/1`; `key_id` ASCII identifier matching `[a-z0-9][a-z0-9._-]{0,63}`; `payload_base64url` canonical unpadded base64url with minLength 1 and the expected type's maximum from the wire-budget table below; `signature_base64url` canonical encoding of 64 bytes. Payload must satisfy its purpose-specific schema. `key_id` must be permitted for this purpose in the trusted activation manifest. |
| `ConsumeBinding` | `version` const `owner-bootstrap/1`; `operation_id`, `installation_id`, `host_id`, `organization_id`, `claim_id`, `entitlement_id` UUIDv4; `generation` as claim; `claim_sha256`, `principal_commitment`, `initialization_sha256` lowercase hexadecimal SHA-256; `installation_public_key` canonical base64url of 32 Ed25519 public bytes. No native account name, password or lead data. |
| `ConsumeRequest` | `version` const `owner-bootstrap/1`, `owner_claim` signed envelope, `binding` ConsumeBinding, `attempt_id` UUIDv4, `requested_at` fixed UTC timestamp, `installation_signature` canonical base64url of 64 bytes. No extra app, billing or document fields. |
| `ConsumedReceipt` payload | `version` const `owner-bootstrap/1`; `purpose` const `owner-bootstrap-receipt`; `state` const `CONSUMED`; `receipt_id` UUIDv4; `binding` exact ConsumeBinding; `consumed_at` fixed UTC timestamp. Wrap in the signed envelope above. |
| Refusal | `version` const `owner-bootstrap/1`; `code` enum `OWNER_AUTHORIZATION_INVALID`, `OWNER_AUTHORIZATION_EXPIRED`, `OWNER_AUTHORIZATION_REVOKED`, `OWNER_BINDING_CONFLICT`, `OWNER_CLOCK_SKEW`, `LICENSING_UNAVAILABLE`; `operation_id` UUIDv4; `completion` enum `NOT_COMMITTED` or `UNKNOWN`. Do not return free-form upstream text, claim bytes or account data. Never treat an unsigned refusal as proof of non-consumption after a timeout. |

**Single wire-budget owner:** the following table supplies every envelope
schema's maximum payload string length, pre-decode byte limit and total canonical
envelope limit. It replaces the former global payload cap; endpoint and IPC
consumers reference this table, not a second copied cap. The enclosing trusted
operation selects the expected type before reading/decoding; an attacker cannot
select a larger budget by supplying a payload purpose. Use closed per-type schema
branches with those `maxLength` constraints, then the same named bounded decoder
and native URI parser; no parallel regex-based size/URI checker.

| Expected signed type | Decoded canonical payload bytes, max | Unpadded base64url characters, max | Complete canonical signed-envelope bytes, max |
| --- | ---: | ---: | ---: |
| `ActivationManifest` | 3072 | 4096 | 4608 |
| `OwnerClaim` or `ConsumedReceipt` | 1536 | 2048 | 2560 |

A 3072-byte payload encodes to at most 4096 unpadded base64url characters;
1536 bytes encodes to at most 2048. The largest envelope overhead is 241 bytes
with the declared constant version, 64-character key ID and fixed signature
encoding: 4096 + 241 fits 4608, and 2048 + 241 fits 2560. Check enclosing byte
limits before parsing, encoded length before decoding, then decoded size, schema,
canonical form and signature. Never truncate or fall back to a larger type.
The consume endpoint keeps its existing request/response budgets, which fit the
smaller claim/receipt envelopes. The activation manifest's envelope budget applies
only within normal activation; this is not a new manifest fetch or a change to
legacy licence wire limits. Reject it in a consume-response/ordinary IPC slot;
it must not silently inherit that slot's smaller response cap.

All schema-permitted manifest fields are now finite. With both arrays at 16
unique 64-character IDs, a valid 255-character ASCII origin and fixed-width
maximal timestamps, the canonical manifest is 2590 bytes, its base64url payload
3454 characters and its complete envelope 3695 bytes. The maximum-shape owner
claim is 353/471/712 bytes/characters/envelope bytes and consumed receipt is
899/1199/1440 respectively. Thus every permitted field combination is representable
within its type budget; no need to reduce the allowed key counts or lengths.
These are synthetic documentation byte calculations with placeholder strings,
not signing/key work or conformance/runtime tests. Oversight's correction
`463c587a` distinguishes its sample from the connector's sample; neither sample's
exact origin length is used as the general bound.

The prefixes are `local-connect.owner-activation.v1`,
`local-connect.owner-claim.v1`, `local-connect.owner-consume.v1`,
`local-connect.owner-receipt.v1`. Claim digest
hashes the complete canonical signed claim envelope. The installation signs the
canonical object containing `version`, `binding`, `attempt_id`, `requested_at`
with the consume prefix. Each explicit recovery uses a fresh attempt/time and
signature over the same durable binding; a stored receipt or copied unsigned
result cannot replace proof verification. Require request time within 60 seconds
of issuer UTC on every attempt, including receipt lookup. The boundary is
inclusive: offsets -60 through +60 seconds are eligible; a larger absolute offset
returns only `OWNER_CLOCK_SKEW`, completion `NOT_COMMITTED`, before ledger lookup
or mutation. This completion describes this refused attempt, not whether a prior
ambiguous consume committed. It must not clear that prior pending binding.
This proves a recently signed request, not that a captured signed request cannot be forwarded within
that window: such forwarding may only return the same bound receipt, never alter
or create a second owner. No prior online challenge is needed. The claim binds
the business; the first valid consumption binds the installation/key. The issuer never receives the local principal record:
`principal_commitment` is SHA-256 of a fresh 32-byte local salt plus canonical
stable native-principal record; the salt and native fields remain in protected
host custody. This closed record is `platform` (linux/windows), `machine_id`
(immutable protected deployment UUID), `principal_id` (Linux integer UID or
Windows SID parsed by the native SID API), and `account_generation` (positive
host authority revision). It excludes PID/session/incarnation, which change on
restart. Current process/session facts are verified afresh during every recovery;
they cannot change the stable principal or initialization digest. Linux account
directory changes invalidate sessions and advance authority generation; recreated
UIDs cannot inherit an earlier mapping. Windows recreated accounts have new SIDs.
The qualification must exercise this invalidation rather than assume name reuse
is safe. The local initialization digest covers immutable deployment/org, native binding,
initial role `admin`, operation and commitment. Salt/key/operation are durable
before sending and cannot change on recovery. An attempt with a different key,
missing signature or stale proof cannot recover a receipt; possession of a
returned receipt is never sufficient to publish local authority.

**Issuer transaction and replay:** verify envelope/purpose, request shape and
installation signature first; then apply the attempt-time rule and its sole
`OWNER_CLOCK_SKEW` outcome, all before any ledger lookup. An invalid signature
cannot elicit an authenticated clock-skew classification.
The single request validator compares binding claim/org/entitlement/generation
and claim digest against the verified signed claim; no independently valid but
mismatched pair may reach the ledger. In one durable writer transaction, serialize by
`claim_id` with a unique claim row and unique operation identity. Exact consumed
binding returns the stored signed receipt even after claim expiry; changed
operation, installation/key, principal/payload or business fails with
`OWNER_BINDING_CONFLICT`. Replay still verifies possession; a copied result is
not authentication. For a new consumption, check active generation, unreplaced,
unrevoked/unexpired claim, then atomically store consumed binding and signed receipt before responding. A revoke
or reissue uses the same claim lock and generation check. No cache-as-authority,
check-then-insert race or receipt generated only after commit. Database failure
must roll back both rows; a crash after commit replays the stored receipt.

Revocation before consume wins; consume before revocation keeps the existing
owner. Reissue an unconsumed claim only in the same transaction that supersedes
its prior generation. Post-consumption recovery cannot elect another owner.
Revoke/reissue is a licensing-admin operation authenticated through that owner's
separately approved provisioning channel, never by possession of the leaked
claim. No public revoke/reissue endpoint is added to the CA client. A restored
issuer backup starts `RECOVERY_LOCKED` until ledger continuity is proven against
its durable journal; it must not resume issuance from a rollback that revives a
claim. This recovery behavior requires issuer-side qualification, not CA SQL.

**Bounds and outcomes for the consume endpoint:** request 8192 bytes, response
4096 bytes (including its bounded receipt envelope above), decompression
and redirects disabled. TLS server verification mandatory; qualification TLS
trust cannot be enabled in a production build. Connect timeout 3 seconds, total
call deadline 10 seconds, no automatic retry or hidden refresh/health call. One
normal first-launch consumption operation; user-initiated recovery may replay
only that frozen operation with a new authenticated attempt. Network silence
after dispatch is `UNKNOWN`, never a definite rollback. Existing licence checks remain separate and unchanged.

| Outcome | Result and permitted next action |
| --- | --- |
| Verified `CONSUMED` receipt | Verify issuer purpose/key/signature, exact binding and consumed_at within the signed claim validity interval, then recheck fresh native identity/state and claim validity before local commit. Persist receipt and owner/admin/audit atomically. A receipt alone never creates authority for a different local person. |
| `OWNER_AUTHORIZATION_REQUIRED` | No companion claim, including a hand-signed licence alone. Licence remains valid; no bootstrap request or admin write. |
| `OWNER_AUTHORIZATION_INVALID`, `OWNER_AUTHORIZATION_EXPIRED`, `OWNER_AUTHORIZATION_REVOKED`, `OWNER_BINDING_CONFLICT` | Deterministic refusal; no admin publication. Do not substitute another person/claim automatically. |
| `OWNER_CLOCK_SKEW` | Authenticated, otherwise well-formed attempt outside the 60-second clock window; completion `NOT_COMMITTED` for this attempt. User message: "Your computer clock differs from the licensing service. Correct the clock, then retry owner setup." Preserve any pending operation/receipt and obtain fresh native verification. After clock correction, sign a fresh attempt/time for the same operation, claim, key and initialization binding; do not mint another owner or silently change the clock. Apply this recovery to receipt lookup as well as first consumption. |
| `LICENSING_UNAVAILABLE` | Missing endpoint, TLS/transport/timeout, stale/unverifiable response or unavailable service. Preserve any pending operation with completion `UNKNOWN` if dispatch could have occurred. Tell the user first-launch setup could not complete; offer only explicit recovery of that operation. |
| `BOOTSTRAP_BUSY`, `NATIVE_AUTH_UNAVAILABLE`, `NATIVE_AUTH_DENIED`, `NATIVE_SESSION_INACTIVE`, `AUTHORITY_CORRUPT` | Local-only closed outcomes. No licensing call until native proof is valid and no owner authority on refusal. Shared credentials are unsupported; do not pretend to detect them from a username. |

The issuer may use HTTP 200 for a consumed receipt, 400 for malformed requests,
403 for an invalid/revoked claim, 409 for binding conflict, 410 for expired new
consumption, 422 with `OWNER_CLOCK_SKEW` for the clock-window refusal, and 503 for
unavailable/recovery-locked state. HTTP success is not
consumption proof without the bound signed receipt. Oversize/partial/mixed or
unknown-version replies fail closed. Replays after expiry may recover evidence,
but expired native proof or claim never permits local publication; retain the
consumed binding for explicitly authorized recovery rather than freeing it.

**Protected storage/retention:** CA owns an authority-only SQLite database under
its protected service directory: deployment identity, pending binding/salt,
consumed receipt, employee/native mapping and minimal audit. Use one writer
transaction and unique deployment/claim/operation constraints; never write source,
custody or runtime tables. Private installation keys stay in service-only custody,
not the SQLite file or employee config. Keep unresolved intent until reconciled;
keep consumed identity/receipt and replay tombstone for deployment lifetime.
Issuer retains full expired, unconsumed claims for 7 days, minimal consumed/revoked
claim digest/binding/receipt for deployment lifetime, then 90 days after explicit
retirement. No reuse of retired claim/org/install identities. These proposed
retention additions need licensing acceptance; they do not settle that service's
other retention questions. Backups preserve the same ACL/encryption owner and
replay continuity. No secure-erasure or encryption qualification is claimed.

**Review pin versus proof:** B0-I's interface is specified by this section. The
licensing service, signed endpoint manifest, key-purpose publication, transaction
and recovery implementation remain unimplemented/unqualified dependencies. This
contract does not authorize changing or accepting that separate service. Lead
operations acquire no continuing network dependency from owner bootstrap.

This mechanism is **PROPOSED and unqualified**. No employee, grant or session may
be created on the strength of this prose. An unrelated administrator without a
valid scoped authorization must be denied through the supported bootstrap
interface. This does not promise protection from a compromised kernel or an
attacker replacing the protected host/trust anchor; pin that computing boundary.

## Native mechanism pins and protected ownership

### B1: selected native qualification profile

**PROPOSED selection, not native proof.** Qualify local, distinct computer accounts
on Ubuntu 24.04 LTS x86-64 with GNOME 46/Wayland, systemd 255, and PolicyKit1;
and Windows 11 24H2 x64 (build family 26100), local password accounts. This is a
bounded qualification target, not a statement that those guests exist or a
support claim for other desktops, remote/domain/Entra/Hello-only accounts, shared
native credentials or Windows legacy builds. Patched package/build identities
are frozen in the run manifest, never silently upgraded during a run. New native
helper code is qualification-only C17 plus the locked CA Python 3.13 environment;
Windows helper uses Windows SDK 10.0.26100.0, Linux uses distribution GCC 13 and
libpolkit-gobject-1/libsystemd headers. No new production dependency is adopted.

Ubuntu's package catalog documents the chosen
[GNOME 46 family](https://packages.ubuntu.com/noble/gnome-shell) and
[systemd 255 family](https://packages.ubuntu.com/noble/systemd).
These references verify available API families, not an installed guest's build.
The package revision, executable hashes and OS image digest are frozen only after
harness preparation, before requesting run approval. A mismatch stops the run;
qualifying a different platform requires an explicit contract revision.

**Linux boundary:** a root-owned system service exposes a filesystem Unix
`SOCK_SEQPACKET` endpoint under `/run/local-connect-authority/`; directory root
owned, group limited to the disposable test employees, socket 0660. State under
`/var/lib/local-connect-authority/` is root-only, directory 0700/files 0600;
no employee-group access to data/keys. Privileged helper root ownership is part
of the TCB; normal app clients run as employees, never root. Reuse the retained
SCM_CREDENTIALS probe. Receive bounded frames with `SO_PASSCRED`; reject missing,
extra/truncated ancillary data, FD passing, identity changes and oversized frames.
Use kernel sender PID/UID plus held process identity/start time, not JSON identity
or connection-time credentials alone; prove exit/PID-reuse and passed-handle cases.

Resolve sender to `org.freedesktop.login1` session via `GetSessionByPID`, requiring
matching UID, local `seat0`, active graphical session, expected boot/session
identity and unlocked state. Subscribe to session/lock/seat changes and reread at
admission, after waits and before commit/release. `LockedHint` alone is NOT trusted:
the systemd interface permits `SetLockedHint`. On the selected GNOME desktop also
query the session's `org.gnome.ScreenSaver.GetActive` using this exact candidate
connection path. The root service derives the decimal UID from kernel credentials
and root system-bus login1 session data, then constructs only
`unix:path=/run/user/<UID>/bus`. Do not use `DBUS_SESSION_BUS_ADDRESS`, the client's
environment/address, autolaunch or discovery. Connect as root with
`g_dbus_connection_new_for_address_sync`, authentication-client and message-bus
flags, EXTERNAL authentication, cancellable under B1's local I/O deadline; no
anonymous mechanism or switch to an employee helper on failure. If the selected
bus denies root access, deny with `NATIVE_AUTH_UNAVAILABLE` and record that
qualification blocker. The [GIO constructor](https://docs.gtk.org/gio/ctor.DBusConnection.new_for_address_sync.html)
defines the explicit-address client; it is not a lock oracle.

The `/run/user/<UID>` directory and bus socket are employee-owned on the target,
as reported in [oversight's native observation](https://github.com/canfieldjuan/connect-automate/pull/72#discussion_r4437617899),
not newly probed here. The employee can replace the socket and run a fake bus.
Matching socket ownership, `SO_PEERCRED` UID, a bus GUID or a well-known name does
not distinguish that server from the intended bus. A root connection to this
path is therefore an unqualified observation, not proof of trusted lock state.
Lost connection/name owner, shell restart, endpoint replacement or unknown state
must invalidate the host session; do not silently reconnect and trust a new bus.

Run the socket-replacement/fake-bus attack as the FIRST Linux native case, before
normal bootstrap, issuer effects or the remaining test budget. In the isolated
guest, while the actual desktop is locked, the employee unlinks/rebinds its bus
socket, serves a fake message bus and ScreenSaver service returning unlocked,
and also tries clearing `LockedHint`. Test replacement before the first root
connection and after an established connection drops; bus-name replacement alone
is insufficient. The service must deny every forged-unlocked result. Retain the
actual locked-console observation and endpoint/identity evidence. If the fake bus
can authorize the request, report FAIL to Juan with the first defeated owner
(the root service's user-bus/lock observation boundary), preserve evidence and
stop all dependent Linux/native work. No weaker fallback, alternate hint, proxy
check or reset-and-continue is authorized. A connection-denied result alone is
not a platform pass: the later genuine unlocked positive case must also succeed.
These are mandatory proof obligations, not a claim of a proven defense against
socket replacement. Other attacks still cover `SetLockedHint(false)`, ScreenSaver
calls, bus-name replacement and transferred handles.

Fresh sign-in uses system-bus `org.freedesktop.PolicyKit1.Authority.CheckAuthorization`
for root-installed action `org.localconnect.owner-authenticate`. Policy pins:
`allow_any=no`, `allow_inactive=no`, `allow_active=auth_self`; no `*_keep`, implicit
YES or admin substitution. Subject is the kernel-bound process UID/start identity.
Before user interaction require a challenge, not already-authorized YES; then
allow interaction only for the explicit sign-in request through GNOME's native
agent and require successful non-retained authorization. Root-owned policy/rule
hashes and PAM account-disable behavior are frozen and tested. No app password
entry or subprocess `pkexec`/shell escape. Account, session and process are
rechecked after the dialog; a supplied policy-success Boolean is never accepted.
See [PolicyKit1 API](https://polkit.pages.freedesktop.org/polkit/eggdbus-interface-org.freedesktop.PolicyKit1.Authority.html),
[auth_self/retention semantics](https://polkit.pages.freedesktop.org/polkit/polkit.8.html),
[systemd 255 session API](https://www.freedesktop.org/software/systemd/man/255/org.freedesktop.login1.html),
and the [GNOME 46 ScreenSaver interface](https://github.com/GNOME/gnome-shell/blob/46.0/data/dbus-interfaces/org.gnome.ScreenSaver.xml).
These APIs supply the proposed mechanism; their availability does not pass the
fresh-prompt, current-account or lock-spoof tests.

**Windows boundary:** LocalSystem qualification service, private authority path
`%ProgramData%\LocalConnect\Authority`, protected DACL allowing only SYSTEM and
the service SID. Explicit local-only named pipe, `PIPE_REJECT_REMOTE_CLIENTS`,
`FILE_FLAG_FIRST_PIPE_INSTANCE`, bounded message frames and explicit DACL; never
default Everyone/anonymous access. Each message must successfully impersonate its
client, open that thread token and inspect TokenUser SID, TokenSessionId and
TokenStatistics AuthenticationId; fail closed if impersonation or reversion fails.
Client uses dynamic security context tracking; pipe PID/process creation identity,
SID, logon LUID, session, channel and host incarnation bind the request. A token
query failure must never substitute the service token. See
[pipe ACLs](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
and [last-message impersonation](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient).

A trusted desktop broker uses native `CredUIPromptForWindowsCredentialsW` with
`CREDUIWIN_SECURE_PROMPT`, no generic/save/admin-enumeration flags, then the
protected verifier uses `LogonUserW(LOGON32_LOGON_INTERACTIVE)` to authenticate.
The prompt itself is NOT authentication. Compare verified TokenUser SID to the
per-request pipe identity; the new authentication token's LUID is not the original
interactive logon's LUID. Bind the latter from the verified caller token and
recheck it separately. No account-name equality shortcut. Broker credential
buffers traverse only the authenticated local channel to the protected verifier,
are never persisted/logged/dumped, and are zeroed/freed using native APIs on all
paths. Pin broker binary/ACL and prove request/credential swap denial. Synthetic
password entry is operator-controlled on the secure desktop; agents never see
or record it. This password-account qualification does not claim Hello support.
See [CredUI and buffer handling](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw)
and [LogonUserW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-logonuserw).

Require `WTSQuerySessionInformationW(WTSSessionInfoEx)` for that token's session:
active and `WTS_SESSIONSTATE_UNLOCK` only; lock, disconnect, unknown or API failure
denies. Subscribe to WTS session notifications and reread after every wait and
before commit/release. Check local account enablement at those checkpoints.
Per-request impersonation plus fresh sign-in plus current interactive-session
state are separate checks. Prove inherited/duplicated pipe handles and context
changes; if the selected APIs cannot distinguish a transferred authority, fail
qualification instead of claiming an unchanged connection PID proves the sender.
See [WTS flags and legacy-build caveat](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/ns-wtsapi32-wtsinfoex_level1_w).

**Shared host limits:** an individual principal maps to one employee only.
Privileged OS/root replacement is outside the trusted-computing boundary; an
ordinary unrelated employee or an unelevated administrator must fail supported
bootstrap APIs without the valid scoped claim. Sharing credentials is unsupported,
not automatically detectable. Recreated accounts require explicit controlled
re-enrollment, never UID/name reuse fallback. Scope qualification to the frozen
account directory and record this identity-lifetime limitation.

One prompt at a time; queue limit 8, wait deadline 5 seconds, authentication dialog
deadline 120 seconds. Host session is random 32-byte opaque handle, bound to the
native person, original interactive session, authenticated channel/process and
random host incarnation; absolute lifetime 300 seconds, no sliding renewal.
IPC frames use the same 8192-byte request/4096-byte response bounds as B0-I;
the Windows broker's separate credential-buffer exchange is capped at 65536 bytes
and never routed through an ordinary JSON frame. Apply caps before allocation,
with a 5-second local I/O/store wait deadline; timeout denies before authority
publication. Fresh sign-in is usable for bootstrap for at most 60 seconds. Use monotonic
elapsed time and authoritative issuer UTC; backward wall-clock movement or a
wall/monotonic discrepancy over 30 seconds invalidates pending authentication.
Forward wall movement cannot extend validity. On lock/logout/disable/role change,
unknown state or restart invalidate immediately at the next observation; unlocking
does not revive a handle. No claim of atomicity with independent OS events.

This selection supersedes the older proposal's unselected native candidates
for this bounded qualification only. It does not qualify the
[protected-read host gate](LEAD-PROTECTED-READ.md#canonical-host-gate-requirements)
or expose any custody endpoint. B1's choices are pinned; both-platform success,
fresh-account verification and Linux lock-spoof resistance remain proof gates.

| Owner | Required boundary in this qualification | Excluded responsibility |
| --- | --- | --- |
| Licensing/release owner, using existing issuer trust chain | Issue a business-scoped companion claim; bind installation/key proof and opaque native/payload commitment at consumption; own revoke/reissue and bound receipts under B0-I | Native employee authentication, lead data, granting ownership from installer privilege or a new identity cloud service |
| Existing Connect/Automate protected host seam | Own installation identity, immutable org scope, employee enrollment/role, bootstrap consumption, host sessions and authority versions | Source/custody/workflow SQL or a second scheduler/lead store |
| Native adapter under that host | Verify current caller/person/session and perform fresh native authentication using pinned mechanisms | Trusting webview JSON, an account name/PID alone, a copied result or a transport bearer |
| Existing policy evaluator | Evaluate the existing closed human-operation catalog using host-acquired facts | Becoming a native credential verifier or accepting a machine as an employee |
| Existing source/custody/runtime owners | Remain unchanged regression references | Being exposed to employee clients during this qualification |

The protected host owns authority state through one access interface, using
B0-I's record/transaction ownership and B1's protected service directories.
Concrete SQL DDL and migration parity are reviewed with the harness/implementation;
they cannot add new owners or change these invariants. No second custody store or cross-owner SQL
is permitted. Normal employee processes must be unable to read, replace, restore
or impersonate protected state/keystore. Test same-user exposure explicitly;
private filenames or file modes under the employee's own identity are insufficient.

Machine grants remain absent in V1b.1. Successful owner bootstrap/sign-in does
not publish source keys or authorize a sender, rule, route, content read or
custody operation. Do not extend `_host_policy`'s catalog to disguise enrollment
or machine delegation as an existing human operation.

## Required qualification behavior and failure/recovery contract

These are proof obligations for a later, explicitly authorized disposable run;
they are not implemented APIs or approval to run now.

1. Verify installation and the purpose-specific license-backed authorization
   before opening a bootstrap mutation. Authenticate its holder natively and bind
   the request channel; reject unknown/locked/shared-account identities and
   ordinary licenses presented as owner claims.
2. The licensing owner serializes claim consumption against revoke/reissue; the
   protected host serializes local bootstrap. Follow the pending-operation and
   receipt protocol above. After waits, recheck claim, validity and native state.
   Initialize immutable installation/org identity, individual owner/admin mapping,
   consumed receipt and minimal audit in the same local transaction. Concurrent
   callers cannot elect different owners or create partial local admin state.
3. Recheck the relevant authority and native state before commit and before
   releasing a result. Define the adapter's observation point honestly: a host
   lock cannot control an independent OS lock/logout event. Unknown state denies;
   no claim of atomicity across OS state and SQLite.
4. Exact authenticated bootstrap replay may recover the same committed outcome;
   a changed scope/person/payload/operation is a conflict, never a new bootstrap.
   A lost response or post-commit crash does not justify deleting/reinitializing
   authority. Corrupt/missing-after-initialization state requires controlled
   recovery, not fallback to an empty store. Crash before commit leaves no partial
   identity, role, audit or locally consumed proof. Issuer-side consumption may
   already have committed; recover its receipt rather than declaring rollback
   across the application boundary or making the claim reusable.
5. Native sign-in maps a verified person to the existing individual employee,
   immutable org and current role. Session handles and finite session/freshness,
   queue, frame and clock limits use B1's single profile above. Possession of a
   copied handle is insufficient; no sliding/default-unbounded session.
6. Logout, disablement, role change, expiry, lock and restart deny further
   interactive use. Check after waits and before any response. Test both orders
   of revocation versus session issuance/validation. A locked human session does
   not erase a future already-delegated machine grant; that separate authority is
   not created or exercised here.
7. No personal-data response or privileged business effect is reachable. The
   qualification result contains only synthetic references, selected native
   mechanism, outcome and evidence identity. Keep secrets and authentication
   conversations outside ordinary records, logs, command lines and public CI
   artifacts. Agents never read or copy real credentials.

Do not borrow the source database lock as employee authorization or claim a
cross-store transaction. This first qualification touches no source transaction.
Later cross-owner enforcement must explicitly adopt or supersede the proposed
[protected-read host-gate ordering](LEAD-PROTECTED-READ.md#canonical-host-gate-requirements)
in its own accepted contract, including busy waits, finite queues, fairness,
response bounds and owner death. That proposed gate is not implemented here.

## Proof matrix and executable acceptance gates

### B2: disposable qualification work order and freeze protocol

**Contract pin, no run authorization.** Prepare the harness in a separately
accepted implementation PR after review of this revision. Proposed owned paths
(not files claimed to exist): `qualification/owner_authority/controller.py`,
`licensing_fixture.py`, `linux_peer.c`, `windows_peer.c`, `native_broker.c`,
`cases.json`, `run.schema.json`, `result.schema.json`, and `README.md`. The harness
must call the same proposed verifier/adapter boundary on each platform, with the
retained Linux credential probe as the regression reference. It is not a new
workflow engine or production issuer. CI may test synthetic wire/ledger cases;
native desktop/account proof has its own run authorization.

**Environments:** two new disposable VM overlays, one per selected target above,
cloned from operator-approved, shut-down images. Do not use a live employee desktop,
reset an existing VM password, inspect existing accounts or assume prior Windows
access. Each guest contains synthetic principals `li_owner`, `li_other` and
`li_admin_test` (an unrelated administrator), plus its protected service. Guest
local console only, no shared clipboard/folders, no mail/database/cloud secrets,
no bridged NIC or production registry; default-deny guest egress. The licensing
fixture runs inside each guest over loopback TLS using ephemeral test keys/CA;
no production keyring mutation or runtime trust override. Freeze the baseline
before account/service setup; setup and teardown are limited to these overlays.
If an image or the operator's native-password entry is unavailable, record STOP;
no host change, password recovery or Linux mock substitution.

**Freeze-before-run sequence:**

1. Review/accept this contract, then separately authorize building the bounded
   harness. Independently review its exact commit and wire/negative fixtures.
2. Create a secret-free `run.json` in durable evidence with full contract/harness
   commits, executable/fixture/policy hashes, base-image SHA-256 and overlay IDs,
   OS build/kernel, GNOME/systemd/polkit/PAM and compiler/SDK package revisions,
   locked Python dependency digest, service/principal aliases, trust policy,
   isolation/network policy, exact setup/run/teardown argv and evidence paths.
   These observed content hashes cannot truthfully be invented before the files
   or guest exist. No mutable `latest`, unresolved variable or missing hash is
   runnable; a hash-only preparation receipt is not qualification.
3. Send that frozen manifest and bounded setup/run/teardown scope for oversight
   and Juan's explicit native-run authorization. This review-only revision does
   not authorize provisioning or generating passwords/keys now.
4. On the approved fresh overlays, freeze image/package state and execute only
   the reviewed entrypoints. Controller interface is pinned as
   `controller.py preflight --manifest <run.json>`,
   `controller.py run --manifest <run.json> --platform linux|windows`, and
   `controller.py collect --manifest <run.json>`. `<run.json>` resolves to one
   approved absolute path in the receipt; no shell interpolation or guessed path.
   Preflight validates every frozen hash, guest identity and deny-egress rule
   before any native setup. A mismatch produces STOP without executing the run.
5. Collect/review before teardown. Remove only the specifically authorized test
   overlays and service/accounts inside them; preserve durable evidence. Operator
   approval of teardown names the exact overlays, never a wildcard or host path.

**Finite cases and verdicts:** the FIRST Linux native case is B1's socket-replacement
and fake-user-bus gate, including initial connect and reconnect while the real
desktop stays locked. Failure is sent to Juan and stops dependent work before
any normal bootstrap/consumption or the remaining Linux matrix. Then, only if
that gate is not defeated, execute every proof-matrix row below on each platform.
Ordinary lifecycle and boundary fixtures use the same public synthetic identities. Test min-1/min/max/max+1 for every declared bound, false/zero/empty/
unknown enum, mixed valid-invalid and individually isolated corruptions. Required
negative cases include ordinary/offline licence without claim; invalid signature,
wrong purpose/org; simultaneous initial installations; revoked/expired claim;
changed native/key/payload replay; service down before send; signed reply lost
after issuer commit; issuer and host restart; restore attempting claim reuse;
cancellation/timeout and native session change while waiting; direct file/key
access; transferred handles; replaced user-bus socket/fake server and spoofed
Linux lock state; disabled/recreated account. Issuance fixtures must include a
purchase more than 86400 seconds before first launch, valid activation-time
issuance, and an unconsumed claim expiring after activation followed by explicit
activation renewal. Clock fixtures use -61/-60/-59/0/+59/+60/+61 seconds for both
new consumption and pending-receipt lookup: only the out-of-window cases return
`OWNER_CLOCK_SKEW`/`NOT_COMMITTED`, no ledger writes, prior ambiguity retained;
clock correction and a fresh signed attempt recover the same operation/binding.

Manifest-size fixtures derive from B0-I's single wire-budget table. Include
both arrays at maximum cardinality and ID length with a valid maximum-length
origin and maximum envelope key ID; assert that payload, encoding and envelope
all fit and preserve exact bytes. Add origin length 256 (otherwise valid URI),
an array with 17 distinct IDs, and a 65-character ID as independent max+1 schema
negatives. Exercise each type's encoded/decoded/envelope boundary plus one with
untrusted over-limit input; assert the intended early cap rejects before signature
or model admission, without truncation. Do not invent a schema-valid payload at
the aggregate cap when the field-derived maximum is smaller: record that size
as unreachable for a valid model. A manifest over the smaller claim/receipt cap
must succeed only in the manifest context; supplying it as a claim or consume
receipt must refuse. Keep the ordinary consume/IPC response caps unchanged.
These are required future fixtures, not a new harness or test execution here.

Instrument exact barriers at native validation, issuer lookup/transition/commit,
local pending/receipt/admin/audit writes, local commit and result release. For
each two-way race exercise both winners, three repetitions per order using
separate processes and explicit barriers, no sleeps as proof. Inject an SQL
failure between each row write and terminate the process before/after each commit.
Assertions inspect both owners through their supported interfaces: no partial
admin state, no duplicate consumption or replacement owner, same replay receipt,
no publication while denied, and no hidden licensing call during subsequent
synthetic host operations. Barrier/test interfaces exist only in the harness.
No lead/custody read or live workflow is exercised to prove this profile.

Case deadline 180 seconds, platform budget 3600 seconds, at most one guest test
at a time. A watchdog timeout preserves evidence and fails that case; no unbounded
retry. Overall result PASS only if every mandatory case on both native targets
passes with assertions and no unreviewed environment drift. FAIL for an observed
invariant violation; STOP for missing access/approval/environment; neither counts
as pass. No automatic rerun after a security or data-integrity failure: reproduce,
isolate the first losing owner, explain it and fix there in a separately reviewed
harness/adapter delta. No production adoption follows a green packet.

**Evidence:** save `run.json`, sanitized per-case JSONL, native result codes,
barrier/commit receipts, deny-egress counters, fixture/adapter digests and a
SHA-256 manifest outside worktrees under
`~/Desktop/codex-evidence/connect-automate/lead-owner-authority-qualification/<run-id>/`.
Directories 0700/files 0600 on the evidence owner, equivalent guest ACLs. Result
schema is closed: contract/harness/run IDs, case/platform, outcome PASS/FAIL/STOP,
expected and actual code, assertion IDs, public synthetic fixture digest, monotonic
duration and artifact hashes. Never capture credential dialogs/keystrokes, private
keys, native account names beyond fixture aliases, raw source content or memory
dumps. Synthetic fixture envelopes may be retained; secrets may not. Keep packets
through independent review; removal requires operator instruction. No evidence
exists yet for this new profile. B2's plan is pinned; hashes and approval of the
later executable freeze are a distinct execution gate, not an unspecified plan.

| Required proof | Decisive assertions; evidence to retain |
| --- | --- |
| Owner authority | An issued business-scoped claim needs no pre-existing installation/key. A valid consumption request with fresh native holder and actual host-key proof succeeds; unrelated employee/admin/installer without the claim cannot self-enroll. Wrong-purpose/issuer-key, forged, missing, revoked, expired, wrong-organization or invalid host-key proof fails without authority writes. Test actual provenance verification with disposable issuer keys, not a pretrusted boolean. A leaked unconsumed claim can be won by another eligible holder: preserve that trust limit. |
| Claim lifecycle | Both consumption/revocation orders, atomic supersession/reissue, competing initial installations, and copied consumed claim replay from a different installation/key/person. Exact consumed bindings are immutable; restored local state cannot rebind them. Same operation resumes after issuer or host crash/lost response; changed principal/payload fails. Already consumed claims cannot create replacement admins. Compromise recovery requires independent licensing authority. Pin and exercise the real B0-I mechanism before claiming one-use or current revocation. |
| Offline/availability and dependency boundary | A valid hand-signed entitlement alone returns `OWNER_AUTHORIZATION_REQUIRED` without admin writes or invalidating the licence. A valid companion claim with disconnected, unavailable, stale or unverifiable consumption returns `LICENSING_UNAVAILABLE`; an ambiguous response retains the same pending operation. Prove the normal first-launch path uses one authoritative consumption call and has no prior host-key handshake. After bootstrap, lead operations add no licensing-status calls. Existing v1 feature checks remain unchanged. |
| Native identity | Real caller/person/session binding; claimed actor, inherited/transferred handle, sender change, process exit/reuse, account reuse and shared-account ambiguity cannot impersonate the owner. Fresh sign-in is independent of channel identity. |
| Bootstrap linearization | Separate native processes, exact barriers, both winner orders, repeated initialization, SQL fault between writes and forced exit before/after commit. Same authenticated replay recovers the same identity; conflicts never overwrite it. |
| Session lifecycle | Locked/unlocked/unknown, logout, expiry, disable/role change and restart; revocation during a busy wait and before release. Copied handles/results, false/zero/default windows and concurrent renewals fail according to pinned rules. |
| Isolation and secrets | Actual unrelated employee cannot directly read/replace authority, keystore or source paths, including indirect restore/reparse/symlink access. Encryption and backup protection are separate proofs, not inferred from ACLs. No raw credential in diagnostics or evidence. |
| No effects / parity | Existing entitlement-v1/policy/source/custody/runtime schemas and tests unchanged; no production issuance, Connect registration, provider discovery, source authority publication, body read, Gmail, workflow dispatch or lead creation. Only an expressly authorized disposable B0-I harness may exercise claim lifecycle; deny all unapproved external calls. Assert denied calls, not just an empty result. |
| Two-platform qualification | Native Linux and Windows result packets use the same invariants and retain platform-specific blockers. Linux mocks do not pass Windows; a green existing Windows custody suite does not prove the new native boundary. |

Each new security guard needs otherwise-valid independent negative fixtures,
valid/invalid/partial/falsy/boundary probes and a deliberate fault that the
intended assertion catches. Record equivalent or unreachable mutations honestly.
Reuse the existing Linux credential probe and existing regression owners; native
adapters must be tested through real process/account/session boundaries. No
sleep-based race proof, synthetic admin grants presented as genuine authority,
or undocumented provisioned state. Record ordinary failures and ambiguous commit
outcomes as well as successes; do not count a missing test environment as a pass.

Acceptance sequence:

- Review B0-I's specified interface/retention additions, B1's selected native
  profile and B2's bounded freeze/run sequence at this exact revision. Licensing
  owner accepts its own work order separately; existing licence behavior remains
  unchanged. No further product or connectivity change is implied by earlier
  direction. Harness preparation and the later frozen native run need their own
  explicit authorization, as specified above.
- Oversight review of the exact revision, explicit operator acceptance of that
  bounded work/run order, and contract CI/connector/merge gates. Docs acceptance
  alone does not authorize unspecified account/service setup.
- Separately authorized native qualification, then recorded independent review of
  its exact evidence. A failed platform blocks its dependent enforcement.
- Only then propose the bounded executable host-authority work order. Subsequent
  V1b contracts pin admin-delegated machine grants, proof wire formats and durable
  replay/revocation at owning operations, authenticated GET results and the thin
  Connect v2 provider. No receiver activation is granted by this work order.

## Required change surface, non-scope and rollback

This PR changes only this proposed contract and the receiver roadmap's completed
V1a/next-work pointer. It preserves the entire accepted vertical plan and V1a
work order, all source/tests, schemas, dependency pins, workflows and runtime
configuration. The non-blocking malformed-refusal, activation-manifest renewal
and failed-PC recovery questions from this review are deferred to [issue #73](https://github.com/canfieldjuan/connect-automate/issues/73),
not resolved or implemented here. The existing malformed `handoff_id`
negative-test gap noted on PR #71 stays deferred until that test file is next touched; no incidental test
change belongs in this contract PR.

Future qualification evidence belongs outside worktrees in the durable evidence
root, with private directory/file permissions and equivalent native ACL proof.
Its proposed files, controller entrypoints and exact freeze protocol are pinned
under B2. Their future content hashes and the approved guest/setup manifest must
be reviewed before a run; no placeholder code or probe is added by this PR.

Non-scope: production signing keys, license issuance or issuer/service changes,
real users/credentials, installed host changes, receiver/transport
activation, account or service provisioning, Gmail/OAuth, source capture or lead
extraction, canonical lead records, UI, CRM/EOM, automatic package adoption and
the shared AI inference runtime. No new workflow engine, polling/dispatch service,
public API or cloud identity dependency. No parallel EW or shared-runtime work.

Rollback of this proposal is a documentation revert. A future qualification must
have an accepted disposable-environment teardown plan. Do not reset a protected
identity, alter current stores or remove retained proof to make a run repeatable.
For future executable authority, disabling exposure must preserve identity and
audit/replay state; its recovery/rollback is a separate acceptance input.

## Implementation summary, cold diff audit and gap audit

**Contract preparation only.** The concrete next slice is the authority
prerequisite of V1b, not V1c template discovery or another custody expansion.
Cold-audit checks: ordering against the accepted plan; source citations at the
pinned merge; prior evidence hashes; owner/native trust separation; first-admin
decision attributed to oversight's operator relay; entitlement reuse and strict
v1 compatibility; issue-time/consumption-time bindings separated, offline-licence
outcomes explicit and first-launch dependency limited to the actual decision; no changed
accepted text or executable files.
Run documentation scope/link/citation/whitespace checks only. Do not rerun code
tests or represent historical primitive/custody results as native sign-in proof.

**DONE for contract preparation:** B0-I wire/ownership/recovery/retention profile,
B1 native API and platform selection, and B2 bounded disposable harness/freeze/run
plan are specified for independent review. They are proposals, not tested behavior.

**NOT DONE for execution:** licensing-side acceptance/implementation and signed
endpoint publication, oversight/connector review of this revision, Juan's
exact-revision acceptance, separately authorized harness implementation and
hash-frozen native run, qualification, integrated enforcement and later V1b
activation. Linux lock resistance may fail qualification and remains an explicit
safety gate. Publish the documentation-only revision and stop for review; no
merge, production claim or executable authority is implied.
