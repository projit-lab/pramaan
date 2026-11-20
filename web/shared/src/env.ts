/**
 * Every environment value the web lane reads, in one place, so no screen reaches
 * into import.meta.env directly and nothing is read by a name that is only
 * spelled correctly in one file.
 *
 * See web/.env.example for what each value is and where to get it.
 */

export type PayoutsSource = 'api' | 'firestore';

export interface FirebaseWebConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
}

export interface PramaanEnv {
  /** Route Firebase Auth and Firestore at the local emulators. */
  useEmulators: boolean;
  /** Base URL of the API. The Prism mock in development, Cloud Run later. */
  apiBase: string;
  /** Show the demo control panel and presenter view. Dev and demo projects only. */
  demoMode: boolean;
  /** Where the public sandbox bank page reads payouts from. */
  payoutsSource: PayoutsSource;
  /**
   * Base URL of the public mandate verifier, so the console can link a mandate
   * out to it. A separate hosting site, hence a separate value.
   */
  verifyBase: string;
  firebase: FirebaseWebConfig;
  emulator: {
    authUrl: string;
    firestoreHost: string;
    firestorePort: number;
  };
}

type RawEnv = Record<string, string | boolean | undefined>;

function readRaw(): RawEnv {
  // import.meta.env is injected by Vite in apps and by vitest in tests.
  try {
    return (import.meta.env ?? {}) as RawEnv;
  } catch {
    return {};
  }
}

function text(raw: RawEnv, key: string, fallback = ''): string {
  const value = raw[key];
  if (typeof value === 'string' && value.trim() !== '') return value.trim();
  return fallback;
}

function flag(raw: RawEnv, key: string, fallback: boolean): boolean {
  const value = raw[key];
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    const normalised = value.trim().toLowerCase();
    if (normalised === 'true' || normalised === '1') return true;
    if (normalised === 'false' || normalised === '0') return false;
  }
  return fallback;
}

function whole(raw: RawEnv, key: string, fallback: number): number {
  const parsed = Number.parseInt(text(raw, key), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/**
 * Reads the environment. Defaults are the local development setup, so a fresh
 * clone runs on emulators and the mock server with no Firebase project and no
 * secrets at all.
 */
export function readEnv(overrides: RawEnv = {}): PramaanEnv {
  const raw = { ...readRaw(), ...overrides };
  const useEmulators = flag(raw, 'VITE_USE_EMULATORS', true);

  const payoutsRaw = text(raw, 'VITE_PAYOUTS_SOURCE', 'api');
  const payoutsSource: PayoutsSource = payoutsRaw === 'firestore' ? 'firestore' : 'api';

  return {
    useEmulators,
    apiBase: text(raw, 'VITE_API_BASE', 'http://127.0.0.1:4010').replace(/\/+$/, ''),
    demoMode: flag(raw, 'VITE_DEMO_MODE', useEmulators),
    payoutsSource,
    verifyBase: text(raw, 'VITE_VERIFY_BASE', 'http://localhost:5175').replace(/\/+$/, ''),
    firebase: {
      // On emulators a placeholder key is enough: the Auth emulator does not check it.
      apiKey: text(raw, 'VITE_FIREBASE_API_KEY', useEmulators ? 'emulator-api-key' : ''),
      authDomain: text(raw, 'VITE_FIREBASE_AUTH_DOMAIN', useEmulators ? 'localhost' : ''),
      projectId: text(raw, 'VITE_FIREBASE_PROJECT_ID', 'pramaan-dev'),
      storageBucket: text(raw, 'VITE_FIREBASE_STORAGE_BUCKET'),
      messagingSenderId: text(raw, 'VITE_FIREBASE_MESSAGING_SENDER_ID'),
      appId: text(raw, 'VITE_FIREBASE_APP_ID'),
    },
    emulator: {
      authUrl: text(raw, 'VITE_EMULATOR_AUTH_URL', 'http://127.0.0.1:9099'),
      firestoreHost: text(raw, 'VITE_EMULATOR_FIRESTORE_HOST', '127.0.0.1'),
      firestorePort: whole(raw, 'VITE_EMULATOR_FIRESTORE_PORT', 8080),
    },
  };
}

/**
 * Lists what is missing for a real (non-emulator) Firebase project, so an app can
 * say so on screen instead of failing with an opaque Firebase error.
 */
export function missingFirebaseConfig(env: PramaanEnv): string[] {
  if (env.useEmulators) return [];
  const required: Array<[keyof FirebaseWebConfig, string]> = [
    ['apiKey', 'VITE_FIREBASE_API_KEY'],
    ['authDomain', 'VITE_FIREBASE_AUTH_DOMAIN'],
    ['projectId', 'VITE_FIREBASE_PROJECT_ID'],
    ['appId', 'VITE_FIREBASE_APP_ID'],
  ];
  return required.filter(([key]) => env.firebase[key] === '').map(([, name]) => name);
}
