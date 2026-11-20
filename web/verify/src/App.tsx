/**
 * The public mandate verifier, M0 shell.
 *
 * What a person can do here: paste a mandate id or a mandate JSON, and have their
 * own browser check the Cloud KMS countersignature with WebCrypto. The point is
 * that it does not take Pramaan's word for anything: a breach of our servers
 * cannot forge a countersignature that this page would accept.
 *
 * M0 builds the shell, the input, the disabled-until-valid Verify button and all
 * four result states. The cryptographic check itself lands in M2 and is honestly
 * marked as not yet running, because a verifier that said "valid" without
 * checking would be the single most dishonest screen we could ship.
 *
 * Two things M2 needs, both already flagged to Prajit:
 *   - GET /mandates/{id} must return canonical_b64, the exact bytes that were
 *     countersigned, so this page hashes those bytes instead of re-implementing
 *     canonicalisation in TypeScript and drifting from Kotlin and Python.
 *   - Cloud KMS returns a DER signature; WebCrypto wants raw r||s, 64 bytes. The
 *     conversion happens here.
 */

// Deep import, not the @pramaan/shared barrel: the barrel re-exports the Firebase
// modules, whose side effects defeat tree-shaking, and this public page must not
// ship a Firebase SDK it never uses.
import { PramaanMark } from '@pramaan/shared/components/PramaanMark';
import { type ReactNode, useState } from 'react';

type Mode = 'id' | 'json';

/**
 * The console links here as /?mandate=pm_... so an auditor lands with the id
 * already filled in. Read once, at first render.
 */
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

  const trimmed = value.trim();
  const canVerify = trimmed.length > 0;

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
            </div>
          )}

          <div className="pr-row">
            <button
              type="button"
              className="pr-button pr-button--primary"
              disabled={!canVerify}
              title={
                canVerify
                  ? 'The signature check arrives in M2.'
                  : 'Enter a mandate id or paste a mandate first.'
              }
            >
              Verify
            </button>
            {canVerify ? (
              <button type="button" className="pr-button" onClick={() => setValue('')}>
                Clear
              </button>
            ) : null}
          </div>
        </section>

        <section className="pr-card pr-stack" aria-labelledby="pending-heading">
          <h2 id="pending-heading" className="pr-h2">
            Not verifying yet
          </h2>
          <p>
            This page cannot check a signature until Pramaan&rsquo;s mandate service is
            live. Rather than show a result it has not computed, it shows nothing.
          </p>
          <p className="pr-fineprint">
            When it does run, it will fetch the mandate and the Cloud KMS public key,
            convert the DER signature to the raw form WebCrypto expects, and verify
            ECDSA P-256 with SHA-256 over the exact bytes that were countersigned. It
            will then say one of four things: valid, invalid signature, expired, or not
            found &mdash; and nothing else.
          </p>
        </section>
      </main>
    </div>
  );
}
