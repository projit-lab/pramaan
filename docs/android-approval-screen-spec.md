# The approver's approval screen: a build spec for Prajit

Author: Shoaib. Date: 20 Nov 2026. Milestone: M1. Status: ready to build against.

**What this is, and is not.** The build plan says I hand over the approval screen
"from Stitch, with every state". This is the specification, written so Prajit can
build the Compose screen now without waiting: exact copy, layout order, every
state, and the rules that must not be broken. It is **not** a Stitch export — I
will produce the visual file separately and it will match this. Nothing here
depends on seeing it first; the colours all come from the shared tokens, which the
console already uses, so the two products will look like one.

This screen is the product. It is the only place a human decides, and everything
else in Pramaan exists to put the right facts on it.

---

## The one rule

**The approver must be able to spot a wrong payment in three seconds.**

Every layout choice below follows from that, and from one more: **the signature
covers the full account number, while the screen shows the last four**. If those
two ever disagree, the screen is lying about what is being signed.

---

## What the screen shows, in this order

Order is not cosmetic. It runs from "who is being paid" down to "why you are being
asked", because the payee and the amount are what a fraud gets wrong.

1. **Payee name, as the bank returns it.** Largest text on the screen. Where the
   bank or payout provider exposes a name look-up, this is that name, not the name
   typed into the ERP. If they differ, that is a reason chip (below), not a quiet
   substitution.
2. **Account and IFSC.** Last four digits only, as `•••• 7781`, with the IFSC
   beside it. **Tap reveals the full number**, and the reveal is logged.
3. **Amount in figures**, Indian grouping: `₹46,50,000`.
4. **Amount in Indian words**, directly beneath, same visual block:
   "forty-six lakh fifty thousand rupees". This is the digit-transposition catch
   and it is not optional.
5. **Purpose**: the invoice number, and the invoice itself behind a tap.
6. **Who raised it**: a person's work email, or, when an agent raised it, the
   agent identifier with a distinct marker. An approver must never have to work
   out that a machine asked.
7. **Every reason it was held**, as chips. A reason that records a change shows
   the old value struck through and the new value in red:
   `•••• 5540 → •••• 8117`. This is the sentence that saves the money.
8. **Gemini's explanation**, one to three sentences, under the label
   **"Explanation written by Gemini; rules made the decision"**. Word for word,
   the same label as the console.
9. **The expiry**, as a live countdown: "Expires in 58 min".
10. **Approve / Decline / Report fraud.**

### What must never be on this screen

- A "remember me" or "don't ask again" affordance of any kind.
- A total, a batch, or any summary of several payments. One signature, one payment.
- Any button that approves without the biometric prompt.
- Any claim about a check Pramaan did not run.

---

## The buttons

| Button | Weight | Behaviour |
| :--- | :--- | :--- |
| **Approve** | Primary, full width, but **not** the easiest reflex target: it sits below Decline, so the thumb does not find it first | Opens BiometricPrompt with the signature as its crypto object |
| **Decline** | Secondary, equal size to Approve | Records a decline; the payment is blocked |
| **Report fraud** | Tertiary, text button, red | Blocks the payment and raises an alert |

Approve is **disabled**, with the reason shown in place of the countdown, when:

- the approval has expired;
- the device key has been revoked;
- the approval has already been decided;
- the app could not reach the server to refresh the approval.

A disabled Approve always says why. An approver who cannot approve and cannot see
why will phone someone, and that call is the thing Pramaan exists to replace.

---

## Every state

Nine states. The first five are the build plan's; the last four are ones a real
day produces and they are cheaper to design now than to discover on stage.

### 1. Loading

Skeleton blocks in the shape of the final layout: payee line, amount block, three
reason chips. No spinner alone — a spinner on a payment screen reads as "something
is happening to the money".

No buttons are rendered at all. A disabled Approve that becomes enabled under a
thumb already travelling toward it is how an accident happens.

### 2. Ready (the normal state)

Everything above, Approve enabled, countdown live.

### 3. Waiting for the fingerprint

The system BiometricPrompt is up. Behind it, the screen keeps the payee and the
amount visible: the approver's last look before the finger lands must be at what
they are signing, not at a dimmed rectangle.

The app never draws its own fingerprint UI. The prompt is the platform's, bound to
the signing key, or the signature is not hardware-backed.

### 4. Signing

After the biometric succeeds, while the signature is computed and sent. Brief, but
it needs a state because the network can be slow and a second tap must be
impossible. All buttons disabled. Copy: "Sending your signed approval".

### 5. Signed

Green confirmation. Shows **what was signed**, not just that something was: payee,
last four, amount. Then what happens next, honestly:

> Approved. Pramaan is countersigning this and the payment will be released to the
> bank.

Not "Payment sent". Pramaan does not move money; the connector does, and the
mandate still has to match at the gate.

### 6. Failed

Separate copy per cause, because they need different actions from the person:

| Cause | Copy | What they can do |
| :--- | :--- | :--- |
| Biometric not recognised | "That fingerprint wasn't recognised." | Try again |
| Biometric cancelled | No error. Return to Ready. | — |
| Key invalidated (a new fingerprint was enrolled) | "This phone's signing key is no longer valid, because a new fingerprint was added. You'll need to enrol again." | Enrol again |
| Signature rejected by the server | "Pramaan could not verify this signature. The payment has not been approved." | Contact support; never a retry loop |
| Network | "Couldn't reach Pramaan. Your approval was not sent." | Retry |

**"Couldn't verify" never becomes "fraud".** A rejected signature is a rejected
signature; only the approver choosing "Report fraud" produces the word fraud.

### 7. Expired

The payment is shown greyed, Approve removed entirely rather than disabled, with:

> This approval expired at 11:42 am. Ask the accounts team to raise it again.

### 8. Already decided elsewhere

Two approvers can hold the same payment in the approval matrix. If it was decided
while this screen was open, replace the buttons with who decided, what, and when.
Never let the second approver sign something already resolved.

### 9. Revoked device

> This phone can no longer approve payments. Contact your administrator.

No Approve button. This is also what a lost-phone revocation looks like from the
other side.

---

## The enrolment screen, briefly

Same spec style, because M1 needs it too.

- **Sign in with Google**, then "Set up this phone".
- **Success**: shows where the key ended up, honestly — "StrongBox" or "Trusted
  Execution Environment", never a generic tick. If the key landed in the TEE
  rather than StrongBox, say TEE. A judge will ask, and the honest answer is a
  better answer.
- **"This phone can't be used"**, with the actual reason, when: no strong
  biometric is enrolled, the device is rooted or the bootloader is unlocked, or
  the key could only be created in software.

That last one is the whole security model refusing to bend, so the copy should
own it rather than apologise:

> Pramaan needs a signing key held in this phone's secure hardware. This phone
> can't provide one, so it can't be used to approve payments.

---

## Colours, type and spacing

Take them from `web/shared/src/styles/tokens.css`. The console, the ERP and this
screen must use one language, and that file is it. The values there are
placeholders until the Stitch design system lands; when it does, that file changes
and this screen changes with it.

The parts that are not placeholders and must not drift:

| Meaning | Token | Rule |
| :--- | :--- | :--- |
| Held, waiting | `--pr-held` (amber) | always with the word |
| Released, signed | `--pr-released` (green) | always with the word |
| Blocked, declined, a failed check | `--pr-blocked` (red) | always with the word |
| Anything a model wrote | `--pr-ai` (violet) | distinct from every status colour on purpose, so "written by Gemini" can never be mistaken for a pass |

**Colour never carries meaning alone.** Roughly one in twelve men has a colour
vision deficiency, and some of them are CFOs.

---

## Accessibility, and the projector

- The amount must stay legible at the largest system font size without truncating.
  The screen scrolls; the amount never shrinks.
- Every reason chip is real text, never an icon alone.
- Touch targets at least 48dp, and Approve and Decline are separated by enough
  space that a thumb cannot catch both.
- Screen-reader order follows the visual order above, and reads the amount in
  words after the figures.

---

## What I need back from Prajit

1. **The approval payload shape** — `GET /approvals/{id}` in `contracts/openapi.yaml`
   is my draft. If a field is missing for this screen, it has to go in the
   contract before the screen is built, not after.
2. **Whether the bank-returned payee name is available** at approval time, or only
   the ERP's name. The copy differs and so does the claim we make on stage.
3. **What the server sends when a signature is rejected** — a problem-details
   `type` per cause, so the failure copy above can be chosen by code rather than
   by matching on a message string.
