/**
 * The sandbox bank. Public: no sign-in.
 *
 * This is the "money moved" screen, and it is a Pramaan surface rather than an
 * Acme one: a simple statement as a PaymentList. A payout appears here only
 * because a mandate released it, so the empty state is not a placeholder, it
 * is the claim: no money has moved yet.
 *
 * Where it reads from depends on VITE_PAYOUTS_SOURCE, because of an open
 * decision in contracts/firestore.md: the Firestore rules require a signed-in
 * user and this page has nobody signed in. The default is the API, which keeps
 * the rules closed and keeps a public page off the database.
 */

import {
  Avatar,
  COLLECTIONS,
  EmptyState,
  ErrorState,
  Icon,
  LoadingState,
  Money,
  type Payout,
  PramaanLockup,
  StateBand,
  formatIfsc,
  formatIstWithRelative,
  maskAccount,
  problemMessage,
  publicApi,
  readEnv,
  toProblem,
  useLiveCollection,
} from '@pramaan/shared';
import { type ReactNode, useCallback, useEffect, useState } from 'react';

interface PayoutRow {
  payout_id: string;
  mandate_id: string;
  amount_paise: string;
  payee_name_at_bank: string;
  payee_account_last4: string;
  payee_ifsc: string;
  created_at: string;
}

export function SandboxBank(): ReactNode {
  const source = readEnv().payoutsSource;

  return (
    <div>
      <header className="pm-page" style={{ paddingBottom: 0 }}>
        <div className="pm-spread">
          <span className="pm-title">Sandbox Bank</span>
          <span className="pm-row">
            <span className="pm-hint">Gated by</span>
            <PramaanLockup size={24} />
          </span>
        </div>
      </header>

      <main className="pm-page pm-page--narrow">
        <StateBand eyebrow={<span className="pm-label">Statement</span>}>
          <h1 className="pm-display">Payouts</h1>
          <div className="pm-muted">
            Money that actually left Acme&rsquo;s account. A payout appears here only
            when a Pramaan mandate released it.
          </div>
        </StateBand>

        {source === 'api' ? <PayoutsFromApi /> : <PayoutsFromFirestore />}

        <p className="pm-hint" style={{ marginTop: 'var(--space-6)' }}>
          A sandbox, not a real bank. Every name and account number is fictional.
        </p>
      </main>
    </div>
  );
}

function NoMoneyMoved(): ReactNode {
  return (
    <EmptyState
      title="No money has moved yet"
      detail="Payouts appear here only when a Pramaan mandate released them."
      icon="account_balance"
    />
  );
}

function Row({
  name,
  account,
  ifsc,
  paise,
  mandateId,
  when,
}: {
  name: string;
  account: string;
  ifsc: string;
  paise: string;
  mandateId: string;
  when: string | null;
}): ReactNode {
  return (
    <div className="pm-list__row" style={{ cursor: 'default' }}>
      <Avatar name={name} size="sm" />
      <div className="pm-list__main">
        <div className="pm-list__name">{name}</div>
        <div className="pm-list__sub">
          {maskAccount(account)} &middot; {formatIfsc(ifsc)}
          {when ? ` · ${when}` : ''}
        </div>
        <div className="pm-list__sub pm-mono">{mandateId}</div>
      </div>
      <div className="pm-list__end">
        <Money paise={paise} />
        <span className="pm-chip pm-chip--released">
          <Icon name="check_circle" />
          Paid
        </span>
      </div>
    </div>
  );
}

/** The default: GET /payouts, no sign-in needed. */
function PayoutsFromApi(): ReactNode {
  const [rows, setRows] = useState<PayoutRow[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    setProblem(null);
    try {
      // publicApi, not api: this page has nobody signed in and must not pull in
      // Firebase Auth just to read a public endpoint.
      const { data, error, response } = await publicApi().GET('/payouts');
      if (error || !data) {
        setProblem(problemMessage(toProblem(error, response?.status)));
        return;
      }
      setRows((data.payouts ?? []) as PayoutRow[]);
    } catch (caught) {
      setProblem(problemMessage(toProblem(caught)));
    }
  }, []);

  useEffect(() => {
    void load();
    // A public page cannot open a Firestore listener, so it polls. Ten seconds
    // is fast enough for a demo and slow enough not to hammer a free service.
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (problem) {
    return (
      <ErrorState
        title="We could not load the payouts"
        error={new Error(problem)}
        onRetry={() => void load()}
      />
    );
  }

  if (rows === null) return <LoadingState label="Loading payouts" />;
  if (rows.length === 0) return <NoMoneyMoved />;

  return (
    <div className="pm-list">
      {rows.map((payout) => (
        <Row
          key={payout.payout_id}
          name={payout.payee_name_at_bank}
          account={payout.payee_account_last4}
          ifsc={payout.payee_ifsc}
          paise={payout.amount_paise}
          mandateId={payout.mandate_id}
          when={formatIstWithRelative(payout.created_at)?.absolute ?? null}
        />
      ))}
    </div>
  );
}

/** The alternative: read Firestore directly, which needs a signed-in clerk. */
function PayoutsFromFirestore(): ReactNode {
  const { data, status, error } = useLiveCollection<Payout>(COLLECTIONS.payouts);

  if (status === 'loading') return <LoadingState label="Loading payouts" />;
  if (status === 'error') {
    return (
      <ErrorState
        title="We could not load the payouts"
        error={error}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (data.length === 0) return <NoMoneyMoved />;

  return (
    <div className="pm-list">
      {data.map((payout) => (
        <Row
          key={payout.id}
          name={payout.payeeName}
          account={payout.payeeAccountLast4}
          ifsc={payout.payeeIfsc}
          paise={payout.amountPaise}
          mandateId={payout.mandateId}
          when={formatIstWithRelative(payout.createdAt)?.absolute ?? null}
        />
      ))}
    </div>
  );
}
