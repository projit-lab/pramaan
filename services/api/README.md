# Pramaan API Service

What goes here: FastAPI backend service running on Cloud Run, providing payment gate APIs, hold lifecycle management, and mandate verification.
Owner: Prajit.

## What's here so far

Only the M4 Tier 2 voice step (`POST /v1/approvals/{approvalId}/voice`), built by
Danish for Prajit's review. Contract: `approvalVoice` in `contracts/openapi.yaml` and
`approval.voice_checked` in `contracts/events.md`.

| Path | What |
| :--- | :--- |
| `domain/voice.py` | The rules: six-digit code bound to approval and nonce, two minutes, single use, three wrong tries then call-back, at most three codes, ledger gets a hash only |
| `routers/voice.py` | The FastAPI route and problem-details errors |
| `adapters/demo.py` | In-memory approvals, voice sessions and events for `DEMO_MODE` only |
| `main.py` | App factory. Refuses to start unless `DEMO_MODE=true`, until real auth and storage are wired |
| `tests/` | Rules, HTTP layer, demo app, and contract tests that fail on drift from `contracts/` and `web/shared` |
| `scripts/voice_smoke.py` | Live check against a running server |

## Run and test

From `services/api`, with Python 3.11 or later:

```powershell
pip install -e ".[dev]"
python -m pytest
$env:DEMO_MODE="true"; python -m uvicorn main:create_app --factory --port 8765
python scripts/voice_smoke.py
```

In `DEMO_MODE` the caller is taken from an `X-Demo-Uid` header in place of the Firebase
ID token, and three approvals are seeded. `GET /_demo/voice/approvals`,
`GET /_demo/voice/events` and `POST /_demo/voice/reset` are dev helpers, left out of the
served OpenAPI.

## Still to wire (Prajit)

- `current_approver_uid`: the Firebase ID token check plus App Check.
- `ApprovalLookup` on AlloyDB. `tier1_verified` is true once `POST /approvals/{id}/decision` has verified the signature.
- `VoiceStore` on AlloyDB, locked per approval (`SELECT ... FOR UPDATE`).
- `VoiceEvents` on Pub/Sub topic `approval-voice-checked` and the Firestore step writer.
- The HMAC secret from Secret Manager (`PRAMAAN_VOICE_SECRET` in demo).
- Mandate issuance: at tier 2 and above, issue only when `VoiceService.is_tier2_passed(approval_id)`.
