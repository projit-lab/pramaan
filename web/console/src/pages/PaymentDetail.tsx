/**
 * One payment, in full.
 *
 * The page opens with the state band in the payment's colour, carrying the
 * AmountBlock: payee avatar, who is being paid, the masked account, the big
 * figure and the amount in words. Below, on white: what the rules found,
 * Gemini's explanation, the invoice, the attestation card, the timeline and
 * the mandate.
 *
 * No Approve button. The console cannot approve, at any role.
 */

import {
  AiLabel,
  AmountBlock,
  Banner,
  COLLECTIONS,
  ChannelBadge,
  EmptyState,
  ErrorState,
  type Hold,
  Icon,
  LoadingState,
  ModelArmorBadge,
  type Step,
  StatusBadge,
  TierBadge,
  formatIstWithRelative,
  formatIstTime,
  readEnv,
  useLiveDocument,
  useLiveSubcollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AttestationCard } from '../components/AttestationCard';
import { InvoicePanel } from '../components/InvoicePanel';
import { MandateViewer } from '../components/MandateViewer';
import { ReasonChips } from '../components/ReasonChips';

/** One line of plain fact at the top, which always says whether money moved. */
function statusBanner(hold: Hold): ReactNode {
  const approver = hold.approvers?.[0] ?? 'the approver';
  if (hold.status === 'held') {
    return (
      <Banner tone="held">
        <strong style={{ fontWeight: 500 }}>Waiting for {approver}.</strong> Sent to
        their phone. The money has not moved.
      </Banner>
    );
  }
  if (hold.status === 'declined' || hold.status === 'blocked') {
    return (
      <Banner tone="blocked">
        <strong style={{ fontWeight: 500 }}>
          {hold.status === 'declined' ? 'Declined on the approver’s phone.' : 'Stopped.'}
        </strong>{' '}
        The money did not move.
      </Banner>
    );
  }
  if (hold.status === 'released') {
    return (
      <Banner tone="released">
        <strong style={{ fontWeight: 500 }}>Released.</strong> The money has left
        Acme&rsquo;s account.
      </Banner>
    );
  }
  if (hold.status === 'approved') {
    return (
      <Banner tone="info">
        <strong style={{ fontWeight: 500 }}>Approved, releasing.</strong> Pramaan
        countersigned it; the gate has not released it yet.
      </Banner>
    );
  }
  return (
    <Banner tone="info" icon="timer_off">
      Nobody approved this in time, so it lapsed. No money moved.
    </Banner>
  );
}

const STEP_ICONS: Record<string, string> = {
  created: 'add',
  scored: 'rule',
  held: 'schedule',
  pushed: 'smartphone',
  signed: 'draw',
  verified: 'verified_user',
  countersigned: 'approval',
  released: 'check',
  blocked: 'block',
};

function stepClass(step: string): string {
  if (step === 'held' || step === 'pushed') return 'is-held';
  if (step === 'blocked') return 'is-blocked';
  if (step === 'released') return 'is-released';
  return '';
}

export function PaymentDetail(): ReactNode {
  const { intentId } = useParams<{ intentId: string }>();
  const hold = useLiveDocument<Hold>(COLLECTIONS.holds, intentId);
  const steps = useLiveSubcollection<Step>(COLLECTIONS.holds, intentId, 'steps');

  if (hold.status === 'loading') return <LoadingState label="Loading this payment" />;

  if (hold.status === 'error') {
    return <ErrorState title="We could not load this payment" error={hold.error} />;
  }

  if (!hold.data) {
    return (
      <EmptyState
        title="No such payment"
        detail={`Pramaan has nothing recorded for ${intentId ?? 'this id'}.`}
        icon="search_off"
      >
        <Link to="/" className="pm-btn pm-btn--tonal">
          Back to the board
        </Link>
      </EmptyState>
    );
  }

  const payment = hold.data;
  const raised = formatIstWithRelative(payment.createdAt);
  const ordered = [...steps.data].sort((a, b) => (a.n ?? 0) - (b.n ?? 0));

  return (
    <>
      <div style={{ marginBottom: 'var(--space-4)' }}>
        <Link to="/" className="pm-btn pm-btn--text" style={{ paddingLeft: 0 }}>
          <Icon name="arrow_back" size="sm" />
          All payments
        </Link>
      </div>

      <StateBandForPayment payment={payment} />

      <div className="pm-stack pm-stack--lg">
        {statusBanner(payment)}

        {/* Why it was held */}
        <section className="pm-card pm-stack" aria-labelledby="reasons-heading">
          <h2 id="reasons-heading" className="pm-heading">
            Why Pramaan held it
          </h2>
          <ReasonChips reasons={payment.reasons ?? []} showCodes />

          <div className="pm-row">
            <ChannelBadge channel={payment.instructionChannel} />
            <span className="pm-hint">
              Raised by {payment.initiator?.id ?? 'unknown'}
              {raised ? ` · ${raised.absolute} (${raised.relative})` : ''}
            </span>
          </div>

          {payment.instructionNote ? (
            <blockquote className="pm-quote">{payment.instructionNote}</blockquote>
          ) : null}

          {payment.explanation ? (
            <div className="pm-ai">
              <AiLabel variant="explanation" />
              <div>{payment.explanation.text}</div>
              <div className="pm-ai__note">
                Pramaan&rsquo;s rules decided the hold. This summary only explains it.
              </div>
            </div>
          ) : null}

          {payment.modelArmorFinding ? (
            <div className="pm-stack">
              <div className="pm-row">
                <ModelArmorBadge category={payment.modelArmorFinding.category} />
                <span>{payment.modelArmorFinding.detail}</span>
              </div>
              {payment.modelArmorFinding.excerpt ? (
                <pre className="pm-excerpt">{payment.modelArmorFinding.excerpt}</pre>
              ) : null}
            </div>
          ) : null}
        </section>

        <InvoicePanel invoice={payment.invoice} />

        <AttestationCard approval={payment.approval} />

        {/* Timeline */}
        <section className="pm-card pm-stack" aria-labelledby="timeline-heading">
          <h2 id="timeline-heading" className="pm-heading">
            What happened
          </h2>

          {steps.status === 'loading' ? (
            <LoadingState label="Loading the trail" />
          ) : steps.status === 'error' ? (
            <ErrorState title="We could not load the trail" error={steps.error} />
          ) : ordered.length === 0 ? (
            <div className="pm-muted">Nothing has happened yet.</div>
          ) : (
            <ol className="pm-timeline">
              {ordered.map((step) => (
                <li key={step.id} className={stepClass(step.step)}>
                  <span className="pm-timeline__dot">
                    <Icon name={STEP_ICONS[step.step] ?? 'circle'} />
                  </span>
                  <div className="pm-timeline__step">{step.detail ?? step.step}</div>
                  <div className="pm-timeline__at">
                    {formatIstTime(step.at) ?? 'No time recorded'}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>

        {/* The mandate */}
        <section className="pm-card pm-stack" aria-labelledby="mandate-heading">
          <h2 id="mandate-heading" className="pm-heading">
            The signed approval
          </h2>

          {payment.mandateId ? (
            <>
              <div className="pm-hash">{payment.mandateId}</div>
              <MandateViewer mandateId={payment.mandateId} />
              <div className="pm-row">
                <a
                  className="pm-btn pm-btn--tonal"
                  href={`${readEnv().verifyBase}/?mandate=${encodeURIComponent(payment.mandateId)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Icon name="verified_user" />
                  Verify mandate
                </a>
              </div>
            </>
          ) : (
            <div className="pm-muted">
              No mandate yet. One exists only once an approver has signed these exact
              details on their phone.
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function StateBandForPayment({ payment }: { payment: Hold }): ReactNode {
  const modifier =
    payment.status === 'held'
      ? 'pm-band--held'
      : payment.status === 'released'
        ? 'pm-band--released'
        : payment.status === 'blocked' || payment.status === 'declined'
          ? 'pm-band--blocked'
          : '';

  return (
    <div className={`pm-band ${modifier} pm-band--page`.trim()}>
      <div className="pm-band__inner" style={{ alignItems: 'center' }}>
        <div className="pm-row" style={{ alignSelf: 'flex-start' }}>
          <StatusBadge status={payment.status} onBand />
          <TierBadge tier={payment.tier} />
        </div>
        <AmountBlock
          paise={payment.amountPaise}
          payeeName={payment.payeeName}
          payeeAccountLast4={payment.payeeAccountLast4}
          payeeIfsc={payment.payeeIfsc}
          note={payment.purpose}
          onBand
        />
      </div>
    </div>
  );
}
