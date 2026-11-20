# Firestore Read Model

**DRAFT, proposed by Shoaib, needs Prajit's approval.**

Drafted from the build plan, page 10, because this file was still an empty heading
and the web lane cannot build live screens without it.

Firestore is the **live read model**. Only the API writes to it, through the Admin
SDK. No client ever writes. Clients open live listeners and unsubscribe when a
screen closes.

Conventions carried over from the API contract:

- Money is an integer number of paise, stored as a **string**.
- Times are Firestore `Timestamp` values. The web lane renders them in IST with a
  relative time beside them.
- Account numbers are stored **masked to the last four digits**. The full number
  exists only inside the canonical summary the approver signs, which never lands
  in Firestore.
- Anything written by Gemini carries `source: "gemini"` so the screen can label it
  as AI-written.
- A security check that did not run is `null`, never `false` and never absent. The
  web lane renders `null` as "couldn't verify", never as a pass.

## Who may read what

| Role | Reads |
| :--- | :--- |
| `finance` | everything below |
| `clerk` | `holds`, `holds/{id}/steps`, `agentRequests`, `payouts` |
| no role | nothing |
| any client | never writes, anywhere |

> **Needs Prajit's decision.** The build plan says only the `finance` role reads
> these documents. The buildathon wireflow also needs an accounts clerk in the mock
> ERP to see the status of the payment they just raised and the agent run they
> started, so this draft widens the rule to the `clerk` role for four collections.
> This is a real widening of the plan and should not land without his yes.

## `holds/{intentId}`

Read by the console holds board, the console payment detail and the mock ERP
payment status.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `intentId` | string | `pi_` prefixed ULID, same as the document id |
| `status` | string | `held`, `approved`, `declined`, `released`, `blocked`, `expired` |
| `tier` | number | 0 to 3 |
| `amountPaise` | string | integer paise |
| `currency` | string | `INR` |
| `payeeNameAtBank` | string | the name as the bank returns it, where a bank exposes it |
| `payeeAccountLast4` | string | four digits |
| `payeeIfsc` | string | |
| `payerAccountLast4` | string | |
| `purpose` | string or null | usually the invoice number |
| `instructionChannel` | string | `portal`, `email`, `chat`, `phone`, `agent` |
| `initiator` | map | `{ type: "human" \| "agent", id: string }` |
| `reasons` | array of map | `{ code, text, source, changedFrom?, changedTo? }` |
| `explanation` | map or null | `{ text, source: "gemini", modelVersion }` |
| `modelArmorFinding` | map or null | `{ category, detail, excerpt, foundAt }` |
| `policyVersion` | string or null | |
| `approvers` | array of string | work emails from the approval matrix |
| `approver` | string or null | who actually decided |
| `mandateId` | string or null | set once a mandate exists |
| `agentRequestId` | string or null | set when an agent raised it |
| `payoutId` | string or null | set once the sandbox bank paid |
| `createdAt` | timestamp | |
| `updatedAt` | timestamp | |
| `expiresAt` | timestamp or null | |

Indexes the console needs: `status` ascending with `createdAt` descending, and
`tier` descending with `createdAt` descending (the board sorts by risk).

## `holds/{intentId}/steps/{n}`

Read by the payment timeline. One document per step, document id is the zero-padded
step number so ordering is stable.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `n` | number | 1, 2, 3 ... |
| `step` | string | `created`, `scored`, `held`, `pushed`, `signed`, `verified`, `voice_started`, `voice_verified`, `voice_failed`, `countersigned`, `released`, `blocked`. The three `voice_` steps appear only on Tier 2 and higher payments (M4) |
| `at` | timestamp | |
| `detail` | string or null | one line, plain language |

## `devices/{deviceId}`

Read by the console Devices page, which is read-only for the buildathon. The
Revoke button is disabled and says it arrives in a later release.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `deviceId` | string | `dv_` prefixed |
| `approver` | string | work email |
| `phoneModel` | string or null | |
| `keySecurityLevel` | string | `StrongBox`, `TrustedEnvironment` or `Software` |
| `patchLevel` | string or null | `YYYY-MM-DD` |
| `lastIntegrityVerdict` | string or null | **null when no verdict was recorded.** The page says "couldn't verify", never a pass |
| `revoked` | boolean | |
| `enrolledAt` | timestamp | |

## `agentRequests/{agentRequestId}`

Read by the mock ERP's agent run view and the console payment detail.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `agentRequestId` | string | `ag_` prefixed |
| `agentId` | string | the agent's Agent Identity |
| `invoiceRef` | string or null | |
| `intentId` | string or null | the hold the request produced |
| `status` | string | `reading`, `mandate_requested`, `flagged`, `held`, `declined`, `failed` |
| `modelArmorFinding` | map or null | same shape as on `holds` |
| `log` | array of map | `{ at, text, source }`, the live agent log |
| `createdAt` | timestamp | |

## `payouts/{payoutId}`

Read by the sandbox bank page. A payout exists **only** because a mandate released
it; the collection is empty until then, and the page says "No money has moved yet".

| Field | Type | Notes |
| :--- | :--- | :--- |
| `payoutId` | string | `po_` prefixed |
| `mandateId` | string | |
| `intentId` | string or null | |
| `amountPaise` | string | |
| `currency` | string | `INR` |
| `payeeNameAtBank` | string | |
| `payeeAccountLast4` | string | |
| `payeeIfsc` | string | |
| `status` | string | `queued`, `paid`, `failed` |
| `createdAt` | timestamp | |

> **Needs Prajit's decision.** The sandbox bank page carries no sign-in, but the
> rules above require authentication to read anything. Two ways out:
>
> 1. **`GET /payouts` on the API with no auth** (drafted in `openapi.yaml`). The
>    bank page reads the API instead of Firestore. Preferred: it keeps the rules
>    closed and keeps a public page off the database.
> 2. **The bank page signs in silently as a clerk.** Less work for Prajit, but it
>    puts a service credential in a public page and weakens the story on stage.
>
> This draft assumes option 1. The web app is written so either works behind one
> flag.

## What is deliberately not here

`mandates` is not a Firestore collection. The console's mandate viewer and the
public verifier page read `GET /mandates/{id}`, so a mandate is served by the same
service that countersigned it and the verifier needs no Firebase credentials at all.
