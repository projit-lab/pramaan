# Web lane, M0: decisions and what needs Prajit's approval

Author: Shoaib. Date: 20 Nov 2026. Status: proposed.

This is the short version for review. It records what the web lane decided in M0,
why, and the four things that cannot land without Prajit.

## Needs Prajit's approval

### 1. The contract drafts

`contracts/openapi.yaml`, `contracts/firestore.md` and `contracts/events.md` were
empty. The web lane is blocked without them, so they are drafted and marked
**DRAFT, proposed by Shoaib, needs Prajit's approval** at the top of each file.

`contracts/mandate.schema.json` and `contracts/canonical/vectors.json` are
untouched: they are Prajit's, and nothing in the web lane needs them yet.

Where the draft carries a security field (nonce, device signature, attestation
chain, canonical summary, mandate hashes) it passes it through as an **opaque
string** and says so in the description. It does not define how any of them are
built. Request bodies that only the Android app or a connector ever sends are typed
as `additionalProperties: true` with "Owned by Prajit", so he can fill them in
without the contract having guessed wrong first.

### 2. `canonical_b64` on `GET /mandates/{id}`

**Proposal.** The mandate response should carry the exact canonical bytes that were
countersigned, base64-encoded.

The verifier page must hash exactly what Cloud KMS signed. Without those bytes, the
browser would need a third canonicalisation implementation in TypeScript, beside
the Kotlin and the Python ones. Three implementations of "keys sorted by code
point, no whitespace, every value a string, NFC-normalised" will drift, and the
first symptom is the public verifier page calling a genuine mandate invalid on
stage.

Returning the bytes costs nothing and removes the whole class of bug. The signature
still proves itself: the browser hashes the bytes, verifies the KMS signature over
that hash, and separately checks that the mandate fields it renders match those
bytes.

Related, already handled on the web side: KMS returns a DER signature and WebCrypto
wants raw `r||s`, 64 bytes. The verifier converts.

### 3. How the public sandbox bank page reads payouts

The sandbox bank page carries **no sign-in** — a judge or an auditor opens it cold.
But the Firestore rules require an authenticated user to read anything. So the page
cannot read `payouts/{id}` directly.

Two ways out:

| | How | Cost |
| :--- | :--- | :--- |
| **A, preferred** | `GET /payouts` on the API with `security: []` | A small endpoint for Prajit. Keeps the rules closed and keeps a public page off the database. |
| **B** | The bank page signs in silently as a clerk | No backend work, but it ships a credential in a public page and weakens the story when a judge asks who can read what. |

Drafted as **A**. Both are implemented behind one value, `VITE_PAYOUTS_SOURCE`, so
switching is a one-line change either way.

### 4. The `clerk` role widens the read rules

The build plan says only the `finance` role reads the live read model. The
buildathon wireflow also needs an accounts clerk in Acme ERP to see the status of
the payment they just raised and the agent run they started.

`infra/firestore.rules` therefore grants `clerk` read access to `holds`,
`holds/*/steps`, `agentRequests` and `payouts` — and **not** to `devices`, which is
none of a clerk's business. This is a real widening of the plan's rule and should
not merge without his yes. It is covered by tests either way.

## Decisions the web lane made on its own

**The API is generated, never committed.** `shared/src/api/schema.d.ts` is produced
from `contracts/openapi.yaml` by `npm run gen:api`, in the build as well as
locally. If the contract and the code drift, typecheck fails and nothing deploys.

**Firestore types are hand-written.** Firestore has no schema to generate from, so
`shared/src/types/firestore.ts` mirrors `contracts/firestore.md` by hand. A renamed
field there becomes a compile error at every screen that has to change with it.

**Money never passes through a JavaScript number.** Paise are kept as digit strings
and formatted with BigInt. A crore-sized amount has no business going through
floating point on its way to an approver's eyes.

**Mandates are not a Firestore collection.** The console's mandate viewer and the
public verifier both read `GET /mandates/{id}`, so a mandate is served by the same
service that countersigned it, and the verifier needs no Firebase credentials at
all. Noted in `firestore.md` as deliberate.

**The verifier page carries no Firebase SDK.** It deep-imports from
`@pramaan/shared` rather than the barrel, because the barrel's Firebase re-exports
defeat tree-shaking. The bundle is 223 kB instead of 685 kB, and a public page
pulls in nothing it does not use.

**Not-built-yet is said out loud.** Payment detail names the attestation card, the
invoice panel and the mandate viewer as arriving in M1 to M3 instead of showing
empty cards that read like passed checks. The verifier says it is not verifying
yet. Revoke is disabled and says when it arrives. A disabled honest button beats a
live dishonest one.

**`null` is not `false`.** A security check with no recorded result renders
"couldn't verify", never a pass and never "fraud". The seed deliberately includes
one phone with no integrity verdict so that path stays exercised.

## Flagged to Prajit, his lane to decide

- **Cloud KMS protection level.** An HSM key version costs roughly $2.50 a month;
  software protection is about $0.06. For the buildathon, software protection is
  fine and the demo stays honest if the console and the deck say
  "software-protected KMS key". The countersignature and the verifier work
  identically either way, so nothing in the web lane depends on the choice.
- **Model Armor has no free tier**, and no AI Studio equivalent. If it is dropped,
  the console must label the finding "injection check by Gemini" rather than
  "Model Armor". The `model_armor` reason source is already separate from `gemini`
  in the shared library, so relabelling is a one-line change and no screen lies
  either way. The hard rule carries the demo regardless: the invoice's account does
  not match the vendor master, so a **rule** raises the tier whatever a model
  noticed.
- **Agent Identity is a paid Vertex feature.** ADK itself is an open-source library
  and runs free on Cloud Run with an AI Studio key. Without Agent Identity, the
  agent id is a string Pramaan assigns, so the deck should say "an agent identifier
  we issue" rather than "Google Agent Identity".
- **Gemini via AI Studio gives no India data residency guarantee**, while the
  product document promises India-only ML processing and "never the global
  endpoint". Either use Vertex regional endpoints, or say on stage that residency
  is the production design and the buildathon runs on AI Studio.
- **Play Integrity** only recognises builds installed from a Play internal testing
  track, and a new Play developer account needs identity verification that can take
  days. Until a verdict is really produced, no screen claims Play Integrity is
  enforced; the Devices page shows "couldn't verify".
- **Firestore as system of record for the buildathon**, with AlloyDB as the
  production target. AlloyDB Express is preview-only with no India region. The web
  lane only reads Firestore and calls REST, so this does not block it either way.

## Out of scope for the buildathon

M5 in the build plan is product roadmap, not buildathon work: the policies editor,
the bank-change desk, delegation, break-glass, the full Playwright suite and VPC
Service Controls. Also skipped for now: the memo page, Data Studio embedding and a
tablet layout. The Devices page ships read-only, and Ask-the-ledger is "if time
allows".
