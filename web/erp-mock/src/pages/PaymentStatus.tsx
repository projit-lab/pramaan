/**
 * One payment's live status, in the clerk's words.
 *
 * The clerk sees three outcomes: waiting for approval, paid, or stopped. They do
 * not see the attestation chain or the mandate: that is the finance team's view,
 * in the Pramaan console. Here the question is only "can I tell the vendor the
 * money is on its way?".
 *
 * Live from Firestore, so the chip changes under the clerk's eyes the moment the
 * approver signs. That is demo moment 2, seen from the ERP's side.
 */

import {
  COLLECTIONS,
  EmptyState,
  ErrorState,
  type Hold,
  type HoldStatus,
  LoadingState,
  Money,
  type Step,
  StatusBadge,
  formatIstWithRelative,
  maskAccount,
  useLiveDocument,
  useLiveSubcollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

/** What each status means to the person who keyed the payment. */
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
  released: {
    headline: 'Paid',
    detail: 'The money has left Acme’s account.',
  },
  blocked: {
    headline: 'Stopped',
    detail:
      'This payment was stopped and no money moved. Finance can tell you why.',
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

/** The clerk's view of the timeline: no crypto, just what happened. */
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
    return <ErrorState title="Could not load this payment" error={payment.error} />;
  }

  if (!payment.data) {
    return (
      <EmptyState
        title="No such payment"
        detail={`Acme ERP has nothing recorded for ${intentId ?? 'this id'}.`}
      >
        <Link to="/" className="pr-button">
          Back to payments
        </Link>
      </EmptyState>
    );
  }

  const hold = payment.data;
  const wording = CLERK_WORDING[hold.status];
  const created = formatIstWithRelative(hold.createdAt);
  const ordered = [...steps.data].sort((a, b) => (a.n ?? 0) - (b.n ?? 0));

  return (
    <div className="pr-stack">
      <p>
        <Link to="/">&larr; All payments</Link>
      </p>

      <section className="pr-card pr-stack">
        <div className="pr-spread">
          <div>
            <h1 className="pr-h1">{hold.payeeName}</h1>
            <p className="pr-muted">
              {maskAccount(hold.payeeAccountLast4)} &middot; {hold.payeeIfsc}
              {hold.purpose ? ` · ${hold.purpose}` : ''}
            </p>
          </div>
          <StatusBadge status={hold.status} />
        </div>

        <Money paise={hold.amountPaise} withWords />

        <div>
          <h2 className="pr-h2">{wording.headline}</h2>
          <p className="pr-muted">{wording.detail}</p>
        </div>

        {hold.status === 'held' ? (
          <p className="pr-fineprint">
            This page updates on its own. You do not need to refresh it.
          </p>
        ) : null}

        {created ? (
          <p className="pr-fineprint">
            Created {created.relative} &middot; {created.absolute}
          </p>
        ) : null}
      </section>

      <section className="pr-card pr-stack" aria-labelledby="progress-heading">
        <h2 id="progress-heading" className="pr-h2">
          Progress
        </h2>

        {steps.status === 'loading' ? (
          <LoadingState label="Loading progress" />
        ) : ordered.length === 0 ? (
          <EmptyState title="Nothing has happened yet" />
        ) : (
          <ol className="pr-timeline">
            {ordered.map((step) => {
              const at = formatIstWithRelative(step.at);
              return (
                <li key={step.id} className="pr-timeline__item" data-step={step.step}>
                  <span className="pr-timeline__step">{step.step}</span>
                  <span>{STEP_WORDING[step.step] ?? step.detail}</span>
                  <span className="pr-fineprint">{at ? at.relative : ''}</span>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      <p className="pr-fineprint">
        An accounts clerk cannot approve a payment. If this is urgent, ask the
        approver to check their phone; do not ask anyone to bypass Pramaan.
      </p>
    </div>
  );
}
