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
  RouteBadge,
  StateBand,
  StatusBadge,
  TierBadge,
  type WithId,
  comparePaise,
  formatIstWithRelative,
  formatMoney,
  maskAccount,
  relativeTime,
  useLiveCollection,
} from '@pramaan/shared';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

type Filter = HoldStatus | 'all';
type SortField = 'urgency' | 'payee' | 'amount' | 'tier' | 'age';
type SortDir = 'asc' | 'desc';

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: 'held', label: 'Held' },
  { value: 'approved', label: 'Approved' },
  { value: 'released', label: 'Released' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'declined', label: 'Declined' },
  { value: 'all', label: 'All' },
];

const TIER_FILTERS = [
  { value: 'all', label: 'All tiers' },
  { value: '0', label: 'Tier 0' },
  { value: '1', label: 'Tier 1' },
  { value: '2', label: 'Tier 2' },
  { value: '3', label: 'Tier 3' },
];

const ROUTE_FILTERS = [
  { value: 'all', label: 'All doors' },
  { value: 'erp', label: 'ERP' },
  { value: 'bank_file', label: 'Bank file' },
  { value: 'agent', label: 'Agent' },
  { value: 'payout_api', label: 'Payout API' },
];

const LANE_FILTERS = [
  { value: 'all', label: 'All lanes' },
  { value: 'fast', label: 'Fast' },
  { value: 'standard', label: 'Standard' },
  { value: 'enhanced', label: 'Enhanced' },
];

function byUrgency(a: WithId<Hold>, b: WithId<Hold>): number {
  const held = (hold: WithId<Hold>) => (hold.status === 'held' ? 0 : 1);
  if (held(a) !== held(b)) return held(a) - held(b);
  if (a.tier !== b.tier) return b.tier - a.tier;
  const byAmount = comparePaise(b.amountPaise ?? '0', a.amountPaise ?? '0');
  if (byAmount !== 0) return byAmount;
  return (b.createdAt?.toMillis?.() ?? 0) - (a.createdAt?.toMillis?.() ?? 0);
}

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
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [routeFilter, setRouteFilter] = useState<string>('all');
  const [laneFilter, setLaneFilter] = useState<string>('all');
  const [search, setSearch] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('urgency');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const navigate = useNavigate();
  const { data, status, error } = useLiveCollection<Hold>(COLLECTIONS.holds);

  // Figures for the top stat bar
  const stats = useMemo(() => {
    let heldPaiseTotal = 0n;
    let heldCount = 0;
    let todayCount = 0;
    let oldestHeldTime: number | null = null;
    const now = Date.now();
    const startOfToday = new Date().setHours(0, 0, 0, 0);

    for (const hold of data) {
      if (hold.status === 'held') {
        heldCount++;
        try {
          heldPaiseTotal += BigInt(hold.amountPaise ?? '0');
        } catch {}
        const millis = hold.createdAt?.toMillis?.() ?? now;
        if (oldestHeldTime === null || millis < oldestHeldTime) {
          oldestHeldTime = millis;
        }
        if (millis >= startOfToday) {
          todayCount++;
        }
      }
    }

    return {
      heldAmount: formatMoney(heldPaiseTotal.toString()),
      heldCount,
      todayCount,
      oldestWaiting: oldestHeldTime ? relativeTime({ toMillis: () => oldestHeldTime } as any) : 'None',
    };
  }, [data]);

  const visible = useMemo(() => {
    let rows = data;

    // Status filter
    if (filter !== 'all') {
      rows = rows.filter((hold) => hold.status === filter);
    }

    // Tier filter
    if (tierFilter !== 'all') {
      const tierNum = parseInt(tierFilter, 10);
      rows = rows.filter((hold) => hold.tier === tierNum);
    }

    // Route filter
    if (routeFilter !== 'all') {
      rows = rows.filter((hold) => hold.entryRoute === routeFilter);
    }

    // Lane filter
    if (laneFilter !== 'all') {
      rows = rows.filter((hold) => hold.lane === laneFilter);
    }

    // Search query
    const q = search.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (hold) =>
          hold.payeeNameAtBank.toLowerCase().includes(q) ||
          (hold.purpose && hold.purpose.toLowerCase().includes(q)) ||
          hold.id.toLowerCase().includes(q)
      );
    }

    // Sorting
    return [...rows].sort((a, b) => {
      if (sortField === 'urgency') {
        return byUrgency(a, b);
      }
      if (sortField === 'payee') {
        const diff = a.payeeNameAtBank.localeCompare(b.payeeNameAtBank);
        return sortDir === 'asc' ? diff : -diff;
      }
      if (sortField === 'amount') {
        const diff = comparePaise(a.amountPaise ?? '0', b.amountPaise ?? '0');
        return sortDir === 'asc' ? diff : -diff;
      }
      if (sortField === 'tier') {
        const diff = (a.tier ?? 0) - (b.tier ?? 0);
        return sortDir === 'asc' ? diff : -diff;
      }
      if (sortField === 'age') {
        const aTime = a.createdAt?.toMillis?.() ?? 0;
        const bTime = b.createdAt?.toMillis?.() ?? 0;
        return sortDir === 'asc' ? aTime - bTime : bTime - aTime;
      }
      return 0;
    });
  }, [data, filter, tierFilter, routeFilter, laneFilter, search, sortField, sortDir]);

  const counts = useMemo(() => {
    const result: Partial<Record<Filter, number>> = { all: data.length };
    for (const value of HOLD_STATUSES) {
      result[value] = data.filter((hold) => hold.status === value).length;
    }
    return result;
  }, [data]);

  const waiting = counts['held'] ?? 0;
  useNewHoldToast(data, status);

  const handleHeaderSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sortArrow = (field: SortField) => {
    if (sortField !== field) return null;
    return <span style={{ marginLeft: 4 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

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
        {/* Figures row: system metrics depth */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 'var(--space-3)',
          }}
        >
          <div className="pm-card pm-card--tight" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span className="pm-label">Money held right now</span>
            <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--held)' }}>{stats.heldAmount}</span>
            <span className="pm-hint">{stats.heldCount} payments held</span>
          </div>

          <div className="pm-card pm-card--tight" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span className="pm-label">Payments held</span>
            <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--ink)' }}>{stats.heldCount}</span>
            <span className="pm-hint">Needs phone hardware sign</span>
          </div>

          <div className="pm-card pm-card--tight" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span className="pm-label">Decisions today</span>
            <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--ink)' }}>{stats.todayCount}</span>
            <span className="pm-hint">Created today</span>
          </div>

          <div className="pm-card pm-card--tight" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span className="pm-label">Oldest one waiting</span>
            <span style={{ fontSize: 22, fontWeight: 600, color: 'var(--ink)' }}>{stats.oldestWaiting}</span>
            <span className="pm-hint">Longest waiting hold</span>
          </div>
        </div>

        {/* Status filters */}
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

        {/* Search and Secondary Filters row */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 'var(--space-3)',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ flex: '1 1 240px', maxWidth: 360 }}>
            <input
              type="text"
              className="pm-input"
              placeholder="Search by payee or invoice…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search holds by payee or invoice"
              style={{ width: '100%', height: 38 }}
            />
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
            <select
              className="pm-select"
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              aria-label="Filter by tier"
              style={{ padding: '6px 12px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--line)', background: 'var(--surface)', fontSize: 13 }}
            >
              {TIER_FILTERS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>

            <select
              className="pm-select"
              value={routeFilter}
              onChange={(e) => setRouteFilter(e.target.value)}
              aria-label="Filter by door"
              style={{ padding: '6px 12px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--line)', background: 'var(--surface)', fontSize: 13 }}
            >
              {ROUTE_FILTERS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>

            <select
              className="pm-select"
              value={laneFilter}
              onChange={(e) => setLaneFilter(e.target.value)}
              aria-label="Filter by lane"
              style={{ padding: '6px 12px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--line)', background: 'var(--surface)', fontSize: 13 }}
            >
              {LANE_FILTERS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {data.length === 0 ? (
          <EmptyState
            title="Nothing is waiting"
            detail="Payments that need an approver will show up here. Create one in Acme ERP to see it arrive."
          />
        ) : visible.length === 0 ? (
          <EmptyState
            title="No matching payments"
            detail="Try adjusting your filters or search terms."
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
                  <th scope="col" onClick={() => handleHeaderSort('payee')} style={{ cursor: 'pointer' }}>
                    Payee {sortArrow('payee')}
                  </th>
                  <th scope="col">Status</th>
                  <th scope="col" className="num" onClick={() => handleHeaderSort('amount')} style={{ cursor: 'pointer' }}>
                    Amount {sortArrow('amount')}
                  </th>
                  <th scope="col" onClick={() => handleHeaderSort('tier')} style={{ cursor: 'pointer' }}>
                    Tier {sortArrow('tier')}
                  </th>
                  <th scope="col">Why</th>
                  <th scope="col" onClick={() => handleHeaderSort('age')} style={{ cursor: 'pointer' }}>
                    Age {sortArrow('age')}
                  </th>
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
                              {hold.initiator?.type === 'agent' ? (
                                <Icon name="smart_toy" size="sm" label="Raised by an AI agent" />
                              ) : null}
                            </Link>
                            <div className="pm-mono pm-muted">
                              {maskAccount(hold.payeeAccountLast4)}
                            </div>
                            <RouteBadge route={hold.entryRoute} />
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
    </>
  );
}

function useNewHoldToast(data: Array<WithId<Hold>>, status: string): WithId<Hold> | null {
  const seenIds = useRef<Set<string>>(new Set());
  const initialLoad = useRef(true);
  const [toast, setToast] = useState<WithId<Hold> | null>(null);

  useEffect(() => {
    if (status !== 'ready') return;
    if (initialLoad.current) {
      for (const item of data) seenIds.current.add(item.id);
      initialLoad.current = false;
      return;
    }
    const newlyAdded = data.find((item) => !seenIds.current.has(item.id));
    for (const item of data) seenIds.current.add(item.id);
    if (newlyAdded && newlyAdded.status === 'held') {
      setToast(newlyAdded);
      const timer = window.setTimeout(() => setToast(null), 6000);
      return () => window.clearTimeout(timer);
    }
  }, [data, status]);

  return toast;
}
