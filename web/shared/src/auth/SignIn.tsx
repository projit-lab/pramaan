/**
 * The sign-in screen. Google only; there is no sign-up page anywhere in Pramaan.
 */

import type { ReactNode } from 'react';
import { useAuth } from './AuthProvider';
import { PramaanMark } from '../components/PramaanMark';

export interface SignInProps {
  appName: string;
  appDescription?: string;
}

export function SignIn({ appName, appDescription }: SignInProps): ReactNode {
  const { signIn, error } = useAuth();

  return (
    <main className="pr-centred" aria-labelledby="signin-heading">
      <div className="pr-card pr-card--narrow">
        <PramaanMark />
        <h1 id="signin-heading" className="pr-h1">
          {appName}
        </h1>
        {appDescription ? <p className="pr-muted">{appDescription}</p> : null}

        <button type="button" className="pr-button pr-button--primary" onClick={() => void signIn()}>
          Sign in with Google
        </button>

        {error ? (
          <p className="pr-error" role="alert">
            {error}
          </p>
        ) : null}

        <p className="pr-fineprint">
          Access is granted by an administrator. There is no sign-up: ask your
          administrator to give your Google account a role.
        </p>
      </div>
    </main>
  );
}
