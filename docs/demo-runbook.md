# Demo runbook

Everything needed to run the Pramaan demo from a clean laptop. The API runs on the
presenter's laptop; the approver's phone reaches it over the same Wi-Fi (use a phone
hotspot that both the laptop and the phone join, not venue Wi-Fi).

## 0. One-time setup

- Python 3.13, `gcloud` signed in (`gcloud auth application-default login`), Android
  Studio with the phone paired (USB or wireless debugging).
- `android/app/google-services.json` from the Firebase console (never committed).
- Windows Firewall: allow Python on **private** networks the first time uvicorn starts.

## 1. Start the API (PowerShell, repo root)

```powershell
cd services\api
py -3.13 -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install .
$env:ENV = "local"
$env:USE_REAL_KMS_IN_LOCAL = "true"      # real Cloud KMS HSM countersignature
# $env:USE_FIRESTORE_IN_LOCAL = "true"   # optional: console shows live holds (needs ADC)
uvicorn app.main:app --host 0.0.0.0 --port 8765
```

The local database is `services/api/.local/pramaan.db`. It is migrated and seeded on the
first request. **Reset before each run-through:** stop uvicorn, rename or remove
`.local\pramaan.db`, start uvicorn again, then re-enrol the phone (step 3).

Find the laptop's IP with `ipconfig` (Wi-Fi adapter, IPv4). Below it is `<IP>`.

## 2. Install the approver app

Android Studio → open `android/` → build with the API address baked in:

```powershell
cd android
.\gradlew.bat :app:installDebug -PapiBase=http://<IP>:8765
```

Add `<IP>` to `app/src/main/res/xml/network_security_config.xml` if it changed (debug
cleartext only). Open **Pramaan Approver Check** on the phone.

## 3. Enrol the phone

Approver Check → **Enrol with server**. Expect `Enrolled ... (StrongBox)`. The server ran
all 11 attestation checks against Google's root before accepting the key.

## 4. Scene: one payment, signed and released

```powershell
$api = "http://<IP>:8765/v1"; $h = @{ "X-Dev-User" = "cfo@acme.example" }
# a held Tier 1 payment, raised from chat (so it needs individual review)
Invoke-RestMethod -Method Post -Uri "$api/intents" -Headers @{ "X-Dev-User" = "clerk" } -ContentType "application/json" -Body '{"payee_vendor_id":"vd_sri_lakshmi","amount_paise":"20000000","purpose":"INV-2219","instruction_channel":"chat","entry_route":"erp","initiator":{"type":"human","id":"clerk@acme.example"}}'
Invoke-RestMethod -Method Post -Uri "$api/_local/delegations" -Headers @{ "X-Dev-User" = "ap.manager@acme.example" } -ContentType "application/json" -Body '{"delegate_email":"cfo@acme.example"}'
```

Phone: **Load pending → Approve** (fingerprint). Note the mandate id (`pm_...`).

```powershell
Invoke-RestMethod -Method Post -Uri "$api/gate/release" -Headers $h -ContentType "application/json" -Body '{"mandate_id":"pm_..."}'
```

Expect a `payout_id`. Run it again: refused (a mandate releases one payment only).

## 5. Scene: hack us live (tamper)

Create a second payment as in step 4, approve it on the phone, then change one digit of
the stored payee account and try to release:

```powershell
Invoke-RestMethod -Method Post -Uri "$api/_local/intents/<intent_id>/tamper" -Headers $h
Invoke-RestMethod -Method Post -Uri "$api/gate/release" -Headers $h -ContentType "application/json" -Body '{"mandate_id":"pm_..."}'
```

Expect **409 "This payment does not match its approval"**. The gate recomputes the signed
summary from the payment as it is now and compares it with the KMS-countersigned mandate,
so editing the database (even the stored hashes) cannot get a changed payment through.

## 6. Scene: one fingerprint for a whole batch

```powershell
.\services\api\scripts\demo_batch.ps1 -Api http://<IP>:8765
```

Phone: **Load batch → Approve batch** (one fingerprint). Expect `3 mandates issued`.
Release each with `gate/release` as above. Tier 2 and 3 payments are never batched.

## 7. Scene: verify a mandate independently

`GET $api/mandates/<pm_...>` returns the mandate. The public verifier (web/verify) checks
the KMS countersignature and the phone's signature in the browser, with no Pramaan login.

## What is real and what is mocked (say this out loud)

| Real | Mocked |
| --- | --- |
| StrongBox key on the phone, 11 attestation checks, fingerprint per signature | The ERP (mock ERP / API calls) |
| Cloud KMS HSM countersignature, the gate, the tamper check | The bank (sandbox payouts) |
| Canonical bytes identical on phone and server (14 shared vectors) | Company and vendors (seed data) |

Not yet wired (roadmap): Play Integrity (mandates say `integrity_verdict: NOT_EVALUATED`),
Cloud Run deployment of the live flow, the four entry doors, the payables agent.

## If something fails

| Symptom | Fix |
| --- | --- |
| Phone shows a connection error | Same Wi-Fi? Firewall allowed Python on private networks? IP in network_security_config? |
| `No active device` | Enrol again (step 3); a database reset forgets the phone |
| `Device signature invalid` | Tap **Enrol with server** again: re-enrolling replaces the key on the phone and on the server together |
| KMS errors | `gcloud auth application-default login`, then restart uvicorn |
| Wireless debugging dropped | Android Studio → Device Manager → pair again; keep the phone awake |
