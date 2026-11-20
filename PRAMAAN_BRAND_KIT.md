# Pramaan Brand Kit and UI Build Guide

> One file with everything needed to design and build Pramaan's UI. Part A is for the coding agent. Parts B to E are the brand kit itself.

---

## Part A. Instructions for the coding agent (read first)

You are restyling and building the UI of an existing project. The code already has features this document does not know about. Your job is to **figure out what exists, then make all of it look like this brand kit without breaking anything**.

### A1. Investigate before changing anything
1. Find the project's web apps and shared UI code (for example a `web/` folder with `console`, `erp-mock`, `verify` and `shared`, but go by what is actually there). If there is an Android app, note it but don't change it unless asked.
2. List every screen, route and component that exists, including features not mentioned in this document.
3. Find where styles and design tokens live today (for example `shared/src/ui/tokens.css`), which CSS approach is used (plain CSS, CSS modules, Tailwind, a UI library), and the existing variable names.
4. Find the data shapes the screens use (statuses, reason codes, timeline steps, fields) from the code and any `contracts/` folder. **The code is the source of truth.** Where this document uses a different name, keep the code's name and apply the closest matching style.
5. Write a short plan: screens found, how you'll map the tokens, which components you'll create or restyle, and anything unclear. Then do it.

### A2. Rules while building
- **Visual change only.** Don't change logic, data fetching, Firestore listeners, API calls, routes, auth, contracts, field names or tests. Every existing feature must keep working exactly as before.
- Put the tokens from Part C into the project's token file. If existing code uses other variable names, map them to these tokens (or rename them everywhere) so nothing breaks. Keep the project's CSS approach; don't add a new UI framework.
- Use Part D (`bundle.css`) and the component markup in Part E as the reference. Turn them into the project's own components (React or whatever is used). Don't paste raw HTML into pages.
- **Light theme only.** Remove any dark-mode styles.
- Load fonts from Google Fonts as shown in B "Typography".
- Keep the existing helpers for money and time (such as `formatRupees`, `rupeesInWords`, `maskAccount`, `formatIst`, `relativeTime`) and the AI label rule.
- For a feature with no matching component here, design it from the same tokens and rules (pill buttons, tinted rounded cards, one state band per screen, Material Symbols icons, real Indian content). Don't invent a new look.
- Acme ERP (the mock customer ERP) keeps its deliberately plain grey style.
- Follow "Do not make it look AI-generated" in Part B strictly.
- Make it responsive: phone width (360px) to desktop, no horizontal scroll, 16px side padding on phones.

### A3. Finish
1. Run the project's checks (for example `npm run typecheck`, `npm test`, `npm run build` in `web/`) and fix anything you broke.
2. Open each app in a browser and check every screen against Parts B and E: the state band colour matches the status, amounts show figures and words, focus rings are visible, and nothing overflows at 360px.
3. **Do NOT commit, do NOT push, do NOT open a pull request.** Leave every change uncommitted. The owner will review and commit.
4. Report: files changed, screens restyled, features you weren't sure how to style and what you chose, any rule you couldn't follow and why, and the check results.

---

## Part B. Brand book


**No signed approval, no payment.**

Pramaan stops a company's money from leaving on a fake instruction. Every outgoing payment that looks risky is held until the right person approves it on their own phone, with a key that never leaves the phone's secure chip. The bank releases money only against that signed approval.

This brand kit is for every screen Pramaan shows: the finance console, the approver's phone app, the public mandate verifier, the sandbox bank, and the mock customer ERP used in the demo.

### Who we design for

| Person | Where they meet Pramaan | What they need from the screen |
| --- | --- | --- |
| **Approver** (CFO, MD, owner) | Android app, often on the move, one hand | The amount, the payee and what changed, readable in two seconds. One clear Approve and one clear Decline. Nothing to tap by accident. |
| **Finance team** | Pramaan console on a laptop, all day | A calm board of held payments, the reasons in plain words, the full trail for audit. No Approve button: only the approver can approve. |
| **Accounts clerk** | Acme ERP (their own system) | Their usual payment run, plus a clear note when Pramaan holds one, so they know it is waiting and not broken. |
| **Auditor, bank, anyone with a mandate** | Mandate verifier, no sign-in | A plain yes or no: is this signature real, who signed, on which phone, for exactly what. |
| **Judges and the presenter** | All of the above on a projector | Big type, strong contrast, a story they can follow from the back of the room. |

These are Indian companies: amounts in lakh and crore, IFSC codes, IST, GST invoices, vendors with names like Sri Lakshmi Castings. The people are busy and careful, and many have been burnt by a fake "our bank details have changed" email.

### The idea behind the look

**As easy as paying on a UPI app.** Every approver already knows how a payments app feels on their phone: white screens, one big centred amount, a round avatar for who you are paying, soft rounded cards, pill buttons, a green tick when it is done. Pramaan speaks that same familiar, friendly language (Material 3), so approving a ₹46 lakh vendor payment feels as clear as paying a friend, while the security happens quietly in the phone's chip.

- **Primary blue** `#0B57D0` is the brand: filled buttons, links, the signed state, the logo.
- **White** is the ground, with **soft blue-grey cards** `#F0F4F9` instead of borders, and a **sky-blue band** `#C2DBFF` across the top of each screen.
- **Round shapes:** 24px cards, pill buttons and chips, circle avatars.
- **Status colours are separate from the brand.** Amber means held, red means blocked or changed, green means the money moved. They never decorate.

It borrows the style of a modern payments app, not anyone's identity: no Google or GPay logo, no four-colour mark, no copied screens.

### What makes it Pramaan, not a template

A payments-app base makes it instantly familiar. Three signatures make it ours, and they are what judges will remember:

1. **The state band.** Every phone screen and console page opens with a coloured band, and its colour *is* the payment's state: blue at rest, amber when held, green when released, red when declined. You know what is happening before you read a word.
2. **Seal lines.** Fine white concentric lines and one dashed ring sit in the band's corner, the security-paper texture of an Indian cheque, echoing the dashed ring idea in the logo. It is the only ornament in the system.
3. **Hold to approve.** The approver presses and holds the Approve pill for one second while a deeper blue fills it, then the phone signs. No accidental ₹46 lakh taps, and the moment feels like putting pen to cheque.

#### Do not make it look AI-generated

Today's "vibe-coded" look is easy to spot. Avoid all of it:

- No purple or violet, no gradient backgrounds or gradient text, no glassmorphism or blur panels, no neon glows.
- No Inter-everywhere with grey 14px text; we use Google Sans Flex with big, confident sizes (40px display, 28px section titles, 56px amounts).
- No hero with three equal feature cards and icons in circles. No dashboard of four stat tiles with sparkline charts.
- No emoji in the interface, no stock 3D illustrations, no "✨ Powered by AI" badges (the AI label is small, factual and only on Gemini text).
- No shadow on every card; cards are flat tinted `surface-container`.
- Real content always: Indian names, lakh amounts, IFSC codes, IST times. Never "John Doe", "$1,234" or lorem ipsum, even in a mockup.
- One icon set (Material Symbols Rounded), one radius scale, one band per screen.

### Principles

1. **The amount and the payee come first.** On any screen where someone decides, the payee, the amount (in figures and in words) and the last four digits of the account are the biggest things.
2. **Show what changed.** A new account, a new payee or a changed IFSC is shown as old → new on a red card. This is the single most important detail on the approval screen.
3. **Rules decide, Gemini explains.** Reasons come from rules and are shown as reason chips. Gemini's explanation is display only and always carries the AI label.
4. **Say "couldn't verify", never "fraud".** We are not accusing a vendor. Write what we checked and what did not match.
5. **Calm by default, loud only when it matters.** Most screens are white with soft cards. Colour appears when a payment needs a person.
6. **Every colour has words beside it.** Status is always a word and an icon, never colour alone.
7. **One decision per screen on the phone.**

### Colour

Use the tokens, never raw hex values. Pramaan is light theme only. Every text pair passes WCAG AA (4.5:1); outlines pass 3:1.

| Token | Means | Use |
| --- | --- | --- |
| `primary` / `on-primary` | Act here, signed | Filled buttons, links, focus, the logo |
| `primary-container` / `on-primary-container` | Friendly emphasis | Tonal buttons, payee avatars, AI summary card, Approved chip |
| `secondary-container` | You are here | Active pill in the console nav drawer |
| `background`, `surface` | Grounds | White page; sheets and dialogs |
| `surface-container`, `surface-container-high` | Soft cards | Cards, lists, nav drawer; table headers and wells |
| `held` / `held-soft` | Waiting for the approver | Held chip, waiting banner |
| `blocked` / `blocked-soft` | Stopped, declined, changed | Blocked and Declined chips, changed-field card |
| `released` / `released-soft` | Money moved | Released chip, success tick |
| `tier-high` / `tier-high-soft` | Tier 2 and 3 | Tier badge only |
| `ink`, `ink-muted` | Text | Everything you read |
| `line` / `line-strong` | Edges | List dividers / outlined buttons and fields |
| `erp-chrome` | Acme ERP only | Acme's sidebar, so it never looks like Pramaan |

Do not: use blue for "released" (that is green), use red for anything that is not a stop or a change, or put borders on cards (use `surface-container`).

### Typography

- **Google Sans Flex** for everything: headings at weight 500, text at 400, big amounts at 500 with tabular numerals (`font-variant-numeric: tabular-nums`). Free and open source on Google Fonts since November 2025.
- **Roboto Mono** for account numbers, IFSC, IDs (`pi_`, `pm_`, `dv_`) and hashes.
- **Noto Sans Tamil** and **Noto Sans Devanagari** are in the fallback stack for vendor names in Tamil or Hindi.
- Sentence case everywhere. No all-caps labels.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Google+Sans+Flex:opsz,wght@6..144,400..700&family=Roboto+Mono:wght@400;500&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0&display=swap" rel="stylesheet">
```

On Android, use Material 3 in Compose with Google Sans Flex through Downloadable Fonts, and map these tokens onto the Material colour scheme (`primary`, `primaryContainer`, `surfaceContainer`…): the names match on purpose.

### Money, numbers and time

| Thing | Write it as | Not |
| --- | --- | --- |
| Amount | `₹46,50,000` (Indian grouping, no paise unless non-zero) | `₹4,650,000`, `INR 4650000`, `Rs.` |
| Amount, where someone decides | `₹46,50,000` and under it *Forty-six lakh fifty thousand rupees* | figures alone |
| Large amounts in summaries | `₹1.2 crore`, `₹46.5 lakh` | `₹12M` |
| Account | `••9999` (last four only, except the approver's changed-field card) | full number |
| IFSC | `ABCD0123456` in mono | lower case |
| Time | `10:41 am IST` with `2 min ago` beside it | UTC, 24-hour without IST |
| Date | `21 Nov 2026` | `11/21/2026` |

Money arrives from the API as paise strings. Use `formatRupees`, `rupeesInWords`, `maskAccount`, `formatIst` and `relativeTime` from `@pramaan/shared`.

### Voice and words

Plain, calm, specific. Short sentences. The reader is a finance professional, not a security engineer.

| Situation | Say | Do not say |
| --- | --- | --- |
| Payment held | "Held for the CFO's approval. First payment to this account." | "Suspicious transaction detected!" |
| Check failed | "We couldn't verify this account. The bank name doesn't match the vendor." | "Fraud detected", "Malicious vendor" |
| Declined | "Declined by Priya Raman on her phone at 10:43 am. The money did not move." | "Transaction rejected" |
| Released | "Approved and released. ₹9,80,000 sent to Sri Lakshmi Castings ••7781." | "Success!" |
| Signature valid | "This approval is genuine. Signed on a Pixel 8 with a hardware key, for exactly these details." | "Cryptographic verification passed" |
| Empty board | "Nothing is waiting. Payments that need an approver will show up here." | "No data" |

Buttons say what they do: **Approve ₹46,50,000**, **Decline**, **Report fraud**, **Verify mandate**. Never "OK" or "Submit" on a decision.

#### The AI label

Anything Gemini writes sits in an AI summary card labelled **"AI summary · Gemini"** with a note that the decision was made by rules. Gemini never writes the reason chips, the amount or the payee.

### The surfaces

#### Pramaan console (finance)
White page with a blue state band across the top of each page (amber, green or red on a payment's detail page), a left nav drawer on `surface-container` with the lockup at the top and the current page in a `secondary-container` pill. The dashboard uses PaymentList cards; the full board uses HoldsTable. A row opens a detail page: AmountBlock, reasons, AI summary, timeline, attestation card, mandate. There is no Approve button anywhere in the console.

#### Approver app (Android)
**Home:** blue band with search, "Good morning, Priya" and the big count "2 payments need you", four action tiles, the "Waiting for you" list, bottom navigation.

**Approval:** the top half is the amber state band with the payee avatar, "Paying Global Trade Solutions" and the 56px amount with words. Below, on white: the changed-field card, reason chips, the AI summary, **Hold to approve ₹46,50,000**, and **Decline** (outlined). The hold opens the fingerprint prompt; after release the band turns green and the ReleasedScreen shows the tick. Minimum touch target 48dp. Report fraud lives behind Decline.

#### Mandate verifier (public)
One centred column on white with a big rounded drop zone. The result is a large card: a green tick "Genuine" or red "Not genuine" heading, then who signed, which phone, which key level, and the exact payment details signed.

#### Sandbox bank
A simple statement as a PaymentList; a new payout row tints `released-soft` for two seconds when the gate releases money.

#### Acme ERP (mock)
The customer's own older system, so it must not look like Pramaan: grey `erp-chrome`, Tahoma/Verdana, square bordered tables, no pills. That contrast makes the friendly Pramaan pieces stand out when they appear inside it: the "Protected by Pramaan" badge and the Held status. The fictional company is **Acme Auto Components Pvt Ltd**; never use a real company's name or logo.

#### Presenter view
White full-screen with huge type, one event per line as the demo runs, under a state band that changes colour as the payment moves.

### Layout and spacing

- 4px base grid; spacing steps 4, 8, 12, 16, 24, 32.
- Console: 220px nav drawer, content max 1200px, 24px gutters. Approver app: 16px side padding.
- Radii: 24px cards and sheets, 12px fields and banners, pills for every button and chip, circles for avatars.
- Cards are tinted `surface-container` with no border; shadows only on sheets, menus and raised cards.
- Generous white space. Centre the key content on phone screens.

### Icons

Use **Material Symbols Rounded** (outlined at rest, filled when selected or for warnings; 20px in text, 24px in app bars). Fixed meanings:

| Meaning | Icon |
| --- | --- |
| Held | `schedule` |
| Declined / Blocked | `block` / `gpp_bad` |
| Released | `check_circle` |
| Signed / mandate | `draw` |
| Approve (biometric) | `fingerprint` |
| Hardware key | `verified_user` (passed), `gpp_maybe` (weak) |
| Changed field | `warning` (filled), `arrow_forward` between old and new |
| AI | `auto_awesome`, only inside the AI label |
| Agent-initiated payment | `smart_toy` |

### Accessibility

- Text 4.5:1, large text and outlines 3:1, checked for every pair including text on the four band colours.
- Visible focus on everything: 2px `focus` ring, 2px offset.
- Status always has a word and an icon. Amounts in words are also read by screen readers.
- Hit targets 44px on the web, 48dp on Android. Hold to approve also works by holding Space or Enter.
- Respect reduced motion: the hold fill, success tick, row tint and timeline animation turn off.
- Light theme only, on every surface. Do not build a dark mode.

### Components in this kit

StateHeader, HoldToApprove, ActionTile, Button, StatusChip, TierBadge, ReasonChip, AmountBlock, ChangedField, AiExplanation, Timeline, AttestationCard, MandateCard, PaymentList, HoldsTable, Banner, EmptyState, ReleasedScreen, ErpShell, ApproverHome and ApproverScreen. Each has a preview and usage notes. The CSS classes (all `pm-` prefixed) are in `components/bundle.css` and read only the tokens, so they switch themes on their own.


---

## Part C. Design tokens (`tokens.css`)

Copy into the project's token file. These are the only colours, sizes and radii to use.

```css
/* Pramaan design tokens (light only). Generated from tokens.json. */
:root {
  --background: #FFFFFF;
  --surface: #FFFFFF;
  --surface-container: #F0F4F9;
  --surface-container-high: #E9EEF6;
  --band: #C2DBFF;
  --band-held: #FFE2AE;
  --band-released: #C8EED2;
  --band-blocked: #FFD9D4;
  --seal-line: #FFFFFF;
  --line: #E1E3E1;
  --line-strong: #747775;
  --ink: #1F1F1F;
  --ink-muted: #444746;
  --primary: #0B57D0;
  --on-primary: #FFFFFF;
  --primary-deep: #062E6F;
  --primary-container: #D3E3FD;
  --on-primary-container: #041E49;
  --secondary-container: #C2E7FF;
  --on-secondary-container: #001D35;
  --held: #7A4100;
  --held-soft: #FFEFD6;
  --blocked: #B3261E;
  --blocked-soft: #FCE8E6;
  --on-blocked: #FFFFFF;
  --released: #146C2E;
  --released-soft: #E6F4EA;
  --neutral-soft: #E9EEF6;
  --tier-high: #8E3A00;
  --tier-high-soft: #FFDBC8;
  --focus: #0B57D0;
  --erp-chrome: #2F343B;
  --on-erp-chrome: #F2F4F7;
  --shadow-card: 0 1px 2px rgba(60, 64, 67, 0.12), 0 1px 3px 1px rgba(60, 64, 67, 0.08);
  --shadow-pop: 0 4px 8px 3px rgba(60, 64, 67, 0.15), 0 1px 3px rgba(60, 64, 67, 0.3);
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 24px;
  --radius-pill: 999px;
  --font-display: "Google Sans Flex", "Google Sans", Roboto, system-ui, sans-serif;
  --font-sans: "Google Sans Flex", "Google Sans", Roboto, "Noto Sans Tamil", "Noto Sans Devanagari", system-ui, sans-serif;
  --font-mono: "Roboto Mono", ui-monospace, Menlo, monospace;
}
.t-display { font-family: var(--font-display); font-size: 40px; line-height: 46px; font-weight: 500; letter-spacing: -0.01em; }
.t-title { font-family: var(--font-display); font-size: 28px; line-height: 34px; font-weight: 400; }
.t-heading { font-family: var(--font-sans); font-size: 17px; line-height: 24px; font-weight: 500; }
.t-body { font-family: var(--font-sans); font-size: 15px; line-height: 22px; font-weight: 400; }
.t-body-strong { font-family: var(--font-sans); font-size: 15px; line-height: 22px; font-weight: 500; }
.t-small { font-family: var(--font-sans); font-size: 13px; line-height: 18px; font-weight: 400; }
.t-label { font-family: var(--font-sans); font-size: 12px; line-height: 16px; font-weight: 500; letter-spacing: 0.02em; }
.t-amount-xl { font-family: var(--font-sans); font-size: 56px; line-height: 60px; font-weight: 500; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.t-amount { font-family: var(--font-sans); font-size: 15px; line-height: 22px; font-weight: 500; font-variant-numeric: tabular-nums; }
.t-amount-words { font-family: var(--font-sans); font-size: 14px; line-height: 20px; font-weight: 400; font-variant-numeric: tabular-nums; }
.t-mono { font-family: var(--font-mono); font-size: 13px; line-height: 18px; font-weight: 400; }
```

---

## Part D. Reference component CSS (`bundle.css`)

All classes are `pm-` prefixed and read only the tokens above. Use them directly, or port them to the project's styling approach while keeping the same values.

```css
@import url("https://fonts.googleapis.com/css2?family=Google+Sans+Flex:opsz,wght@6..144,400..700&family=Roboto+Mono:wght@400;500&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0&display=swap");

/* Pramaan components: a clean, friendly payments-app style. Every value comes from tokens.css; classes are pm- prefixed. */

.pm-root, body { font-family: var(--font-sans); color: var(--ink); background: var(--background); font-size: 15px; line-height: 22px; margin: 0; }
.pm-pad { padding: var(--space-6); }
.pm-row { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.pm-stack { display: flex; flex-direction: column; gap: var(--space-4); }
.pm-center { text-align: center; align-items: center; }
.pm-mono { font-family: var(--font-mono); font-size: 13px; }
.pm-muted { color: var(--ink-muted); }
.pm-label { font-size: 12px; line-height: 16px; font-weight: 500; letter-spacing: .02em; color: var(--ink-muted); }
.pm-title { font-family: var(--font-display); font-size: 22px; line-height: 28px; font-weight: 500; margin: 0; }
.pm-heading { font-size: 17px; line-height: 24px; font-weight: 500; margin: 0; }

/* Icons: Material Symbols Rounded, by ligature name */
.pm-ico { font-family: "Material Symbols Rounded"; font-weight: normal; font-style: normal; font-size: 20px; line-height: 1; display: inline-block; width: 1em; height: 1em; overflow: hidden; white-space: nowrap; direction: ltr; -webkit-font-feature-settings: "liga"; font-feature-settings: "liga"; font-variation-settings: "FILL" 0, "wght" 400, "opsz" 20; flex: none; }
.pm-ico--fill { font-variation-settings: "FILL" 1, "wght" 400, "opsz" 20; }
.pm-ico--sm { font-size: 18px; }
.pm-ico--lg { font-size: 24px; }

/* Button: always a pill */
.pm-btn { font: 500 15px/20px var(--font-sans); display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: 44px; padding: 10px 24px; border-radius: var(--radius-pill); border: 1px solid transparent; cursor: pointer; text-decoration: none; }
.pm-btn:focus-visible, .pm-focus:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.pm-btn--primary { background: var(--primary); color: var(--on-primary); }
.pm-btn--primary:hover { box-shadow: var(--shadow-card); }
.pm-btn--tonal { background: var(--primary-container); color: var(--on-primary-container); }
.pm-btn--outlined { background: transparent; color: var(--primary); border-color: var(--line-strong); }
.pm-btn--outlined:hover, .pm-btn--text:hover { background: var(--primary-container); }
.pm-btn--text { background: transparent; color: var(--primary); padding: 10px 12px; }
.pm-btn--danger { background: var(--blocked); color: var(--on-blocked); }
.pm-btn--block { width: 100%; min-height: 56px; font-size: 16px; }
.pm-btn[disabled] { background: var(--surface-container-high); color: var(--ink-muted); border-color: transparent; cursor: not-allowed; box-shadow: none; }

/* StatusChip */
.pm-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px 4px 8px; border-radius: var(--radius-pill); font-size: 13px; line-height: 18px; font-weight: 500; white-space: nowrap; }
.pm-chip .pm-ico { font-size: 16px; }
.pm-chip--held { background: var(--held-soft); color: var(--held); }
.pm-chip--approved { background: var(--primary-container); color: var(--on-primary-container); }
.pm-chip--released { background: var(--released-soft); color: var(--released); }
.pm-chip--blocked, .pm-chip--declined { background: var(--blocked-soft); color: var(--blocked); }
.pm-chip--expired { background: var(--neutral-soft); color: var(--ink-muted); }

/* TierBadge */
.pm-tier { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: var(--radius-sm); font: 500 12px/16px var(--font-sans); background: var(--neutral-soft); color: var(--ink); }
.pm-tier--2, .pm-tier--3 { background: var(--tier-high-soft); color: var(--tier-high); }

/* ReasonChip */
.pm-reason { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: var(--radius-pill); background: var(--neutral-soft); color: var(--ink); font-size: 13px; line-height: 18px; }
.pm-reason b { font-family: var(--font-mono); font-weight: 400; font-size: 12px; color: var(--ink-muted); }

/* Cards: tinted, no border, big radius */
.pm-card { background: var(--surface-container); border-radius: var(--radius-lg); padding: var(--space-6); }
.pm-card--raised { background: var(--surface); box-shadow: var(--shadow-card); }
.pm-card--tight { padding: var(--space-4); }

/* Avatar: payee initial in a circle */
.pm-avatar { width: 56px; height: 56px; border-radius: var(--radius-pill); background: var(--primary-container); color: var(--on-primary-container); display: inline-flex; align-items: center; justify-content: center; font: 500 24px/1 var(--font-display); flex: none; }
.pm-avatar--sm { width: 40px; height: 40px; font-size: 17px; }

/* AmountBlock: centred, payments-app style */
.pm-amount { display: flex; flex-direction: column; align-items: center; text-align: center; gap: var(--space-1); }
.pm-amount__to { font-size: 15px; color: var(--ink-muted); margin-top: var(--space-2); }
.pm-amount__payee { font-size: 17px; font-weight: 500; color: var(--ink); }
.pm-amount__acct { font-family: var(--font-mono); font-size: 13px; color: var(--ink-muted); }
.pm-amount__fig { font: 500 48px/56px var(--font-display); font-variant-numeric: tabular-nums; margin-top: var(--space-3); }
.pm-amount__words { font-size: 14px; line-height: 20px; color: var(--ink-muted); }
.pm-money { font-weight: 500; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }

/* ChangedField */
.pm-changed { display: flex; gap: var(--space-3); align-items: flex-start; padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); background: var(--blocked-soft); }
.pm-changed > .pm-ico { color: var(--blocked); margin-top: 2px; }
.pm-changed__body { display: flex; flex-direction: column; gap: 2px; }
.pm-changed__title { font-weight: 500; font-size: 14px; color: var(--blocked); }
.pm-changed__vals { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); font-family: var(--font-mono); font-size: 13px; }
.pm-changed__old { color: var(--ink-muted); text-decoration: line-through; }
.pm-changed__new { color: var(--ink); font-weight: 500; }

/* AiExplanation */
.pm-ai { background: var(--primary-container); color: var(--on-primary-container); border-radius: var(--radius-md); padding: var(--space-4); }
.pm-ai__label { display: flex; align-items: center; gap: 6px; font-size: 13px; line-height: 18px; font-weight: 500; margin-bottom: var(--space-2); }
.pm-ai__note { font-size: 12px; line-height: 16px; margin-top: var(--space-2); opacity: .85; }

/* Timeline */
.pm-timeline { list-style: none; margin: 0; padding: 0; }
.pm-timeline li { position: relative; padding: 0 0 var(--space-4) 36px; }
.pm-timeline li::before { content: ""; position: absolute; left: 11px; top: 26px; bottom: 2px; width: 2px; border-radius: 2px; background: var(--line); }
.pm-timeline li:last-child::before { display: none; }
.pm-timeline__dot { position: absolute; left: 0; top: 0; width: 24px; height: 24px; border-radius: var(--radius-pill); background: var(--primary-container); color: var(--on-primary-container); display: flex; align-items: center; justify-content: center; }
.pm-timeline__dot .pm-ico { font-size: 16px; }
.is-held .pm-timeline__dot { background: var(--held-soft); color: var(--held); }
.is-blocked .pm-timeline__dot { background: var(--blocked-soft); color: var(--blocked); }
.is-released .pm-timeline__dot { background: var(--released-soft); color: var(--released); }
.pm-timeline__step { font-weight: 500; }
.pm-timeline__at { font-size: 13px; color: var(--ink-muted); }

/* AttestationCard */
.pm-attest { display: grid; grid-template-columns: auto 1fr; gap: var(--space-3) var(--space-4); font-size: 14px; margin: 0; }
.pm-attest dt { color: var(--ink-muted); }
.pm-attest dd { margin: 0; font-weight: 500; }
.pm-pass, .pm-fail, .pm-warn { font-weight: 500; display: inline-flex; align-items: center; gap: 6px; }
.pm-pass { color: var(--released); }
.pm-fail { color: var(--blocked); }
.pm-warn { color: var(--held); }

/* MandateCard */
.pm-mandate { background: var(--surface-container); border-radius: var(--radius-lg); padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.pm-mandate__head { display: flex; gap: var(--space-4); align-items: center; }
.pm-hash { font-family: var(--font-mono); font-size: 12px; line-height: 18px; background: var(--surface-container-high); border-radius: var(--radius-sm); padding: var(--space-2) var(--space-3); word-break: break-all; color: var(--ink); }

/* List (payments-app style rows) */
.pm-list { background: var(--surface-container); border-radius: var(--radius-lg); padding: var(--space-2) 0; }
.pm-list__row { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); cursor: pointer; }
.pm-list__row:hover { background: var(--surface-container-high); }
.pm-list__main { flex: 1; min-width: 0; }
.pm-list__name { font-weight: 500; display: flex; align-items: center; gap: 6px; }
.pm-list__sub { font-size: 13px; color: var(--ink-muted); }
.pm-list__end { text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }

/* HoldsTable (dense console view) */
.pm-table { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--surface); font-size: 14px; }
.pm-table th { text-align: left; font-size: 12px; line-height: 16px; font-weight: 500; color: var(--ink-muted); padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--line); }
.pm-table td { padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--line); vertical-align: middle; }
.pm-table tbody tr:hover { background: var(--surface-container); cursor: pointer; }
.pm-table .num { text-align: right; }
.pm-cell-payee { display: flex; align-items: center; gap: var(--space-3); }

/* Banner */
.pm-banner { display: flex; gap: var(--space-3); align-items: flex-start; padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); font-size: 14px; color: var(--ink); }
.pm-banner .pm-ico { margin-top: 1px; }
.pm-banner--held { background: var(--held-soft); } .pm-banner--held .pm-ico { color: var(--held); }
.pm-banner--blocked { background: var(--blocked-soft); } .pm-banner--blocked .pm-ico { color: var(--blocked); }
.pm-banner--released { background: var(--released-soft); } .pm-banner--released .pm-ico { color: var(--released); }
.pm-banner--info { background: var(--primary-container); color: var(--on-primary-container); }

/* EmptyState */
.pm-empty { text-align: center; padding: var(--space-8) var(--space-6); color: var(--ink-muted); }
.pm-empty__art { width: 72px; height: 72px; border-radius: var(--radius-pill); background: var(--primary-container); color: var(--on-primary-container); display: inline-flex; align-items: center; justify-content: center; margin-bottom: var(--space-3); }
.pm-empty__art .pm-ico { font-size: 36px; }

/* Success screen */
.pm-success { display: flex; flex-direction: column; align-items: center; text-align: center; gap: var(--space-2); padding: var(--space-8) var(--space-4); }
.pm-success__circle { width: 96px; height: 96px; border-radius: var(--radius-pill); background: var(--released-soft); color: var(--released); display: flex; align-items: center; justify-content: center; margin-bottom: var(--space-3); }
.pm-success__circle .pm-ico { font-size: 56px; }

/* Console shell: nav drawer with active pill */
.pm-shell { display: grid; grid-template-columns: 220px 1fr; min-height: 100%; background: var(--background); }
.pm-side { background: var(--surface-container); padding: var(--space-4) var(--space-3); display: flex; flex-direction: column; gap: 2px; }
.pm-side a { color: var(--ink); text-decoration: none; padding: 10px var(--space-4); border-radius: var(--radius-pill); font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: var(--space-3); }
.pm-side a[aria-current] { background: var(--secondary-container); color: var(--on-secondary-container); }

/* Approver phone */
.pm-phone { width: 360px; max-width: 100%; border-radius: 32px; overflow: hidden; border: 1px solid var(--line); background: var(--background); box-shadow: var(--shadow-pop); }
.pm-appbar { background: var(--background); color: var(--ink); padding: var(--space-3) var(--space-4); display: flex; align-items: center; gap: var(--space-3); font-size: 17px; font-weight: 500; }
.pm-sheet { padding: var(--space-2) var(--space-4) var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }

/* Acme ERP: the customer's system, deliberately not Pramaan */
.erp-shell { display: grid; grid-template-columns: 180px 1fr; font-family: Tahoma, Verdana, "Segoe UI", sans-serif; background: #F7F8FA; color: #1F2328; }
.erp-side { background: var(--erp-chrome); color: var(--on-erp-chrome); padding: var(--space-4) var(--space-3); font-size: 13px; display: flex; flex-direction: column; gap: var(--space-2); }
.erp-side strong { font-size: 14px; letter-spacing: .02em; margin-bottom: var(--space-2); }
.erp-main { padding: var(--space-4); }
.erp-table { width: 100%; border-collapse: collapse; font-size: 13px; background: #FFFFFF; border: 1px solid #C9CED6; }
.erp-table th, .erp-table td { border: 1px solid #C9CED6; padding: 6px 8px; text-align: left; }
.erp-table th { background: #E9ECF0; font-weight: 600; }
.pm-protected { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px 3px 4px; border-radius: 999px; background: #D3E3FD; color: #041E49; font: 500 12px/18px var(--font-sans); }
.pm-protected img { width: 18px; height: 18px; }

@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

/* ---------- Signature pieces: what makes Pramaan look like Pramaan ---------- */

/* Section title: big and light, like a payments app */
.pm-section { font: 400 28px/34px var(--font-display); margin: 0; color: var(--ink); }

/* Band: the coloured header with seal lines. Its colour is the payment's state. */
.pm-band { position: relative; overflow: hidden; background: var(--band); color: var(--ink); }
.pm-band--held { background: var(--band-held); }
.pm-band--released { background: var(--band-released); }
.pm-band--blocked { background: var(--band-blocked); }
.pm-band::before { content: ""; position: absolute; width: 520px; height: 520px; right: -260px; top: -260px; border-radius: 50%; pointer-events: none; opacity: .45;
  background: repeating-radial-gradient(circle, transparent 0 15px, var(--seal-line) 15px 16.5px);
  -webkit-mask-image: radial-gradient(circle, #000 0 45%, transparent 70%); mask-image: radial-gradient(circle, #000 0 45%, transparent 70%); }
.pm-band::after { content: ""; position: absolute; width: 150px; height: 150px; right: -40px; top: -40px; border-radius: 50%; border: 2px dashed var(--seal-line); opacity: .8; pointer-events: none; }
.pm-band > * { position: relative; z-index: 1; }
.pm-band__inner { padding: var(--space-4) var(--space-4) var(--space-6); display: flex; flex-direction: column; gap: var(--space-3); }
.pm-display { font: 500 40px/46px var(--font-display); letter-spacing: -0.01em; margin: 0; }
.pm-band .pm-amount__fig { font-size: 56px; line-height: 60px; letter-spacing: -0.02em; margin-top: var(--space-2); }

/* Search pill, sitting on the band */
.pm-search { display: flex; align-items: center; gap: var(--space-3); background: var(--surface); border-radius: var(--radius-pill); padding: 12px 20px; color: var(--ink-muted); box-shadow: var(--shadow-card); font-size: 16px; }

/* Action tiles: rounded squares with the label under them */
.pm-tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-3); }
.pm-tile { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); text-align: center; font-size: 14px; line-height: 18px; color: var(--ink); text-decoration: none; }
.pm-tile__sq { width: 64px; height: 64px; border-radius: var(--radius-lg); background: var(--primary-container); color: var(--primary); display: flex; align-items: center; justify-content: center; position: relative; }
.pm-tile__sq .pm-ico { font-size: 28px; }
.pm-tile__count { position: absolute; top: -6px; right: -6px; min-width: 22px; height: 22px; padding: 0 6px; box-sizing: border-box; border-radius: var(--radius-pill); background: var(--held); color: var(--on-primary); font: 500 12px/22px var(--font-sans); border: 2px solid var(--background); }

/* Hold to approve: press and hold, a deeper blue fills the pill, then the phone signs */
.pm-hold { position: relative; overflow: hidden; width: 100%; min-height: 60px; border: 0; border-radius: var(--radius-pill); background: var(--primary); color: var(--on-primary); font: 500 16px/20px var(--font-sans); display: flex; align-items: center; justify-content: center; gap: var(--space-2); cursor: pointer; user-select: none; -webkit-user-select: none; touch-action: none; }
.pm-hold::before { content: ""; position: absolute; inset: 0; width: var(--p, 0%); background: var(--primary-deep); transition: width .12s linear; }
.pm-hold > * { position: relative; }
.pm-hold:focus-visible { outline: 2px solid var(--focus); outline-offset: 3px; }
.pm-hold.is-done { background: var(--released); }
.pm-hold.is-done::before { display: none; }
.pm-hold__hint { font-size: 12px; color: var(--ink-muted); text-align: center; margin-top: calc(var(--space-2) * -1); }

/* Extended floating action button */
.pm-fab { display: inline-flex; align-items: center; gap: var(--space-3); padding: 16px 24px; border-radius: var(--radius-lg); background: var(--primary-container); color: var(--on-primary-container); font: 500 16px/20px var(--font-sans); border: 0; box-shadow: var(--shadow-pop); cursor: pointer; }

/* Bottom navigation with the active pill */
.pm-bottomnav { display: grid; grid-template-columns: repeat(4, 1fr); background: var(--surface-container); padding: var(--space-3) var(--space-2) var(--space-4); }
.pm-bottomnav a { display: flex; flex-direction: column; align-items: center; gap: var(--space-1); font-size: 13px; font-weight: 500; color: var(--ink-muted); text-decoration: none; }
.pm-bottomnav .pm-ico { width: 64px; height: 32px; border-radius: var(--radius-pill); display: flex; align-items: center; justify-content: center; font-size: 24px; }
.pm-bottomnav a[aria-current] { color: var(--ink); }
.pm-bottomnav a[aria-current] .pm-ico { background: var(--secondary-container); color: var(--on-secondary-container); font-variation-settings: "FILL" 1, "wght" 400, "opsz" 24; }

/* Outlined info pill (like a payments app's shortcut pills) */
.pm-pill { display: inline-flex; align-items: center; gap: var(--space-3); border: 1px solid var(--line); border-radius: var(--radius-pill); padding: 8px 20px 8px 8px; background: var(--background); }
.pm-pill__ic { width: 40px; height: 40px; border-radius: 50%; background: var(--primary-container); color: var(--primary); display: flex; align-items: center; justify-content: center; }
.pm-pill__k { font-size: 13px; color: var(--ink-muted); line-height: 16px; }
.pm-pill__v { font-size: 15px; font-weight: 500; line-height: 20px; }
```

---

## Part E. Components

Each component has its usage rules and reference markup (built on the classes in Part D). Icons are Material Symbols Rounded ligatures: `<span class="pm-ico">schedule</span>`. Logo paths in the markup point to `assets/Logos/`; use the SVGs in Part F.

### StateHeader

The coloured band at the top of every phone screen and console detail page, with fine white seal lines and a dashed seal ring in the corner, the security-paper texture of a cheque.

- Its colour is the payment's state: `band` blue by default, `band-held` amber, `band-released` green, `band-blocked` red. The whole top of the screen tells you the state before you read a word.
- It always also shows the state as a chip (white background) so colour is never alone.
- Content on it: greeting or app bar, then the hero (count, payee, amount).
- One band per screen, only at the top. Never as a card in the middle of a page.
- Classes: `pm-band`, `pm-band--held|released|blocked`, `pm-band__inner`.

Reference markup:

```html
<div class="pm-stack" style="max-width:380px">
<div class="pm-band" style="border-radius:var(--radius-lg)"><div class="pm-band__inner"><span class="pm-label" style="color:var(--ink-muted)">Default</span><h2 class="pm-display" style="font-size:28px;line-height:34px">2 payments need you</h2></div></div>
<div class="pm-band pm-band--held" style="border-radius:var(--radius-lg)"><div class="pm-band__inner"><span class="pm-chip pm-chip--held" style="align-self:flex-start;background:var(--background)"><span class="pm-ico" aria-hidden="true">schedule</span>Held · Tier 2</span><h2 class="pm-display" style="font-size:28px;line-height:34px">₹46,50,000</h2></div></div>
<div class="pm-row" style="flex-wrap:nowrap">
<div class="pm-band pm-band--released" style="border-radius:var(--radius-lg);flex:1"><div class="pm-band__inner"><span class="pm-chip pm-chip--released" style="align-self:flex-start;background:var(--background)"><span class="pm-ico" aria-hidden="true">check_circle</span>Released</span></div></div>
<div class="pm-band pm-band--blocked" style="border-radius:var(--radius-lg);flex:1"><div class="pm-band__inner"><span class="pm-chip pm-chip--blocked" style="align-self:flex-start;background:var(--background)"><span class="pm-ico" aria-hidden="true">block</span>Declined</span></div></div>
</div></div>
```

### HoldToApprove

Pramaan's signature interaction. The approver presses and holds the Approve pill for one second; a deeper blue fills it from left to right, then the fingerprint prompt opens and the phone signs.

- Why: a ₹46 lakh approval must never happen from an accidental tap in a pocket, and the hold makes the moment feel deliberate, like signing a cheque.
- Label carries the amount: "Hold to approve ₹46,50,000". While holding: "Keep holding…". Done: green, "Signed on this phone".
- Letting go early resets it. Keyboard: hold Space or Enter.
- Fill uses `primary-deep`; done uses `released`. Reduced motion: no fill animation, the prompt opens after the hold.
- Decline is a normal outlined pill, one tap.

Reference markup:

```html
<div class="pm-stack" style="max-width:360px">
<button class="pm-hold" data-live><span class="pm-ico" aria-hidden="true">fingerprint</span><span class="lbl">Hold to approve ₹46,50,000</span></button>
<div class="pm-hold__hint">Try it: press and hold for one second</div>
<button class="pm-hold" style="--p:62%"><span class="pm-ico" aria-hidden="true">fingerprint</span><span class="lbl">Keep holding…</span></button>
<button class="pm-hold is-done"><span class="pm-ico" aria-hidden="true">check</span><span class="lbl">Signed on this phone</span></button>
</div>
```

Reference behaviour:

```js
document.querySelectorAll('.pm-hold[data-live]').forEach(function(b){
  var t=null,p=0,label=b.querySelector('.lbl'),orig=label.textContent;
  function set(v){p=v;b.style.setProperty('--p',v+'%');}
  function stop(){ if(b.classList.contains('is-done'))return; clearInterval(t); set(0); label.textContent=orig; }
  function start(e){ if(b.classList.contains('is-done'))return; e.preventDefault(); label.textContent='Keep holding…';
    t=setInterval(function(){ set(Math.min(100,p+5)); if(p>=100){ clearInterval(t); b.classList.add('is-done'); label.textContent='Signed on this phone'; b.querySelector('.pm-ico').textContent='check';
      setTimeout(function(){ b.classList.remove('is-done'); set(0); label.textContent=orig; b.querySelector('.pm-ico').textContent='fingerprint'; },1800);} },50); }
  b.addEventListener('pointerdown',start); ['pointerup','pointerleave','pointercancel'].forEach(function(ev){b.addEventListener(ev,stop);});
  b.addEventListener('keydown',function(e){ if((e.key===' '||e.key==='Enter')&&!t){start(e);} });
  b.addEventListener('keyup',function(e){ if(e.key===' '||e.key==='Enter'){stop(); t=null;} });
});
```

### ActionTile

Rounded-square shortcut tiles with the label underneath, four to a row, like a payments app's quick actions.

- Use on the approver app home and the console dashboard. Four tiles, never more than eight.
- Tile: 64px, `radius-lg`, `primary-container` with a `primary` icon. Labels two lines max.
- A count badge in `held` amber only for "Waiting for you".

Reference markup:

```html
<div class="pm-tiles" style="max-width:380px">
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">pending_actions</span><span class="pm-tile__count">2</span></span>Waiting for you</a>
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">verified_user</span></span>Verify mandate</a>
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">smartphone</span></span>My phone key</a>
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">history</span></span>History</a>
</div>
```

### Button

Every button is a pill. Labels say exactly what happens; on a decision, the label carries the amount.

| Variant | Class | Use |
| --- | --- | --- |
| Filled | `pm-btn pm-btn--primary` | The one main action: Approve, Sign in with Google. One per view. |
| Outlined | `pm-btn pm-btn--outlined` | Decline, Cancel. Outline is `line-strong` (3:1). |
| Tonal | `pm-btn pm-btn--tonal` | Helpful but not final: Verify mandate, Export, Call vendor. |
| Text | `pm-btn pm-btn--text` | Low-stakes links inside cards: View full trail, Copy ID. |
| Danger | `pm-btn pm-btn--danger` | Only the final confirm of Report fraud, never on the first screen. |
| Block | add `pm-btn--block` | Full-width 56px buttons at the bottom of the approver app. |

- Never place Approve and Report fraud side by side.
- Minimum 44px on the web, 48dp on Android.
- The finance console has no Approve button.

Reference markup:

```html
<div class="pm-row">
<button class="pm-btn pm-btn--primary"><span class="pm-ico" aria-hidden="true">fingerprint</span>Approve ₹46,50,000</button>
<button class="pm-btn pm-btn--outlined">Decline</button>
<button class="pm-btn pm-btn--tonal"><span class="pm-ico" aria-hidden="true">verified_user</span>Verify mandate</button>
<button class="pm-btn pm-btn--text">View full trail</button>
<button class="pm-btn pm-btn--danger">Report fraud</button>
<button class="pm-btn pm-btn--primary" disabled>Verifying…</button>
</div>
```

### StatusChip

A payment's status from `holds.status`: a soft pill with an icon and a word, never colour alone.

| Status | Class | Icon | Meaning |
| --- | --- | --- | --- |
| `held` | `pm-chip--held` | schedule | Waiting for the approver |
| `approved` | `pm-chip--approved` | draw | Signed on the phone |
| `released` | `pm-chip--released` | check_circle | Money moved |
| `declined` | `pm-chip--declined` | block | Approver said no |
| `blocked` | `pm-chip--blocked` | gpp_bad | Reported, failed check or tamper |
| `expired` | `pm-chip--expired` | timer_off | Nobody approved in time |

Approved is blue, not green: green is kept for money that actually moved.

Reference markup:

```html
<div class="pm-row">
<span class="pm-chip pm-chip--held"><span class="pm-ico" aria-hidden="true">schedule</span>Held</span>
<span class="pm-chip pm-chip--approved"><span class="pm-ico" aria-hidden="true">draw</span>Approved</span>
<span class="pm-chip pm-chip--released"><span class="pm-ico" aria-hidden="true">check_circle</span>Released</span>
<span class="pm-chip pm-chip--declined"><span class="pm-ico" aria-hidden="true">block</span>Declined</span>
<span class="pm-chip pm-chip--blocked"><span class="pm-ico" aria-hidden="true">gpp_bad</span>Blocked</span>
<span class="pm-chip pm-chip--expired"><span class="pm-ico" aria-hidden="true">timer_off</span>Expired</span>
</div>
```

### TierBadge

The risk tier the rules gave a payment (0 to 3). Small radius, not a pill, so it never reads as a status.

- Tier 0 and 1 neutral; Tier 2 and 3 in `tier-high` (a burnt orange that is not the amber of "held").
- Always beside the status chip, never instead of it.

Reference markup:

```html
<div class="pm-row"><span class="pm-tier pm-tier--0">Tier 0</span><span class="pm-tier pm-tier--1">Tier 1</span><span class="pm-tier pm-tier--2">Tier 2</span><span class="pm-tier pm-tier--3">Tier 3</span></div>
```

### ReasonChip

One rule that fired, from `holds.reasons[]`, in plain words with an icon.

- Written by rules, never by Gemini.
- In the console, the rule code may follow in mono (`<b>new_payee</b>`) for finance staff; on the phone, text only.
- Show every reason; wrap, never truncate.

Reference markup:

```html
<div class="pm-row">
<span class="pm-reason"><span class="pm-ico pm-ico--sm" aria-hidden="true">person_add</span>First payment to this account</span>
<span class="pm-reason"><span class="pm-ico pm-ico--sm" aria-hidden="true">account_balance</span>Bank details changed 2 days ago</span>
<span class="pm-reason"><span class="pm-ico pm-ico--sm" aria-hidden="true">trending_up</span>4× this vendor's usual amount</span>
</div>
```

### AmountBlock

The heart of every decision screen, laid out like a payments app: payee avatar, who you are paying, masked account, then the big centred amount and the amount in words.

- Avatar: the payee's first letter on `primary-container`. Never a real company logo.
- Figures with Indian grouping (`formatRupees`), words with `rupeesInWords`; tabular numerals; never abbreviated here.
- In lists and tables use `pm-money`, right-aligned.

Reference markup:

```html
<div class="pm-card" style="max-width:380px">
<div class="pm-amount">
<span class="pm-avatar">G</span>
<span class="pm-amount__to">Paying</span>
<span class="pm-amount__payee">Global Trade Solutions</span>
<span class="pm-amount__acct">A/c ••9999 · ABCD0123456</span>
<span class="pm-amount__fig">₹46,50,000</span>
<span class="pm-amount__words">Forty-six lakh fifty thousand rupees</span>
</div></div>
```

### ChangedField

What is different from the vendor master: old value struck through, arrow, new value, on a soft red card with a filled warning icon.

- The most important element on the approver's screen: the fake-invoice scam works by changing bank details.
- Use for bank account, IFSC, payee name and beneficiary bank.
- The title says what changed in words.

Reference markup:

```html
<div class="pm-stack" style="max-width:440px">
<div class="pm-changed"><span class="pm-ico pm-ico--fill" aria-hidden="true">warning</span><div class="pm-changed__body"><span class="pm-changed__title">Bank account changed</span><span class="pm-changed__vals"><span class="pm-changed__old">••4417 HDFC</span><span class="pm-ico pm-ico--sm" aria-hidden="true">arrow_forward</span><span class="pm-changed__new">••9999 ABCD0123456</span></span></div></div>
<div class="pm-changed"><span class="pm-ico pm-ico--fill" aria-hidden="true">person_add</span><div class="pm-changed__body"><span class="pm-changed__title">New payee</span><span class="pm-changed__vals"><span class="pm-changed__new">First time you are paying this account</span></span></div></div>
</div>
```

### AiExplanation

Gemini's plain-words explanation of a hold, from `holds.explanation`, on a soft blue card.

- Always labelled "AI summary · Gemini" with the sparkle icon, and the note that rules decided.
- Display only: never the amount, payee or decision.
- Two or three sentences. If Gemini is unavailable, hide the card.

Reference markup:

```html
<div class="pm-ai" style="max-width:500px">
<div class="pm-ai__label"><span class="pm-ico pm-ico--fill pm-ico--sm" aria-hidden="true">auto_awesome</span>AI summary · Gemini</div>
<div>This invoice asks you to pay a new account added two days ago, and the amount is four times what Acme usually pays this vendor. Call the vendor on the number in your records before approving.</div>
<div class="pm-ai__note">Pramaan's rules decided the hold. This summary only explains it.</div>
</div>
```

### Timeline

The payment's trail, from `holds/{id}/steps`, oldest first, like an order-tracking list.

- Each step has a small round icon: blue for ordinary steps, amber held, red blocked, green released.
- Times in IST with seconds.
- Live: new steps appear at the bottom as Firestore updates.

Reference markup:

```html
<ol class="pm-timeline" style="max-width:420px">
<li><span class="pm-timeline__dot"><span class="pm-ico" aria-hidden="true">add</span></span><div class="pm-timeline__step">Created by clerk@acme.example</div><div class="pm-timeline__at">10:41:00 am IST</div></li>
<li class="is-held"><span class="pm-timeline__dot"><span class="pm-ico" aria-hidden="true">schedule</span></span><div class="pm-timeline__step">Held at Tier 2 for 3 reasons</div><div class="pm-timeline__at">10:41:02 am IST</div></li>
<li><span class="pm-timeline__dot"><span class="pm-ico" aria-hidden="true">smartphone</span></span><div class="pm-timeline__step">Sent to Priya Raman's phone</div><div class="pm-timeline__at">10:41:03 am IST</div></li>
<li><span class="pm-timeline__dot"><span class="pm-ico" aria-hidden="true">draw</span></span><div class="pm-timeline__step">Signed on Pixel 8 (StrongBox)</div><div class="pm-timeline__at">10:42:40 am IST</div></li>
<li class="is-released"><span class="pm-timeline__dot"><span class="pm-ico" aria-hidden="true">check</span></span><div class="pm-timeline__step">Released by the gate</div><div class="pm-timeline__at">10:42:41 am IST</div></li>
</ol>
```

### AttestationCard

What we know about the phone that signed, from `devices/{id}`.

- StrongBox → pass "StrongBox hardware". TrustedEnvironment → pass "TEE hardware". Software → warn (amber) "Software key, not hardware". Revoked → fail (red) "Device removed".
- Words first; IDs and verdict strings in mono, secondary.

Reference markup:

```html
<div class="pm-card" style="max-width:420px">
<h3 class="pm-heading" style="margin-bottom:16px">Approver's phone</h3>
<dl class="pm-attest">
<dt>Device</dt><dd>Pixel 8 · <span class="pm-mono">dv_01JD2X7Q8K</span></dd>
<dt>Key</dt><dd><span class="pm-pass"><span class="pm-ico pm-ico--fill pm-ico--sm" aria-hidden="true">verified_user</span>StrongBox hardware</span></dd>
<dt>Integrity</dt><dd><span class="pm-pass"><span class="pm-ico pm-ico--fill pm-ico--sm" aria-hidden="true">check_circle</span>Meets strong integrity</span></dd>
<dt>Patch level</dt><dd>October 2026</dd>
</dl></div>
```

### MandateCard

The signed approval itself, in the console and the verifier: like a payment receipt.

- Heading: amount and payee in plain words, payee avatar on the left, Signed chip on the right.
- Then who signed, on which phone, when (IST), and that Pramaan countersigned.
- Mandate ID and hash in a mono well with a Copy text button.

Reference markup:

```html
<div class="pm-mandate" style="max-width:500px">
<div class="pm-mandate__head"><span class="pm-avatar pm-avatar--sm">S</span><div style="flex:1"><div class="pm-heading">₹9,80,000 to Sri Lakshmi Castings</div><div class="pm-muted" style="font-size:13px">Payment mandate</div></div><span class="pm-chip pm-chip--approved"><span class="pm-ico" aria-hidden="true">draw</span>Signed</span></div>
<div class="pm-muted" style="font-size:14px">Signed by Priya Raman, CFO, on Pixel 8 at 10:42 am IST, 21 Nov 2026. Countersigned by Pramaan.</div>
<div class="pm-hash">pm_01JD2Y4M3N · sha256 9f2c…a71e</div>
</div>
```

### PaymentList

Payments as friendly list rows, like a payments app's history: avatar, payee, one-line reason and age, amount and status on the right.

- Use on the approver app's home, the console's dashboard, the sandbox bank, and narrow screens.
- For the full finance board with many columns, use HoldsTable.
- Agent-initiated payments show the `smart_toy` icon after the payee.

Reference markup:

```html
<div class="pm-list" style="max-width:560px">
<div class="pm-list__row"><span class="pm-avatar pm-avatar--sm">G</span><div class="pm-list__main"><div class="pm-list__name">Global Trade Solutions</div><div class="pm-list__sub">New account · 4× usual · 2 min ago</div></div><div class="pm-list__end"><span class="pm-money">₹46,50,000</span><span class="pm-chip pm-chip--held"><span class="pm-ico" aria-hidden="true">schedule</span>Held</span></div></div>
<div class="pm-list__row"><span class="pm-avatar pm-avatar--sm">S</span><div class="pm-list__main"><div class="pm-list__name">Sri Lakshmi Castings</div><div class="pm-list__sub">Above ₹5 lakh · 6 min ago</div></div><div class="pm-list__end"><span class="pm-money">₹9,80,000</span><span class="pm-chip pm-chip--released"><span class="pm-ico" aria-hidden="true">check_circle</span>Released</span></div></div>
<div class="pm-list__row"><span class="pm-avatar pm-avatar--sm">K</span><div class="pm-list__main"><div class="pm-list__name">Kaveri Steel Traders <span class="pm-ico pm-ico--sm" aria-hidden="true">smart_toy</span></div><div class="pm-list__sub">Agent invoice had hidden instructions · 9 min ago</div></div><div class="pm-list__end"><span class="pm-money">₹2,40,000</span><span class="pm-chip pm-chip--blocked"><span class="pm-ico" aria-hidden="true">gpp_bad</span>Blocked</span></div></div>
</div>
```

### HoldsTable

The finance console's full board: one row per scored payment, live from `holds`.

- Columns: Payee (avatar + masked account), Status, Amount (right-aligned), Tier, Why, Age.
- No outer border or box: rows separated by `line` dividers on white, hover tints to `surface-container`.
- Held first, then newest. A row opens the payment detail page. No Approve button in the console.

Reference markup:

```html
<table class="pm-table">
<thead><tr><th>Payee</th><th>Status</th><th class="num">Amount</th><th>Tier</th><th>Why</th><th>Age</th></tr></thead>
<tbody>
<tr><td><div class="pm-cell-payee"><span class="pm-avatar pm-avatar--sm">G</span><div><strong style="font-weight:500">Global Trade Solutions</strong><div class="pm-mono pm-muted">••9999</div></div></div></td><td><span class="pm-chip pm-chip--held"><span class="pm-ico" aria-hidden="true">schedule</span>Held</span></td><td class="pm-money">₹46,50,000</td><td><span class="pm-tier pm-tier--2">Tier 2</span></td><td>New account, 4× usual</td><td class="pm-muted">2 min</td></tr>
<tr><td><div class="pm-cell-payee"><span class="pm-avatar pm-avatar--sm">S</span><div><strong style="font-weight:500">Sri Lakshmi Castings</strong><div class="pm-mono pm-muted">••7781</div></div></div></td><td><span class="pm-chip pm-chip--released"><span class="pm-ico" aria-hidden="true">check_circle</span>Released</span></td><td class="pm-money">₹9,80,000</td><td><span class="pm-tier pm-tier--1">Tier 1</span></td><td>Above ₹5 lakh</td><td class="pm-muted">6 min</td></tr>
</tbody></table>
```

### Banner

A one-line message at the top of a page or card. Snackbars use the same text with `shadow-pop` on `ink` background.

- Lead with a short sentence that states the fact, then one detail.
- Always say whether money moved. Never "Error!" or "Success!".

Reference markup:

```html
<div class="pm-stack" style="max-width:540px">
<div class="pm-banner pm-banner--held"><span class="pm-ico" aria-hidden="true">schedule</span><div><strong style="font-weight:500">Waiting for Priya Raman.</strong> Sent to her phone 2 min ago. The money has not moved.</div></div>
<div class="pm-banner pm-banner--blocked"><span class="pm-ico" aria-hidden="true">block</span><div><strong style="font-weight:500">Declined on the approver's phone.</strong> The money did not move.</div></div>
<div class="pm-banner pm-banner--released"><span class="pm-ico" aria-hidden="true">check_circle</span><div><strong style="font-weight:500">Released.</strong> ₹9,80,000 sent to Sri Lakshmi Castings ••7781.</div></div>
<div class="pm-banner pm-banner--info"><span class="pm-ico" aria-hidden="true">info</span><div>You are in the demo workspace. Payments go to the sandbox bank.</div></div>
</div>
```

### EmptyState

For an empty board, an empty verifier or no access: a soft blue circle with one icon, a calm heading, one line.

- No access: "You don't have access yet. Ask your admin to add you as finance or clerk." with a Sign out button.

Reference markup:

```html
<div class="pm-card pm-empty" style="max-width:440px"><span class="pm-empty__art"><span class="pm-ico" aria-hidden="true">inbox</span></span><div class="pm-heading" style="color:var(--ink)">Nothing is waiting</div><div>Payments that need an approver will show up here.</div></div>
```

### ReleasedScreen

The moment after a successful approval on the phone: a big green tick, then the amount and payee, like a payments app's success screen.

- Only show it when the gate has actually released the money. Until then show "Approved, releasing…" with the blue Approved chip.
- Declined has its own screen: a neutral circle with `block`, "Declined. The money did not move.", then "Was this a fake request?" with Report fraud.
- Respect reduced motion: no tick animation.

Reference markup:

```html
<div class="pm-card pm-success" style="max-width:360px;background:var(--background)">
<span class="pm-success__circle"><span class="pm-ico pm-ico--fill" aria-hidden="true">check</span></span>
<div class="pm-title">Approved and released</div>
<div class="pm-amount__fig" style="margin-top:0;font-size:36px;line-height:44px">₹9,80,000</div>
<div class="pm-muted">to Sri Lakshmi Castings ••7781</div>
<div class="pm-muted" style="font-size:13px">Signed on your Pixel 8 · 10:42 am IST</div>
</div>
```

### ErpShell

The mock customer system, Acme Auto Components' ERP. It must look like someone else's older software, so the friendly Pramaan style stands out when it appears.

- Grey `erp-chrome`, Tahoma/Verdana, square bordered tables, dense rows.
- No pills, no Google Sans, no blue frame.
- Pramaan appears only as the "Protected by Pramaan" badge and status chips.
- Fictional company only.

Reference markup:

```html
<div class="erp-shell" style="border:1px solid #C9CED6">
<nav class="erp-side"><strong>ACME ERP</strong><span>Dashboard</span><span>Vendors</span><span style="font-weight:600">Payment run</span><span>Reports</span></nav>
<main class="erp-main"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><b>Payment run · 21-11-2026</b><span class="pm-protected"><img src="../../assets/Logos/pramaan-mark.svg" alt="">Protected by Pramaan</span></div>
<table class="erp-table"><tr><th>Vendor</th><th>Invoice</th><th>Amount (INR)</th><th>Status</th></tr>
<tr><td>Global Trade Solutions</td><td>INV-2301</td><td>46,50,000.00</td><td><span class="pm-chip pm-chip--held">Held by Pramaan</span></td></tr>
<tr><td>Sri Lakshmi Castings</td><td>SLC-0981</td><td>9,80,000.00</td><td><span class="pm-chip pm-chip--released">Paid</span></td></tr></table></main></div>
```

### ApproverHome

The approver app's home screen: the blue band with search, a greeting and the big count ("2 payments need you"), a reassurance line about the phone key, four action tiles, the "Waiting for you" list, and bottom navigation.

- The count is the hero. When nothing is waiting: "You're all caught up" and the list shows the last three approvals.
- Bottom nav: Home, Activity, Verify, You, with the active item in a `secondary-container` pill.
- Tapping a row opens ApproverScreen.

Reference markup:

```html
<div class="pm-phone">
<div class="pm-band"><div class="pm-band__inner" style="padding-top:20px">
<div class="pm-row" style="flex-wrap:nowrap"><div class="pm-search" style="flex:1"><span class="pm-ico" aria-hidden="true">search</span>Search payments</div><span class="pm-avatar pm-avatar--sm" style="background:var(--background)">P</span></div>
<div style="margin-top:12px"><div class="pm-muted" style="font-size:15px">Good morning, Priya</div><h1 class="pm-display">2 payments<br>need you</h1></div>
<div class="pm-row" style="gap:6px"><span class="pm-ico pm-ico--fill" style="color:var(--primary)">verified_user</span><span style="font-size:14px">Your phone key is hardware-protected</span></div>
</div></div>
<div class="pm-sheet" style="padding-top:20px;gap:24px">
<div class="pm-tiles">
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">pending_actions</span><span class="pm-tile__count">2</span></span>Waiting for you</a>
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">verified_user</span></span>Verify mandate</a>
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">smartphone</span></span>My phone key</a>
<a class="pm-tile" href="#"><span class="pm-tile__sq"><span class="pm-ico" aria-hidden="true">history</span></span>History</a>
</div>
<h2 class="pm-section">Waiting for you</h2>
<div style="margin:-8px -16px 0">
<div class="pm-list__row"><span class="pm-avatar pm-avatar--sm">G</span><div class="pm-list__main"><div class="pm-list__name">Global Trade Solutions</div><div class="pm-list__sub">New bank account · 2 min ago</div></div><div class="pm-list__end"><span class="pm-money">₹46,50,000</span><span class="pm-chip pm-chip--held"><span class="pm-ico" aria-hidden="true">schedule</span>Held</span></div></div>
<div class="pm-list__row"><span class="pm-avatar pm-avatar--sm">K</span><div class="pm-list__main"><div class="pm-list__name">Kaveri Steel Traders <span class="pm-ico pm-ico--sm" aria-hidden="true">smart_toy</span></div><div class="pm-list__sub">Requested by payables agent · 5 min ago</div></div><div class="pm-list__end"><span class="pm-money">₹2,40,000</span><span class="pm-chip pm-chip--held"><span class="pm-ico" aria-hidden="true">schedule</span>Held</span></div></div>
</div></div>
<nav class="pm-bottomnav"><a href="#" aria-current="page"><span class="pm-ico" aria-hidden="true">home</span>Home</a><a href="#"><span class="pm-ico" aria-hidden="true">receipt_long</span>Activity</a><a href="#"><span class="pm-ico" aria-hidden="true">verified_user</span>Verify</a><a href="#"><span class="pm-ico" aria-hidden="true">person</span>You</a></nav>
</div>
```

### ApproverScreen

Design reference for the Android approval screen (Prajit builds it in Compose with Material 3; design it in Stitch from this).

Top half is the state band, amber because the payment is held: back arrow, "Held · Tier 2" chip, payee avatar, "Paying Global Trade Solutions", the 56px amount and the amount in words. Below, on white: what changed, reason chips, AI summary, **Hold to approve ₹46,50,000**, and Decline.

- One payment per screen. The hold opens the fingerprint prompt; the signing happens in the phone's secure chip.
- After signing, the band turns green and the screen becomes ReleasedScreen once the gate releases.
- Report fraud is offered after Decline, not here.
- 16dp side padding, 48dp touch targets. Light theme only.

Reference markup:

```html
<div class="pm-phone">
<div class="pm-band pm-band--held"><div class="pm-band__inner" style="padding-top:12px;align-items:center;text-align:center">
<div class="pm-row" style="width:100%;flex-wrap:nowrap"><span class="pm-ico pm-ico--lg" aria-hidden="true">arrow_back</span><span style="flex:1"></span><span class="pm-chip pm-chip--held" style="background:var(--background)"><span class="pm-ico" aria-hidden="true">schedule</span>Held · Tier 2</span></div>
<span class="pm-avatar" style="background:var(--background);color:var(--ink);margin-top:4px">G</span>
<div><div class="pm-muted">Paying</div><div class="pm-amount__payee">Global Trade Solutions</div><div class="pm-amount__acct" style="color:var(--ink-muted)">INV-2301 · from clerk@acme.example</div></div>
<div class="pm-amount__fig">₹46,50,000</div>
<div class="pm-amount__words" style="margin-top:-8px">Forty-six lakh fifty thousand rupees</div>
</div></div>
<div class="pm-sheet" style="padding-top:20px">
<div class="pm-changed"><span class="pm-ico pm-ico--fill" aria-hidden="true">warning</span><div class="pm-changed__body"><span class="pm-changed__title">Bank account changed 2 days ago</span><span class="pm-changed__vals"><span class="pm-changed__old">••4417 HDFC</span><span class="pm-ico pm-ico--sm" aria-hidden="true">arrow_forward</span><span class="pm-changed__new">••9999 ABCD0123456</span></span></div></div>
<div class="pm-row"><span class="pm-reason"><span class="pm-ico pm-ico--sm" aria-hidden="true">person_add</span>First payment to this account</span><span class="pm-reason"><span class="pm-ico pm-ico--sm" aria-hidden="true">trending_up</span>4× usual amount</span></div>
<div class="pm-ai"><div class="pm-ai__label"><span class="pm-ico pm-ico--fill pm-ico--sm" aria-hidden="true">auto_awesome</span>AI summary · Gemini</div><div style="font-size:14px;line-height:20px">Call the vendor on the number you already have before approving.</div></div>
<button class="pm-hold" data-live><span class="pm-ico" aria-hidden="true">fingerprint</span><span class="lbl">Hold to approve ₹46,50,000</span></button>
<button class="pm-btn pm-btn--outlined pm-btn--block" style="margin-top:-4px">Decline</button>
</div></div>
```

Reference behaviour:

```js
document.querySelectorAll('.pm-hold[data-live]').forEach(function(b){
  var t=null,p=0,label=b.querySelector('.lbl'),orig=label.textContent;
  function set(v){p=v;b.style.setProperty('--p',v+'%');}
  function stop(){ if(b.classList.contains('is-done'))return; clearInterval(t); set(0); label.textContent=orig; }
  function start(e){ if(b.classList.contains('is-done'))return; e.preventDefault(); label.textContent='Keep holding…';
    t=setInterval(function(){ set(Math.min(100,p+5)); if(p>=100){ clearInterval(t); b.classList.add('is-done'); label.textContent='Signed on this phone'; b.querySelector('.pm-ico').textContent='check';
      setTimeout(function(){ b.classList.remove('is-done'); set(0); label.textContent=orig; b.querySelector('.pm-ico').textContent='fingerprint'; },1800);} },50); }
  b.addEventListener('pointerdown',start); ['pointerup','pointerleave','pointercancel'].forEach(function(ev){b.addEventListener(ev,stop);});
  b.addEventListener('keydown',function(e){ if((e.key===' '||e.key==='Enter')&&!t){start(e);} });
  b.addEventListener('keyup',function(e){ if(e.key===' '||e.key==='Enter'){stop(); t=null;} });
});
```


---

## Part F. Logos

A solid blue circle with one white pen stroke that ends in a dot: the moment of signing. Friendly and round, so it sits well as an Android app icon and next to other payment apps, without copying any of them.

- `pramaan-mark.svg`, `pramaan-lockup.svg`: circle is primary `#0B57D0`, stroke white, wordmark ink `#1F1F1F`. Use on white, the band colours and light surfaces. On the primary blue, use the mark in white with the stroke in primary.
- Android app icon: the mark centred on a white adaptive-icon background, circle at 66% of the safe zone.
- Clear space: a quarter of the mark's width. Smallest: 20px mark, 96px-wide lockup.
- The lockup's wordmark is live text in Google Sans Flex; outline it before using the file outside the web.
- Never recolour it red, amber or green, never use Google's four-colour style, and never place it inside Acme ERP's frame except in the "Protected by Pramaan" badge.

Save as `pramaan-mark.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="Pramaan mark"><title>Pramaan mark</title>
  <circle cx="32" cy="32" r="30" fill="#0B57D0"/>
  <path d="M17 35c3.6-0.5 5.8 1.8 8.2 6.2 2.7-9.3 8.4-17.3 20.6-23.4" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="46.6" cy="17.4" r="3" fill="#FFFFFF"/>
</svg>
```

Save as `pramaan-lockup.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 64" width="240" height="64" role="img" aria-label="Pramaan"><title>Pramaan</title>
  <circle cx="32" cy="32" r="30" fill="#0B57D0"/>
  <path d="M17 35c3.6-0.5 5.8 1.8 8.2 6.2 2.7-9.3 8.4-17.3 20.6-23.4" fill="none" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="46.6" cy="17.4" r="3" fill="#FFFFFF"/>
  <text x="76" y="43" font-family="'Google Sans Flex', 'Google Sans', Roboto, Arial, sans-serif" font-size="32" font-weight="500" fill="#1F1F1F">Pramaan</text>
</svg>
```
