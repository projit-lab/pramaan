/**
 * The finance console's board: one row per scored payment, live from Firestore.
 *
 * Held first, then riskiest. A row opens the payment detail page. There is no
 * Approve button, by design.
 */

import {
  Avatar,
  COLLECTIONS,
  EmptyState,
  ErrorState,
  type Hold,
  HOLD_STATUSES,
  type HoldStatus,
  Icon,
  LoadingState,
  Money,
  StateBand,
  StatusBadge,
  TierBadge,
  type WithId,
  comparePaise,
  formatIstWithRelative,
  maskAccount,
  relativeTime,
  useLiveCollection,
} from '@pramaan/shared';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

type Filter = HoldStatus | 'all';

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: 'held', label: 'Held' },
  { value: 'approved', label: 'Approved' },
  { value: 'released', label: 'Released' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'declined', label: 'Declined' },
  { value: 'all', label: 'All' },
];

/** Held first, then higher tier, then larger amount, then newest. */
function byUrgency(a: WithId<Hold>, b: WithId<Hold>): number {
  const held = (hold: WithId<Hold>) => (hold.status === 'held' ? 0 : 1);
  if (held(a) !== held(b)) return held(a) - held(b);
  if (a.tier !== b.tier) return b.tier - a.tier;
  const byAmount = comparePaise(b.amountPaise ?? '0', a.amountPaise ?? '0');
  if (byAmount !== 0) return byAmount;
  return (b.createdAt?.toMillis?.() ?? 0) - (a.createdAt?.toMillis?.() ?? 0);
}

/** The one-line "why" in the board's last-but-one column. */
function whyLine(hold: WithId<Hold>): string {
  const reasons = hold.reasons ?? [];
  if (reasons.length === 0) return 'No rules matched';
  return reasons
    .slice(0, 2)
    .map((reason) => reason.text.replace(/\.$/, ''))
    .join(', ');
}

export function HoldsBoard(): ReactNode {
  const [filter, setFilter] = useState<Filter>('held');
  const navigate = useNavigate();

  const { data, status, error } = useLiveCollection<Hold>(COLLECTIONS.holds);

  const visible = useMemo(() => {
    const rows = filter === 'all' ? data : data.filter((hold) => hold.status === filter);
    return [...rows].sort(byUrgency);
  }, [data, filter]);

  const counts = useMemo(() => {
    const result: Partial<Record<Filter, number>> = { all: data.length };
    for (const value of HOLD_STATUSES) {
      result[value] = data.filter((hold) => hold.status === value).length;
    }
    return result;
  }, [data]);

  const waiting = counts['held'] ?? 0;
  const newHold = useNewHoldToast(data, status);

  if (status === 'loading') return <LoadingState label="Loading held payments" />;

  if (status === 'error') {
    return (
      <ErrorState
        title="We could not load the board"
        error={error}
        onRetry={() => window.location.reload()}
      />
    );
  }

  return (
    <>
      <StateBand
        status={waiting > 0 ? 'held' : null}
        eyebrow={
          waiting > 0 ? (
            <StatusBadge status="held" onBand />
          ) : (
            <span className="pm-label">Nothing waiting</span>
          )
        }
      >
        <h1 className="pm-display">
          {waiting === 0
            ? 'All caught up'
            : waiting === 1
              ? '1 payment needs an approver'
              : `${waiting} payments need an approver`}
        </h1>
        <div className="pm-muted">
          Approving happens on the approver&rsquo;s phone, never here.
        </div>
      </StateBand>

      <div className="pm-stack pm-stack--lg">
        <div className="pm-filters" role="group" aria-label="Filter by status">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              className="pm-filter"
              aria-pressed={filter === option.value}
              onClick={() => setFilter(option.value)}
            >
              {option.label}
              {counts[option.value] !== undefined ? ` ${counts[option.value]}` : ''}
            </button>
          ))}
        </div>

        {data.length === 0 ? (
          <EmptyState
            title="Nothing is waiting"
            detail="Payments that need an approver will show up here. Create one in Acme ERP to see it arrive."
          />
        ) : visible.length === 0 ? (
          <EmptyState
            title={`No ${filter} payments`}
            detail="Try another filter, or All."
            icon="filter_alt"
          />
        ) : (
          <div className="pm-table-wrap">
            <table className="pm-table">
              <caption className="pm-visually-hidden">
                Payments Pramaan has scored, held first
              </caption>
              <thead>
                <tr>
                  <th scope="col">Payee</th>
                  <th scope="col">Status</th>
                  <th scope="col" className="num">
                    Amount
                  </th>
                  <th scope="col">Tier</th>
                  <th scope="col">Why</th>
                  <th scope="col">Age</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((hold) => {
                  const raised = formatIstWithRelative(hold.createdAt);
                  return (
                    <tr
                      key={hold.id}
                      onClick={() => navigate(`/payments/${hold.id}`)}
                      title={raised ? raised.absolute : undefined}
                    >
                      <td>
                        <div className="pm-cell-payee">
                          <Avatar name={hold.payeeNameAtBank} size="sm" />
                          <div>
                            <Link
                              to={`/payments/${hold.id}`}
                              className="pm-cell-payee__link"
                              onClick={(event) => event.stopPropagation()}
                            >
                              {hold.payeeNameAtBank}
                              {/* The icon is the only thing saying an agent raised
                                  this, so it carries a label rather than a shape
                                  alone. */}
                              {hold.initiator?.type === 'agent' ? (
                                <Icon name="smart_toy" size="sm" label="Raised by an AI agent" />
                              ) : null}
                            </Link>
                            <div className="pm-mono pm-muted">
                              {maskAccount(hold.payeeAccountLast4)}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={hold.status} />
                      </td>
                      <td className="num">
                        <Money paise={hold.amountPaise} />
                      </td>
                      <td>
                        <TierBadge tier={hold.tier} />
                      </td>
                      <td>{whyLine(hold)}</td>
                      <td className="pm-muted">
                        {relativeTime(hold.createdAt)?.replace(' ago', '') ?? '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {newHold ? (
        <div className="pm-toasts">
          <div className="pm-toast" role="status">
            New hold: {newHold.payeeNameAtBank}
          </div>
        </div>
      ) : null}
    </>
  );
}

/**
 * Shows a toast when a hold arrives that was not in the previous snapshot.
 *
 * Deliberately ignores the first snapshot: on opening the board every hold is
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
