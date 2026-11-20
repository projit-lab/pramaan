# Pramaan Events

**DRAFT, proposed by Shoaib, needs Prajit's approval.**

Drafted from the build plan, pages 5 and 10, because this file was still an empty
heading. Prajit owns the publishers and the subscribers; the web lane never
publishes or consumes a Pub/Sub message. This draft exists so both lanes agree on
what each step is called, because the same names appear as `step` values in
`holds/{intentId}/steps` and therefore on screen in the payment timeline.

## Topics

| Topic | Published when | Consumed by |
| :--- | :--- | :--- |
| `intent.created` | a payment intent is accepted | ledger writer, Firestore projector |
| `intent.decided` | the policy engine returns release, hold or block | ledger writer, Firestore projector, push notifier |
| `approval.signed` | a device signature is verified | ledger writer, Firestore projector |
| `mandate.issued` | the mandate is countersigned with Cloud KMS | ledger writer, Firestore projector |
| `payment.released` | the gate released the payment to the payout rail | ledger writer, Firestore projector |
| `payment.blocked` | declined, reported as fraud, or refused by the gate | ledger writer, Firestore projector, push notifier |
| `device.enrolled` | an approver phone passed every enrolment check | ledger writer, Firestore projector |

Three subscribers consume them: the **ledger writer** (appends to BigQuery with the
previous row's hash, so the ledger is a hash chain), the **Firestore projector**
(writes the `holds` documents the web lane reads) and the **push notifier**
(Firebase Cloud Messaging data messages to approver phones).

## Envelope

Every message carries the same envelope, so the ledger writer and the projector can
be written once.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `event_id` | string | unique per message, for idempotent consumers |
| `event_type` | string | one of the topics above |
| `occurred_at` | string | ISO 8601 with `+05:30` in the message; UTC in BigQuery |
| `company_id` | string | |
| `intent_id` | string or null | null on `device.enrolled` |
| `actor` | object | `{ type: "human" \| "agent" \| "service", id }` |
| `data` | object | the per-event payload below |

Rules that hold for every payload:

- Money is an integer number of paise as a string.
- Account numbers are masked to the last four digits. Full account numbers, device
  signatures and tokens never appear in an event.
- Anything a model wrote carries `source: "gemini"` and a `model_version`, plus a
  hash of the prompt, so the ledger records which model said what.

## Payloads

`intent.created`

    { "amount_paise": "465000000", "currency": "INR",
      "payee_name": "Global Trade Solutions", "payee_account_last4": "9032",
      "payee_ifsc": "WXYZ0004411", "payer_account_last4": "4521",
      "purpose": "Urgent vendor advance", "invoice_sha256": null,
      "instruction_channel": "chat", "initiator": { "type": "human", "id": "clerk@acme.example" } }

`intent.decided`

    { "decision": "hold", "status": "held", "tier": 2, "policy_version": "2026.11.1",
      "reasons": [ { "code": "new_payee", "source": "rule" },
                   { "code": "pressure_language", "source": "rule" } ],
      "model_armor_finding": null, "approvers": ["md@acme.example"] }

`approval.signed`

    { "approval_id": "ap_01JD2X...", "approver": "md@acme.example",
      "decision": "approve", "device_id": "dv_01JD2X...",
      "key_security_level": "StrongBox", "patch_level": "2026-10-01",
      "device_integrity": "MEETS_STRONG_INTEGRITY",
      "summary_sha256": "9f1c...", "verified": true }

`mandate.issued`

    { "mandate_id": "pm_01JD2X...", "summary_sha256": "9f1c...",
      "kms_key_version": "mandate-signer/3", "tier": 1,
      "expires_at": "2026-11-21T11:42:07+05:30" }

`payment.released`

    { "mandate_id": "pm_01JD2X...", "payout_id": "po_01JD2X...",
      "amount_paise": "98000000", "rail": "sandbox" }

`payment.blocked`

    { "reason": "declined_by_approver", "detail": "The MD declined and reported it as fraud.",
      "mandate_id": null, "blocked_at_step": "signed" }

Proposed `reason` values: `declined_by_approver`, `reported_fraud`,
`mandate_mismatch`, `mandate_expired`, `mandate_already_used`,
`signature_invalid`, `approval_expired`. The console renders each as plain text and
never as the word "fraud" unless the approver chose "Report fraud".

`device.enrolled`

    { "device_id": "dv_01JD2X...", "approver": "cfo@acme.example",
      "phone_model": "Pixel 9 Pro", "key_security_level": "StrongBox",
      "patch_level": "2026-10-01", "attestation_root": "ecdsa_p384" }

## Step names must match

The `step` values in `holds/{intentId}/steps` are `created`, `scored`, `held`,
`pushed`, `signed`, `verified`, `countersigned`, `released`, `blocked`. They are not
one-to-one with topics: `scored` and `held` both come out of `intent.decided`,
`signed` and `verified` both out of `approval.signed`, and `pushed` is written by
the push notifier rather than by an event of its own. If Prajit changes a step name,
the payment timeline changes with it, so it belongs in this contract.
