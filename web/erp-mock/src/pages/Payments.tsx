/**
 * The clerk's payment run, live.
 *
 * Acme's own view of what happened to the payments it sent to Pramaan. The
 * clerk sees status and nothing else; they cannot approve, and there is no
 * button here that could.
 *
 * Plain ERP styling, except the status chip, which is Pramaan's and is meant
 * to look like it came from somewhere else.
 */

import {
  COLLECTIONS,
  ErrorState,
  type Hold,
  type HoldStatus,
  LoadingState,
  StatusBadge,
  formatMoney,
  maskAccount,
  relativeTime,
  useLiveCollection,
} from '@pramaan/shared';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/** What each status means to the person who keyed the payment. */
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
    return <ErrorState title="We could not load payments" error={error} />;
  }

  const rows = [...data].sort(
    (a, b) => (b.createdAt?.toMillis?.() ?? 0) - (a.createdAt?.toMillis?.() ?? 0),
  );

  return (
    <div>
      <div className="erp-bar">
        <h1>Payment run</h1>
        <Link to="/new" className="erp-btn erp-btn--go" style={{ textDecoration: 'none' }}>
          New payment
        </Link>
      </div>

      {rows.length === 0 ? (
        <div className="erp-empty">
          No payments yet. Create one and Pramaan will decide whether it can go
          straight through.
        </div>
      ) : (
        <div className="erp-table-wrap">
          <table className="erp-table">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>Invoice</th>
                <th>Account</th>
                <th style={{ textAlign: 'right' }}>Amount (INR)</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((payment) => (
                <tr key={payment.id}>
                  <td>
                    <Link to={`/payments/${payment.id}`}>{payment.payeeNameAtBank}</Link>
                  </td>
                  <td>{payment.purpose ?? '—'}</td>
                  <td>{maskAccount(payment.payeeAccountLast4)}</td>
                  <td style={{ textAlign: 'right' }}>
                    {formatMoney(payment.amountPaise, { symbol: false, paise: 'always' })}
                  </td>
                  <td>
                    <StatusBadge status={payment.status} />
                    <div style={{ fontSize: 11, color: '#5A6169', marginTop: 2 }}>
                      {CLERK_WORDING[payment.status]}
                    </div>
                  </td>
                  <td>{relativeTime(payment.createdAt) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="erp-hint" style={{ marginTop: 10 }}>
        An accounts clerk cannot approve a payment in Pramaan. Approvals are signed
        on the approver&rsquo;s own phone.
      </p>
    </div>
  );
}
