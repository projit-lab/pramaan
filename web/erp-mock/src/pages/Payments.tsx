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
import { type ReactNode, useMemo, useState } from 'react';
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
  const [search, setSearch] = useState('');

  if (status === 'loading') return <LoadingState label="Loading payments" />;
  if (status === 'error') {
    return <ErrorState title="We could not load payments" error={error} />;
  }

  // Filter by search query
  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data;
    return data.filter(
      (p) =>
        p.payeeNameAtBank.toLowerCase().includes(q) ||
        (p.purpose && p.purpose.toLowerCase().includes(q)) ||
        p.id.toLowerCase().includes(q)
    );
  }, [data, search]);

  // Totals calculations
  const totals = useMemo(() => {
    let totalPaise = 0n;
    let waitingCount = 0;
    let waitingPaise = 0n;

    for (const p of data) {
      const paise = BigInt(p.amountPaise ?? '0');
      totalPaise += paise;
      if (p.status === 'held' || p.status === 'approved') {
        waitingCount++;
        waitingPaise += paise;
      }
    }

    return {
      totalCount: data.length,
      totalFormatted: formatMoney(totalPaise.toString(), { paise: 'always' }),
      waitingCount,
      waitingFormatted: formatMoney(waitingPaise.toString(), { paise: 'always' }),
    };
  }, [data]);

  // Grouping by state: "Waiting on Pramaan" at top, then "Paid", then others
  const groups = useMemo(() => {
    const waiting = filteredRows.filter((p) => p.status === 'held' || p.status === 'approved');
    const paid = filteredRows.filter((p) => p.status === 'released');
    const stopped = filteredRows.filter(
      (p) => p.status === 'blocked' || p.status === 'declined' || p.status === 'expired'
    );

    return [
      {
        title: 'Waiting on Pramaan',
        description: 'Held until approved on the approver’s phone with hardware key',
        rows: waiting,
        badgeStyle: { background: '#FFE2AE', color: '#7A4100' },
      },
      {
        title: 'Paid / Released',
        description: 'Released and processed by bank',
        rows: paid,
        badgeStyle: { background: '#C8EED2', color: '#146C2E' },
      },
      {
        title: 'Stopped / Other',
        description: 'Declined, blocked or expired',
        rows: stopped,
        badgeStyle: { background: '#E9EEF6', color: '#444746' },
      },
    ].filter((g) => g.rows.length > 0);
  }, [filteredRows]);

  return (
    <div>
      <div className="erp-bar" style={{ marginBottom: 12 }}>
        <h1>Payment run</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="text"
            className="erp-input"
            placeholder="Search vendor or invoice…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: '5px 8px',
              fontSize: 13,
              border: '1px solid #8A9099',
              borderRadius: 2,
              minWidth: 200,
            }}
          />
          <Link to="/new" className="erp-btn erp-btn--go" style={{ textDecoration: 'none' }}>
            New payment
          </Link>
        </div>
      </div>

      {/* Totals panel in plain grey ERP style */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 8,
          marginBottom: 16,
          padding: 8,
          background: '#FFFFFF',
          border: '1px solid #C9CED6',
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: '#5A6169' }}>Total run volume</div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{totals.totalFormatted}</div>
          <div style={{ fontSize: 11, color: '#5A6169' }}>{totals.totalCount} total entries</div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#5A6169' }}>Waiting on Pramaan approval</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#7A4100' }}>
            {totals.waitingFormatted}
          </div>
          <div style={{ fontSize: 11, color: '#7A4100' }}>{totals.waitingCount} payments waiting</div>
        </div>
      </div>

      {filteredRows.length === 0 ? (
        <div className="erp-empty">
          {search ? 'No payments match your search.' : 'No payments yet. Create one and Pramaan will decide whether it can go straight through.'}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {groups.map((group) => (
            <div key={group.title}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 6,
                }}
              >
                <h2 style={{ margin: 0, fontSize: 14 }}>{group.title}</h2>
                <span
                  style={{
                    fontSize: 11,
                    padding: '2px 6px',
                    borderRadius: 2,
                    fontWeight: 600,
                    ...group.badgeStyle,
                  }}
                >
                  {group.rows.length}
                </span>
                <span style={{ fontSize: 11, color: '#5A6169' }}>— {group.description}</span>
              </div>

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
                    {group.rows.map((payment) => (
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
            </div>
          ))}
        </div>
      )}

      <p className="erp-hint" style={{ marginTop: 12 }}>
        An accounts clerk cannot approve a payment in Pramaan. Approvals are signed
        on the approver&rsquo;s own phone.
      </p>
    </div>
  );
}
