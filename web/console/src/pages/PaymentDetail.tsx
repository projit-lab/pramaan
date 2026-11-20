/**
 * Payment detail, M0 cut.
 *
 * What is real here: the live summary and the live timeline, both straight from
 * Firestore. What is not built yet is named as not built, rather than mocked up to
 * look finished: the invoice panel, the attestation card and the mandate viewer
 * land in M2 and M3, and this page says so instead of showing an empty card that
 * reads like a passed check.
 */

import {
  AiLabel,
  COLLECTIONS,
  ChannelBadge,
  CouldNotVerify,
  EmptyState,
  ErrorState,
  type Hold,
  LoadingState,
  ModelArmorBadge,
  Money,
  StatusBadge,
  type Step,
  TierBadge,
  formatIstWithRelative,
  maskAccount,
  useLiveDocument,
  useLiveSubcollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ReasonChips } from '../components/ReasonChips';

export function PaymentDetail(): ReactNode {
  const { intentId } = useParams<{ intentId: string }>();
  const hold = useLiveDocument<Hold>(COLLECTIONS.holds, intentId);
  const steps = useLiveSubcollection<Step>(COLLECTIONS.holds, intentId, 'steps');

  if (hold.status === 'loading') return <LoadingState label="Loading this payment" />;

  if (hold.status === 'error') {
    return <ErrorState title="Could not load this payment" error={hold.error} />;
  }

  if (!hold.data) {
    return (
      <EmptyState
        title="No such payment"
        detail={`Pramaan has nothing recorded for ${intentId ?? 'this id'}.`}
      >
        <Link to="/" className="pr-button">
          Back to the holds board
        </Link>
      </EmptyState>
    );
  }

  const payment = hold.data;
  const raised = formatIstWithRelative(payment.createdAt);
  const ordered = [...steps.data].sort((a, b) => (a.n ?? 0) - (b.n ?? 0));

  return (
    <div className="pr-stack">
      <p>
        <Link to="/">&larr; All held payments</Link>
      </p>

      {/* Summary */}
      <section className="pr-card pr-stack" aria-labelledby="summary-heading">
        <div className="pr-spread">
          <div>
            <h1 id="summary-heading" className="pr-h1">
              {payment.payeeName}
            </h1>
            <p className="pr-muted">
              {maskAccount(payment.payeeAccountLast4)} &middot; {payment.payeeIfsc}
              {payment.purpose ? ` · ${payment.purpose}` : ''}
            </p>
          </div>
          <div className="pr-row">
            <TierBadge tier={payment.tier} />
            <StatusBadge status={payment.status} />
          </div>
        </div>

        <Money paise={payment.amountPaise} withWords />

        <div className="pr-row">
          <ChannelBadge channel={payment.instructionChannel} />
          <span className="pr-fineprint">
            Raised by {payment.initiator?.id ?? 'unknown'}
            {raised ? ` · ${raised.absolute} (${raised.relative})` : ''}
          </span>
        </div>

        {payment.instructionNote ? (
          <blockquote className="pr-quote">{payment.instructionNote}</blockquote>
        ) : null}
      </section>

      {/* Why it was held */}
      <section className="pr-card pr-stack" aria-labelledby="reasons-heading">
        <h2 id="reasons-heading" className="pr-h2">
          Why Pramaan held it
        </h2>
        <ReasonChips reasons={payment.reasons ?? []} showSource />

        {payment.explanation ? (
          <>
            <p>{payment.explanation.text}</p>
            <AiLabel variant="explanation" />
          </>
        ) : null}

        {payment.modelArmorFinding ? (
          <div className="pr-stack">
            <div className="pr-row">
              <ModelArmorBadge category={payment.modelArmorFinding.category} />
              <span>{payment.modelArmorFinding.detail}</span>
            </div>
            {payment.modelArmorFinding.excerpt ? (
              <pre className="pr-mono pr-excerpt">{payment.modelArmorFinding.excerpt}</pre>
            ) : null}
          </div>
        ) : null}
      </section>

      {/* Timeline */}
      <section className="pr-card pr-stack" aria-labelledby="timeline-heading">
        <h2 id="timeline-heading" className="pr-h2">
          What happened
        </h2>

        {steps.status === 'loading' ? (
          <LoadingState label="Loading the timeline" />
        ) : steps.status === 'error' ? (
          <ErrorState title="Could not load the timeline" error={steps.error} />
        ) : ordered.length === 0 ? (
          <EmptyState title="No steps recorded yet" />
        ) : (
          <ol className="pr-timeline">
            {ordered.map((step) => {
              const at = formatIstWithRelative(step.at);
              return (
                <li key={step.id} className="pr-timeline__item" data-step={step.step}>
                  <span className="pr-timeline__step">{step.step}</span>
                  <span>{step.detail}</span>
                  <span className="pr-fineprint">{at ? at.absolute : 'No time recorded'}</span>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      {/* Honest placeholders. Not built yet is said out loud. */}
      <section className="pr-card pr-stack" aria-labelledby="evidence-heading">
        <h2 id="evidence-heading" className="pr-h2">
          Evidence
        </h2>
        <dl className="pr-defs">
          <dt>Mandate</dt>
          <dd>
            {payment.mandateId ? (
              <code className="pr-mono">{payment.mandateId}</code>
            ) : (
              <span className="pr-muted">
                No mandate yet. One exists only once an approver has signed this exact
                payment on their phone.
              </span>
            )}
          </dd>

          <dt>Attestation</dt>
          <dd>
            <CouldNotVerify what="the signing key" />
            <p className="pr-fineprint">
              The attestation card arrives in M1, once Prajit&rsquo;s enrolment checks
              run. Pramaan will not show a security check as passed before it has
              really run one.
            </p>
          </dd>

          <dt>Invoice</dt>
          <dd>
            <span className="pr-muted">
              The invoice panel, with the fields Gemini read beside the vendor master,
              arrives in M3.
            </span>
          </dd>
        </dl>

        <div className="pr-row">
          <button type="button" className="pr-button" disabled title="Enabled once a mandate exists">
            Verify this mandate
          </button>
          <button
            type="button"
            className="pr-button"
            disabled
            title="Enabled once a mandate has released this payment"
          >
            Open in sandbox bank
          </button>
        </div>
      </section>
    </div>
  );
}
