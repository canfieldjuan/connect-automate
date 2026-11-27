# V1c work order for one form notification and one lead

**Proposed, contract only.** This moves the first-lead finish line from an
authenticated form notification to one canonical lead. The
[first-proof amendment](LEAD-FIRST-PROOF-AMENDMENT.md) was accepted at
`c9a3f11839a2e70400b194a61b15948c97e0ee94` and merged as PR 116. Juan authorized
starting V1c. The [accepted delivery plan](LEAD-VERTICAL-DELIVERY.md) requires
a reviewed, accepted bounded work order before its implementation PR. This
work order covers the real local path using entirely synthetic inputs.

## Root cause and inventory

At `0b14674fc7a1318b746324f8a67b9d56ec077b6e`, the signed source model accepts
only a normalized-text snapshot. It cannot preserve the exact selected form
part. Source custody identifies receipts by organization, namespace and event
ID. When a provider sends the same physical message under another event ID,
the receipt is not a canonical lead identity. Lead Intake has no derived
record owner on this path.

| Existing owner | Reuse and intended difference |
| --- | --- |
| `src/connect_automate/lead_intake/source.py:77,129,228` and `auth.py` | Reuse physical-source identity, closed signed envelopes, canonical bytes and source-writer authorization. Add a versioned form-source branch at this owner. |
| `lead_intake/admission.py:146,160` and `custody_store.py:192` | Reuse the authenticated source writer and retained-read path. The form uses one template parser before its custody commit. Resume reads through the owner. |
| `lead_intake/custody_handoff.py:153,193,199` and `automate/runtime.py:290,308` | Reuse scoped submit/resume and the signed no-action route. Extend the path to commit a lead after source and workflow success. |
| Lead Intake record writer | Add one owner for derived fields and physical-source uniqueness. Existing custody and workflow owners contain different records and do not own lead fields. |

Existing source, authentication and custody suites are the regression baseline.
Use existing signed no-action workflow fixtures with synthetic form input.
No model, prompt, inference or real sender is involved. Preserve v1 wire bytes
and results for existing source and workflow versions before claiming parity.

## Required behavior and change surface

1. **Preserve the selected form.** Extend `lead.source.admission` with a
   closed, discriminated `2.0` branch. Reuse the signed scope, physical source,
   event and retention fields and the existing canonical signing owner. V2
   carries a versioned template ID, exact selected MIME part identifier,
   media type and charset, canonical base64 of the exact transfer-decoded
   bytes and their SHA-256. Bind source-owner evidence to the raw-message
   digest, selected part, signing domain and selector. Full envelope/receipt
   bindings stay in force. The synthetic signer only supplies fixture
   evidence. EW will qualify its actual DKIM verifier in V1d. A caller flag
   or mail header is insufficient as proof. The old normalized-text branch
   retains its wire bytes and validation. Reuse existing source envelope and
   body budgets without raising them. Reject unknown or mixed variants.
2. **Extract one structural template.** Use a synthetic UTF-8 plain-text
   form with a header block containing one `Name:` and one `Email:` field,
   followed by a `Message:` boundary and the free-form message body. Accept
   either order of the two headers and LF or CRLF framing. Label-like text
   inside the message is data. One named Lead Intake parser recognizes the
   grammar using the line/field structure and validates required
   `name`, `email` and `message` strings in a strict closed model. A missing
   field remains distinct from a present blank. The submitted email is text
   for review and conveys no identity or delivery authority. Preserve Unicode
   and message whitespace. Unknown or duplicate headers, malformed structure
   or bytes and nonmatching template/media type fail closed. Hash the exact
   original bytes. This synthetic format is a testable candidate and does not
   claim to match the selected live notification.
3. **Commit one canonical lead.** Add a Lead Intake record writer and a
   transactionally enforced unique key over the organization and complete
   physical `SourceIdentity`. After authenticated source custody and the
   no-action workflow commit, store the lead ID, immutable source receipt
   reference, versioned template and field schema, part identity and digest,
   canonical fields, `NEEDS_REVIEW`, and scoped stable stage-set and initial
   stage references. Reuse the accepted default stages. Initial stage
   assignment does not change review state. A current authorized replay with
   the same source and form binding returns the original lead even if the
   delivery ID or current signing key changed. A changed part, template or
   content for the same physical source refuses. Different physical sources
   can share the same submitted values and still create distinct leads.
4. **Recover in commit order.** Source, workflow and lead own separate
   commits. Use retained, freshly authorized source custody and the original
   template to resume the missing step. Keep replay checks at their owners
   and evaluate current authority and source availability after relevant
   waits. A lost reply after the lead commit returns the same committed
   reference. If retained content expires while the lead is still missing,
   report the incomplete outcome. Do not read Gmail again or fabricate a
   lead. Logs, workflow outputs and errors carry only scoped references and
   typed outcomes. Private lead records own fields. Existing custody owns
   source bytes.

Implementation touches the listed source/admission and handoff/runtime seams,
the scoped lead writer, synthetic fixtures, tests and the existing Windows
CI selection. Keep public capabilities disabled. V1c introduces no product
installer behavior, new transport, scheduler, dependency, attachment path,
mailbox discovery or lead-list surface.

## Restrictions, assumptions and verification

| Constraint | Cost, concrete need and why a lighter rule fails |
| --- | --- |
| One synthetic template for V1c | A fixed structure can prove deterministic field ownership. Guessing fields across unknown layouts could produce a false lead. This limits the proof fixture, with real template qualification left to V1e. |
| Signed, lossless part and scoped admission | Adds evidence at the source owner. Normalized text or a matching sender label cannot identify the original bytes that populated the fields. |
| One lead per physical source in its organization | Event-only uniqueness duplicates redelivery. Contact-based matching discards distinct leads. The physical-source key suffices. |
| Existing bounded custody and signed no-action route | Existing limits protect the same parser/storage path. A generic action pack would add external effects. No new cap, purchase or native sign-in is needed. |

The real sender, form template and proof-PC entitlement are unverified.
Confirm the selected template privately in V1e. The later V1e work order can
check entitlement early when host access is separately authorized. Synthetic
V1c proceeds while it is unverified. EW delivery and DKIM belong to V1d.
V1e owns the real run. V2 owns list reads. All Gmail, activation, native
sign-in, Hello and restore holds apply. PR 115 stays parked.

The executable pass condition is one synthetic signed notification through
real local custody and no-action workflow stores yielding one retrievable
canonical lead reference and the exact private fields. The expected baseline
failure is refusal of the v2 source and absence of a lead commit. Keep existing
v1 wire and behavior coverage. Add focused Linux and Windows CI from the first
implementation push.

- Probe valid Unicode and both line endings, label-like message content, bad
  or mixed schemas, missing/duplicate headers, empty/present versus absent,
  wrong template or media, malformed encodings, wrong digests/scope, evidence
  gaps and source-size boundaries. Denied pre-commit inputs have no effect.
- Probe exact replay, changed delivery ID, fresh authorized signer, distinct
  source with matching fields, source/content conflict, wrong scope and revoked
  authority. Exercise independent writers racing for one lead after the same
  source, for the same binding and both orders of competing bindings. Assert
  stable fields. Exercise current-authority loss before the final check and
  after the already committed lead.
- Cover interruption before each commit, after custody before workflow, after
  workflow before lead, and after lead before reply. Cover loss of retained
  content before resume and the expiry boundary during a wait. Reopen real
  stores to prove durable outcomes and no mailbox reread or action dispatch.
- Deliver per-clause neutralizing mutations for changed guards with passing
  controls, negative tests, a process-tree memory cap, and per-mutant and
  total run budgets. Report each result in the implementation PR. Keep
  durable evidence outside the worktree, including hosted Windows checks.

Rollback disables the new form branch and preserves committed source,
workflow and lead records. This proposal adds only the work order and parent link.
Verify source citations, links and diff scope. **NOT DONE** for executable
V1c. Independent review and Juan's exact-revision acceptance of this work
order precede implementation under his recorded go.
