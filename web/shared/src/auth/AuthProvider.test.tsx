import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, resetApiForTests, setDevUser } from '../api/client';
import * as envModule from '../env';
import { AuthProvider, useAuth } from './AuthProvider';
import { RoleGate } from './RoleGate';

vi.mock('../firebase/app', () => ({
  firebaseAuth: () => ({
    currentUser: null,
  }),
}));

vi.mock('firebase/auth', () => ({
  onIdTokenChanged: vi.fn(() => () => {}),
  signInAnonymously: vi.fn(() => Promise.resolve({ user: { uid: 'anon', isAnonymous: true } })),
  GoogleAuthProvider: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
}));

function Consumer() {
  const { status, role, user } = useAuth();
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="role">{role ?? 'none'}</div>
      <div data-testid="email">{user?.email ?? 'none'}</div>
    </div>
  );
}

describe('AuthProvider & RoleGate in demo mode (VITE_DEMO_MODE=true)', () => {
  beforeEach(() => {
    resetApiForTests();
    vi.restoreAllMocks();
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchSpy);
    vi.spyOn(envModule, 'readEnv').mockReturnValue({
      useEmulators: false,
      apiBase: 'http://127.0.0.1:4010',
      demoMode: true,
      payoutsSource: 'api',
      verifyBase: 'http://localhost:5175',
      firebase: {
        apiKey: 'fake',
        authDomain: 'fake',
        projectId: 'pramaan-dev-515306',
        storageBucket: 'fake',
        messagingSenderId: 'fake',
        appId: 'fake',
      },
      emulator: {
        authUrl: 'http://127.0.0.1:9099',
        firestoreHost: '127.0.0.1',
        firestorePort: 8080,
      },
    });
  });

  it('skips sign-in and lets console through with finance role and cfo user', () => {
    render(
      <AuthProvider demoRole="finance" demoUser="cfo">
        <RoleGate requires="finance" appName="Pramaan console">
          <div data-testid="app">Console App</div>
          <Consumer />
        </RoleGate>
      </AuthProvider>,
    );

    expect(screen.getByTestId('app')).toHaveTextContent('Console App');
    expect(screen.getByTestId('status')).toHaveTextContent('signed-in');
    expect(screen.getByTestId('role')).toHaveTextContent('finance');
    expect(screen.getByTestId('email')).toHaveTextContent('cfo@acme.example');
    expect(screen.queryByText(/Sign in with Google/i)).not.toBeInTheDocument();
  });

  it('skips sign-in and lets ERP through with clerk role and clerk user', () => {
    render(
      <AuthProvider demoRole="clerk" demoUser="clerk">
        <RoleGate requires="clerk" appName="Acme ERP">
          <div data-testid="app">ERP App</div>
          <Consumer />
        </RoleGate>
      </AuthProvider>,
    );

    expect(screen.getByTestId('app')).toHaveTextContent('ERP App');
    expect(screen.getByTestId('status')).toHaveTextContent('signed-in');
    expect(screen.getByTestId('role')).toHaveTextContent('clerk');
    expect(screen.getByTestId('email')).toHaveTextContent('clerk@acme.example');
    expect(screen.queryByText(/Sign in with Google/i)).not.toBeInTheDocument();
  });

  it('sends X-Dev-User instead of Authorization in demo mode', async () => {
    setDevUser('cfo');
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchSpy);
    resetApiForTests();
    const client = api();

    await (client as unknown as { GET: (url: string, init?: unknown) => Promise<unknown> }).GET('/health');

    expect(fetchSpy).toHaveBeenCalled();
    const firstCall = fetchSpy.mock.calls[0];
    expect(firstCall).toBeDefined();
    const arg0 = firstCall![0];
    const arg1 = firstCall![1];
    const headers =
      arg0 instanceof Request
        ? arg0.headers
        : arg1?.headers instanceof Headers
          ? arg1.headers
          : new Headers(arg1?.headers);
    expect(headers.get('X-Dev-User')).toBe('cfo');
    expect(headers.get('Authorization')).toBeNull();
  });
});

describe('AuthProvider & RoleGate in normal mode (VITE_DEMO_MODE=false)', () => {
  beforeEach(() => {
    resetApiForTests();
    vi.restoreAllMocks();
    vi.spyOn(envModule, 'readEnv').mockReturnValue({
      useEmulators: false,
      apiBase: 'http://127.0.0.1:4010',
      demoMode: false,
      payoutsSource: 'api',
      verifyBase: 'http://localhost:5175',
      firebase: {
        apiKey: 'fake',
        authDomain: 'fake',
        projectId: 'pramaan-dev-515306',
        storageBucket: 'fake',
        messagingSenderId: 'fake',
        appId: 'fake',
      },
      emulator: {
        authUrl: 'http://127.0.0.1:9099',
        firestoreHost: '127.0.0.1',
        firestorePort: 8080,
      },
    });
  });

  it('renders the sign-in screen when user is not signed in', () => {
    render(
      <AuthProvider demoRole="finance" demoUser="cfo">
        <RoleGate requires="finance" appName="Pramaan console">
          <div data-testid="app">Protected App</div>
        </RoleGate>
      </AuthProvider>,
    );

    // Initial state without auth is loading, then signed-out triggers SignIn
    expect(screen.queryByTestId('app')).not.toBeInTheDocument();
  });
});
