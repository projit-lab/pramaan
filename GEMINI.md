# Gemini & AI Agent Context - Pramaan

## Project Overview
Pramaan is a corporate payment protection platform. It holds a company's risky payments until the real approver signs that exact payment on their own phone, using a key stored in the phone's secure hardware.

## Architecture & Directory Ownership
- `android/`: Prajit. Approver app (`app` module) and hardware key module (`core-crypto`).
- `services/api/`: Prajit. FastAPI backend on Cloud Run.
- `services/agent/`: Prajit. ADK payables agent, MCP server, Model Armor.
- `web/`: Shoaib. Console (`web/console`), ERP mock (`web/erp-mock`), verification portal (`web/verify`), and shared components (`web/shared`).
- `contracts/`: Both (Prajit & Shoaib). API specs, mandate schema, test vectors, event models, Firestore models. Dual approval required.
- `data/`: Both. Seed fixtures, sample invoices, BigQuery DDL.
- `infra/`: Both. Cloud Build pipelines, Firestore rules, IAM scripts.
- `docs/`: Both. Architecture and milestone documentation.
- `.agents/skills/`: Both. Antigravity skill definitions.

## Repository Rules
1. Branches must be short-lived and named `type/area-description` (e.g. `feat/android-keystore`).
2. Commits must follow Conventional Commits (`feat:`, `fix:`, `chore:`, etc.).
3. `main` is always deployable. All changes merge via squash PRs with review from the other developer.
4. Any change to `contracts/` requires both Prajit and Shoaib's approval.
5. Security-critical code (`android/core-crypto`, attestation/mandate/gate logic in `services/api`) requires Prajit's approval and automated test passage.
6. Never commit secrets, keys, `google-services.json`, or service account keys.
7. Money is an integer number of paise sent as a string (e.g., `"100000"` for ₹1,000.00).
8. Time in the API is ISO 8601 with `+05:30` offset.

## Absolute Safety Rule
**Never write code that lets an AI agent release a payment.** All payments require explicit cryptographic human approval with a phone's hardware-backed key.
