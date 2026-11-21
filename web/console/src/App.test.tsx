import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import * as sharedModule from '@pramaan/shared';
import { App } from './App';

vi.mock('@pramaan/shared', async (importOriginal) => {
  const actual = await importOriginal<typeof sharedModule>();
  return {
    ...actual,
    useAuth: () => ({
      status: 'signed-in',
      user: { email: 'cfo@acme.example', uid: 'cfo' },
      role: 'finance',
      signOut: vi.fn(),
    }),
    useLiveCollection: () => ({
      status: 'ready',
      data: [
        {
          id: 'pi_01JD2XBOSSSCAM0001',
          intentId: 'pi_01JD2XBOSSSCAM0001',
          status: 'held',
          tier: 2,
          amountPaise: '465000000',
          currency: 'INR',
          payeeNameAtBank: 'Global Trade Solutions',
          payeeAccountLast4: '9032',
          payeeIfsc: 'WXYZ0004411',
          instructionChannel: 'portal',
          initiator: { type: 'human', id: 'clerk@acme.example' },
          reasons: [],
          createdAt: { seconds: 1732147200, nanoseconds: 0 },
        },
      ],
      error: null,
    }),
  };
});

describe('Console App', () => {
  it('renders Demo mode chip when demoMode is true', () => {
    vi.spyOn(sharedModule, 'readEnv').mockReturnValue({
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

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('demo-mode-chip')).toHaveTextContent('Demo mode');
    expect(screen.getByText('Global Trade Solutions')).toBeInTheDocument();
  });

  it('hides Demo mode chip when demoMode is false', () => {
    vi.spyOn(sharedModule, 'readEnv').mockReturnValue({
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

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId('demo-mode-chip')).not.toBeInTheDocument();
  });
});
