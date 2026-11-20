# Pramaan API Service

The backend FastAPI service for Pramaan, providing payment gate APIs, hold lifecycle management, and mandate verification.

Owner: Prajit

---

## Architecture & Adapters

The service is built around Python `typing.Protocol` interfaces with environment-driven runtime adapter selection (`local` vs `dev` / `demo` / `prod`):

| Component | Protocol | Local Adapter (`ENV=local`) | Cloud Adapter (`ENV=dev|demo|prod`) |
| :--- | :--- | :--- | :--- |
| **Mandate Signer** | `MandateSigner` | `LocalKeySigner` (generates/loads ECDSA P-256 key from gitignored `.local/dev_key.pem`; strictly refuses to load if `ENV != "local"`) | `KmsMandateSigner` (Cloud KMS HSM key `mandate-signer`, algorithm `EC_SIGN_P256_SHA256`) |
| **Event Bus** | `EventBus` | `InMemoryEventBus` (in-process event list) | `PubSubEventBus` (publishes uniform envelope per `contracts/events.md` to Cloud Pub/Sub topics) |
| **Read Model** | `ReadModel` | `InMemoryReadModel` (in-memory dictionary) | `FirestoreReadModel` (writes camelCase fields per `contracts/firestore.md`; honors `FIRESTORE_EMULATOR_HOST` if set) |
| **Ledger** | `Ledger` | `LocalJsonlLedger` (appends records to gitignored `.local/ledger.jsonl`) | `BigQueryLedger` (appends rows to BigQuery dataset `pramaan_ledger`) |

---

## Configuration & Environment Variables

Settings are managed via `pydantic-settings` in `app/config.py`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENV` | `local` \| `dev` \| `demo` \| `prod` | `local` | Active runtime environment |
| `GCP_PROJECT` | string | `pramaan-dev-515306` | Google Cloud project ID |
| `REGION` | string | `asia-south1` | Target GCP region |
| `KMS_KEY` | string | `projects/pramaan-dev-515306/.../cryptoKeys/mandate-signer` | Full resource name of Cloud KMS signing key |
| `DEMO_MODE` | boolean | `false` | Enables demo seed scenarios |
| `ALLOW_TEST_SIGNER` | boolean | `false` | Allows test signer in automated testing |
| `FIRESTORE_EMULATOR_HOST` | string \| null | `null` | Optional Firestore emulator host (e.g. `localhost:8080`) |
| `GIT_SHA` | string \| null | dynamic | Git short commit SHA for `/v1/health` |

See `.env.example` for local setup. Real `.env` files and `.local/` directories remain gitignored.

---

## Authentication & Authorization

- **Production / Dev**: Verifies Firebase ID tokens using `firebase-admin.auth.verify_id_token`.
- **Local Dev Bypass**: Passing `X-Dev-User: <username>` header bypasses Firebase Auth **ONLY** when `ENV=local`. Any attempt to send `X-Dev-User` when `ENV != "local"` is rejected with `403 Forbidden` (`RFC 9457 Problem Details`).

---

## Error Handling & Observability

- **RFC 9457 Problem Details**: All errors (4xx, 5xx, and validation errors) return `application/problem+json` formatted responses containing `type`, `title`, `status`, `detail`, `instance`, and field-level `errors`.
- **Cloud Logging JSON**: Logs are formatted as structured JSON lines (`severity`, `message`, `timestamp`, `trace`).
- **Data Protection & Sanitization**:
  - Full bank account numbers are masked to the last 4 digits (e.g., `********9012`).
  - Sensitive tokens, credentials, and signatures (`authorization`, `token`, `signature`, `summary_b64`, `mandate_b64`, `secret`, `private_key`) are stripped from log payloads.

---

## Local Development

### 1. Setup Virtual Environment
```powershell
python -m venv services/api/.venv
.\services\api\.venv\Scripts\Activate.ps1
pip install -e services/api
```

### 2. Run Tests & Linter
```powershell
ruff check services/api
ruff format --check services/api
pytest -v services/api/tests
```

To run the live Google Cloud KMS integration test against `asia-south1`:
```powershell
$env:RUN_GCP_TESTS = "1"
pytest -v services/api/tests/test_kms_integration.py
```

### 3. Run Local Server
```powershell
uvicorn app.main:app --reload --port 8080
```
Health endpoint:
```powershell
curl http://localhost:8080/v1/health
```

---

## M2 payment plumbing (Danish)

| Endpoint | What it does |
| :--- | :--- |
| `POST /v1/intents` | Validates, scores with policy engine v1, stores, routes holds to approvers, publishes `intent.created` and `intent.decided`, sends the approvers' phones an FCM data message |
| `GET /v1/intents/{intentId}` | The stored payment (`PaymentIntent`) |
| `GET /v1/approvals?status=pending` | The signed-in approver's own approvals, riskiest first; expired ones are marked on read |
| `GET /v1/mandates/{mandateId}` | Public. Serves the mandate document Prajit's mandate service stored |
| `GET /v1/vendors`, `GET /v1/policies` | Vendor master (with bank-change dates) and the active policy, read-only |

- **System of record** (`app/db/`): companies, approvers, devices, vendors with full bank-account history, payment intents, approvals, mandates, versioned policies. Alembic migrations in `migrations/`; a test fails if the models and the migration drift apart. `ENV=local` uses `.local/pramaan.db` (SQLite) and migrates and seeds it on first request; in the cloud set `DATABASE_URL` to AlloyDB and run `alembic upgrade head` as a deploy step.
- **Policy engine v1** (`app/domain/policy.py`): six rules (new payee, bank details changed in 30 days, amount thresholds, outside working hours, raised by an agent, instruction by chat or email). Tier 1 on any rule, tier 2 above the tier2 threshold or with three rules together, tier 3 above the tier3 threshold or for a first payment above Rs 10 lakh to an account changed in the last 30 days. Thresholds, hours and the approval matrix come from the stored policy; a broken policy fails closed.
- **Decline and report** (`app/services/approvals.py`): `block_by_approver()` is what `POST /approvals/{id}/decision` calls after the signature is verified. It sets the payment `declined` or `blocked`, closes the other approvers' requests, publishes `payment.blocked` and updates `holds/{intentId}`. `ENV=local` also mounts `POST /v1/_local/approvals/{id}/block` to drive it without a phone.
- **Push** (`app/adapters/notifier.py`): the FCM message carries only `approval_id` and `intent_id`, never the payment, and goes only to non-revoked devices with a token.

```powershell
cd services/api
pytest -q
$env:ENV="local"; uvicorn app.main:app --port 8090
python scripts/m2_smoke.py
```

Set `PRAMAAN_TEST_PG_URL` to an empty PostgreSQL database to run the schema test against PostgreSQL too.

---

## Deployment to Cloud Run

The idempotent deployment script is located at `infra/deploy-api.ps1`:

```powershell
.\infra\deploy-api.ps1
```

This script:
1. Builds the container image via Cloud Build: `asia-south1-docker.pkg.dev/pramaan-dev-515306/pramaan/api:latest`.
2. Deploys the service to Cloud Run in `asia-south1` running as `pramaan-api@pramaan-dev-515306.iam.gserviceaccount.com`.
3. Binds `roles/run.invoker` on the Cloud Run service to `pramaan-agent@pramaan-dev-515306.iam.gserviceaccount.com`.
4. Tests the live `/v1/health` endpoint on Cloud Run.
