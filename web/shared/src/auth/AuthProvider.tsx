/**
 * Google sign-in and the role claim.
 *
 * There is no sign-up page anywhere in Pramaan. Everyone signs in with Google; an
 * admin grants a role with web/tools/grant-role.mjs, which sets the Firebase Auth
 * custom claim `role`. A signed-in user with the wrong role, or no role, sees the
 * "No access" page.
 */

import {
  GoogleAuthProvider,
  type User,
  onIdTokenChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
} from 'firebase/auth';
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { firebaseAuth } from '../firebase/app';

/** The roles the web lane knows. `finance` reads the console, `clerk` the ERP. */
export type Role = 'finance' | 'clerk';

export type AuthStatus = 'loading' | 'signed-out' | 'signed-in';

export interface AuthState {
  status: AuthStatus;
  user: User | null;
  /** The `role` custom claim, or null when the account has none. */
  role: Role | null;
  /** Set when sign-in itself failed, so a screen can say why. */
  error: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  /** A fresh ID token, for the API client. Null when signed out. */
  idToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthState | null>(null);

function readRole(claims: Record<string, unknown>): Role | null {
  const value = claims['role'];
  return value === 'finance' || value === 'clerk' ? value : null;
}

export function AuthProvider({ children }: { children: ReactNode }): ReactNode {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // onIdTokenChanged rather than onAuthStateChanged, so a role granted while the
    // tab is open takes effect on the next token refresh instead of needing a
    // reload.
    const unsubscribe = onIdTokenChanged(firebaseAuth(), async (nextUser) => {
      if (!nextUser) {
        setUser(null);
        setRole(null);
        setStatus('signed-out');
        return;
      }
      try {
        const result = await nextUser.getIdTokenResult();
        setRole(readRole(result.claims as Record<string, unknown>));
      } catch {
        // A token we cannot read is a user with no role, never a user with one.
        setRole(null);
      }
      setUser(nextUser);
      setStatus('signed-in');
    });
    return unsubscribe;
  }, []);

  const signIn = useCallback(async () => {
    setError(null);
    try {
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: 'select_account' });
      await signInWithPopup(firebaseAuth(), provider);
    } catch (caught) {
      const code = caught instanceof Error ? caught.message : String(caught);
      if (code.includes('popup-closed-by-user') || code.includes('cancelled-popup-request')) {
        // The person changed their mind. Not an error worth showing.
        return;
      }
      setError('Could not sign in with Google. Please try again.');
    }
  }, []);

  const signOut = useCallback(async () => {
    setError(null);
    await firebaseSignOut(firebaseAuth());
  }, []);

  const idToken = useCallback(async () => {
    const current = firebaseAuth().currentUser;
    if (!current) return null;
    try {
      return await current.getIdToken();
    } catch {
      return null;
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({ status, user, role, error, signIn, signOut, idToken }),
    [status, user, role, error, signIn, signOut, idToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider.');
  }
  return context;
}
