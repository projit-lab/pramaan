/**
 * Holds board v1.
 *
 * A live list from Firestore with status filters, plus the loading, empty and
 * error states. Riskiest first: tier descending, then newest.
 *
 * There is no Approve button here, at any role. An approval is a hardware
 * signature made on a phone, and no amount of being signed in to a web console
 * can produce one. That absence is the product.
 */

import {
  COLLECTIONS,
  EmptyState,
  ErrorState,
  type Hold,
  HOLD_STATUSES,
  type HoldStatus,
  LoadingState,
  Money,
  StatusBadge,
  TierBadge,
  type WithId,
  comparePaise,
  formatIstWithRelative,
  maskAccount,
  useLiveCollection,
} from '@pramaan/shared';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ReasonChips } from '../components/ReasonChips';

type Filter = HoldStatus | 'all';

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: 'held', label: 'Held' },
  { value: 'approved', label: 'Approved' },
  { value: 'released', label: 'Released' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'declined', label: 'Declined' },
  { value: 'all', label: 'All' },
];

/** Riskiest first: higher tier, then larger amount, then newest. */
function byRisk(a: WithId<Hold>, b: WithId<Hold>): number {
  if (a.tier !== b.tier) return b.tier - a.tier;
  const byAmount = comparePaise(b.amountPaise ?? '0', a.amountPaise ?? '0');
  if (byAmount !== 0) return byAmount;
  const aTime = a.createdAt?.toMillis?.() ?? 0;
  const bTime = b.createdAt?.toMillis?.() ?? 0;
  return bTime - aTime;
}

export function HoldsBoard(): ReactNode {
  const [filter, setFilter] = useState<Filter>('held');

  // The whole collection is read live and filtered in the browser. For the
  // buildathon's data volume this is one listener instead of six, and switching
  // a filter costs nothing. A real tenant would push the filter into the query.
  const { data, status, error } = useLiveCollection<Hold>(COLLECTIONS.holds);

  const visible = useMemo(() => {
    const rows = filter === 'all' ? data : data.filter((hold) => hold.status === filter);
    return [...rows].sort(byRisk);
  }, [data, filter]);

  const counts = useMemo(() => {
    const result: Partial<Record<Filter, number>> = { all: data.length };
    for (const value of HOLD_STATUSES) {
      result[value] = data.filter((hold) => hold.status === value).length;
    }
    return result;
  }, [data]);

  const newHold = useNewHoldToast(data, status);

  if (status === 'loading') {
    return <LoadingState label="Loading held payments" />;
  }

  if (status === 'error') {
    return (
      <ErrorState
        title="Could not load the holds board"
        error={error}
        onRetry={() => window.location.reload()}
      />
    );
  }

  return (
    <div className="pr-stack">
      <div className="pr-spread">
        <div>
          <h1 className="pr-h1">Held payments</h1>
          <p className="pr-muted">
            Every payment Pramaan is holding until the real approver signs it on their
            phone. Approving happens on the phone, never here.
          </p>
        </div>
      </div>

      <div className="pr-filters" role="group" aria-label="Filter by status">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            className="pr-filter"
            aria-pressed={filter === option.value}
            onClick={() => setFilter(option.value)}
          >
            {option.label}
            {counts[option.value] !== undefined ? ` (${counts[option.value]})` : ''}
          </button>
        ))}
      </div>

      {data.length === 0 ? (
        <EmptyState
          title="No payments held yet"
          detail="A payment appears here the moment a rule holds it. Create one in Acme ERP to see it arrive."
        />
      ) : visible.length === 0 ? (
        <EmptyState
          title={`No ${filter} payments`}
          detail="Try another filter, or All."
        />
      ) : (
        <HoldsTable rows={visible} />
      )}

      {newHold ? (
        <div className="pr-toasts">
          <div className="pr-toast pr-toast--held" role="status">
            New hold: {newHold.payeeNameAtBank}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function HoldsTable({ rows }: { rows: Array<WithId<Hold>> }): ReactNode {
  return (
    <table className="pr-table">
      <caption className="pr-visually-hidden">
        Held payments, riskiest first
      </caption>
      <thead>
        <tr>
          <th scope="col">Payee</th>
          <th scope="col">Amount</th>
          <th scope="col">Tier</th>
          <th scope="col">Status</th>
          <th scope="col">Why it was held</th>
          <th scope="col">Raised</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((hold) => {
          const raised = formatIstWithRelative(hold.createdAt);
          return (
            <tr key={hold.id}>
              <td>
                <Link to={`/payments/${hold.id}`}>{hold.payeeNameAtBank}</Link>
                <div className="pr-fineprint">
                  {maskAccount(hold.payeeAccountLast4)} &middot; {hold.payeeIfsc}
                </div>
              </td>
              <td>
                <Money paise={hold.amountPaise} />
              </td>
              <td>
                <TierBadge tier={hold.tier} />
              </td>
              <td>
                <StatusBadge status={hold.status} />
              </td>
              <td>
                <ReasonChips reasons={hold.reasons ?? []} />
              </td>
              <td>
                {raised ? (
                  <>
                    <div>{raised.relative}</div>
                    <div className="pr-fineprint">{raised.absolute}</div>
                  </>
                ) : (
                  <span className="pr-unverified">No time recorded</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/**
 * Shows a toast when a hold arrives that was not in the previous snapshot.
 *
 * Deliberately ignores the first snapshot: on opening the board, every hold is
 * "new", and six toasts at once is noise rather than news.
 */
function useNewHoldToast(
  data: Array<WithId<Hold>>,
  status: string,
): WithId<Hold> | null {
  const seen = useRef<Set<string> | null>(null);
  const [toast, setToast] = useState<WithId<Hold> | null>(null);

  useEffect(() => {
    if (status !== 'ready') return;

    if (seen.current === null) {
      seen.current = new Set(data.map((hold) => hold.id));
      return;
    }

    const arrived = data.find((hold) => !seen.current?.has(hold.id));
    for (const hold of data) seen.current.add(hold.id);

    if (arrived) {
      setToast(arrived);
      const timer = window.setTimeout(() => setToast(null), 6000);
      return () => window.clearTimeout(timer);
    }
    return;
  }, [data, status]);

  return toast;
}
