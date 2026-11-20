/**
 * The AI agent run, live.
 *
 * Demo moment 4, from the clerk's side. The clerk hands an invoice to the
 * payables agent; the agent reads it, looks up the vendor, and asks Pramaan for a
 * mandate. What the clerk watches here is an agent doing work and then **stopping
 * at a human**, which is the whole argument of the product.
 *
 * The agent has no tool that releases money. This screen is careful never to
 * suggest otherwise: the furthest it goes is "asked for a mandate".
 */

import {
  COLLECTIONS,
  type AgentRequest,
  type AgentRequestStatus,
  EmptyState,
  ErrorState,
  LoadingState,
  ModelArmorBadge,
  ReasonSourceTag,
  formatIstWithRelative,
  useLiveDocument,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

const STATUS_WORDING: Record<AgentRequestStatus, { headline: string; detail: string; tone: string }> = {
  reading: {
    headline: 'The agent is reading the invoice',
    tone: 'grey',
    detail: 'It will look the vendor up and then ask Pramaan for a mandate.',
  },
  mandate_requested: {
    headline: 'The agent asked for a mandate',
    tone: 'amber',
    detail: 'Pramaan is deciding. The agent cannot release this payment itself.',
  },
  flagged: {
    headline: 'Something is wrong with this invoice',
    tone: 'red',
    detail:
      'Pramaan found a problem with what the agent read. The payment is held for a human.',
  },
  held: {
    headline: 'Held for approval',
    tone: 'amber',
    detail: 'An approver has to sign this on their phone before anything moves.',
  },
  declined: {
    headline: 'Declined',
    tone: 'red',
    detail: 'The approver declined. No money moved.',
  },
  failed: {
    headline: 'The agent run failed',
    tone: 'grey',
    detail: 'Nothing was requested and no money moved.',
  },
};

export function AgentRun(): ReactNode {
  const { agentRequestId } = useParams<{ agentRequestId: string }>();
  const run = useLiveDocument<AgentRequest>(COLLECTIONS.agentRequests, agentRequestId);

  if (run.status === 'loading') return <LoadingState label="Loading the agent run" />;
  if (run.status === 'error') {
    return <ErrorState title="Could not load the agent run" error={run.error} />;
  }

  if (!run.data) {
    return (
      <EmptyState
        title="No such agent run"
        detail={`Nothing is recorded for ${agentRequestId ?? 'this id'}.`}
      >
        <Link to="/" className="pr-button">
          Back to payments
        </Link>
      </EmptyState>
    );
  }

  const request = run.data;
  const wording = STATUS_WORDING[request.status];
  const log = [...(request.log ?? [])];

  return (
    <div className="pr-stack">
      <p>
        <Link to="/">&larr; All payments</Link>
      </p>

      <section className="pr-card pr-stack">
        <div className="pr-spread">
          <div>
            <h1 className="pr-h1">Payables agent</h1>
            <p className="pr-muted">
              <code className="pr-mono">{request.agentId}</code>
              {request.invoiceRef ? ` · invoice ${request.invoiceRef}` : ''}
            </p>
          </div>
          <span className={`pr-badge pr-badge--${wording.tone}`}>{wording.headline}</span>
        </div>

        <p>{wording.detail}</p>

        {request.modelArmorFinding ? (
          <div className="pr-stack">
            <div className="pr-row">
              <ModelArmorBadge category={request.modelArmorFinding.category} />
              <span>{request.modelArmorFinding.detail}</span>
            </div>
            {request.modelArmorFinding.excerpt ? (
              <>
                <pre className="pr-mono pr-excerpt">{request.modelArmorFinding.excerpt}</pre>
                <p className="pr-fineprint">
                  This text was hidden in the invoice and addressed to an automated
                  reader rather than to a person.
                </p>
              </>
            ) : null}
          </div>
        ) : null}

        {request.intentId ? (
          <p>
            This became payment <code className="pr-mono">{request.intentId}</code>.{' '}
            <Link to={`/payments/${request.intentId}`}>See its status</Link>.
          </p>
        ) : null}
      </section>

      <section className="pr-card pr-stack" aria-labelledby="log-heading">
        <h2 id="log-heading" className="pr-h2">
          What the agent did
        </h2>

        {log.length === 0 ? (
          <EmptyState title="The agent has not logged anything yet" />
        ) : (
          <ol className="pr-timeline">
            {log.map((line, index) => {
              const at = formatIstWithRelative(line.at);
              return (
                <li key={`${index}-${line.text}`} className="pr-timeline__item">
                  <span className="pr-timeline__step">
                    {line.source ? <ReasonSourceTag source={line.source} /> : null}
                  </span>
                  <span>{line.text}</span>
                  <span className="pr-fineprint">{at ? at.relative : ''}</span>
                </li>
              );
            })}
          </ol>
        )}

        <p className="pr-fineprint">
          The agent can ask for a mandate. It has no tool that releases money, and
          no model can lower the tier a rule set.
        </p>
      </section>
    </div>
  );
}
