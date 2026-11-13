# US business-verification methods and licensing-record work order

Status: **PROPOSED; CONTRACT ONLY; NOT READY FOR EXECUTION.**
This work order develops the accepted [enrollment contract](LEAD-OWNER-ENROLLMENT.md)
and [business-verification policy](LEAD-OWNER-BUSINESS-VERIFICATION.md).
Those owners retain eligibility, authentication, freshness, retention and approval
rules. This document proposes concrete source investigations and the missing
licensing-record handoff; it does not qualify a real identity method.
Native sign-in, Hello, Gmail and live activation remain on hold.
No real records, accounts, keys, storage, implementation or live verification are
authorized. Independent oversight and Juan's exact-revision acceptance are required.

## Inventory, ownership and deliberate differences

| Inspected input | What exists; what it does not establish |
| --- | --- |
| Connect Automate `14f1247e6307d040009b28fd6f7a04894db117b6`, enrollment contract and `qualification/owner_authority/protocol.py` | Accepted custody/retention proposal and synthetic recovery relations. `OwnerClaim`, `ConsumeBinding` and `RecoveryEvidenceCase.relations` preserve original organization/entitlement identifiers. They do not verify a person or business. |
| `connect-contracts` main `07cc315b97772f6eb182dcd2cda6fc8ffde707cb`, `entitlements/v1/claims.schema.json` and `tools/entitlement_issuer.py::issue_entitlement` | Opaque subject and a fresh entitlement UUID per issuance; no sales ledger or verified-business meaning. |
| `local-connect-licensing` main `c7ac955674b680f04c2ebbcdc4806682f707f81d` | README only; no implemented issuance/association registry. |
| Licensing PR 1, open proposed head `9f9d1be530653300926315294ef1721ce3d4fc98`, `docs/contracts/LICENCE-SERVICE.md` | Proposed installation-derived subject and identity-free service storage. Its named release-session owner is a proposal, not an adopted operating record owner. This work order does not accept that PR or extend its application scope. |
| Private commercial decision referenced by licensing README, invoice-processor issue 94 | A provider decision is not evidence of a deployed account, authoritative sale record, or an order-to-entitlement association. Provider identity and commercial terms stay in that private decision. |

Juan is the accountable enrollment-record owner. Licensing must name the operating
owner of its issuance/association records and adopt the handoff before execution;
the same person may hold both roles. No additional staff member is required.
No authoritative external sales system has been confirmed. Oversight's report
relayed by Juan also identifies the missing system in code; it does not establish
the presence or absence of records outside the repositories. No customer records
were inspected. Atlas cleaning-business invoices are not assumed to be licence sales.

The new work is a proposed manual evidence method and licensing journal, not a
port of a validated identity system. There is no model/runtime/prompt to port.
Later synthetic work must reuse the existing recovery relation and preserve its
evidence-only semantics. Deliberate additions are source provenance and an external
business-to-issuance association; entitlement claims, subject generation and the
existing consumed-deployment relation remain unchanged.

## Public source catalogue and coverage

Research establishes source properties, **not qualified enrollment methods**.
The following public materials were inspected for this proposal:

| Source | Independently retrieved facts and limits | Proposed use |
| --- | --- | --- |
| [SBA state registration directory](https://www.sba.gov/counseling/launch-your-business/state-registration-lookup/) | Routes to state registration offices. The directory is paginated; its destinations have not all been audited. | Locate the issuing office for a registered entity, then check that office's actual record coverage. The directory itself proves no business or person's authority. |
| [California Secretary of State information requests](https://www.sos.ca.gov/business-programs/business-entities/information-requests) | Describes entity/status records and available officer/director/member/manager fields. It does not maintain owner/shareholder information, telephone/email, or company governing agreements. Sole proprietors are not registered there; fictitious names are filed with the relevant county. | Retrieve the official entity record and available filed documents through the official service. Distinguish an officer/manager statement from agent/organizer or existence-only information; use actual governing authority evidence for scope not established by the filing. Free official copies are not rejected merely for lacking paid certification. |
| [Ohio Secretary of State sole-proprietorship guide](https://www.ohiosos.gov/assets/business-start-a-sole-proprietorship.pdf) | A sole proprietor operating under their own personal name need not file formation paperwork with that office. Trade/fictitious-name records apply to other naming circumstances; application fields identify an applicant, not a remotely contacting person's identity. | For an applicable registered name, retrieve the issuing office's record and link the recorded applicant to the verified natural person. For an own-name business, use the independently established business/commercial relationship below without demanding an inapplicable registration. |
| [NIST identity-proofing guidance](https://pages.nist.gov/800-63-4/sp800-63a/proofing/) | Separates evidence validation from binding the applicant to that evidence. | Structure separate proof obligations. This is not adoption of an assurance level, biometric procedure, document count or identity provider. |
| [FTC personal-information guidance](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business) | Recommends collecting needed information and a defined retention/disposal policy. It supplies no universal business-verification retention period. | Minimize source copies under the canonical schedule; identify actual method-specific obligations before use. |

California and Ohio have researched source properties here, but **neither has a
qualified end-to-end method**. California county fictitious-name sources still
need the actual county's source profile; the state page is not a county lookup.
The [Texas management-information page](https://www.sos.state.tx.us/corp/managementinfofaqs.shtml)
and [Washington licensing page](https://dor.wa.gov/manage-business/my-dor-help/renew-or-update-business-license/apply-new-business-license)
returned access errors during research. Search material from Washington's
[business tax guide](https://dor.wa.gov/sites/default/files/2022-03/BusinessTaxBasics_0.pdf)
also raises limits on reuse of public tax/business data; usage permission is
unresolved. Neither state's
preview material is adopted as an executable method. Other states' issuing
sources remain unresearched in this work order.

All 50 states remain the target. These research gaps describe unfinished methods,
not excluded customers. Reuse one profile across states where it genuinely proves
the same facts; qualify the actual case's sources and jurisdiction before use.
Completion of unrelated states is not a prerequisite for a qualified case.

## Proposed manual method: separate the three facts

Each decision records evidence for **identity**, **current authority**, and
**the exact business-to-entitlement association** separately. No checkbox, public
name match, contact challenge, paid status or signed licence establishes all three.

1. **Resolve the business and source.** Start from an independently located
   issuing office or the record owner's authenticated source system, not a URL or
   document supplied by the requester. Retrieve by jurisdiction and source record
   identifier where available; a name search yields candidates, not a binding.
   Record source owner, stable reference, retrieval time, source revision/date,
   attributes actually established and coverage limits. A requester may supply
   a search lead; validate it independently before it becomes evidence.
2. **Establish identity independently.** Prefer an existing, independently
   established customer identity relationship with recorded provenance. The verifier
   initiates contact using the route independently retrieved from that relationship
   and binds the actual person to it under the qualified identity procedure.
   A billing email, shared inbox, successful callback or control of a phone alone
   is insufficient. The profile must explain how the original person was identified,
   why the route still belongs to that person and how reassignment/compromise is
   checked. If that provenance is absent, identify and qualify another independent
   identity-binding method before use; none is selected by this work order.
   Do not create a new relationship from this request and call it prior evidence.
3. **Establish the relevant authority.** Apply the authority basis below. Retrieve
   current source information, establish its effective dates and check available
   amendments, withdrawals and contradictory records. A filing's retrieval time is
   not proof that the underlying facts are current. Where the source cannot expose
   the needed scope or a change, qualify an additional independent source for that
   missing fact instead of declaring the filing complete. No universal document
   or arbitrary fixed freshness interval is introduced.
4. **Establish the licensing association.** Licensing retrieves its authoritative
   issuance and commercial provenance and records the association below. Verify
   the particular business, not simply the payer or a provider customer label.
   Separate identity success from authority success and association success;
   a missing fact leaves that component unresolved without manufacturing a denial
   of customer eligibility. Missing/corrupt required history retains the canonical
   STOP semantics and cannot become a new-enrollment or unconsumed claim.
5. **Record and hand off.** The authenticated verifier records a decision bound to
   the method, source and association revisions. Qualified evidence then enters the
   canonical pending-enrollment and separately qualified credential-registration
   ceremony. Licensing rechecks current revisions/withdrawals at approval under
   its future serialized writer. A manual read followed by a write is not atomic
   authorization. This method supplies neither recovery approval nor publication.

| Authority basis | Procedure and missing qualification |
| --- | --- |
| Owner/officer, including single-member company | Use the issuing entity record for facts it actually contains, then independently validate existing governing or authorization records only where needed for the requested scope. The profile must establish authenticity and current effect through independent corroboration, such as issuer validation or authoritative records retrieved through an independently established route. Custody by the requester alone is not that corroboration; no universal extra custodian contact is required. An agent, organizer or shareholder label alone is not authority for recovery. Own authority needs no self-authorization document or second owner. The concrete governing-record validation profile is still required where a registry is insufficient. |
| Sole proprietor | Link the independently identified natural person to the business activity and authoritative commercial relationship. Use an applicable issuing trade-name record if it supplies that link; own-name proprietors can use independently maintained direct-sale/business records that actually establish the relationship. An unverified invoice, payment, uploaded statement or operator recollection alone does not. The actual sales-source provenance must be qualified; its absence is a method gap, not a reason to require incorporation, a new registration or a new purchase. |
| Delegate | Verify the delegate's identity, the grantor's current authority by the applicable path above, and the existing instrument's authenticity, scope, effective dates and withdrawal status. Follow the full current chain. No new form is needed where the existing instrument suffices. The requester cannot approve their own delegation; this does not impose a second authority on an owner acting on their own authority. |

For enrollment during recovery, source relationship and contact provenance must
meet the canonical pre-case independence rules; independent retrieval may happen
after the case opens. Current verification remains required. An old genuine
record cannot rescue expired or withdrawn authority. Bound credential registration
and the recovery-independent credential profile remain separate work orders.

## Proposed licensing issuance and association journal

The proposed [licensing register specification](LEAD-OWNER-LICENSING-REGISTER.md)
develops the source/owner recommendation, closed record branches and writer ordering.
It is a separate contract proposal, not an implemented registry or licensing adoption.

Because no registry exists in the inspected main branches, propose a licensing-owned
revisioned journal and an adapter to the actual authoritative commercial source.
This is a new record system requiring adoption, not an existing service capability.
If a suitable authoritative issuance system is found, use its supported record and
revision mechanisms rather than build a redundant journal. The provider designated
in private invoice-processor issue 94 is a candidate input only; public contracts
contain no provider-specific commercial details.

The proposed record carries the following facts; this table is not a wire schema:

| Record component | Required provenance and meaning |
| --- | --- |
| Commercial authority reference | Opaque source-system and record reference, source revision/event, authenticated retrieval and responsible record owner; evidence explaining why the verified business owns this issuance. A provider customer ID or paid flag alone is not that explanation. A legitimately non-sale issuance uses its authoritative grant/issuance provenance, not a fictitious purchase. |
| Issuance reference | Exact entitlement ID, original signed-envelope reference/digest, issuer/key context and issuance record revision. Verify under the applicable entitlement contract. A customer-submitted valid signature proves issuance, not business ownership. |
| Verified association | Opaque enrollment reference and revision, organization ID, method/evidence decision references, authenticated decision maker and provenance-bearing association revision. Identity documents and contact details stay outside the licence service and entitlement. |
| Consumed-deployment extension | Original claim ID, consumed operation, authoritative receipt digest and exact original organization/entitlement binding. Before consumption this extension is pending, never an assertion of non-consumption. Recovery requires the actual authoritative consumed record. |
| History and current decision state | Preserved association revisions, withdrawal/correction reason and provenance, prior decision references and current-version comparison. No silent rewriting or reassignment of original consumption. |

The later storage/wire contract must use closed branches and existing identifier
types, database uniqueness and transactional revision checks at the authoritative
writer. Exact retries refer to the same issuance/association; a reused operation
with different facts conflicts. Serialize competing association/correction writes
and revalidate referenced enrollment authority at the decision boundary. Define
cross-store fencing and restore baselines rather than assume a transaction spans
both stores. No executable schema or database is created here.

One business may own multiple entitlements. Renewal can produce a new entitlement
ID and needs its own association; it cannot replace the original recovery lineage.
An evidenced correction preserves prior history and its consequences for existing
decisions. A conflict needs reconciliation against authoritative sources, not an
email/name join, automated reassignment or an invented new organization.

## Minimal retained facts and end conditions

The canonical [retention schedule](LEAD-OWNER-BUSINESS-VERIFICATION.md#proposed-source-retention-schedule)
owns the configurable receipt-based source-copy default, zero-duration path,
deletion receipts and retention disclosures. This work order introduces no new
duration, automatic extension or permanent raw-document requirement.

| Class | Minimum purpose-bound facts; end condition |
| --- | --- |
| Raw method source copies | Only copies the qualified method actually needs; canonical source-copy expiry/deletion applies, including pending uploads and backups. Prefer independently retrievable references when sufficient. Zero means no persistent source copy, not no verification. |
| Enrollment evidence decision | Method/source references and versions, attributes needed to explain identity/authority, observed validity/withdrawal, verifier and decision references. Retain while supporting current authority or a dependent decision; after that, remove identifying details not needed by the retained decision/lineage classes. The storage profile must enumerate those fields and its demonstrable end condition before use. |
| Licensing association and consumed lineage | Opaque binding, issuance/consumption references and revision history needed to preserve the original association and explain derived recovery decisions. Retain under the canonical active-authority/derived-replacement conditions. Source expiry, contract expiry or account closure alone cannot erase consumption or prove that the lineage can be discarded. |
| Commercial source, backups and required audit | The actual source owner's separate schedule and obligations must be identified. Do not inherit a proposed payment-service duration or assume a source-copy slider deletes licensing history or third-party records. Disclose each retained class, basis and demonstrable end condition; unresolved schedules prevent collecting that class. |

The new journal must avoid names, email addresses and source-document contents;
opaque references still need controlled access. The private enrollment store owns
identity-bearing facts. Source deletion can make a future re-verification necessary
under the canonical unavailable-evidence rules; it never repairs corrupt history or
grants permission to reuse a consumed claim. Pre-expiry notice remains the separate
follow-up in issue 101 and does not extend a selected retention period.

## Restriction and cost audit

| Obligation | Cost/exclusion | Concrete need and why the lighter alternative fails |
| --- | --- | --- |
| Independent source retrieval and separate identity binding | Verifier work; a method may wait for adequate evidence. | Public filings and receipts are copyable. A name match or contact challenge alone lets an impersonator claim deployment authority. Reuse adequate existing evidence; ask only for the missing fact, with no universal paid certificate, ID document, biometric step or second person. |
| Scope/current-authority check | Additional source work only when existing evidence is insufficient. | Registry existence and agent labels do not establish authority to replace a deployment; an old authority can be withdrawn. Adding an unsupported universal document would not solve this. Use the source that actually establishes the missing scope/current fact. |
| Actual source owner and revisioned issuance association | Licensing adoption and record-management work. | The current licence subject has no verified-business semantics, and renewals change entitlement IDs. A mutable email join loses the original binding; one explicit association with preserved history is enough, without adding identity fields to licences. |
| Case-specific qualification and source-use permission | Research/access work for the affected profile. | A source with unknown fields, provenance or permitted use cannot support a defensible authority decision. This requires qualifying the source actually used, not finishing all states or excluding sole proprietors. |

## Future qualification and completion gates

These are planned synthetic cases, not executed identity or source qualification:

| Case | Required observation |
| --- | --- |
| Valid owner/officer, sole proprietor using applicable trade-name record, own-name proprietor with no registry requirement, valid delegate | Each path can establish all three facts without inapplicable registration, self-authorization paperwork or a second owner. |
| Copied filing plus impersonator; registered agent without recovery authority; real officer with another business's entitlement | Each missing fact fails independently despite other valid components. |
| Shared/reassigned contact, stale officer record, revoked delegation, conflicting current sources | Contact control or a genuine old document cannot qualify the decision; record the unresolved component and retrieve independent current evidence. |
| Recovery-time enrollment with pre-case provenance retrieved later; relationship created by the request | First remains possible under the canonical checks; second cannot be its own trust root. |
| New issuance before consumption; valid non-sale grant; multiple licences and later renewal | No invented consumption or purchase requirement; explicit associations preserve original recovery identifiers. |
| Exact retry, changed retry, concurrent competing bindings, correction against stale authority, withdrawal racing approval | One authoritative outcome, preserved history, stale/conflicting decisions rejected at the writer. No approved state from an unguarded manual lookup. |
| Deleted raw sources with intact lineage; absent/corrupt original consumption; restored pre-withdrawal snapshot | Canonical unavailable-source versus STOP distinctions preserved; no reset to unconsumed and no approval on stale restored authority. |
| Partial proof, unknown fields, free-form verified flag, real source failure | Missing proof cannot become qualified; schema-first validation and one owner for cross-record checks in the later implementation. Synthetic success never claims a real identity method passed. |

Before execution, complete and accept the actual source profiles, identity-binding
procedure, sales/grant and issuance source with its owner, store/retention choices,
licensing adoption, and closed storage/wire ordering contract. Demonstrate the
actual source access and evidence properties separately from synthetic transitions.
No provider account, business source or new credential mechanism is selected here.

Drafting can finish with those gaps explicit. This revision is ready for contract
review only. Acceptance accepts this work order, not live verification, fixtures,
implementation, a production registry or the open licensing proposal. Track the
remaining inputs in [issue 101](https://github.com/canfieldjuan/connect-automate/issues/101).
