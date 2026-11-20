# Pramaan Contracts

What goes here: Canonical API specifications, mandate schema definitions, test vectors, event formats, and Firestore read models.
Owner: Prajit and Shoaib (both). Any change requires approvals from both developers.

## Naming Rule

- **REST APIs and Pub/Sub events** use `snake_case` (e.g. `payee_name_at_bank`, `amount_paise`, `intent_id`).
- **Firestore collections and documents** use `camelCase` with the **identical words** (e.g. `payeeNameAtBank`, `amountPaise`, `intentId`).
- The mapping between REST/events and Firestore is strictly mechanical (lossless 1:1 casing transform).
