# Pramaan Web Applications

Owner: Shoaib.

Four npm workspaces:

| Workspace | What it is | Who signs in | Port |
| :--- | :--- | :--- | :--- |
| `console` | The Pramaan console: live holds board, payment detail, devices | `finance` role | 5173 |
| `erp-mock` | **Acme ERP**, the mock customer system, plus the public sandbox bank at `/bank` | `clerk` role (the bank page needs nobody) | 5174 |
| `verify` | The public mandate verifier | nobody, by design | 5175 |
| `shared` | Firebase init, auth and the role gate, live Firestore hooks, the generated API client, formatting, components | — | — |
| `tools` | Admin scripts and the Firestore rules tests | — | — |

Two products are on screen in the demo. **Acme ERP** represents the customer's own
software; **Pramaan** is our product. The ERP's Pay button goes through Pramaan.

## What you need installed

- **Node 22 or later.** Check with `node -v`.
- **Java 21 or later**, for the Firestore emulator. Check with `java -version`.
  On Windows: `winget install --id Microsoft.OpenJDK.21`
- No Firebase project is needed to run everything locally.

## Running it locally

Everything below runs from this `web/` directory. You need four terminals; each
command keeps running.

### 0. Once, after cloning

```bash
cd web
npm install
cp .env.example .env.local      # Windows PowerShell: copy .env.example .env.local
npm run gen:api
```

`npm run gen:api` generates `shared/src/api/schema.d.ts` from
`../contracts/openapi.yaml`. It is **not committed**: it is generated here and in
CI, so the code can never drift from the contract. Run it again after any change
to the contract.

The defaults in `.env.example` need no Firebase project and no secrets: emulators
for Auth and Firestore, and a mock API server.

### 1. The emulators (terminal 1)

```bash
npm run emulators
```

Auth on 9099, Firestore on 8080, the emulator UI on <http://127.0.0.1:4000>.
This reads `../firebase.json` and `../infra/firestore.rules`, so the rules you are
developing are the rules being enforced.

### 2. The mock API server (terminal 2)

```bash
npm run mock:api
```

Prism serves `../contracts/openapi.yaml` on <http://127.0.0.1:4010>, returning the
examples written into the contract. This is how the web lane was built before
Prajit's API existed. When his Cloud Run endpoint lands, change one value,
`VITE_API_BASE` in `.env.local`, and stop this.

### 3. Seed the data and grant yourself a role (terminal 3)

```bash
npm run seed
node tools/grant-role.mjs --email you@example.com --role finance
node tools/grant-role.mjs --email clerk@example.com --role clerk
```

`npm run seed` loads `../data/firestore-seed.json`, which follows
`../contracts/firestore.md`: four held payments, two approver phones and one
flagged agent request. `payouts` is deliberately left empty, so the sandbox bank
honestly says "No money has moved yet" until a mandate moves some.

`grant-role.mjs` talks to the **emulator by default** and creates the account if it
does not exist, because there is no real Google to sign in with locally. It needs
`--real` to touch a live project, and then uses your own gcloud credentials, so no
service account key is ever required. `--role none` revokes. `--list` shows who
has what.

Signing in locally: the Auth emulator shows a fake Google sign-in screen. Pick
"Add new account" and use the same email you granted the role to.

### 4. An app (terminal 4)

```bash
npm run dev:console     # http://localhost:5173
npm run dev:erp         # http://localhost:5174  (sandbox bank at /bank)
npm run dev:verify      # http://localhost:5175
```

## Checks

```bash
npm run typecheck       # every workspace
npm run test            # unit tests
npm run build           # production build of all three apps
```

The Firestore rules tests need the emulator running in another terminal:

```bash
npm run emulators       # terminal 1
npm run rules:test      # terminal 2
```

They prove the two claims the live read model rests on: **no client can write to
Firestore, ever**, and reading requires a role.

## Conventions these apps follow

From the build plan, page 24, and not negotiable per screen:

- **Money** is an integer number of paise carried as a string. Rupees 46.5 lakh is
  `"465000000"`. Only the screen formats it, with Indian grouping
  (`₹46,50,000`) and in Indian words where a person decides on it.
- **Times** are ISO 8601 with `+05:30` in the API and Firestore `Timestamp`s in the
  read model. Screens show IST with a relative time beside it.
- **Accounts** show only the last four digits.
- **Colour carries meaning only, and never alone**: amber held, red blocked or
  declined, green released, each always with its own text.
- **Anything Gemini wrote is labelled** as AI-written. Rules decide; Gemini
  explains.
- **A check that did not run says "couldn't verify"**, never a pass and never
  "fraud". `null` is not `false`.
- **Live Firestore listeners unsubscribe** when a screen closes. The hooks in
  `shared` do this for you.
- **The API is called only through the generated client.** There are no
  hand-written URLs in the web lane.
- **No sign-up page anywhere.** Everyone signs in with Google; an admin grants a
  role.
- **The console has no Approve button, at any role.** An approval is a hardware
  signature made on a phone. That absence is the product.

## Deploying

`../infra/cloudbuild.web.yaml` installs, generates the client, typechecks, tests,
builds and deploys to Firebase Hosting on every merge to `main`, plus the Firestore
rules and indexes. The trigger command and the IAM roles the build service account
needs are documented at the top of that file.

Three Firebase Hosting sites are expected, named in `../.firebaserc`:

```bash
firebase hosting:sites:create pramaan-dev-515306-console
firebase hosting:sites:create pramaan-dev-515306-erp
firebase hosting:sites:create pramaan-dev-515306-verify
```

## What is not built yet

M0 is foundations. These are named here rather than mocked up to look finished:

- The new-payment form and its Pay button (M2), and "Let the AI agent pay this" (M3).
- The attestation card and the mandate viewer on payment detail (M1, M2).
- The invoice panel with the fields Gemini read (M3).
- The verifier's actual signature check (M2). The page says it is not verifying
  yet rather than showing a result it has not computed.
- Revoking a device (M5, outside buildathon scope). The button is disabled and
  says so.
- The demo control panel and presenter view (M6).

## Open decisions

Both are flagged in `../contracts/firestore.md` and need Prajit:

1. **How the public sandbox bank page reads payouts.** Firestore rules require a
   signed-in user, and that page has nobody signed in. Default here is
   `GET /payouts` on the API with no auth (`VITE_PAYOUTS_SOURCE=api`); the
   alternative is signing the page in silently as a clerk
   (`VITE_PAYOUTS_SOURCE=firestore`). Both are implemented behind that one value.
2. **`canonical_b64` on `GET /mandates/{id}`.** The verifier must hash the exact
   bytes that were countersigned. Returning them avoids a third canonicalisation
   implementation in TypeScript that would drift from the Kotlin and Python ones.

Also: the `clerk` role widens the build plan's finance-only read rule, so the
Firestore rules need his approval.
