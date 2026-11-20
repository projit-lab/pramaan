/**
 * The sign-in screen. Google only; there is no sign-up page anywhere in
 * Pramaan, because access is granted by an administrator.
 */

import type { ReactNode } from 'react';
import { useAuth } from './AuthProvider';
import { Icon } from '../components/Icon';
import { PramaanLockup } from '../components/PramaanMark';

export interface SignInProps {
  appName: string;
  appDescription?: string;
}

export function SignIn({ appName, appDescription }: SignInProps): ReactNode {
  const { signIn, error } = useAuth();

  return (
    <main className="pm-centred" aria-labelledby="signin-heading">
      <div className="pm-stack" style={{ maxWidth: 420, width: '100%' }}>
        <div className="pm-band">
          <div className="pm-band__inner">
            <PramaanLockup size={36} />
            <h1 id="signin-heading" className="pm-display" style={{ fontSize: 30, lineHeight: '36px' }}>
              {appName}
            </h1>
            {appDescription ? <div className="pm-muted">{appDescription}</div> : null}
          </div>
        </div>

        <div className="pm-card pm-stack">
          <button
            type="button"
            className="pm-btn pm-btn--primary pm-btn--block"
            onClick={() => void signIn()}
          >
            Sign in with Google
          </button>

          {error ? (
            <div className="pm-banner pm-banner--blocked" role="alert">
              <Icon name="error" />
              <div>{error}</div>
            </div>
          ) : null}

          <div className="pm-hint">
            Access is granted by an administrator. There is no sign-up: ask your
            administrator to give your Google account a role.
          </div>
        </div>
      </div>
    </main>
  );
}
