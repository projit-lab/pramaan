/**
 * The public mandate verifier.
 *
 * An auditor or a payee pastes a mandate, or follows a link with its id, and
 * their own browser checks Pramaan's Cloud KMS countersignature with WebCrypto.
 * The point of this page is that it does not take Pramaan's word for anything: a
 * breach of our servers cannot forge a countersignature this page would accept,
 * because the signing key never leaves Cloud HSM.
 *
 * No sign-in and no Firebase. Everything here is deep-imported so the bundle
 * carries no auth SDK.
 */

import { publicApi } from '@pramaan/shared/api/public';
import { problemMessage, toProblem } from '@pramaan/shared/api/problem';
import { PramaanMark } from '@pramaan/shared/components/PramaanMark';
import { formatMoney } from '@pramaan/shared/format/money';
import { formatIst } from '@pramaan/shared/format/time';
import { maskAccount } from '@pramaan/shared/format/account';
import {
  type VerificationResult,
  verifyCountersignature,
} from '@pramaan/shared/mandate/verify';
import { type ReactNode, useCallback, useEffect, useState } from 'react';

type Mode = 'id' | 'json';

/** Only the fields this page displays. The rest of the mandate rides along. */
interface MandateShape {
  mandate_id?: string;
  type?: string;
  intent_id?: string;
  summary_sha256?: string;
  canonical_b64?: string;
  decision?: string;
  tier?: number;
  amount_paise?: string;
  payee?: { name_at_bank?: string; account_last4?: string; ifsc?: string };
  payer?: { company?: string; account_last4?: string };
  purpose?: { invoice?: string | null };
  approval?: { approver?: string; signed_at?: string; key_security_level?: string | null };
  countersignature?: { kms_key_version?: string; signature?: string };
  expires_at?: string;
}

interface Outcome {
  result: VerificationResult;
  mandate: MandateShape;
}

/** The console links here as /?mandate=pm_..., so an auditor lands ready to go. */
function mandateFromQuery(): string {
  try {
    return new URLSearchParams(window.location.search).get('mandate')?.trim() ?? '';
  } catch {
    return '';
  }
}

export function App(): ReactNode {
  const [mode, setMode] = useState<Mode>('id');
  const [value, setValue] = useState(mandateFromQuery);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [notFound, setNotFound] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const trimmed = value.trim();
  const canVerify = trimmed.length > 0 && !busy;

  const run = useCallback(async () => {
    setBusy(true);
    setOutcome(null);
    setNotFound(null);
    setFailure(null);

    try {
      let mandate: MandateShape;

      if (mode === 'json') {
        try {
          mandate = JSON.parse(trimmed) as MandateShape;
        } catch {
          setFailure('That is not valid JSON. Paste the whole mandate, including its braces.');
          return;
        }
      } else {
        const { data, error, response } = await publicApi().GET('/mandates/{mandateId}', {
          params: { path: { mandateId: trimmed } },
        });
        if (response?.status === 404) {
          setNotFound(trimmed);
          return;
        }
        if (error || !data) {
          setFailure(problemMessage(toProblem(error, response?.status)));
          return;
        }
        mandate = data as MandateShape;
      }

      const signature = mandate.countersignature?.signature;
      if (!signature) {
        setOutcome({
          result: {
            outcome: 'cannot_check',
            detail: 'This mandate carries no countersignature, so there is nothing to check.',
          },
          mandate,
        });
        return;
      }

      // The public key comes from the API, but it is the same key an auditor can
      // fetch themselves and pin. Nothing here is taken on trust from the
      // mandate itself.
      const keyResponse = await publicApi().GET('/keys/countersign');
      if (keyResponse.error || !keyResponse.data?.pem) {
        setFailure(
          problemMessage(toProblem(keyResponse.error, keyResponse.response?.status)) +
            " Pramaan's public key could not be fetched, so the signature was not checked.",
        );
        return;
      }

      const result = await verifyCountersignature({
        canonicalB64: mandate.canonical_b64 ?? '',
        signatureB64: signature,
        publicKeyPem: keyResponse.data.pem,
        expiresAt: mandate.expires_at ?? null,
        keyVersion: mandate.countersignature?.kms_key_version ?? null,
      });

      setOutcome({ result, mandate });
    } catch (caught) {
      setFailure(problemMessage(toProblem(caught)));
    } finally {
      setBusy(false);
    }
  }, [mode, trimmed]);

  // Follow a console link straight through, so the auditor sees a result rather
  // than a form they have to submit.
  useEffect(() => {
    if (mandateFromQuery()) void run();
    // Deliberately once, on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="pr-shell">
      <header className="pr-header">
        <div className="pr-header__inner">
          <PramaanMark size={26} />
          <span className="pr-badge pr-badge--grey">Public verifier</span>
        </div>
      </header>

      <main className="pr-main pr-stack">
        <div>
          <h1 className="pr-h1">Verify a Pramaan mandate</h1>
          <p className="pr-muted">
            Check that a payment really was approved by an enrolled approver, and
            countersigned by Pramaan. The check runs in your browser, so you do not
            have to trust Pramaan&rsquo;s servers or ours.
          </p>
        </div>

        <section className="pr-card pr-stack" aria-labelledby="input-heading">
          <h2 id="input-heading" className="pr-h2">
            The mandate
          </h2>

          <div className="pr-filters" role="group" aria-label="How to provide the mandate">
            <button
              type="button"
              className="pr-filter"
              aria-pressed={mode === 'id'}
              onClick={() => setMode('id')}
            >
              By mandate id
            </button>
            <button
              type="button"
              className="pr-filter"
              aria-pressed={mode === 'json'}
              onClick={() => setMode('json')}
            >
              Paste the JSON
            </button>
          </div>

          {mode === 'id' ? (
            <div className="pr-field">
              <label className="pr-label" htmlFor="mandate-id">
                Mandate id
              </label>
              <input
                id="mandate-id"
                className="pr-input"
                placeholder="pm_01JD2XGENUINE0001"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              <p className="pr-fineprint">
                The id printed on the evidence pack, or the one the console shows.
              </p>
            </div>
          ) : (
            <div className="pr-field">
              <label className="pr-label" htmlFor="mandate-json">
                Mandate JSON
              </label>
              <textarea
                id="mandate-json"
                className="pr-textarea"
                rows={10}
                placeholder='{"type":"pramaan.payment_mandate.v1", ...}'
                value={value}
                onChange={(event) => setValue(event.target.value)}
                spellCheck={false}
              />
              <p className="pr-fineprint">
                Pasting works offline for everything except Pramaan&rsquo;s public key,
                which is still fetched so the signature can be checked.
              </p>
            </div>
          )}

          <div className="pr-row">
            <button
              type="button"
              className="pr-button pr-button--primary"
              disabled={!canVerify}
              onClick={() => void run()}
              title={canVerify ? undefined : 'Enter a mandate id or paste a mandate first.'}
            >
              {busy ? 'Checking…' : 'Verify'}
            </button>
            {trimmed.length > 0 && !busy ? (
              <button
                type="button"
                className="pr-button"
                onClick={() => {
                  setValue('');
                  setOutcome(null);
                  setNotFound(null);
                  setFailure(null);
                }}
              >
                Clear
              </button>
            ) : null}
          </div>
        </section>

        {failure ? (
          <section className="pr-card pr-stack" role="alert">
            <h2 className="pr-h2">Could not check this</h2>
            <p>{failure}</p>
            <p className="pr-fineprint">
              This says nothing about whether the mandate is genuine. It only means the
              check did not run.
            </p>
          </section>
        ) : null}

        {notFound ? (
          <section className="pr-card pr-stack" role="alert">
            <div className="pr-row">
              <span className="pr-badge pr-badge--grey">Not found</span>
            </div>
            <h2 className="pr-h2">Pramaan has no mandate with that id</h2>
            <p className="pr-muted">
              Nothing is recorded for <code className="pr-mono">{notFound}</code>. Check the
              id, or paste the mandate itself instead.
            </p>
          </section>
        ) : null}

        {outcome ? <Result outcome={outcome} /> : null}
      </main>
    </div>
  );
}

const RESULT_PRESENTATION: Record<
  VerificationResult['outcome'],
  { tone: string; heading: string }
> = {
  valid: { tone: 'green', heading: 'This mandate is genuine' },
  invalid_signature: { tone: 'red', heading: 'This mandate does not check out' },
  expired: { tone: 'amber', heading: 'Genuine, but expired' },
  not_found: { tone: 'grey', heading: 'Not found' },
  cannot_check: { tone: 'grey', heading: 'Could not check this' },
};

function Result({ outcome }: { outcome: Outcome }): ReactNode {
  const { result, mandate } = outcome;
  const presentation = RESULT_PRESENTATION[result.outcome];
  const payee = mandate.payee;

  return (
    <section className="pr-card pr-stack" aria-labelledby="result-heading" role="status">
      <div className="pr-row">
        <span className={`pr-badge pr-badge--${presentation.tone}`}>
          {presentation.heading}
        </span>
        {mandate.countersignature?.kms_key_version ? (
          <span className="pr-fineprint">
            Key version {mandate.countersignature.kms_key_version}
          </span>
        ) : null}
      </div>

      <h2 id="result-heading" className="pr-h2">
        {presentation.heading}
      </h2>
      <p>{result.detail}</p>

      {result.outcome === 'valid' || result.outcome === 'expired' ? (
        <p className="pr-fineprint">
          Checked in your browser: ECDSA P-256 with SHA-256, over the exact bytes
          Pramaan countersigned.
        </p>
      ) : null}

      <h3 className="pr-h3">What was signed</h3>
      <dl className="pr-defs">
        <dt>Payee</dt>
        <dd>
          {payee?.name_at_bank ?? <span className="pr-muted">Not in this mandate</span>}
          {payee?.account_last4 ? (
            <span className="pr-fineprint">
              {maskAccount(payee.account_last4)} {payee.ifsc ? `· ${payee.ifsc}` : ''}
            </span>
          ) : null}
        </dd>

        <dt>Amount</dt>
        <dd>{mandate.amount_paise ? formatMoney(mandate.amount_paise) : <span className="pr-muted">Not in this mandate</span>}</dd>

        <dt>Purpose</dt>
        <dd>{mandate.purpose?.invoice ?? <span className="pr-muted">Not recorded</span>}</dd>

        <dt>Approved by</dt>
        <dd>
          {mandate.approval?.approver ?? <span className="pr-muted">Not in this mandate</span>}
          {mandate.approval?.signed_at ? (
            <span className="pr-fineprint">{formatIst(mandate.approval.signed_at)}</span>
          ) : null}
        </dd>

        <dt>Key held in</dt>
        <dd>
          {mandate.approval?.key_security_level ?? (
            <span className="pr-unverified">Couldn&rsquo;t verify</span>
          )}
        </dd>

        <dt>Expires</dt>
        <dd>
          {mandate.expires_at ? formatIst(mandate.expires_at) : <span className="pr-muted">No expiry recorded</span>}
        </dd>

        {result.canonicalSha256 ? (
          <>
            <dt>Hash of the signed bytes</dt>
            <dd>
              <code className="pr-mono">{result.canonicalSha256}</code>
              {mandate.summary_sha256 ? (
                <span className="pr-fineprint">
                  Mandate records summary_sha256 {mandate.summary_sha256}
                </span>
              ) : null}
            </dd>
          </>
        ) : null}
      </dl>

      {result.outcome === 'invalid_signature' ? (
        <p className="pr-fineprint">
          This means the details above are not the details Pramaan countersigned, or
          the signature was not made by Pramaan&rsquo;s key. It does not, by itself,
          tell you what happened or who did it.
        </p>
      ) : null}
    </section>
  );
}
