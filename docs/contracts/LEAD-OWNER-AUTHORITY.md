# V1b.1: owner bootstrap and native admin qualification

Status: **PROPOSED, CONTRACT ONLY. B0-I licensing interface, B1 native mechanisms
and B2 qualification plan (Linux VM, Windows 11 dev-drive boot, one Windows 10
VM) are specified below for review. PR72 acceptance is ON HOLD at Juan's direction. Windows ships in the
first release; local passwords, Microsoft accounts and Windows Hello are required
qualification coverage, not exclusions. They are not implemented or qualified.
Licensing-side acceptance, oversight of this revision,
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
a native admin session. Use synthetic identities in the unchanged Linux VM lane
and dedicated test accounts on Juan's Windows 11 dev-drive boot plus one
Windows 10 VM, only on his explicit go. Deliver a reproducible feasibility packet
and
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

The issuer may use HTTP 200 for a consumed receipt, 400 as specified in
[Malformed consume requests](#malformed-consume-requests),
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

#### Malformed consume requests

**Proposed contract amendment for [issue #73](https://github.com/canfieldjuan/connect-automate/issues/73).**
The HTTP mapping allows 400 when the request fails wire validation. The
operation-bound `Refusal` requires a UUIDv4 operation ID, which may be absent,
ambiguous or invalid at that boundary. Use a separate response so malformed
input cannot supply an operation identity or a completion claim.

The licensing owner's consume endpoint applies its existing request byte cap,
strict JSON decoder and closed `ConsumeRequest` validation before using any
request field as authority. If that wire validation fails and the endpoint
can return a response, it sends HTTP 400 with `Content-Type: application/json`
and this canonical UTF-8 body:

```json
{"code":"MALFORMED_CONSUME_REQUEST","version":"owner-bootstrap/1"}
```

The response body schema is closed:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "code": {"const": "MALFORMED_CONSUME_REQUEST"},
    "version": {"const": "owner-bootstrap/1"}
  },
  "required": ["code", "version"],
  "additionalProperties": false
}
```

The same response applies even if a rejected request appears to contain a valid
operation ID. This branch uses no request-derived data in the response, performs
no claim or operation lookup, and writes no consumption, receipt or
operation-linked audit record. It does not extract an ID from a rejected
document. Well-formed requests continue through the existing claim and
installation proof, binding and clock checks before any ledger access.
An invalid signature on a well-formed request stays on that verification path.

The CA client recognizes this diagnostic only with HTTP 400,
`application/json` and the canonical body defined here, under the existing
response byte cap and strict decoding rules. A different status with that
body, a different 400 body, or a transport-layer rejection follows the
existing unverifiable-response handling. A recognized
400 also uses the existing `LICENSING_UNAVAILABLE` outcome. If dispatch may
have occurred, the client keeps any pending binding with completion
`UNKNOWN`, including when this response follows an earlier lost response.
It neither clears the pending operation nor grants authority or triggers an
automatic retry. Explicit recovery still requires a fresh authenticated
attempt for the same binding. Only the existing verified receipt and local
checks can permit publication.

Synthetic acceptance examples for a later implementation:

| Input or sequence | Required observation |
| --- | --- |
| Truncated JSON, duplicate members, a missing binding, missing or invalid operation ID, or an over-cap body | Endpoint rejection before ledger access. If the endpoint responds, it sends the fixed 400 body. |
| Valid-looking operation ID with a missing attempt ID | The same 400 body, without echoing the operation ID or accessing the ledger. |
| Structurally valid request with an invalid installation signature | The existing verification path refuses before ledger access. It cannot yield the malformed-wire diagnostic or an authenticated clock-skew classification. |
| Valid signed control with a fresh attempt for the frozen binding | The existing consume or receipt-recovery path runs and returns its existing bound outcome. |
| 400 with an extra `operation_id` or `completion`, a duplicate field, or a missing or wrong literal | The client rejects the body. The fixed body on a non-400 response is also rejected. |
| Earlier issuer commit followed by response loss, then a 400 during recovery | The client preserves the original pending binding and `UNKNOWN` completion, with no authority publication or automatic retry. A later explicit, authenticated replay of the original binding can recover the same signed receipt. |

This proposal requires independent review and Juan's exact-revision acceptance.
The licensing owner must separately accept its implementation work order. The
H1 case stays blocked pending an accepted follow-up. Manifest renewal, device
replacement, inaccessible-disk evidence, native sign-in, Hello, Gmail and live
activation remain outside this slice.

#### Expired activation manifests during pending recovery

**Proposed contract amendment for [issue #73](https://github.com/canfieldjuan/connect-automate/issues/73).**
A pending consume operation can outlive the activation manifest needed to
authenticate its next attempt and receipt. The existing expiry check blocks
that attempt, while the configuration-renewal owner and recovery sequence are
unspecified. The pending operation remains durable with its original binding.

The licensing/release owner publishes the replacement manifest through normal
licence activation. CA's protected activation-configuration owner validates and
installs it. The user explicitly requests configuration renewal through that
activation path, then explicitly resumes the saved owner-setup operation.
Neither opening the app nor a failed consume attempt starts renewal, a refresh,
a health call or an automatic retry. If the licensing owner has no accepted
renewal operation, recovery stays `LICENSING_UNAVAILABLE`.

This bounded renewal changes the validity interval of the previously admitted
`ActivationManifest`. Its version, purpose, HTTPS origin and claim/receipt
key-ID sets must match both the original retained and currently installed
manifests. Validation uses the installed release authority and
the existing closed manifest schema, wire budget and key-purpose rules. The
replacement must satisfy `issued_at <= now < expires_at`, have an expiry later
than both the original retained manifest's expiry and the currently installed
manifest's expiry, and have an issue time no earlier than either manifest's
issue time. The existing maximum validity interval still applies. These bounds
apply on every renewal, including successive renewals. Read the installed signed
manifest from the protected configuration owner, never from a caller assertion
or a stale in-memory copy. A missing or unverifiable installed manifest blocks
this renewal path. Endpoint migration, claim/receipt key-policy changes and trust
installation require their own accepted work order.

The installed-state comparison is a proposed contract refinement for issue #73;
its exact revision requires Juan's acceptance before implementation. The bounded
[offline renewal work order](LEAD-OWNER-MANIFEST-RENEWAL.md) proposes its later
synthetic proof without authorizing a production or native renewal path.

Retain the previously admitted signed manifest with the saved operation so
that its policy can be compared without treating its expired interval as
current authority. An absent or unverifiable retained manifest blocks this
renewal path. Publish the fully verified replacement through the protected
configuration writer atomically. Recheck that the pending operation, its
original retained manifest and the currently installed signed manifest are still
the ones the user selected, under the same protected-host writer serialization
as publication. A changed installed selection requires explicit reselection;
never silently rebase or retry a renewal against another configuration.
A validation, write or concurrent-state failure preserves the saved operation
and its last complete configuration.

Renewal cannot consume, revoke, reissue or replace an owner claim. It preserves
the original signed claim bytes, operation, installation/key, business,
principal commitment, initialization digest and any retained receipt. The
protected host checks the replacement manifest again when the user resumes,
obtains fresh native verification under the existing rules, and signs a new
attempt/time for that same durable binding. The original consumption/replay
owner decides the outcome. An expired claim can still recover a previously
consumed receipt under the existing replay rule, while the existing local
claim-validity and native checks continue to gate publication.

An unsuccessful renewal or replay keeps unresolved completion `UNKNOWN` and
the same pending binding. Configuration renewal alone never grants owner/admin
authority or turns an ambiguous dispatch into `NOT_COMMITTED`. Established
lead operations retain their existing local authorization behavior.

Synthetic acceptance examples for a later implementation:

| Input or sequence | Required observation |
| --- | --- |
| Expired manifest and a saved pending operation, without a user renewal action | `LICENSING_UNAVAILABLE`, retained binding and receipt, and no renewal or consume call. |
| Explicit renewal with the same policy and a valid later interval | Protected configuration publication only. A separate explicit resume makes one fresh authenticated attempt for the saved binding. |
| Wrong release authority, missing key purpose, changed origin/key-ID sets, future issue time, expired replacement or non-advancing expiry | Refusal before configuration publication, with the pending operation retained. |
| A second candidate is later than the original retained manifest but regresses the installed issue time or fails to advance its expiry | Refuse configuration publication; preserve the newer installed manifest and original pending evidence. |
| Otherwise valid candidate with regressed issue time or a validity interval over the existing maximum | Refuse before publication; do not replace or reinterpret the saved operation. |
| Renewal failure or a different pending operation, retained manifest or installed configuration appearing before publication | Preserve the last complete configuration and the selected pending operation's evidence. Require a new explicit selection before another attempt. |
| Issuer commit, response loss, manifest expiry, then successful renewal and explicit replay | Recover the same signed consumed receipt. Publish only after the original local validity and fresh native checks pass. |
| The same sequence with an expired claim, invalid native proof or another lost response | Preserve the original binding and receipt evidence with no local authority publication or automatic retry. |

Independent review and Juan's exact-revision acceptance are required. Licensing
implementation and an offline renewal fixture need separate accepted work
orders. The H1 catalog entry remains blocked. Native sign-in, Hello, Gmail and
live activation remain on hold.

#### Failed or replaced PC recovery

**Proposed contract amendment for [issue #73](https://github.com/canfieldjuan/connect-automate/issues/73).**
The licensing owner retains the original consumed claim, exact installation
binding and receipt. A failed PC, missing local database, restored backup or
replacement key does not make that claim available for first-admin bootstrap.
The existing consume endpoint continues to refuse a changed binding.

When the original installation can still prove its original protected key,
native-person binding and pending operation, use its existing authenticated
replay path with fresh verification. A restored store must pass its existing
continuity checks before it can supply authority. Loss of that proof enters
the separate replacement-recovery process below.

The licensing administrator owns replacement approval through the licensing
owner's separately approved administrative provisioning channel. Approval
requires independent verification of the requester's authority for the same
business and entitlement under an explicitly accepted recovery policy.
A licence, old claim, receipt, email address, local account or installer
privilege alone cannot meet that requirement. The licensing owner must supply
the concrete verification policy for acceptance before this path becomes
available. This proposal does not select new identity documents or an identity
service.

The licensing owner opens an auditable recovery case against the original
consumed deployment. It records the approving administrative identity and
accepted policy revision, verified business/entitlement, predecessor claim
and consumed binding, the evidence references and the requested replacement
binding. That binding includes a new installation/host/key and operation,
freshly verified replacement native-person commitment and initialization
digest. Native credentials and source documents stay outside the case.
Possession of a case reference supplies no host authority.

Before approving a replacement for publication, the licensing owner must
determine the predecessor's authoritative consumption outcome and the
protected-host owner must prove that its old authority has been disabled.
The old host's qualified retirement mechanism must persist that decision,
invalidate its admin sessions and machine grants, and preserve history.
Qualification must establish that supported restart or restore cannot revive
that authority. Disabling an issuer claim or recording a support decision
alone cannot prove those local effects.

An unreachable predecessor has no proven disablement under the current local
operation policy. In that case replacement publication stays blocked,
including when the requester's business authority is verified. A hardware
failure report or an assumed lost disk cannot satisfy the disablement gate.
Supporting replacement without that proof requires Juan's separate product
decision and an accepted enforcement contract. Ordinary lead operations gain
no licensing polling or background revocation dependency from this proposal.

The licensing owner's durable writer serializes recovery approval against
the predecessor and any competing replacement case. It permits one selected
replacement binding at a time. Exact administrative retries resume the same
case and binding; changed targets or competing approvals require a new
decision and cannot overwrite an admitted binding. Preserve an uncertain
predecessor outcome and every partial approval or failed publication.
There is no transaction spanning the licensing ledger and either host.

A separately accepted recovery protocol must bind any executable replacement
authorization to that case, predecessor, verified business/entitlement and
exact replacement binding. It must specify its closed wire models, signing
purpose, bounds, validity, replay, revocation and receipts before use. Ordinary
owner claims and consumed receipts retain their existing purposes. The new
host publishes its owner/admin record only after the recovery authorization,
predecessor-disablement evidence and fresh native proof all pass, in its own
protected authority transaction. The linked recovery history preserves the
original consumed record and every subsequent replacement.

Synthetic acceptance examples for a later recovery work order:

| Input or sequence | Required observation |
| --- | --- |
| Original installation, original proof and an unresolved response | Existing same-binding replay with fresh authentication; the stored consumed receipt remains bound to that installation. |
| Otherwise-valid signed consume request using a consumed claim with a changed installation/key/person commitment | Existing binding conflict and no replacement authority. |
| Copied receipt presented without fresh proof of the original binding | Existing proof verification refuses authority publication. |
| Verified business requester, exact replacement binding, determined predecessor outcome and qualified old-host disablement | A separately accepted recovery protocol may admit the linked replacement. The original consumed row remains immutable. |
| Verified requester but unreachable old PC, missing retirement proof or unsupported restore behavior | Replacement publication remains blocked with history retained. |
| Lost response with unknown predecessor consumption, or an unverified requester's business authority | Preserve the unresolved case. No assumed unconsumed claim, replacement approval or local authority publication. |
| Two approvals for different replacements, or a retry after a partial write | Serialize the case and preserve the selected binding. An exact retry resumes; another target cannot silently replace it. |

Independent oversight and Juan's exact-revision acceptance are required for
this proposal. The business-verification policy, recovery wire contract and
retirement qualification are named blockers for an executable replacement
path. Licensing implementation and an offline recovery fixture need their
own accepted work orders. The H1 device-replacement case remains blocked.
Native sign-in, Hello, Gmail and live activation remain on hold.

## Native mechanism pins and protected ownership

### B1: selected native qualification profile

**PROPOSED selection, not native proof.** Qualify local, distinct computer accounts
on Ubuntu 24.04 LTS x86-64 with GNOME 46/Wayland, systemd 255, and PolicyKit1;
and two separately required Windows targets: Juan's Windows 11 dev-drive boot
on his own PC, and one Windows 10 22H2 x64 VM (build family 19045; see
[Microsoft release information](https://learn.microsoft.com/en-us/windows/release-health/release-information)). Juan directly
confirmed "Windows 11 PC plus Windows 10 VM" after clarifying that the dev drive
has the Windows 11 installation. Earlier relays about two native Windows boots
are superseded. No machine, disk or installed build was inspected in this work.
Freeze the actual Windows 11 edition/build only during his later authorized
preflight. Windows 11 24H2 x64 (build family 26100) remains the API reference
baseline, not permission to upgrade/reimage his box. If a target's APIs/build
cannot satisfy the profile, return `WINDOWS_PLATFORM_BLOCKED` and bring the
blocker to Juan; no VM may substitute for the Windows 11 native proof.
Windows is a first-release gate, including local password accounts, Microsoft
accounts and Windows Hello on dedicated test identities. These modes cannot be
silently excluded or deferred behind Linux release. Remote/domain/Entra accounts,
shared native credentials and other legacy-build support remain outside this lane.
This is a coverage commitment and qualification target, not a claim of proven
support. Patched package/build identities are frozen in the run manifest, never
silently upgraded during a run. New native
helper code is qualification-only C17 plus the locked CA Python 3.13 environment;
Windows helper uses Windows SDK 10.0.26100.0 with explicit Windows 10/11 runtime
capability gates; SDK availability does not prove an API runs on Windows 10.
Linux uses distribution GCC 13 and
libpolkit-gobject-1/libsystemd headers. No new production dependency is adopted.

Ubuntu's package catalog documents the chosen
[GNOME 46 family](https://packages.ubuntu.com/noble/gnome-shell) and
[systemd 255 family](https://packages.ubuntu.com/noble/systemd).
These references verify available API families, not an installed guest's build.
The Linux package revision, executable hashes and OS image digest are frozen
after harness preparation; Windows records only the exact build and approved test
artifacts/settings, without imaging or reading Juan's disk. All precede run
approval. A mismatch stops the run;
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

**Windows boundary:** on Juan's real box use only a separately named LocalSystem
qualification service and `%ProgramData%\LocalConnect\Qualification\<run-id>\Authority`,
with protected DACL allowing only SYSTEM and that service SID. Never open the
production authority directory or an existing deployment store. The run namespace
must be new and collision-checked within the approved parent, not found by scanning
user profiles. Service privileges do not authorize reading Juan's files.
Explicit local-only named pipe, `PIPE_REJECT_REMOTE_CLIENTS`,
`FILE_FLAG_FIRST_PIPE_INSTANCE`, bounded message frames and explicit DACL; never
default Everyone/anonymous access. Each message must successfully impersonate its
client, open that thread token and inspect TokenUser SID, TokenSessionId and
TokenStatistics AuthenticationId; fail closed if impersonation or reversion fails.
Client uses dynamic security context tracking; pipe PID/process creation identity,
SID, logon LUID, session, channel and host incarnation bind the request. A token
query failure must never substitute the service token. See
[pipe ACLs](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
and [last-message impersonation](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient).

### Windows account modes and independently verifiable proof

The protected service verifies each mode itself, in addition to the per-request
caller token/SID/LUID/session/channel checks above. Desktop UI success, an email
address, a browser session, a credential-provider label or a copied broker result
is never sufficient. These are proposed verifier requirements, not proof that an
API or mode already works on Juan's box. The closed local outcome vocabulary
extends the existing host outcomes with
`WINDOWS_PLATFORM_BLOCKED`, `WINDOWS_SAFETY_BLOCKED`,
`NATIVE_PASSWORD_VERIFIER_UNAVAILABLE`, `NATIVE_MICROSOFT_ACCOUNT_VERIFIER_UNAVAILABLE`
and `NATIVE_HELLO_VERIFIER_UNAVAILABLE`. Each publishes no authority and makes no
licensing consume call. Do not add these to the licensing server's refusal enum.
These blockers fail required qualification; they are not successful support.

| Mode | Protected-service verification mechanism | Typed blocker and no-fallback rule |
| --- | --- | --- |
| Local password | The trusted desktop broker invokes `CredUIPromptForWindowsCredentialsW` with `CREDUIWIN_SECURE_PROMPT`, no generic/save/admin-enumeration flags. Juan enters the test account password. The protected service calls `LogonUserW(LOGON32_LOGON_INTERACTIVE)` and compares the returned TokenUser SID to the authenticated requesting SID. It separately checks the original interactive LUID/session; the newly authenticated token's LUID is not the original logon's LUID. | `NATIVE_PASSWORD_VERIFIER_UNAVAILABLE` for absent/unsupported provider/API; `NATIVE_AUTH_DENIED` for rejected authentication or wrong SID. No username-equality, service-token or cached-dialog fallback. |
| Microsoft-account password | Use the Windows account credential provider for the dedicated test Microsoft account, followed by protected-service OS/LSA authentication through `LogonUserW` with that provider's account/domain representation and exact returned-SID comparison. Success must be an actual Windows-issued authentication token for the current requesting account, not cloud email equality. This verifies a local Windows logon, not an independent claim of current cloud-account status. | `NATIVE_MICROSOFT_ACCOUNT_VERIFIER_UNAVAILABLE` if the target provider cannot yield a verifiable matching token, including unsupported/passwordless configurations. Documentation for `LogonUserW` does not itself promise Microsoft-account coverage; the real native case must prove it. Do not map this identity to a local test user or add a browser/OAuth fallback. Passwordless Microsoft-account/Hello coverage uses the Hello row and must be qualified separately. |
| Windows Hello (PIN/biometric, including Microsoft-account-backed Windows sign-in) | The service issues a fresh single-use challenge; a supported, trusted interactive WinRT broker calls `KeyCredential.RequestSignAsync`. The service cryptographically verifies the response with the RSA public key (imported from `RetrievePublicKey(X509SubjectPublicKeyInfo)`) already enrolled in protected custody for the exact native SID/machine/app. Microsoft's documented KeyCredential proof is RSA/SHA-256 with PKCS#1 signature verification; it is separate from the licensing Ed25519 format. Check exact challenge bytes, service incarnation, operation, SID, account generation, session/channel and freshness before consuming the challenge once. | `NATIVE_HELLO_VERIFIER_UNAVAILABLE` when the broker/API, trusted key-to-SID enrollment, attestation/trust policy or signature verification is missing/unqualified; `NATIVE_AUTH_DENIED` for replay, wrong key/SID/challenge or rejected verification. A client-supplied public key, UserConsentVerifier `Verified`, a pipe token alone or a password fallback cannot pass this mode. |

**Hello trust remains an explicit blocker until proved:** `RetrievePublicKey`
returns a public key and `GetAttestationAsync` can supply key attestation; neither
by itself establishes our trusted SID/application enrollment. The Microsoft
pattern assumes an authenticated registration step. This codebase has no proven
protected enrollment/attestation verifier for this seam. An operator-approved,
separately reviewed enrollment must bind an application-specific test credential
to the already authenticated native SID, machine and trusted broker identity,
validate the chosen attestation/trust policy, and prevent replacing an existing
binding. A passwordless first-use case that cannot establish that trust returns
`NATIVE_HELLO_VERIFIER_UNAVAILABLE`; do not bootstrap a key merely because it signed
its own registration. Whether a secure passwordless enrollment can meet this
boundary is UNKNOWN and blocks that required release case. No new cloud identity
service or automatic attestation-provider request is authorized to bypass it.

The proposed Hello challenge is a closed local message: version const
`native-hello/1`, fresh 32-byte nonce, UUID operation/machine/service-incarnation,
stable native-SID binding, account generation, current session/channel commitment,
issued monotonic time and expiry at the existing fresh-verification deadline.
Canonicalize using the existing bounded JSON pattern; verify RSA/SHA-256 PKCS#1
against the protected enrolled public key, not the client's choice of algorithm.
Record and consume the challenge under the host owner; replays after success,
restart, lock or identity change deny. Do not export a PIN, biometric template,
private key or Windows token as a licensing payload. Do not claim a signature
alone proves a fresh Hello gesture. The qualified key/provider policy must require
that gesture for this exact challenge; unattended or cached signing that bypasses
it is a failed proof and `NATIVE_HELLO_VERIFIER_UNAVAILABLE`, even if the RSA
signature is valid. Missing trusted enrollment/attestation is the same blocker.
`UserPrefersPassword`, cancellation or a request for unsupported Hello proof
cannot silently switch this mode to LogonUser; return the closed denied/unavailable
outcome and keep the required Hello case blocked. Challenge/broker/proof frames
stay within B1's existing IPC limits; oversize or
unsupported representations return the typed blocker, without increasing caps.

A qualification broker that needs WinRT app identity must have its supported
package/process context pinned and separately approved. A C17 helper alone is not
assumed to support every WinRT UI API; proposed additional path
`qualification/owner_authority/windows_hello_broker.cpp` uses the selected Windows
SDK/C++/WinRT projection only after its own implementation authority. Missing app
identity or blocked package policy is `NATIVE_HELLO_VERIFIER_UNAVAILABLE`; no global
developer-mode, trust-store or sideload-policy change is authorized here.

For password modes, broker credential buffers traverse only the authenticated
local channel to the protected verifier, are never persisted/logged/dumped and
are zeroed/freed with native APIs on every path. Juan types every password/PIN
and performs biometric gestures through native UI; agents never collect, type,
record or replay them. Cancel/lock/focus or identity change denies the operation.

Primary API evidence (not native qualification):
[LogonUserW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-logonuserw),
[CredUI](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw),
[Hello challenge/verification model](https://learn.microsoft.com/en-us/windows/apps/develop/security/windows-hello),
[RequestSignAsync](https://learn.microsoft.com/en-us/uwp/api/windows.security.credentials.keycredential.requestsignasync?view=winrt-26100),
[RetrievePublicKey](https://learn.microsoft.com/en-us/uwp/api/windows.security.credentials.keycredential.retrievepublickey?view=winrt-26100),
[GetAttestationAsync](https://learn.microsoft.com/en-us/uwp/api/windows.security.credentials.keycredential.getattestationasync?view=winrt-26100),
and [UserConsentVerifier result API](https://learn.microsoft.com/en-us/windows/win32/api/userconsentverifierinterop/nf-userconsentverifierinterop-iuserconsentverifierinterop-requestverificationforwindowasync).
The last supplies an application result, not this service's independent proof,
and its documented Windows build minimum is 22000: it cannot be assumed on the
Windows 10 target. The KeyCredential route must be qualified independently on
both OS versions in its approved app context. Missing API/context/proof on either
version produces the named typed blocker; Windows 11 success does not pass 10.

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
| Licensing/release owner, using existing issuer trust chain | Issue a business-scoped companion claim; bind installation/key proof and opaque native/payload commitment at consumption; own revoke/reissue and bound receipts under B0-I; own replacement approval under [PC recovery](#failed-or-replaced-pc-recovery) | Native employee authentication, lead data, granting ownership from installer privilege or a new identity cloud service |
| Existing Connect/Automate protected host seam | Own installation identity, immutable org scope, employee enrollment/role, bootstrap consumption, host sessions and authority versions; own retirement proof and local replacement publication under [PC recovery](#failed-or-replaced-pc-recovery) | Source/custody/workflow SQL or a second scheduler/lead store |
| Protected activation-configuration owner under the existing host seam | Own the installed signed manifest and immutable original retained manifest for a pending operation; validate interval-only renewal under [pending recovery](#expired-activation-manifests-during-pending-recovery), recheck selected state and publish through the same protected-host writer | Issuing a manifest, changing issuer trust or claim/receipt key policy, source/custody SQL, granting admin authority or implementing native proof in an offline fixture |
| Native adapter under that host | Verify current caller/person/session and perform fresh native authentication using pinned mechanisms | Trusting webview JSON, an account name/PID alone, a copied result or a transport bearer |
| Qualification operator and native preflight owner | Juan establishes and preserves the isolation boundary; the preflight owner admits only the exact reviewed evidence under [non-test-disk isolation](#non-test-disk-isolation-evidence) | Inferring physical isolation from a caller flag, discovering non-test disks or changing their state |
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

### B2: platform qualification work order and freeze protocol

**Contract pin, no run authorization.** Prepare the harness in a separately
accepted implementation PR after review of this revision. Proposed owned paths
(not files claimed to exist): `qualification/owner_authority/controller.py`,
`licensing_fixture.py`, `linux_peer.c`, `windows_peer.c`, `native_broker.c`,
`cases.json`, `run.schema.json`, `result.schema.json`, and `README.md`. The harness
must call the same proposed verifier/adapter boundary on each platform, with the
retained Linux credential probe as the regression reference. It is not a new
workflow engine or production issuer. CI may test synthetic wire/ledger cases;
native desktop/account proof has its own run authorization.

**Linux environment (unchanged VM lane):** one new disposable Linux VM overlay,
cloned from operator-approved, shut-down images. Do not use a live employee desktop,
reset an existing VM password, inspect existing accounts or assume access to any existing installation. Each guest contains synthetic principals `li_owner`, `li_other` and
`li_admin_test` (an unrelated administrator), plus its protected service. Guest
local console only, no shared clipboard/folders, no mail/database/cloud secrets,
no bridged NIC or production registry; default-deny guest egress. The licensing
fixture runs inside each guest over loopback TLS using ephemeral test keys/CA;
no production keyring mutation or runtime trust override. Freeze the baseline
before account/service setup; setup and teardown are limited to these overlays.
If an image or the operator's native-password entry is unavailable, record STOP;
no host change, password recovery or Linux mock substitution.

**Windows 11 environment: Juan's physical dev-drive boot, later, only on his go.**
Treat it as the main workstation with live apps and model storage to preserve;
that reported layout is not a new disk observation or a spare machine to reimage. No remote-agent takeover, background
scheduling or automated execution is authorized by this document. Do not connect,
inspect Windows accounts/build,
provision or run even preflight now. Windows is in the first release; a missing
mode proof is a release blocker, not permission to ship only Linux or relabel a
Hello/MS-account case as local-password success.
Before any authorized Windows preflight, Juan identifies the current test boot
and its boot-volume alias, and physically disconnects or otherwise makes the
Linux boot disk and other non-test data disks inaccessible for the Windows proof.
The [non-test-disk isolation evidence gate](#non-test-disk-isolation-evidence)
below defines what can establish that prerequisite; a status flag is insufficient.
The reviewed
manifest pins that isolation and only the specifically named boot/test-volume
identities; the harness must not enumerate drives or probe other disks. If that
isolation cannot be established without touching them, return
`WINDOWS_SAFETY_BLOCKED` and stop for Juan. No mounting, unlocking, imaging,
indexing, reading, writing, cleaning or recovery of the other disks is permitted.
No reboot/boot-order change, partition/bootloader edit, BitLocker operation or
cross-boot cleanup is automated. Juan switches boots himself under a separate go.
Use a distinct run ID, dedicated accounts and resource/cleanup ledger for the
Windows 11 boot and Windows 10 guest; a path spelling alone does not prove the
intended boot volume. Juan first saves/quiesces his Linux work and chooses when
to boot Windows; this PC cannot keep running Linux coding jobs during that boot.
Agents must not stop his live apps/sessions or assume concurrent Linux access.
Prepare/review all artifacts before that switch; pause dependent Linux work until
he returns. Missing safe scheduling or disk isolation is `WINDOWS_SAFETY_BLOCKED`.
Models on the Windows boot disk stay outside all test roots; no discovery, loads,
GPU benchmarks, downloads, model-service restarts or cleanup of that storage.

**Windows 10 environment: one VM, separate authority, no substitution.** Use a
single operator-approved Windows 10 22H2 x64 image and disposable overlay, dedicated
synthetic local/Microsoft/Hello-capable test identities, no shared host drives,
clipboard or production registry, and scoped fixture network access. Freeze the
image/hypervisor/OS/API/broker identities and exact setup/run/teardown plan before
requesting go. No VM is created, booted or inspected now. Follow the same
per-mode service-verification, user-entered credentials, no-personal-data and
no-fallback rules; lack of a required Hello/TPM/provider capability is a typed
release blocker, not a waived Windows 10 case. State any virtual hardware need
before run approval; do not weaken attestation or borrow Juan's host credentials.
Teardown removes only that named VM overlay and its guest-created resources,
never the Windows 11 dev drive, Linux disk or existing VM. A native Windows 11
result and a Windows 10 VM result must both pass; neither substitutes for the other.

**Real-machine safeguard owner:** the frozen Windows run manifest must name a
new run-scoped test directory, service, broker/app identity, dedicated test-account
SIDs and any test-only firewall/IPC resources. Proposed aliases are
`LocalConnectOwnerQualification-<run-id>` and
`%ProgramData%\LocalConnect\Qualification\<run-id>`. Juan separately creates or
approves dedicated local, Microsoft-account and Hello-capable test identities;
never use, enumerate or change his everyday account or existing credentials.
Linking a test Microsoft account and establishing its native Hello setup are
Juan-controlled actions under separate go, not account work authorized now.
Existing personal Hello/TPM registrations, sign-in methods, recovery material,
BitLocker, cloud sync/OneDrive and application settings must not be reset, cleared
or changed. No new cloud accounts, purchases, identity-service registrations or
machine-wide authentication/network policy changes without their own named plan.

The reviewed file-I/O boundary allows only the manifest's new test root and the
dedicated test fixture profiles, plus exact OS/API/runtime dependencies required
by the reviewed binaries. Do not list drives, recursively enumerate profiles,
scan/import existing documents, read Juan's files, browser/credential stores,
mail, production databases, history or general event logs. Service privileges do
not broaden that allowlist. Keep file operations out of the privileged auth path;
any fixture I/O worker must enforce the parsed root/handle allowlist and reject
reparse/symlink/alternate-volume escapes before reading. Unknown path/resource
requests STOP. Exercise denial only with operator-approved synthetic sentinels,
never a real personal file. Retain an operation audit of allowed/denied test
resource aliases; no private path/content capture and no full-disk inventory.
If the implementation cannot enforce that boundary, use `WINDOWS_SAFETY_BLOCKED`
and stop before the real-machine run.

The issuer fixture stays loopback-only with ephemeral test trust, separate from
production licensing/authority configuration. Restrict network rules to named
test binaries/resources; do not disconnect the PC or change global firewall
settings. Only Juan-approved OS identity-provider traffic for dedicated Microsoft
account setup/authentication is an explicit exception; it is not permission for
an application OAuth/browser login or cloud data transfer. If native verification
needs another dependency, record its typed blocker for review first. Capture
only sanitized case/status evidence; no screenshots/recordings of credential UI,
keystrokes, biometrics, private keys, memory dumps or personal account identifiers.
Juan controls password/PIN entry and sees the exact next operation before go.

**Evidence handoff across boots:** before any Windows go, Juan chooses a new,
empty, dedicated evidence-exchange directory on an approved removable device or
other specifically approved shared destination, with privacy ACLs and a recorded
alias/path. It must be reachable from the relevant boot or have a user-controlled
sanitized export step. Do not assume the Linux evidence root stays mounted or
available from Windows, or use the model directory as a share. Only sanitized
run receipts/manifests cross that boundary; no test credentials, keys, private
files, raw account IDs or broad drive copy. Record exported artifact hashes on
Windows, and verify those hashes on return to Linux before independent review.
No test/controller work continues from Linux while this PC boots Windows. If the
exchange destination, access controls or return path is unapproved/unavailable,
record STOP before the run rather than mounting or scanning another disk.

**Named Windows 11 cleanup, separately approved and limited to created resources:**

- `W1_QUIESCE`: stop test admission, reconcile/preserve test-only pending receipts
  and collect sanitized evidence. Do not touch any production pending operation.
- `W2_STOP_SERVICE`: stop only `LocalConnectOwnerQualification-<run-id>` after
  confirming its recorded service identity and binary hash; no wildcard stop.
- `W3_REMOVE_BROKER_CREDENTIAL`: in each dedicated test profile, remove only the
  recorded app-specific test credential using [KeyCredentialManager.DeleteAsync](https://learn.microsoft.com/en-us/uwp/api/windows.security.credentials.keycredentialmanager.deleteasync?view=winrt-26100)
  for its exact recorded name if it was created by this run. Juan authorizes any
  native UI gesture. Never clear Windows Hello/NGC, the TPM or existing keys.
- `W4_REMOVE_REGISTRATION`: remove only the run-created service/broker registration
  and precisely named per-test rules; restore only settings this run changed from
  its explicit before-receipt. Leave pre-existing registrations/rules untouched.
- `W5_REMOVE_TEST_ACCOUNTS`: Juan approves the exact dedicated test SIDs/profile
  paths and signs those test sessions out; delete only run-created local users
  and test profiles under the approved cleanup scope. No everyday-account changes,
  Microsoft-account cloud deletion, credential-manager clearing or password reset.
- `W6_REMOVE_TEST_ROOT`: after evidence is copied to its approved private destination
  and reviewed, remove only the recorded run root, rejecting reparse points and
  verifying ownership/run marker. Preserve durable evidence until Juan approves
  its later deletion. No directory wildcard or machine reset.
- `W7_VERIFY_CLEANUP`: query only the recorded test resource names and synthetic
  sentinel state; report removed/retained/blocked for each. An unexpected resource
  or cleanup failure STOPs for Juan, not broader scanning or repair.

Each cleanup step has exact argv/resource identities and boot-volume binding in
the frozen manifest, Juan's explicit cleanup go and a result receipt. Before
every step, confirm the operator-selected current boot/test volume and named
resource marker; a different boot or volume stops cleanup without touching it.
Cancelling a run stops further
actions and retains evidence; it does not authorize automatic cleanup outside
that list. No step is executable under this contract-only work order.

**Freeze-before-run sequence:**

1. Review/accept this contract, then separately authorize building the bounded
   harness. Independently review its exact commit and wire/negative fixtures.
2. Create a secret-free `run.json` in durable evidence with full contract/harness
   commits, executable/fixture/policy hashes, Linux base-image SHA-256/overlay ID,
   Windows 11 operator-approved machine/boot-volume alias/build and named test-resource/
   cleanup allowlists (no host disk imaging or personal inventory), Windows 10
   image/hypervisor/overlay identities, OS build/kernel, GNOME/systemd/polkit/PAM and compiler/SDK package revisions,
   locked Python dependency digest, service/principal aliases, trust policy,
   isolation/network policy, exact setup/run/teardown argv and evidence paths.
   These observed content hashes cannot truthfully be invented before the files
   or guest exist. No mutable `latest`, unresolved variable or missing hash is
   runnable; a hash-only preparation receipt is not qualification.
3. Send that frozen manifest and bounded setup/run/teardown scope for oversight
   and Juan's explicit native-run authorization. This review-only revision does
   not authorize provisioning or generating passwords/keys now.
4. On the approved Linux overlay, Windows 10 overlay or Juan's Windows 11 boot,
   freeze only the authorized platform/test state and execute the reviewed entrypoints solely
   after Juan's explicit go for that platform/run. No go is inferred from contract
   acceptance, CI, review or an earlier run. Controller interface is pinned as
   `controller.py preflight --manifest <run.json>`,
   `controller.py run --manifest <run.json> --platform linux|windows`, and
   `controller.py collect --manifest <run.json>`. `<run.json>` resolves to one
   approved absolute path in the receipt; no shell interpolation or guessed path.
   Preflight validates frozen hashes, Linux/Windows 10 guest identities or the
   approved Windows 11 machine/test identities, allowlisted resources and scoped network rules before
   native setup, and itself requires Juan's go. A mismatch produces STOP without executing the run.
5. Collect/review before teardown. Linux removes only its specifically approved
   overlay and guest service/accounts, as before. Windows 10 removes only its
   expressly approved guest overlay/resources. Windows 11 uses only W1 through W7
   above on Juan's separate cleanup go. Preserve evidence; no wildcard, reset,
   broad repair or Windows image rollback is authorized.

**Finite cases and verdicts:** the FIRST Linux native case is B1's socket-replacement
and fake-user-bus gate, including initial connect and reconnect while the real
desktop stays locked. Failure is sent to Juan and stops dependent work before
any normal bootstrap/consumption or the remaining Linux matrix. Then, only if
that gate is not defeated, execute every proof-matrix row below on each platform.
Ordinary lifecycle and boundary fixtures use the same public synthetic identities.
On each Windows target, run the full native matrix for local password, Microsoft-account
password and Windows Hello/PIN-biometric modes on dedicated test accounts. Include
wrong-SID credentials, unsupported/passwordless provider, missing or swapped Hello
enrollment/attestation, fake Verified result, replay/wrong-key/challenge signature,
lock/logout/disconnect, account disablement/recreation and cancellation. A required
mode returning its typed blocker is STOP for that release case, not PASS.
Only successful service-side proof qualifies it; no mode is skipped or downgraded. Test min-1/min/max/max+1 for every declared bound, false/zero/empty/
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

Case deadline 180 seconds, platform budget 3600 seconds, at most one platform
case at a time. Windows runs only while Juan is present and approving its actions. A separate
per-target budget applies; no Windows 10/11 result is merged into a single pass. A watchdog timeout preserves evidence and fails that case; no unbounded
retry. Overall result PASS only if every mandatory case on all required platform targets
passes with assertions and no unreviewed environment drift. FAIL for an observed
invariant violation; STOP for missing access/approval/environment; neither counts
as pass. No automatic rerun after a security or data-integrity failure: reproduce,
isolate the first losing owner, explain it and fix there in a separately reviewed
harness/adapter delta. No production adoption follows a green packet.

**Evidence:** save `run.json`, sanitized per-case JSONL, native result codes,
barrier/commit receipts, deny-egress counters, fixture/adapter digests and a
SHA-256 manifest outside worktrees under
`~/Desktop/codex-evidence/connect-automate/lead-owner-authority-qualification/<run-id>/`.
Directories 0700/files 0600 on the evidence owner, equivalent Linux guest and
Windows dedicated-test/evidence ACLs. Result
schema is closed: contract/harness/run IDs, case/platform, outcome PASS/FAIL/STOP,
expected and actual code (including Windows typed blockers), assertion IDs,
public synthetic fixture digest, monotonic
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
| Required platform qualification | Linux uses its unchanged VM lane; Windows 11 uses Juan's dev-drive boot and Windows 10 22H2 uses one VM. Each Windows target has dedicated local/Microsoft/Hello cases and explicit go. Per-target/per-mode results retain blockers, safety and cleanup receipts. Both Windows targets gate the first release; no Linux/mock/hosted-CI substitution, silent exclusion or weaker fallback. |

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

### Non-test-disk isolation evidence

This amendment proposes the evidence gate for B2's later Windows 11 real-machine
run. It does not establish that Juan's current disks are isolated. Physical
disconnection remains the baseline. A disk that remains connected qualifies only
through the separately accepted and qualified isolation profile described below;
without that profile, the connected-disk case is `WINDOWS_SAFETY_BLOCKED`.

**Owner and trust boundary.** Juan supplies the approved physical-layout mapping,
identifies the boot/test volumes and separately approved evidence-exchange
destination, and confirms the complete set of non-test disks to exclude. Use
private, run-scoped aliases, not a drive scan or personal file/device inventory.
He establishes isolation before the test boot and preserves it through the
authorized phase. An unknown connection, uncertain mapping or inability to
confirm completeness blocks the run; the harness must not discover the answer.
This operator-supplied mapping and continued physical control are explicit trust
assumptions, not facts independently proved by a JSON record. Unreported manual
reconnection is outside that evidence guarantee; no claim of resistance to an
adversarial physical operator follows.

The native preflight owner validates the frozen evidence and the specifically
approved current boot identity before admitting any setup, test or cleanup
effect. It may read only the approved manifest/receipt and named boot-identity
metadata through its reviewed adapter; no disk enumeration, non-test device
open or access attempt is a verification method. The adapter's precise API,
identity stability and allowlist require separate implementation review and
qualification. A path, drive letter, display name or elapsed uptime alone cannot
stand in for the approved boot-volume and boot-session identities.

**Admissible mechanism evidence.** Each protected disk has one method selected
in the frozen isolation plan:

- `PHYSICAL_DISCONNECTION`: Juan confirms the mapped device's physical
  disconnection, including every attachment path named by that mapping, before
  the approved boot. The later phase confirmation establishes that he has
  preserved that state. A written claim that a connected disk is disconnected
  is not qualifying evidence.
- `QUALIFIED_EXTERNAL_ISOLATION`: the disk remains connected, but a pinned
  isolation profile establishes an enforcing boundary outside the test OS's
  control. Its independently reviewed qualification packet must demonstrate on
  disposable synthetic storage that the exact mechanism withholds all access
  to the protected device, including raw/alternate access and attempted
  re-enablement by the run's most privileged test identity. It must cover its
  boot/reset behavior, supported hardware/firmware/configuration and failure
  modes. The actual frozen configuration must match that qualified profile.
  Qualification must not target Juan's real non-test disks. No such profile,
  hardware capability or qualification result is selected or asserted here.

Unmounted/offline status, a missing drive letter, encryption/locked status, file
ACLs, a denied file open, a process list or an empty disk listing do not satisfy
either method. Neither an operator waiver nor a well-formed receipt can replace
the required enforcing boundary. Missing or inconclusive profile evidence is a
blocker, not permission to probe a protected disk or choose a weaker proxy.

**Frozen plan and phase receipt.** Extend the later native protocol owner's
closed models, not H1's offline schemas. The frozen `run.json` must bind the
contract/harness commits, machine and boot/test aliases, approved exchange
destination, complete protected-disk alias set, each disk's selected method,
and the exact profile/configuration/evidence digests for any external isolator.
The operator-controlled private mapping is reviewed with that plan; the public
packet contains only aliases and digests. Changing a disk set, method, target,
profile or destination requires a new freeze and go.

After the approved boot and before each separately authorized phase, retain one
sanitized isolation receipt binding all of the following:

- one fresh receipt ID, the run ID and phase (`PREFLIGHT`, `RUN` or `CLEANUP`);
- the exact frozen manifest SHA-256, machine/boot-volume aliases and the actual
  current boot-session identity acquired through the reviewed adapter;
- exactly one evidence entry for every protected-disk alias, matching its frozen
  method and applicable profile/configuration digests, with bounded references
  to the approved evidence rather than inline device contents;
- the observation time and Juan's fresh confirmation of complete coverage and
  unchanged physical/isolation state for that phase, through the existing
  explicit operator-authorization boundary.

The operator's phase go must name the manifest and receipt digests. A field
claiming approval, possession of a receipt or a matching digest is not operator
authorization. The receipt binds the frozen manifest; that manifest must not
embed the receipt's digest and create a circular hash dependency. Preserve both
digests and the actual go in the admission record. Their hashes establish byte
binding, not independent proof of physical state.

The future protocol revision must pin the wire version, exact fields and finite
bounds in its single closed model and derived JSON Schema: required nonempty
identities, enum-selected method/phase, conditional profile fields, bounded
lists/references and no extra properties. Reject duplicate JSON members before
admission. Use the same schema for admission; one validator at that owner handles
exact plan/boot/alias coverage, uniqueness and approval-provenance relations.
Do not add a parallel regex or a second receipt validator in the controller.
No native schema or receipt producer is implemented by this amendment.

**Freshness, concurrency and refusal.** Evidence covers one uninterrupted boot
and one specifically authorized phase. Reboot, suspend/resume, isolation or
connection changes, cancellation, controller restart or uncertain state invalidate
it; a later phase needs a fresh receipt and go. Recheck the named current boot,
receipt bindings and operator confirmation after waits and before phase effects.
One admission owner serializes acceptance of a receipt for a phase and records
its disposition before effects; concurrent or repeated use cannot start another
phase. A crash or uncertain disposition stops for reconciliation and new
authorization, not automatic replay. No software/physical-state atomicity is
claimed: Juan must preserve the confirmed boundary throughout the phase.

Absent, stale, partial, duplicated, contradictory, wrong-run/boot or unqualified
evidence returns STOP with `WINDOWS_SAFETY_BLOCKED` before setup, test, cleanup or
new test-root creation. Retain only sanitized reason/alias/digest evidence in the
already approved destination, or the bounded refusal diagnostic if it is
unavailable. Do not mount, unlock, enumerate, read, write or repair another disk
to complete the packet. An exchange destination on a protected disk cannot be
used to satisfy an otherwise missing evidence path.

The following synthetic examples describe required future behavior; none has
been run or qualifies the current machine:

| Example | Required gate result |
| --- | --- |
| Complete physical-disconnection evidence, exact boot/run/phase binding and fresh operator go | Isolation prerequisite eligible; all other B2 gates still apply |
| Complete matching external-isolation profile with independently qualified synthetic proof and fresh go | Isolation prerequisite eligible; not a native qualification PASS |
| Connected disk with only offline/unmounted/encrypted/ACL or absence-of-listing evidence | `WINDOWS_SAFETY_BLOCKED`; no protected-disk probe |
| Otherwise valid receipt for another manifest, boot session, phase or target | `WINDOWS_SAFETY_BLOCKED`; no phase effects |
| Mixed valid entries with one missing, duplicate, unknown or mismatched protected alias | Reject the whole receipt; no partial admission |
| Missing/empty evidence, false/default approval or a copied receipt without actual operator go | `WINDOWS_SAFETY_BLOCKED`; no inferred approval |
| Two admissions race for the same otherwise valid receipt | At most one phase admission; the other is refused without effects |
| Reboot, suspend/resume, controller restart or changed isolation after confirmation | Invalidate; STOP pending a fresh receipt and go |
| Profile evidence is missing, expired under its policy or for another configuration | `WINDOWS_SAFETY_BLOCKED`; no substitution or waiver |
| Exchange destination is unavailable or lies on a protected disk | STOP; no alternate-disk discovery, mount or read |

Acceptance of this proposal does not authorize receipt collection, physical
changes, a preflight, a probe or a run. The executable closed protocol,
boot-identity adapter, any alternative isolation profile and its qualification,
and the exact native freeze/go remain separately accepted work. The H1
`inaccessible-disk-evidence` case stays `BLOCKED`; its native commands still
refuse. Native sign-in, Hello, Gmail and live activation remain on hold.

## Required change surface, non-scope and rollback

This PR changes only this proposed contract and the receiver roadmap's completed
V1a/next-work pointer. It preserves the entire accepted vertical plan and V1a
work order, all source/tests, schemas, dependency pins, workflows and runtime
configuration. The later [malformed consume requests](#malformed-consume-requests)
amendment proposes one resolution for [issue #73](https://github.com/canfieldjuan/connect-automate/issues/73).
The [expired activation-manifest recovery](#expired-activation-manifests-during-pending-recovery)
amendment proposes its renewal sequence. The
[failed or replaced PC recovery](#failed-or-replaced-pc-recovery) amendment
proposes replacement approval and its prerequisite gates. The
[non-test-disk isolation evidence](#non-test-disk-isolation-evidence) amendment
proposes its evidence gate; native implementation and qualification remain separate.
The existing malformed `handoff_id`
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
have accepted Linux/Windows-10 overlay teardown and named Windows-11 real-machine
cleanup plans. Do not reset a protected
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
B1 native API and platform selection, and B2 Linux-VM/Windows-11-native/Windows-10-VM freeze/run
plan are specified for independent review. PR72 acceptance is on hold for this
Windows real-machine and account-mode revision. These are proposals, not tested behavior.

**NOT DONE for execution:** licensing-side acceptance/implementation and signed
endpoint publication, oversight/connector review of this revision, Juan's
exact-revision acceptance, separately authorized harness implementation and
hash-frozen native run, qualification, integrated enforcement and later V1b
activation. Linux lock resistance and Windows account/Hello proof may fail qualification;
their typed blockers and the real-machine safeguards are explicit release gates. Publish the documentation-only revision and stop for review; no
merge, production claim or executable authority is implied.
