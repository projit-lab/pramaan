# Pramaan Infrastructure & Cloud Foundation

This directory contains the infrastructure bootstrapping automation, pipeline definitions, and security policies for the **Pramaan** payment protection platform.

## Target Environment

- **Google Cloud Project ID**: `pramaan-dev-515306`
- **Primary Region**: `asia-south1` (Mumbai)

---

## 1. How to Run `infra/bootstrap.ps1`

### Prerequisites

1. Install the [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) and ensure `bq` is in your PATH.
2. PowerShell 5.1+ or PowerShell 7+ on Windows.
3. Authenticate with your administrator credentials:
   ```powershell
   gcloud auth login
   gcloud auth application-default login
   ```
4. Set the active project:
   ```powershell
   gcloud config set project pramaan-dev-515306
   ```

### Execution

Execute the script from the root of the repository:

```powershell
.\infra\bootstrap.ps1
```

The script is **completely idempotent**: running it multiple times checks each resource before creating it, will not fail, will not overwrite existing resources, and will not produce duplicate entities.

---

## 2. What the Bootstrap Script Creates

1. **API Enablement**:
   - Cloud Run (`run.googleapis.com`)
   - Artifact Registry (`artifactregistry.googleapis.com`)
   - Cloud Build (`cloudbuild.googleapis.com`)
   - Cloud Pub/Sub (`pubsub.googleapis.com`)
   - Cloud Firestore (`firestore.googleapis.com`)
   - BigQuery (`bigquery.googleapis.com`)
   - Cloud Key Management Service (`cloudkms.googleapis.com`)
   - Secret Manager (`secretmanager.googleapis.com`)
   - AlloyDB API (`alloydb.googleapis.com` - *API only, no clusters/instances created*)
   - Vertex AI / Agent Platform (`aiplatform.googleapis.com`)
   - Model Armor (`modelarmor.googleapis.com`)
   - Firebase Management (`firebase.googleapis.com`)
   - Firebase Cloud Messaging (`fcm.googleapis.com`)
   - Google Play Integrity (`playintegrity.googleapis.com`)
   - Identity & Access Management (`iam.googleapis.com`)

2. **Artifact Registry**:
   - Docker repository `pramaan` located in `asia-south1` for storing backend container images.

3. **Cloud Firestore**:
   - Firestore database `(default)` in Native mode located in `asia-south1`.

4. **BigQuery**:
   - Dataset `pramaan_ledger` located in `asia-south1` for audit logs and immutable ledger entries (tables defined separately).

5. **Cloud Pub/Sub**:
   - 7 canonical topics:
     - `intent-created`
     - `intent-decided`
     - `approval-signed`
     - `mandate-issued`
     - `payment-released`
     - `payment-blocked`
     - `device-enrolled`

6. **Cloud KMS (Hardware Security Module - HSM)**:
   - Key Ring: `pramaan` in `asia-south1`.
   - Asymmetric Signing Key: `mandate-signer`
     - **Purpose**: `asymmetric-signing`
     - **Algorithm**: `ec-sign-p256-sha256` (FIPS 186-4 ECDSA P-256)
     - **Protection Level**: `hsm` (Hardware Security Module)
     - *Strict Policy*: Never falls back to software keys.

7. **Service Accounts & Least-Privilege IAM Bindings**:
   - `pramaan-api@pramaan-dev-515306.iam.gserviceaccount.com`
   - `pramaan-agent@pramaan-dev-515306.iam.gserviceaccount.com`

---

## 3. Service Account Roles & Responsibilities

Roles are assigned at the **narrowest resource scope possible** (key-level, dataset-level, and topic-level) rather than project-wide whenever Google Cloud IAM allows it.

| Service Account | Role Name | Resource Scope | Purpose |
|---|---|---|---|
| `pramaan-api` | `roles/cloudkms.signerVerifier` | Key: `mandate-signer` | Sign payment mandates and verify cryptographic signatures. Cannot manage keys or access any other key. |
| `pramaan-api` | `roles/datastore.user` | Project / Firestore | Read and write documents in Firestore (intents, holds, devices). |
| `pramaan-api` | `roles/bigquery.dataEditor` | Dataset: `pramaan_ledger` | Insert and append ledger audit records in the specific ledger dataset only. |
| `pramaan-api` | `roles/bigquery.jobUser` | Project | Execute BigQuery jobs/queries. |
| `pramaan-api` | `roles/pubsub.publisher` | Topics (7 individual topics) | Publish workflow state transitions directly to the 7 topics. |
| `pramaan-api` | `roles/pubsub.subscriber` | Project | Consume and pull messages from Pub/Sub subscriptions. |
| `pramaan-api` | `roles/secretmanager.secretAccessor` | Project | Read runtime secrets (API tokens, private configs). |
| `pramaan-api` | `roles/aiplatform.user` | Project | Invoke Vertex AI / Gemini models for assistive checks. |
| `pramaan-agent` | `roles/aiplatform.user` | Project | Invoke Vertex AI / Gemini models for payables risk evaluation. |
| `pramaan-agent` | `roles/modelarmor.user` | Project | Sanitize prompts and validate LLM outputs against prompt injection / jailbreaks. |

---

## 4. Cost Breakdown & Idle Cost Note

We operate under strict cost control on Google Cloud free trial credits.

### Idle Costs vs On-Demand Costs

- **Cloud KMS HSM Key (`mandate-signer`)**:
  - HSM key versions have a fixed monthly maintenance fee (approximately **$5.00/month** per active HSM key version).
  - This is the **only resource with a recurring idle cost** in this foundation bootstrap.
- **AlloyDB**:
  - **$0 idle cost**: Only the AlloyDB API is enabled. **No** AlloyDB clusters, primary instances, or read replicas are provisioned. Provisioning a cluster would incur significant continuous hourly compute and memory charges (~$100+/month), which is strictly avoided.
- **Artifact Registry**:
  - Billed strictly on stored GBs. The standard free tier includes the first 0.5 GB/month free.
- **Cloud Firestore**:
  - Native mode provides a free tier of 1 GiB storage, 50,000 reads/day, 20,000 writes/day, and 20,000 deletes/day. No idle charges.
- **BigQuery**:
  - Pay-per-query. 1 TB/month free analysis tier and 10 GB free active storage. $0 when idle.
- **Cloud Pub/Sub**:
  - Pay-per-use. First 10 GiB of messages per month are free. $0 when idle.
- **Cloud Run & Vertex AI**:
  - Completely serverless / pay-per-request. Scale to 0 instances when not handling requests. $0 when idle.

---

## 5. Security & Credential Management Policy

- **NEVER create service-account key files (`.json`)**: Downloading service account private keys creates severe security and credential leak risks.
- **Local Development**: Authenticate developers and local scripts using Application Default Credentials (ADC):
  ```powershell
  gcloud auth application-default login
  ```
- **Cloud Run Deployment**: When deploying container services (`services/api` or `services/agent`), attach the corresponding service account via the `--service-account` flag:
  ```bash
  gcloud run deploy pramaan-api --service-account pramaan-api@pramaan-dev-515306.iam.gserviceaccount.com ...
  ```
- **Mandate Safety Rule**: No agent service account has access to the Cloud KMS HSM signing key. Only `pramaan-api` has the signer role, and payment release strictly requires cryptographic verification of an approver's physical device signature.
