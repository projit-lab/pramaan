/**
 * The AI agent run, live, from the clerk's side.
 *
 * Demo moment 4. The clerk hands an invoice to the payables agent; the agent
 * reads it, looks up the vendor, and asks Pramaan for a mandate. What the
 * clerk watches here is an agent doing work and then **stopping at a human**,
 * which is the whole argument of the product.
 *
 * The agent has no tool that releases money, and this screen never suggests
 * otherwise: the furthest it goes is "asked for a mandate".
 */

import {
  COLLECTIONS,
  type AgentRequest,
  type AgentRequestStatus,
  ErrorState,
  LoadingState,
  ModelArmorBadge,
  formatIstTime,
  relativeTime,
  useLiveDocument,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';

const STATUS_WORDING: Record<AgentRequestStatus, { headline: string; detail: string }> = {
  reading: {
    headline: 'The agent is reading the invoice',
    detail: 'It will look the vendor up and then ask Pramaan for a mandate.',
  },
  mandate_requested: {
    headline: 'The agent asked for a mandate',
    detail: 'Pramaan is deciding. The agent cannot release this payment itself.',
  },
  flagged: {
    headline: 'Something is wrong with this invoice',
    detail:
      'Pramaan found a problem with what the agent read. The payment is held for a human.',
  },
  held: {
    headline: 'Held for approval',
    detail: 'An approver has to sign this on their phone before anything moves.',
  },
  declined: { headline: 'Declined', detail: 'The approver declined. No money moved.' },
  failed: {
    headline: 'The agent run failed',
    detail: 'Nothing was requested and no money moved.',
  },
};

export function AgentRun(): ReactNode {
  const { agentRequestId } = useParams<{ agentRequestId: string }>();
  const run = useLiveDocument<AgentRequest>(COLLECTIONS.agentRequests, agentRequestId);

  if (run.status === 'loading') return <LoadingState label="Loading the agent run" />;
  if (run.status === 'error') {
    return <ErrorState title="We could not load the agent run" error={run.error} />;
  }

  if (!run.data) {
    return (
      <div className="erp-empty">
        Nothing is recorded for {agentRequestId ?? 'this id'}.{' '}
        <Link to="/">Back to the payment run</Link>.
      </div>
    );
  }

  const request = run.data;
  const wording = STATUS_WORDING[request.status];
  const log = request.log ?? [];

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        <Link to="/">&larr; Payment run</Link>
      </p>

      <h1>Payables agent</h1>
      <p className="erp-hint" style={{ marginBottom: 10 }}>
        {request.agentId}
        {request.invoiceRef ? ` · invoice ${request.invoiceRef}` : ''}
      </p>

      <div className="erp-note">
        <strong>{wording.headline}.</strong> {wording.detail}
      </div>

      {request.modelArmorFinding ? (
        <div
          className="erp-note"
          style={{ borderColor: '#B3261E', background: '#FFF6F5' }}
        >
          <div style={{ marginBottom: 6 }}>
            <ModelArmorBadge category={request.modelArmorFinding.category} />
          </div>
          <div>{request.modelArmorFinding.detail}</div>
          {request.modelArmorFinding.excerpt ? (
            <>
              <pre className="pm-excerpt" style={{ marginTop: 6 }}>
                {request.modelArmorFinding.excerpt}
              </pre>
              <div className="erp-hint">
                This text was hidden in the invoice and addressed to an automated
                reader rather than to a person.
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {request.intentId ? (
        <p style={{ fontSize: 13 }}>
          This became payment {request.intentId}.{' '}
          <Link to={`/payments/${request.intentId}`}>See its status</Link>.
        </p>
      ) : null}

      <h2>What the agent did</h2>
      {log.length === 0 ? (
        <div className="erp-empty">The agent has not logged anything yet.</div>
      ) : (
        <div className="erp-table-wrap">
          <table className="erp-table" style={{ maxWidth: 720 }}>
            <thead>
              <tr>
                <th style={{ width: 110 }}>Source</th>
                <th>Step</th>
                <th style={{ width: 150 }}>Time</th>
              </tr>
            </thead>
            <tbody>
              {log.map((line, index) => (
                <tr key={`${index}-${line.text}`}>
                  <td>{line.source ?? 'rule'}</td>
                  <td>{line.text}</td>
                  <td>
                    {formatIstTime(line.at) ?? '—'}
                    <div style={{ fontSize: 11, color: '#5A6169' }}>
                      {relativeTime(line.at) ?? ''}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="erp-hint" style={{ marginTop: 10 }}>
        The agent can ask for a mandate. It has no tool that releases money, and no
        model can lower the tier a rule set.
      </p>
    </div>
  );
}
