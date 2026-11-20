/**
 * New payment, M0 cut.
 *
 * The full form, the Pay button that calls POST /intents, and the
 * "Let the AI agent pay this" button land in M2 and M3. The shell, the fields and
 * the validation rules are here so the Stitch design has something to land on,
 * and the Pay button is honestly disabled rather than wired to nothing.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export function NewPayment(): ReactNode {
  return (
    <div className="pr-stack">
      <div>
        <h1 className="pr-h1">New payment</h1>
        <p className="pr-muted">
          Keying a payment here sends it to Pramaan first. Nothing reaches the bank
          without a matching mandate.
        </p>
      </div>

      <section className="pr-card pr-stack">
        <p>
          The payment form, the Pay button and &ldquo;Let the AI agent pay this&rdquo;
          arrive in M2 and M3, once <code className="pr-mono">POST /intents</code> and
          the agent service are live.
        </p>
        <p className="pr-fineprint">
          What is already agreed and will be built here: vendor, amount, invoice
          upload, how the instruction arrived and a note; Pay stays disabled until the
          form is valid; validation errors appear inline; an API error keeps everything
          that was typed; and &ldquo;Let the AI agent pay this&rdquo; needs an uploaded
          invoice.
        </p>
        <div className="pr-row">
          <Link to="/" className="pr-button">
            Back to payments
          </Link>
        </div>
      </section>
    </div>
  );
}
