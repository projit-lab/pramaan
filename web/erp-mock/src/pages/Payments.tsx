/**
 * The clerk's payments list, live.
 *
 * This is the ERP's own view of what happened to the payments it sent to Pramaan:
 * waiting for approval, released, or stopped. The clerk sees status and nothing
 * else; they cannot approve, and there is no button here that could.
 */

import {
  COLLECTIONS,
  EmptyState,
  ErrorState,
  type Hold,
  type HoldStatus,
  LoadingState,
  Money,
  StatusBadge,
  formatIstWithRelative,
  maskAccount,
  useLiveCollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/** What a clerk is told, in their words rather than Pramaan's. */
const CLERK_WORDING: Record<HoldStatus, string> = {
  held: 'Waiting for approval',
  approved: 'Approved, releasing',
  released: 'Paid',
  blocked: 'Stopped',
  declined: 'Stopped',
  expired: 'Expired, not paid',
};

export function Payments(): ReactNode {
  const { data, status, error } = useLiveCollection<Hold>(COLLECTIONS.holds);

  if (status === 'loading') return <LoadingState label="Loading payments" />;
  if (status === 'error') {
    return <ErrorState title="Could not load payments" error={error} />;
  }

  const rows = [...data].sort(
    (a, b) => (b.createdAt?.toMillis?.() ?? 0) - (a.createdAt?.toMillis?.() ?? 0),
  );

  return (
    <div className="pr-stack">
      <div className="pr-spread">
        <div>
          <h1 className="pr-h1">Payments</h1>
          <p className="pr-muted">
            Outgoing payments and what Pramaan did with each one.
          </p>
        </div>
        <Link to="/new" className="pr-button pr-button--primary">
          New payment
        </Link>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No payments yet"
          detail="Create one and Pramaan will decide whether it can go straight through."
        >
          <Link to="/new" className="pr-button pr-button--primary">
            New payment
          </Link>
        </EmptyState>
      ) : (
        <table className="pr-table">
          <thead>
            <tr>
              <th scope="col">Payee</th>
              <th scope="col">Purpose</th>
              <th scope="col">Amount</th>
              <th scope="col">Status</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((payment) => {
              const created = formatIstWithRelative(payment.createdAt);
              return (
                <tr key={payment.id}>
                  <td>
                    <Link to={`/payments/${payment.id}`}>{payment.payeeNameAtBank}</Link>
                    <div className="pr-fineprint">
                      {maskAccount(payment.payeeAccountLast4)}
                    </div>
                  </td>
                  <td>{payment.purpose ?? <span className="pr-muted">&mdash;</span>}</td>
                  <td>
                    <Money paise={payment.amountPaise} />
                  </td>
                  <td>
                    <StatusBadge status={payment.status} />
                    <div className="pr-fineprint">{CLERK_WORDING[payment.status]}</div>
                  </td>
                  <td>{created ? created.relative : <span className="pr-muted">&mdash;</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <p className="pr-fineprint">
        An accounts clerk cannot approve a payment in Pramaan. Approvals are signed on
        the approver&rsquo;s own phone.
      </p>
    </div>
  );
}
