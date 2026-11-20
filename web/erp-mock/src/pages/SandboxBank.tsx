/**
 * The sandbox bank. Public: no sign-in.
 *
 * This is the "money moved" screen. A payout appears here only because a mandate
 * released it, so the empty state is not a placeholder, it is the claim: no money
 * has moved yet.
 *
 * Where it reads from depends on VITE_PAYOUTS_SOURCE, because of an open decision
 * in contracts/firestore.md: the Firestore rules require a signed-in user, and
 * this page has nobody signed in. Default is the API, which keeps the rules closed
 * and keeps a public page off the database. Switching to firestore works only if
 * the page is also signed in as a clerk.
 */

import {
  COLLECTIONS,
  EmptyState,
  ErrorState,
  type FirestoreTime,
  LoadingState,
  Money,
  type Payout,
  PramaanMark,
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

interface UnifiedPayout {
  id: string;
  mandateId: string;
  amountPaise: string;
  payeeNameAtBank: string;
  payeeAccountLast4: string;
  payeeIfsc: string;
  createdAt: string | FirestoreTime;
}

export function SandboxBank(): ReactNode {
  const source = readEnv().payoutsSource;
  return (
    <div className="pr-shell">
      <header className="pr-header">
        <div className="pr-header__inner">
          <div className="pr-row">
            <span className="pr-h3">Sandbox Bank</span>
            <span className="pr-badge pr-badge--grey">Payouts</span>
          </div>
          <div className="pr-row">
            <span className="pr-fineprint">Gated by</span>
            <PramaanMark size={20} />
          </div>
        </div>
      </header>

      <main className="pr-main pr-stack">
        <div>
          <h1 className="pr-h1">Payouts</h1>
          <p className="pr-muted">
            Money that actually left Acme&rsquo;s account. A payout appears here only
            when a Pramaan mandate released it.
          </p>
        </div>

        {source === 'api' ? <PayoutsFromApi /> : <PayoutsFromFirestore />}

        <p className="pr-fineprint">
          A sandbox, not a real bank. Every name and account number is fictional.
        </p>
      </main>
    </div>
  );
}

/** The default: GET /payouts, no sign-in needed. */
function PayoutsFromApi(): ReactNode {
  const [rows, setRows] = useState<UnifiedPayout[] | null>(null);
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
      const rawPayouts = (data.payouts ?? []) as Array<{
        payout_id: string;
        mandate_id: string;
        amount_paise: string;
        payee_name_at_bank: string;
        payee_account_last4: string;
        payee_ifsc: string;
        created_at: string;
      }>;
      setRows(
        rawPayouts.map((p) => ({
          id: p.payout_id,
          mandateId: p.mandate_id,
          amountPaise: p.amount_paise,
          payeeNameAtBank: p.payee_name_at_bank,
          payeeAccountLast4: p.payee_account_last4,
          payeeIfsc: p.payee_ifsc,
          createdAt: p.created_at,
        })),
      );
    } catch (caught) {
      setProblem(problemMessage(toProblem(caught)));
    }
  }, []);

  useEffect(() => {
    void load();
    // A public page cannot open a Firestore listener, so it polls. Ten seconds is
    // fast enough for a demo and slow enough not to hammer a free-tier service.
    const timer = window.setInterval(() => void load(), 10_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (problem) {
    return (
      <ErrorState
        title="Could not load payouts"
        error={new Error(problem)}
        onRetry={() => void load()}
      />
    );
  }

  if (rows === null) return <LoadingState label="Loading payouts" />;

  if (rows.length === 0) return <NoMoneyMoved />;

  return <PayoutTable payouts={rows} />;
}

/** The alternative: read Firestore directly, which needs a signed-in clerk. */
function PayoutsFromFirestore(): ReactNode {
  const { data, status, error } = useLiveCollection<Payout>(COLLECTIONS.payouts);

  if (status === 'loading') return <LoadingState label="Loading payouts" />;
  if (status === 'error') {
    return (
      <ErrorState
        title="Could not load payouts"
        error={error}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (data.length === 0) return <NoMoneyMoved />;

  return <PayoutTable payouts={data} />;
}

function PayoutTable({ payouts }: { payouts: readonly UnifiedPayout[] }): ReactNode {
  return (
    <table className="pr-table">
      <thead>
        <tr>
          <th scope="col">Payee</th>
          <th scope="col">Amount</th>
          <th scope="col">Released by mandate</th>
          <th scope="col">When</th>
        </tr>
      </thead>
      <tbody>
        {payouts.map((payout) => {
          const when = formatIstWithRelative(payout.createdAt);
          return (
            <tr key={payout.id}>
              <td>
                {payout.payeeNameAtBank}
                <div className="pr-fineprint">
                  {maskAccount(payout.payeeAccountLast4)} &middot;{' '}
                  {formatIfsc(payout.payeeIfsc)}
                </div>
              </td>
              <td>
                <Money paise={payout.amountPaise} />
              </td>
              <td>
                <code className="pr-mono">{payout.mandateId}</code>
              </td>
              <td>{when ? when.absolute : <span className="pr-muted">&mdash;</span>}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function NoMoneyMoved(): ReactNode {
  return (
    <EmptyState
      title="No money has moved yet"
      detail="Payouts appear here only when a Pramaan mandate released them."
    />
  );
}
