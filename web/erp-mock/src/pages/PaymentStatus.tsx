/**
 * One payment's live status, in the clerk's words.
 *
 * Three outcomes: waiting for approval, paid, or stopped. The clerk does not
 * see the attestation chain or the mandate; that is the finance team's view in
 * the Pramaan console. Here the question is only "can I tell the vendor the
 * money is on its way?".
 *
 * Live from Firestore, so the status changes under the clerk's eyes the moment
 * the approver signs. That is demo moment 2, seen from the ERP's side.
 */

import {
  COLLECTIONS,
  ErrorState,
  type Hold,
  type HoldStatus,
  LoadingState,
  type Step,
  StatusBadge,
  formatIstTime,
  formatMoney,
  maskAccount,
  relativeTime,
  useLiveDocument,
  useLiveSubcollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

const CLERK_WORDING: Record<HoldStatus, { headline: string; detail: string }> = {
  held: {
    headline: 'Waiting for approval',
    detail:
      'Pramaan has sent this to the approver’s phone. No money moves until they sign it.',
  },
  approved: {
    headline: 'Approved, releasing',
    detail: 'The approver signed it. Pramaan is releasing the payment to the bank.',
  },
  released: { headline: 'Paid', detail: 'The money has left Acme’s account.' },
  blocked: {
    headline: 'Stopped',
    detail: 'This payment was stopped and no money moved. Finance can tell you why.',
  },
  declined: {
    headline: 'Stopped',
    detail: 'The approver declined this payment. No money moved.',
  },
  expired: {
    headline: 'Expired, not paid',
    detail: 'Nobody signed this in time, so it lapsed. Raise it again if it is still needed.',
  },
};

const STEP_WORDING: Record<string, string> = {
  created: 'You created this payment',
  scored: 'Pramaan checked it against the rules',
  held: 'Held for approval',
  pushed: 'Sent to the approver’s phone',
  signed: 'The approver signed it',
  verified: 'Pramaan verified the signature',
  countersigned: 'Pramaan countersigned the approval',
  released: 'Released to the bank',
  blocked: 'Stopped',
};

export function PaymentStatus(): ReactNode {
  const { intentId } = useParams<{ intentId: string }>();
  const payment = useLiveDocument<Hold>(COLLECTIONS.holds, intentId);
  const steps = useLiveSubcollection<Step>(COLLECTIONS.holds, intentId, 'steps');

  if (payment.status === 'loading') return <LoadingState label="Loading this payment" />;
  if (payment.status === 'error') {
    return <ErrorState title="We could not load this payment" error={payment.error} />;
  }

  if (!payment.data) {
    return (
      <div className="erp-empty">
        Acme ERP has nothing recorded for {intentId ?? 'this id'}.{' '}
        <Link to="/">Back to the payment run</Link>.
      </div>
    );
  }

  const hold = payment.data;
  const wording = CLERK_WORDING[hold.status];
  const ordered = [...steps.data].sort((a, b) => (a.n ?? 0) - (b.n ?? 0));

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        <Link to="/" className="erp-back-link">&larr; Payment run</Link>
      </p>

      <h1>
        {hold.payeeNameAtBank}
        {hold.purpose ? ` · ${hold.purpose}` : ''}
      </h1>

      <table className="erp-table" style={{ maxWidth: 560, marginBottom: 12 }}>
        <tbody>
          <tr>
            <th style={{ width: 160 }}>Amount</th>
            <td>{formatMoney(hold.amountPaise, { symbol: false, paise: 'always' })} INR</td>
          </tr>
          <tr>
            <th>Account</th>
            <td>
              {maskAccount(hold.payeeAccountLast4)} &middot; {hold.payeeIfsc}
            </td>
          </tr>
          <tr>
            <th>Status</th>
            <td>
              <StatusBadge status={hold.status} />
            </td>
          </tr>
        </tbody>
      </table>

      <div className="erp-note">
        <strong>{wording.headline}.</strong> {wording.detail}
        {hold.status === 'held' ? ' This page updates on its own.' : ''}
      </div>

      <h2>Progress</h2>
      {steps.status === 'loading' ? (
        <LoadingState label="Loading progress" />
      ) : ordered.length === 0 ? (
        <div className="erp-empty">Nothing has happened yet.</div>
      ) : (
        <div className="erp-table-wrap">
          <table className="erp-table" style={{ maxWidth: 640 }}>
            <thead>
              <tr>
                <th style={{ width: 90 }}>Step</th>
                <th>What happened</th>
                <th style={{ width: 150 }}>Time</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((step) => (
                <tr key={step.id}>
                  <td>{step.n}</td>
                  <td>{STEP_WORDING[step.step] ?? step.detail}</td>
                  <td>
                    {formatIstTime(step.at) ?? '—'}
                    <div style={{ fontSize: 11, color: '#5A6169' }}>
                      {relativeTime(step.at) ?? ''}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="erp-hint" style={{ marginTop: 10 }}>
        An accounts clerk cannot approve a payment. If this is urgent, ask the
        approver to check their phone; do not ask anyone to bypass Pramaan.
      </p>
    </div>
  );
}
