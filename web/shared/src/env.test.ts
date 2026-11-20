import { describe, expect, it } from 'vitest';
import { missingFirebaseConfig, readEnv } from './env';

describe('readEnv', () => {
  it('defaults to the local development setup, so a fresh clone needs no secrets', () => {
    const env = readEnv({
      VITE_USE_EMULATORS: undefined,
      VITE_API_BASE: undefined,
      VITE_DEMO_MODE: undefined,
      VITE_PAYOUTS_SOURCE: undefined,
      VITE_FIREBASE_PROJECT_ID: undefined,
    });
    expect(env.useEmulators).toBe(true);
    expect(env.apiBase).toBe('http://127.0.0.1:4010');
    expect(env.payoutsSource).toBe('api');
    expect(env.firebase.projectId).toBe('pramaan-dev-515306');
  });

  it('reads booleans from the strings an env file actually contains', () => {
    expect(readEnv({ VITE_USE_EMULATORS: 'false' }).useEmulators).toBe(false);
    expect(readEnv({ VITE_USE_EMULATORS: 'TRUE' }).useEmulators).toBe(true);
    expect(readEnv({ VITE_USE_EMULATORS: '0' }).useEmulators).toBe(false);
    expect(readEnv({ VITE_USE_EMULATORS: '1' }).useEmulators).toBe(true);
  });

  it('strips a trailing slash from the API base, so no URL ends up doubled', () => {
    expect(readEnv({ VITE_API_BASE: 'https://api.example.com/v1/' }).apiBase).toBe(
      'https://api.example.com/v1',
    );
  });

  it('only accepts the two payout sources it knows', () => {
    expect(readEnv({ VITE_PAYOUTS_SOURCE: 'firestore' }).payoutsSource).toBe('firestore');
    expect(readEnv({ VITE_PAYOUTS_SOURCE: 'something-else' }).payoutsSource).toBe('api');
  });

  it('turns demo mode off by default once emulators are off', () => {
    expect(readEnv({ VITE_USE_EMULATORS: 'false', VITE_DEMO_MODE: undefined }).demoMode).toBe(false);
    expect(readEnv({ VITE_USE_EMULATORS: 'false', VITE_DEMO_MODE: 'true' }).demoMode).toBe(true);
  });
});

describe('missingFirebaseConfig', () => {
  it('asks for nothing while on emulators', () => {
    expect(missingFirebaseConfig(readEnv({ VITE_USE_EMULATORS: 'true' }))).toEqual([]);
  });

  it('names every value a real project still needs', () => {
    const missing = missingFirebaseConfig(
      readEnv({
        VITE_USE_EMULATORS: 'false',
        VITE_FIREBASE_API_KEY: '',
        VITE_FIREBASE_AUTH_DOMAIN: '',
        VITE_FIREBASE_PROJECT_ID: 'pramaan-dev-515306',
        VITE_FIREBASE_APP_ID: '',
      }),
    );
    expect(missing).toEqual([
      'VITE_FIREBASE_API_KEY',
      'VITE_FIREBASE_AUTH_DOMAIN',
      'VITE_FIREBASE_APP_ID',
    ]);
  });
});
