/**
 * The role gate every signed-in screen sits behind.
 *
 *   signed out            -> the sign-in screen
 *   signed in, wrong role -> "No access", with Sign out
 *   signed in, right role -> the app
 *
 * The console requires `finance`; the mock ERP requires `clerk`. The console has
 * no Approve button at any role, by design: approvals happen on a phone.
 */

import type { ReactNode } from 'react';
import { type Role, useAuth } from './AuthProvider';
import { NoAccess } from './NoAccess';
import { SignIn } from './SignIn';
import { LoadingState } from '../components/States';

export interface RoleGateProps {
  /** The role this app needs. */
  requires: Role;
  /** What this app is called on the sign-in screen. */
  appName: string;
  /** One line about what the app is for, on the sign-in screen. */
  appDescription?: string;
  children: ReactNode;
}

export function RoleGate({
  requires,
  appName,
  appDescription,
  children,
}: RoleGateProps): ReactNode {
  const { status, role, user, signOut } = useAuth();

  if (status === 'loading') {
    return <LoadingState label="Checking your sign-in" />;
  }

  if (status === 'signed-out') {
    return <SignIn appName={appName} appDescription={appDescription} />;
  }

  if (role !== requires) {
    return (
      <NoAccess
        email={user?.email ?? null}
        requiredRole={requires}
        grantedRole={role}
        onSignOut={signOut}
      />
    );
  }

  return <>{children}</>;
}
