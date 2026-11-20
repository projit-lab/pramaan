# Pramaan Android Application

What goes here: Approver mobile application (`app` module) and the hardware-backed key module (`core-crypto`).
Owner: Prajit.

## What's here so far

The `app` module with the M4 Tier 2 voice step (Danish). `core-crypto` is not here yet.

| Path | What |
| :--- | :--- |
| `voice/VoiceStepApi.kt` | Types for `POST /approvals/{approvalId}/voice` |
| `voice/HttpVoiceStepApi.kt` | Small HTTP client; replace with the generated client, which sends the ID token and App Check token |
| `voice/GeminiLiveVoiceSession.kt` | Gemini 3.8 Live via Firebase AI Logic. One function only: `submit_spoken_code(digits)` |
| `voice/KeypadVoiceConversation.kt` | Typed stand-in for Gemini Live when there is no Firebase config |
| `voice/VoiceStepViewModel.kt` | State machine: code shown, listening, read-back, retry, expired, passed, call-back |
| `voice/VoiceStepScreen.kt` | Compose screens. Colours are placeholders until Shoaib's Stitch tokens |
| `MainActivity.kt` | Dev harness for the seeded Tier 2 approval on the API in `DEMO_MODE` |

Stack: AGP 9.2.1, Kotlin 2.1, Compose, Firebase BoM 35.2.0 (firebase-ai 18.2.0), minSdk 30,
JDK 17. In firebase-ai 18 the Vertex AI backend is `GenerativeBackend.agentPlatform(location)`.

## Build and test

```powershell
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug
```

Run the API with `DEMO_MODE=true` on port 8765 (see `services/api/README.md`), then
install `app/build/outputs/apk/debug/app-debug.apk` on an emulator; it reaches the host
at `http://10.0.2.2:8765`. For a real phone, build with `-PapiBase=http://<pc-ip>:8765`,
start uvicorn with `--host 0.0.0.0`, and add that IP to `res/xml/network_security_config.xml`.

Without `app/google-services.json` (never committed) the app uses the keypad stand-in;
add the `pramaan-dev` config to use the real Gemini Live session.
