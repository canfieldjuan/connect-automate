# Licensing-owned recovery approval work order

Status: **PROPOSED; CONTRACT ONLY.** Juan authorized drafting and independent
oversight submission. This revision requires independent oversight and Juan's
exact-revision acceptance before merge. Acceptance approves these requirements;
it does not accept a still-unspecified verification policy, authorize
implementation, run fixtures, generate keys or approve an individual recovery.

The [canonical recovery policy](LEAD-OWNER-AUTHORITY.md#failed-or-replaced-pc-recovery)
remains the product-policy owner. This work order defines the licensing approval
boundary and the inputs required before an executable work order can be accepted.
Native sign-in, Hello, Gmail and live activation remain on hold.
`device-replacement` and `inaccessible-disk-evidence` remain `BLOCKED`; native
cases remain `NOT_RUN`. The unreachable-predecessor decision remains open under
[issue 84](https://github.com/canfieldjuan/connect-automate/issues/84).

## Missing capability and change surface

The offline issuer records evidence, not independent business verification,
administrative approval or qualified predecessor retirement. Elevating that
record into replacement permission would cross an unimplemented trust boundary.
This is a missing capability, not a reproduced defect in the evidence owner.

This PR changes only this document and its canonical pointer. It selects no
identity provider, identity documents, hosting, signing key or administrative
endpoint. It changes no source, schema, catalog, fixture profile, workflow or
entitlement format. It does not extend the existing issuer CLI with recovery.
Later code and native qualification require separately accepted work orders and
explicit authorization; this document is not an implementation-ready wire spec.

## Inventory before design

Connect Automate baseline: `e6e431a7c3bd1979870833051b9774ef6c903515`, the PR96
merge. The following source references are pinned to that revision. Prior
runtime proof is historical evidence, not rerun for this documentation change.

| Owner | What exists and its limit |
| --- | --- |
| `qualification/owner_authority/protocol.py:615-725` | Closed synthetic case, exact replacement target, signed evidence, selection, admission and refusal values. Admission is literally `EVIDENCE_RECORDED_ONLY`; evidence asserts `SYNTHETIC_RETIREMENT_ONLY` with `qualification_pass=false`. |
| `qualification/owner_authority/licensing_fixture.py:355-443,482-533` | Authoritative fixture consumption lookup, immutable case binding, serialized admission and replay. Missing or changed consumption under an existing case is corruption, not an available claim. No administrative approval is written. |
| `qualification/owner_authority/controller.py:479-533,567-673`, `cases.json` in that directory | Separate issuer/host workers prove evidence admission while preserving predecessor authority and leaving replacement unpublished. Device replacement remains blocked. |
| `qualification/owner_authority/host_fixture.py:344-356` | Read-only recovery snapshot. It supplies no predecessor retirement or rollback fence. |
| [Evidence work order](LEAD-OWNER-DEVICE-RECOVERY.md), [controller work order](LEAD-OWNER-RECOVERY-CONTROLLER.md) | Existing synthetic proof and its limits remain unchanged; store reopen is not process restart or durable signing-key custody. |

Additional inspected local checkouts, not assertions about deployed services:

- `local-connect-licensing` at `9f9d1be530653300926315294ef1721ce3d4fc98`:
  tracked files are README and `docs/contracts/LICENCE-SERVICE.md`. The latter
  is a proposed online entitlement-issuing contract with operator questions,
  not an implemented recovery service or accepted business-verification policy.
- `connect-contracts` at `a168b9a67450556d95b4939a59ca36aa7aedfda5`:
  `tools/entitlement_issuer.py:359-451` issues entitlement-v1 envelopes. Its
  signing authority does not establish recovery approval. The unrelated local
  `.gitignore` modification was preserved; neither checkout was modified.

Reusable controller evidence alias:
`offline-recovery-controller/review-fixes/final/manifest.json`, SHA256
`789061b8548a20e6382ccd68e55296ef0c45345b8b5c7c385c18cc40167ab46b`.
It proves the offline controller at `cb38427bea1fafc3c1384d26f24630cbe40cf375`,
not any of the approval prerequisites below. Source and dependency hashes for
this proposal are sealed separately with its review packet. No model, model
settings, prompts, chat template or private document input exists in this lane.

Deliberate differences from validated work: this proposal adds approval
requirements and explicit gates only. There is no behavioral port. A future
implementation contract must inventory the then-current owners, list every
departure and reuse their existing parity proofs before changing behavior.

## Approval ownership and required policy input

Only the licensing administrator, authenticated and authorized through the
licensing owner's separately accepted administrative provisioning channel, may
make the recovery decision. Caller-supplied administrator names, policy hashes,
case IDs or `verified=true` fields cannot establish that authority. The channel
must derive the approver identity and permissions from its own trusted session
and revalidate them at the durable decision boundary.

The licensing owner must supply a concrete, revisioned business-verification
policy for oversight and Juan's acceptance. It must name:

- The authority allowed to approve for this business and entitlement, and how
  the requester is independently verified against an authoritative source.
- The verification method and evidence provenance, its validity/freshness,
  how revoked or superseded authority is detected, and how ambiguous results
  are retained without approval.
- The administrative channel's authentication and permission owner, session
  expiry/revocation behavior, and audit identity provenance.
- The references permitted in the case and the access, retention and deletion
  policy for underlying private verification material outside the case.

These are required inputs, not selected services or accepted policy values.
Possessing a licence, consumed claim, receipt, email address, local account,
installer privilege or evidence-admission packet alone is insufficient.
No real identity documents are collected by this work order.

The proposed [business-verification policy and administrator channel](LEAD-OWNER-BUSINESS-VERIFICATION.md)
recommends a restricted initial policy and channel profile for licensing-owner
adoption and Juan's exact acceptance. It does not establish that an authoritative
enrollment source exists, satisfy native retirement or authorize execution.

## Exact decision binding and independent prerequisites

The licensing owner must read its authoritative consumed deployment and bind
each decision to the immutable original claim, consumed binding and receipt
digest; case ID and revision/digest; verified business and entitlement; accepted
policy revision; authenticated approving administrator; and the exact selected
replacement. That target includes its new host, installation, protected public
key and operation, fresh native-person commitment and initialization digest.
The case retains decision time and provenance references; native credentials
and source identity documents stay outside it.

Before an affirmative decision for replacement publication, all of these must
be established by their actual owners:

1. Independent business authority and current administrator permission under
   the accepted policy and channel above.
2. Determined predecessor consumption and unchanged exact case/target binding.
   An unknown outcome never means unconsumed. Stored corruption is STOP and
   cannot be reinterpreted as ordinary unavailability or a fresh recovery case.
3. Qualified predecessor disablement: the protected-host owner durably retires
   authority, invalidates admin sessions and machine grants, and preserves
   history. Qualification demonstrates that supported restart and restore
   cannot revive that authority. A signed assertion, revoked issuer claim,
   support decision or synthetic evidence admission is insufficient.
4. Fresh replacement native proof bound to the exact target, under a separately
   accepted and qualified native mechanism. The replacement host must validate
   fresh proof again at its eventual publication boundary.

An unreachable old PC lacks qualified disablement. Even a verified requester
therefore remains blocked. Neither presumed disk loss nor a signature fences
an older disk image. Issue 84 requires a separate product decision and accepted
enforcement contract before this can change. Ordinary lead operations gain no
licensing polling or background revocation dependency.

## Durable decisions, retries and the publication boundary

The licensing owner alone serializes decisions against the predecessor lineage
and competing cases. Within its durable transaction it rechecks the selected
case/target, current administrator authority, policy and prerequisite validity
after waiting and immediately before commit. Uniqueness and referential
constraints belong in that owner's storage wherever expressible. There may be
only one selected replacement binding at a time for a predecessor; no request
may overwrite the consumed row, admitted evidence or earlier decision.

An exact authenticated retry returns the same recorded decision and binding;
it does not mint a second approval or revive expired/revoked permission. A
historical decision remains history when current authorization is unavailable.
A changed target or policy is a new administrative decision, not a retry. It
must retain the previous case/decision and resolve its selection explicitly.
If publication or revocation of the earlier selection is uncertain, a competing
target stays blocked; a new case reference cannot bypass that uncertainty.

Retain blocked/denied attempts and reasons, partial decisions, issuance failures
and unknown publication outcomes with their lineage. Recording a failure may
append audit history but cannot alter authority or free the predecessor. A
missing or damaged record needed to establish that history is STOP, not denial.
There is no atomic transaction spanning licensing and either host. A lost
response requires authenticated reconciliation against the actual owner; it
does not imply rollback or permit automatic selection of another replacement.

An approval record is not an executable authorization. A separately accepted
recovery wire work order must define closed models, purpose-separated signing
and trust ownership, byte/time bounds, exact case/target binding, validity,
revocation, replay and receipts before any authorization may be issued. Ordinary
owner claims, entitlement envelopes, consumed receipts and synthetic retirement
evidence retain their existing purposes and cannot substitute for that wire.

Only the new host's protected authority transaction may publish its owner/admin
record, after validating that authorization, qualified predecessor-disablement
evidence and fresh native proof. Neither an admin-console response nor a
licensing decision alone performs this write. Linked history must retain the
original consumed deployment and every subsequent decision and replacement.

Future schemas must express required/closed fields, fixed purposes, enums,
types and bounds at one protocol owner; real parsers own structured values.
Use one named semantic validator for remaining cross-record constraints, with
distinct refusal, corruption and uncertainty meanings. Do not add duplicate
regex or parallel controller policy. Concrete wire fields, bounded reason
codes and storage/API design belong to that later accepted work order.

## Required acceptance examples for later executable work

These are obligations, not executed tests or permission to create fixtures.

| Input or sequence | Required result |
| --- | --- |
| Valid authorized administrator, accepted policy, independently verified same business/entitlement, exact target and all qualified prerequisites | One durable bound decision; no host publication from the decision itself. |
| Correctly signed synthetic evidence or copied entitlement/receipt, without independent verification | No affirmative approval, authorization or host write. Existing evidence remains evidence-only. |
| Valid requester but unreachable predecessor, missing retirement qualification or unsupported restore behavior | Blocked; history retained; no presumed retirement and no new lead-operation connectivity dependency. |
| Wrong business, entitlement, case, target key/host/operation, policy revision or stale proof; mixed valid and invalid prerequisites | No affirmative approval. Never silently normalize, substitute or default a failed prerequisite. |
| Request supplies approver identity or true approval flags; real session lacks permission or is revoked during writer wait | No affirmative decision; trusted channel identity and commit-time permission control the result. |
| Existing case loses or changes its predecessor consumption | Corruption STOP; no refusal-as-unavailable fallback or replacement claim. |
| Two concurrent approvals for different targets | At most one selected binding; conflicting attempt cannot overwrite history or publish another target. |
| Exact retry after committed decision but lost response | Same decision identity and bytes; no second approval or implicit issuance. Recheck current authority before any new effect. |
| Crash before commit, after decision commit, during issuance or before publication acknowledgement | Preserve each owner's actual outcome; reconcile explicit retry; no invented cross-owner rollback, double publication or freed predecessor. |
| Policy/target change after prior decision, including uncertain publication | New linked decision only after prior selection is authoritatively resolved; no in-place edit or uncertainty bypass. |

The later proof must cover both valid admission and invalid rejection, partial
inputs, empty/falsy/default defeats and exact min/max boundaries selected in
its wire contract. Use actual owner writes, concurrency and fault controls;
prove downstream code consumes validated values. Synthetic proof remains
`OFFLINE_CONFORMANCE` with `qualification_pass=false` and cannot qualify native
retirement, business verification or actual replacement.

## Exit gates

This proposal may be accepted as requirements while executable recovery stays
blocked. Before an executable approval work order can be accepted, supply the
concrete licensing policy and administrative-channel contract, exact approval
wire/storage design and prerequisite qualification plan. An offline simulation
must have its own explicit synthetic-only scope and must not claim those real
prerequisites have passed. Actual authorization/publication additionally needs
the accepted recovery wire and completed native/retirement qualification.

Independent oversight reviews this exact contract commit. Juan then accepts
that exact revision. CI and connector review are additional merge gates, not
operator acceptance or approval of any recovery case. Implementation requires
a separate go after its executable work order is accepted. Native sign-in,
Hello, Gmail and live activation stay on hold throughout this contract slice.
