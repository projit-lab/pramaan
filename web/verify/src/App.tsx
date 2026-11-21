/**
 * The public mandate verifier.
 *
 * What a person can do here: paste a mandate id or a mandate JSON, and have their
 * own browser check the Cloud KMS countersignature and the approver signature
 * with WebCrypto.
 *
 * The approver's phone and Cloud KMS sign DIFFERENT bytes, and this page never
 * blurs the two:
 * - Payee, account, IFSC and amount are decoded from summary_b64 only.
 * - Decision, tier, device and signed time are decoded from mandate_b64 only.
 *
 * Nothing on this page is read from the outer JSON, because the outer JSON is the
 * part an attacker can rewrite. The verification itself lives in ./crypto.
 *
 * Deep imports from @pramaan/shared, never the package root: this page is public
 * and must not ship Firebase Auth to someone who only wants to check a mandate.
 */

import { Icon } from '@pramaan/shared/components/Icon';
import { AmountBlock } from '@pramaan/shared/components/Money';
import { DemoModeChip } from '@pramaan/shared/components/Badges';
import { PramaanLockup } from '@pramaan/shared/components/PramaanMark';
import { StateBand } from '@pramaan/shared/components/StateBand';
import { readEnv } from '@pramaan/shared/env';
import { type ReactNode, useCallback, useState } from 'react';
import { type MandateInput, type VerificationResult, verifyMandate } from './crypto';

type Mode = 'id' | 'json';

/**
 * The band colour and the words that go with each outcome. "Not found" and
 * "error" leave the band blue on purpose: neither is a verdict on the payment.
 */
const OUTCOME: Record<
  string,
  {
    band: 'released' | 'blocked' | 'expired' | null;
    chip: string;
    icon: string;
    heading: string;
  }
> = {
  valid: { band: 'released', chip: 'Valid', icon: 'verified', heading: 'This mandate is valid' },
  invalid_signature: {
    band: 'blocked',
    chip: 'Invalid',
    icon: 'gpp_bad',
    heading: 'This mandate did not verify',
  },
  expired: {
    band: 'expired',
    chip: 'Expired',
    icon: 'schedule',
    heading: 'This mandate has expired',
  },
  not_found: { band: null, chip: 'Not found', icon: 'help', heading: 'No mandate with that id' },
  error: { band: null, chip: 'Error', icon: 'error', heading: 'We could not finish the check' },
};

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
      (import.meta as unknown as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ??
      'http://localhost:4010';

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
          setResult({ status: 'not_found', message: `Mandate ${trimmed} not found.` });
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
      setResult({ status: 'error', message: (err as Error).message });
    } finally {
      setVerifying(false);
    }
  }, [mode, trimmed]);

  const outcome = result ? OUTCOME[result.status] : null;

  return (
    <div>
      <header className="pm-page pm-page--narrow" style={{ paddingBottom: 0 }}>
        <div className="pm-spread">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <PramaanLockup size={26} href="/" />
            {readEnv().demoMode ? <DemoModeChip /> : null}
          </div>
          <span className="pm-chip" style={{ cursor: 'default', userSelect: 'none' }}>
            <Icon name="public" size="sm" />
            Public verifier
          </span>
        </div>
      </header>

      <main className="pm-page pm-page--narrow pm-stack--lg">
        <StateBand
          status={outcome?.band ?? null}
          eyebrow={<span className="pm-label">Mandate check</span>}
        >
          <h1 className="pm-display">{outcome ? outcome.heading : 'Verify a Pramaan mandate'}</h1>
          <div className="pm-muted">
            Check that a payment really was approved by an enrolled approver phone, and
            countersigned by Pramaan&rsquo;s Cloud KMS HSM. The check runs in your own browser, so
            you do not have to trust Pramaan&rsquo;s servers, or ours.
          </div>
        </StateBand>

        <section className="pm-card pm-stack" aria-labelledby="input-heading">
          <h2 id="input-heading" className="pm-heading">
            The mandate
          </h2>

          <div className="pm-filters" role="group" aria-label="How to provide the mandate">
            <button
              type="button"
              className="pm-filter"
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
              className="pm-filter"
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
            <div className="pm-field">
              <label className="pm-field__label" htmlFor="mandate-id">
                Mandate id
              </label>
              <input
                id="mandate-id"
                className="pm-input pm-mono"
                placeholder="pm_01JD2XGENUINE0001"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              <p className="pm-hint">
                The id printed on the evidence pack, or the one the console shows.
              </p>
            </div>
          ) : (
            <div className="pm-field">
              <label className="pm-field__label" htmlFor="mandate-json">
                Mandate JSON
              </label>
              <textarea
                id="mandate-json"
                className="pm-textarea pm-mono"
                rows={10}
                placeholder="The mandate object, with its summary_b64 and mandate_b64 fields"
                value={value}
                onChange={(event) => setValue(event.target.value)}
                spellCheck={false}
              />
            </div>
          )}

          <div className="pm-row">
            <button
              type="button"
              className="pm-btn pm-btn--primary"
              disabled={!canVerify}
              onClick={() => void handleVerify()}
            >
              {verifying ? (
                <>
                  <span className="pm-spinner" aria-hidden="true" />
                  Verifying&hellip;
                </>
              ) : (
                <>
                  <Icon name="verified_user" size="sm" />
                  Verify
                </>
              )}
            </button>
            {trimmed.length > 0 ? (
              <button
                type="button"
                className="pm-btn pm-btn--text"
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
          <section className="pm-card pm-stack" aria-labelledby="how-heading">
            <h2 id="how-heading" className="pm-heading">
              What your browser will check
            </h2>
            <p className="pm-muted" style={{ margin: 0 }}>
              Five steps, and it fails closed: if any one of them cannot be completed, the answer
              is not &ldquo;valid&rdquo;.
            </p>
            <ol className="pm-stack" style={{ margin: 0, paddingLeft: '1.25rem' }}>
              <li>
                The Cloud KMS countersignature over <code className="pm-mono">mandate_b64</code>.
              </li>
              <li>
                The approver&rsquo;s device public key, taken only from inside{' '}
                <code className="pm-mono">mandate_b64</code>.
              </li>
              <li>
                The approver&rsquo;s signature over <code className="pm-mono">summary_b64</code>,
                using that device key.
              </li>
              <li>
                That <code className="pm-mono">SHA-256(summary_b64)</code> equals the{' '}
                <code className="pm-mono">summary_sha256</code> bound inside the mandate.
              </li>
              <li>
                The expiry recorded inside <code className="pm-mono">mandate_b64</code>.
              </li>
            </ol>
          </section>
        ) : null}

        {result?.status === 'valid' && result.details ? (
          <section className="pm-card pm-stack--lg" aria-labelledby="valid-heading">
            <div className="pm-success" style={{ padding: 'var(--space-6) var(--space-4)' }}>
              <div className="pm-success__circle">
                <Icon name="verified" fill />
              </div>
              <h2 id="valid-heading" className="pm-title">
                Both signatures verified
              </h2>
              <p className="pm-muted" style={{ margin: 0 }}>
                The approver&rsquo;s phone signed this payment, and Cloud KMS countersigned that
                signature. Your browser checked both.
              </p>
            </div>

            <div>
              <div className="pm-label">
                The payment that was signed &middot; from{' '}
                <code className="pm-mono">summary_b64</code>
              </div>
              <AmountBlock
                paise={result.details.amountPaise}
                payeeName={result.details.payeeName}
                payeeAccountLast4={result.details.accountLast4}
                payeeIfsc={result.details.ifsc}
              />
            </div>

            <div>
              <div className="pm-label">
                The decision &middot; from <code className="pm-mono">mandate_b64</code>
              </div>
              <dl className="pm-defs">
                <dt>Decision</dt>
                <dd>
                  <span className="pm-chip pm-chip--approved">
                    <Icon name="how_to_reg" size="sm" />
                    {result.details.decision}
                  </span>
                </dd>

                <dt>Tier</dt>
                <dd>Tier {result.details.tier}</dd>

                <dt>Approver device</dt>
                <dd>
                  <code className="pm-mono">{result.details.deviceId}</code>
                  {result.details.keySecurityLevel ? (
                    <span className="pm-hint">{result.details.keySecurityLevel}</span>
                  ) : null}
                </dd>

                <dt>Signed at</dt>
                <dd>{result.details.signedAt}</dd>
              </dl>
            </div>

            <p className="pm-hint" style={{ margin: 0 }}>
              Every payment field above comes from <code className="pm-mono">summary_b64</code> and
              every governance field from <code className="pm-mono">mandate_b64</code>. Values in
              the surrounding JSON are never displayed, because those are the ones an attacker
              could change.
            </p>
          </section>
        ) : null}

        {result && result.status !== 'valid' && outcome ? (
          <section className="pm-card pm-stack" aria-labelledby="outcome-heading">
            <div className="pm-spread">
              <h2 id="outcome-heading" className="pm-heading">
                {outcome.heading}
              </h2>
              <span
                className={`pm-chip ${
                  result.status === 'invalid_signature'
                    ? 'pm-chip--blocked'
                    : result.status === 'expired'
                      ? 'pm-chip--expired'
                      : ''
                }`.trim()}
              >
                <Icon name={outcome.icon} size="sm" />
                {outcome.chip}
              </span>
            </div>

            {result.status === 'invalid_signature' ? (
              <div className="pm-banner pm-banner--blocked">
                <Icon name="gpp_bad" fill />
                <div>
                  Do not act on this mandate. One of the checks failed: a signature did not match,
                  the summary hash differed from the one bound inside the countersigned mandate, or
                  the signing key was not the enrolled device&rsquo;s.
                </div>
              </div>
            ) : null}

            {result.status === 'expired' ? (
              <div className="pm-banner pm-banner--held">
                <Icon name="schedule" fill />
                <div>
                  The signatures on this mandate are genuine, but the validity window recorded
                  inside <code className="pm-mono">mandate_b64</code> has passed. A payment should
                  not be released on an expired mandate.
                </div>
              </div>
            ) : null}

            {result.status === 'not_found' || result.status === 'error' ? (
              <div className="pm-banner pm-banner--info">
                <Icon name="info" />
                <div>
                  {result.status === 'not_found'
                    ? 'This is not a statement about a payment. Nothing was checked, because there was nothing to check.'
                    : 'The check did not run to completion, so this is neither a pass nor a failure.'}
                </div>
              </div>
            ) : null}

            {result.message ? <p className="pm-hint pm-mono">{result.message}</p> : null}
          </section>
        ) : null}

        <p className="pm-hint" style={{ textAlign: 'center' }}>
          Pramaan never holds your money and cannot move it. This page only reads signatures.
        </p>
      </main>
    </div>
  );
}
