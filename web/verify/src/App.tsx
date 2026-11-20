/**
 * The public mandate verifier.
 *
 * What a person can do here: paste a mandate id or a mandate JSON, and have their
 * own browser check the Cloud KMS countersignature and approver signature with WebCrypto.
 *
 * All payment details (payee, account, IFSC, amount) are parsed and displayed
 * exclusively from the decoded canonical_b64 bytes, never from surrounding JSON.
 */

import { Money } from '@pramaan/shared/components/Money';
import { PramaanMark } from '@pramaan/shared/components/PramaanMark';
import { formatIfsc, maskAccount } from '@pramaan/shared/format/account';
import { type ReactNode, useCallback, useState } from 'react';
import {
  type MandateInput,
  type VerificationResult,
  verifyMandate,
} from './crypto';

type Mode = 'id' | 'json';

export function App(): ReactNode {
  const [mode, setMode] = useState<Mode>('id');
  const [value, setValue] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [result, setResult] = useState<VerificationResult | null>(null);

  const trimmed = value.trim();
  const canVerify = trimmed.length > 0 && !verifying;

  const handleVerify = useCallback(async () => {
    if (!trimmed) return;
    setVerifying(true);
    setResult(null);

    const apiBase =
      (import.meta as unknown as { env?: { VITE_API_BASE?: string } }).env
        ?.VITE_API_BASE ?? 'http://localhost:4010';

    const fetchKmsKey = async (): Promise<string> => {
      const res = await fetch(`${apiBase}/keys/countersign`);
      if (!res.ok) {
        throw new Error(`Failed to fetch countersigning key: ${res.statusText}`);
      }
      const data = (await res.json()) as { pem?: string };
      if (!data.pem) {
        throw new Error('Countersigning key response did not contain pem');
      }
      return data.pem;
    };

    try {
      let mandate: MandateInput;
      if (mode === 'id') {
        const res = await fetch(`${apiBase}/mandates/${encodeURIComponent(trimmed)}`);
        if (res.status === 404) {
          setResult({
            status: 'not_found',
            message: `Mandate ${trimmed} not found.`,
          });
          setVerifying(false);
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to fetch mandate: ${res.statusText}`);
        }
        mandate = (await res.json()) as MandateInput;
      } else {
        mandate = JSON.parse(trimmed) as MandateInput;
      }

      const res = await verifyMandate(mandate, fetchKmsKey);
      setResult(res);
    } catch (err) {
      setResult({
        status: 'error',
        message: (err as Error).message,
      });
    } finally {
      setVerifying(false);
    }
  }, [mode, trimmed]);

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
              onClick={() => {
                setMode('id');
                setResult(null);
              }}
            >
              By mandate id
            </button>
            <button
              type="button"
              className="pr-filter"
              aria-pressed={mode === 'json'}
              onClick={() => {
                setMode('json');
                setResult(null);
              }}
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
                placeholder='{"type":"pramaan.payment_mandate.v1", "canonical_b64":"...", ...}'
                value={value}
                onChange={(event) => setValue(event.target.value)}
                spellCheck={false}
              />
            </div>
          )}

          <div className="pr-row">
            <button
              type="button"
              className="pr-button pr-button--primary"
              disabled={!canVerify}
              onClick={() => void handleVerify()}
            >
              {verifying ? 'Verifying...' : 'Verify'}
            </button>
            {trimmed.length > 0 ? (
              <button
                type="button"
                className="pr-button"
                onClick={() => {
                  setValue('');
                  setResult(null);
                }}
              >
                Clear
              </button>
            ) : null}
          </div>
        </section>

        {result === null ? (
          <section className="pr-card pr-stack" aria-labelledby="pending-heading">
            <h2 id="pending-heading" className="pr-h2">
              How verification works
            </h2>
            <p>
              When you click Verify, your browser decodes the canonical mandate bytes,
              verifies the approver&rsquo;s hardware key signature and Cloud KMS countersignature
              over those bytes using WebCrypto, and parses payment details directly
              from the signed bytes.
            </p>
            <p className="pr-fineprint">
              It will say one of four things: valid, invalid signature, expired, or not
              found &mdash; and nothing else.
            </p>
          </section>
        ) : null}

        {result?.status === 'valid' && result.details ? (
          <section className="pr-card pr-stack pr-card--success" aria-labelledby="valid-heading">
            <div className="pr-spread">
              <h2 id="valid-heading" className="pr-h2">
                Mandate Valid
              </h2>
              <span className="pr-badge pr-badge--green">Valid</span>
            </div>

            <p className="pr-fineprint">
              Cryptographic proof verified with WebCrypto. Both the approver hardware signature
              and Cloud KMS countersignature match the exact canonical mandate bytes.
            </p>

            <table className="pr-table">
              <caption className="pr-visually-hidden">
                Payment details parsed from decoded canonical mandate bytes
              </caption>
              <thead>
                <tr>
                  <th scope="col">Payee</th>
                  <th scope="col">Amount</th>
                  <th scope="col">Account</th>
                  <th scope="col">IFSC</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{result.details.payeeName}</td>
                  <td>
                    <Money paise={result.details.amountPaise} withWords />
                  </td>
                  <td>{maskAccount(result.details.accountLast4)}</td>
                  <td>{formatIfsc(result.details.ifsc)}</td>
                </tr>
              </tbody>
            </table>

            <p className="pr-fineprint" style={{ color: 'var(--pr-color-text-muted)' }}>
              Note: All payment details above are parsed directly from the verified
              <code className="pr-mono"> canonical_b64</code> bytes, never from surrounding JSON.
            </p>
          </section>
        ) : null}

        {result?.status === 'invalid_signature' ? (
          <section className="pr-card pr-stack pr-card--error" aria-labelledby="invalid-heading">
            <div className="pr-spread">
              <h2 id="invalid-heading" className="pr-h2">
                Invalid Signature
              </h2>
              <span className="pr-badge pr-badge--red">Invalid</span>
            </div>
            <p>
              The cryptographic signature does not match the canonical mandate bytes.
              The mandate or signature may have been altered in transit.
            </p>
            {result.message ? (
              <p className="pr-fineprint pr-error">{result.message}</p>
            ) : null}
          </section>
        ) : null}

        {result?.status === 'expired' ? (
          <section className="pr-card pr-stack" aria-labelledby="expired-heading">
            <div className="pr-spread">
              <h2 id="expired-heading" className="pr-h2">
                Mandate Expired
              </h2>
              <span className="pr-badge pr-badge--amber">Expired</span>
            </div>
            <p>
              This mandate was genuine, but its validity window has passed.
            </p>
            {result.message ? (
              <p className="pr-fineprint">{result.message}</p>
            ) : null}
          </section>
        ) : null}

        {result?.status === 'not_found' ? (
          <section className="pr-card pr-stack" aria-labelledby="notfound-heading">
            <div className="pr-spread">
              <h2 id="notfound-heading" className="pr-h2">
                Mandate Not Found
              </h2>
              <span className="pr-badge pr-badge--grey">Not found</span>
            </div>
            <p>
              {result.message ?? 'No mandate with that identifier was found.'}
            </p>
          </section>
        ) : null}

        {result?.status === 'error' ? (
          <section className="pr-card pr-stack" aria-labelledby="error-heading">
            <div className="pr-spread">
              <h2 id="error-heading" className="pr-h2">
                Verification Error
              </h2>
              <span className="pr-badge pr-badge--red">Error</span>
            </div>
            <p>{result.message ?? 'An unexpected error occurred during verification.'}</p>
          </section>
        ) : null}
      </main>
    </div>
  );
}
