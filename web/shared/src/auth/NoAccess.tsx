/**
 * "No access": signed in with a Google account that does not carry the role
 * this app needs. The only way forward is to sign out, or to ask an
 * administrator for the role.
 */

import type { ReactNode } from 'react';
import type { Role } from './AuthProvider';
import { Icon } from '../components/Icon';
import { PramaanLockup } from '../components/PramaanMark';

const ROLE_LABELS: Record<Role, string> = {
  finance: 'finance',
  clerk: 'clerk',
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
    <main className="pm-centred" aria-labelledby="noaccess-heading">
      <div className="pm-stack" style={{ maxWidth: 440, width: '100%' }}>
        <PramaanLockup size={32} />

        <div className="pm-card pm-empty">
          <span className="pm-empty__art">
            <Icon name="lock" />
          </span>
          <div id="noaccess-heading" className="pm-heading" style={{ color: 'var(--ink)' }}>
            You don&rsquo;t have access yet
          </div>
          <div>
            Ask your admin to add {email ? <strong>{email}</strong> : 'this account'} as{' '}
            {ROLE_LABELS[requiredRole]}.
            {grantedRole ? ` It currently has the ${ROLE_LABELS[grantedRole]} role.` : ''}
          </div>
          <div style={{ marginTop: 'var(--space-4)' }}>
            <button type="button" className="pm-btn pm-btn--outlined" onClick={() => void onSignOut()}>
              Sign out
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
