# Pramaan Data Assets

What goes here: Seed fixtures, sample enterprise invoices, and BigQuery ledger table DDLs.
Owner: Prajit and Shoaib (both).

## Files

| File | What it is | Owner |
| :--- | :--- | :--- |
| `firestore-seed.json` | Seed for the Firestore emulator, following `contracts/firestore.md`. Loaded by `web/tools/seed-firestore.mjs`. | Shoaib |
| `invoices/INV-2219.pdf` | The genuine Sri Lakshmi invoice, ₹9,80,000. Demo moment 2. | Shoaib |
| `invoices/KAVERI-4471.pdf` | The poisoned Kaveri Steel invoice, ₹18,40,000, hiding an instruction to pay another account. Demo moment 4. | Shoaib |
| `invoices/generate_invoices.py` | Regenerates both, so neither is a hand-edited binary. | Shoaib |

See `invoices/README.md` before touching the poisoned one: the account printed on
its face is deliberately **correct**, and only a hidden line redirects it. That is
what makes the demo honest rather than a straw man.

All names are fictional, per the build plan: Acme Auto Components Pvt Ltd, and the
vendors Sri Lakshmi Castings, Kaveri Steel Traders, the look-alike Sri Laxmi
Castings, and the brand-new payee Global Trade Solutions.

Two things about the seed are deliberate and should stay that way:

- **`payouts` is empty.** A payout exists only because a mandate released it, so
  the sandbox bank page honestly reads "No money has moved yet" until the demo
  actually moves money. That is demo moment 2, and pre-seeding it would give the
  moment away and make the screen a lie.
- **One approver phone has no integrity verdict** (`lastIntegrityVerdict: null`).
  Play Integrity only recognises builds installed from a Play internal testing
  track, so until that track exists there will be no verdicts. The console renders
  that as "couldn't verify", never as a pass, and the seed exists partly to keep
  that path exercised.

## Still to come

| File | What it is | Owner | Milestone |
| :--- | :--- | :--- | :--- |
| `generate_history.py` | 24 months of payment history into BigQuery, so the anomaly check and the data agent have something real | Prajit | M2 |
| `bigquery/*.sql` | Ledger DDL and the `v_payments`, `v_holds`, `v_approvals` views | Shoaib, per the 20 Nov rebalance | M4 |
