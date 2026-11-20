/**
 * "No access": signed in with a Google account that does not carry the role this
 * app needs. The only way forward is to sign out, or to ask an administrator for
 * the role.
 */

import type { ReactNode } from 'react';
import type { Role } from './AuthProvider';
import { PramaanMark } from '../components/PramaanMark';

const ROLE_LABELS: Record<Role, string> = {
  finance: 'finance team',
  clerk: 'accounts clerk',
};

export interface NoAccessProps {
  email: string | null;
  requiredRole: Role;
  grantedRole: Role | null;
  onSignOut: () => void | Promise<void>;
}

export function NoAccess({
  email,
  requiredRole,
  grantedRole,
  onSignOut,
}: NoAccessProps): ReactNode {
  return (
    <main className="pr-centred" aria-labelledby="noaccess-heading">
      <div className="pr-card pr-card--narrow">
        <PramaanMark />
        <h1 id="noaccess-heading" className="pr-h1">
          No access
        </h1>

        <p>
          {email ? <strong>{email}</strong> : 'This account'} does not have access to
          this app.
        </p>

        <p className="pr-muted">
          {grantedRole
            ? `It has the ${ROLE_LABELS[grantedRole]} role. This app needs the ${ROLE_LABELS[requiredRole]} role.`
            : `It has no role yet. This app needs the ${ROLE_LABELS[requiredRole]} role.`}
        </p>

        <button type="button" className="pr-button" onClick={() => void onSignOut()}>
          Sign out
        </button>

        <p className="pr-fineprint">
          Ask an administrator to grant your account the {ROLE_LABELS[requiredRole]}{' '}
          role, then sign in again.
        </p>
      </div>
    </main>
  );
}
