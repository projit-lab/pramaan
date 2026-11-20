# Contributing to Pramaan

Welcome to Pramaan. Both contributors (Prajit and Shoaib) follow these core practices:

## Branching & Commit Workflow
- **Branch Naming**: Branches are short-lived and named `type/area-description` (e.g., `feat/android-keystore`, `feat/console-holds-board`, `fix/api-nonce-expiry`).
- **Conventional Commits**: Commit messages follow the Conventional Commits specification (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- **Deployability**: `main` is always deployable. Changes land only through pull requests, squash-merged, with at least one approval from the other developer.

## Governance & Approval Policies
- **Contracts Changes**: Any change under `contracts/` strictly requires approvals from both Prajit and Shoaib.
- **Security-Critical Code**: Code touching `android/core-crypto` or attestation, mandate, and gate code in `services/api` strictly requires Prajit's approval and passing automated tests.

## Security & Secrets
- Never commit secrets, private keys, `google-services.json`, or service account credentials. Use Google Secret Manager.

## Domain & Protocol Conventions
- **Financial Amounts**: Money is represented as an integer number of paise sent as a string (e.g. `"100000"` for ₹1,000.00).
- **Timestamps**: All timestamps in the API follow ISO 8601 with the `+05:30` offset (Indian Standard Time).
