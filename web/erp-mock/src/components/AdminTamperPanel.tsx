/**
 * Hack us live.
 *
 * Demo scene 5. A judge is handed full administrator rights on Acme's ERP —
 * the most powerful insider there is — and invited to steal the money. They
 * change the account number on a payment the CFO already signed, and press
 * release.
 *
 * The gate refuses, because the mandate is a signature over the payment as it
 * was when the approver saw it. Changing the ERP's copy afterwards changes
 * nothing the signature covers, so the hash no longer matches and no amount of
 * admin access inside Acme can make it match. That is the entire argument of
 * the product, demonstrated by letting someone try to break it.
 *
 * This panel is deliberately part of the ERP and not of Pramaan: the attacker
 * here is the customer's own system, compromised. It only renders where the
 * demo runs, because a real Acme would never ship an "edit an approved payment"
 * button, and the point lands harder for being obviously a deliberate hole.
 */

import { Money, type WithId, type Hold, maskAccount, readEnv } from '@pramaan/shared';
import { type ReactNode, useState } from 'react';

interface TamperResult {
  intent_id: string;
  payee_account: string;
}

type Outcome =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'tampered'; account: string }
  | { kind: 'refused'; detail: string }
  | { kind: 'released'; detail: string }
  | { kind: 'error'; detail: string };

/**
 * Both endpoints belong to Prajit's API and both are local-only. They are
 * called with plain fetch rather than the generated client because neither is
 * in the contract this branch was cut from: `_local/...` is a development route
 * that must never reach the served OpenAPI, and `/gate/release` arrives with
 * his live-flow branch.
 */
async function post(base: string, path: string): Promise<Response> {
  return fetch(`${base}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
}

export function AdminTamperPanel({ payment }: { payment: WithId<Hold> }): ReactNode {
  const env = readEnv();
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' });

  // Only where the demo runs. A production ERP has no such button, and this one
  // calls a route Prajit's API refuses to serve unless ENV=local anyway.
  if (!env.demoMode) return null;

  // Nothing to steal until an approver has actually signed something.
  const signed = payment.approval != null || payment.mandateId != null;

  const tamper = async () => {
    setOutcome({ kind: 'working' });
    try {
      const res = await post(env.apiBase, `/v1/_local/intents/${payment.intentId}/tamper`);
      if (!res.ok) {
        setOutcome({ kind: 'error', detail: `The ERP could not change the record (${res.status}).` });
        return;
      }
      const body = (await res.json()) as TamperResult;
      setOutcome({ kind: 'tampered', account: body.payee_account });
    } catch (caught) {
      setOutcome({ kind: 'error', detail: (caught as Error).message });
    }
  };

  const release = async () => {
    setOutcome({ kind: 'working' });
    try {
      const res = await post(env.apiBase, `/v1/gate/release`);
      const body = (await res.json().catch(() => ({}))) as { detail?: string; title?: string };
      if (res.ok) {
        // Only reachable if the gate accepted, which for a tampered payment
        // would be the demo failing. Say so plainly rather than hiding it.
        setOutcome({
          kind: 'released',
          detail: 'The gate accepted this. That is not supposed to happen.',
        });
        return;
      }
      setOutcome({
        kind: 'refused',
        detail: body.detail ?? body.title ?? 'The gate refused to release this payment.',
      });
    } catch (caught) {
      setOutcome({ kind: 'error', detail: (caught as Error).message });
    }
  };

  return (
    <section className="erp-admin" aria-labelledby="admin-heading">
      <h2 id="admin-heading" className="erp-admin__title">
        Administrator
      </h2>
      <p className="erp-hint" style={{ marginTop: 0 }}>
        You have full rights on Acme&rsquo;s ERP. You can change this payment, even
        though it has already been approved.
      </p>

      <dl className="erp-admin__row">
        <dt>Payee</dt>
        <dd>{payment.payeeNameAtBank}</dd>
        <dt>Account on this system</dt>
        <dd className="pm-mono">
          {outcome.kind === 'tampered'
            ? maskAccount(outcome.account.slice(-4))
            : maskAccount(payment.payeeAccountLast4)}
        </dd>
        <dt>Amount</dt>
        <dd>
          <Money paise={payment.amountPaise} />
        </dd>
      </dl>

      {!signed ? (
        <p className="erp-hint">
          Nothing has been signed for this payment yet, so there is nothing for the
          gate to check. Get it approved on the phone first.
        </p>
      ) : null}

      <div className="erp-admin__actions">
        <button
          type="button"
          className="erp-btn"
          onClick={() => void tamper()}
          disabled={outcome.kind === 'working'}
        >
          Change the account number
        </button>
        <button
          type="button"
          className="erp-btn"
          onClick={() => void release()}
          disabled={outcome.kind === 'working' || !signed}
        >
          Release the payment
        </button>
      </div>

      {outcome.kind === 'tampered' ? (
        <div className="erp-admin__out erp-admin__out--changed">
          <strong>Changed.</strong> Acme&rsquo;s record now says{' '}
          <span className="pm-mono">{maskAccount(outcome.account.slice(-4))}</span>. The
          approver signed the old one. Press release and see what the gate does.
        </div>
      ) : null}

      {outcome.kind === 'refused' ? (
        <div className="erp-admin__out erp-admin__out--refused">
          <strong>The gate refused.</strong> {outcome.detail}
          <div className="erp-hint" style={{ marginTop: 6 }}>
            The mandate covers the payment as the approver saw it. Admin rights on
            Acme cannot reach inside a signature.
          </div>
        </div>
      ) : null}

      {outcome.kind === 'released' ? (
        <div className="erp-admin__out erp-admin__out--released">
          <strong>Released.</strong> {outcome.detail}
        </div>
      ) : null}

      {outcome.kind === 'error' ? (
        <div className="erp-admin__out">
          {outcome.detail}
          <div className="erp-hint" style={{ marginTop: 6 }}>
            This is a problem reaching the API, not a verdict on the payment.
          </div>
        </div>
      ) : null}
    </section>
  );
}
