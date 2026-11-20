/**
 * One Firebase app per browser tab, wired at the emulators when
 * VITE_USE_EMULATORS=true.
 *
 * Everything is lazy and memoised: an app that never touches Firestore (the
 * public verifier page, for one) never opens a connection to it.
 */

import { type FirebaseApp, getApps, initializeApp } from 'firebase/app';
import { type Auth, connectAuthEmulator, getAuth } from 'firebase/auth';
import { type Firestore, connectFirestoreEmulator, getFirestore } from 'firebase/firestore';
import { type PramaanEnv, readEnv } from '../env';

let cachedApp: FirebaseApp | null = null;
let cachedAuth: Auth | null = null;
let cachedFirestore: Firestore | null = null;
let cachedEnv: PramaanEnv | null = null;

/** The environment this app was initialised with. */
export function env(): PramaanEnv {
  if (!cachedEnv) cachedEnv = readEnv();
  return cachedEnv;
}

export function firebaseApp(): FirebaseApp {
  if (cachedApp) return cachedApp;
  const existing = getApps();
  cachedApp = existing[0] ?? initializeApp(env().firebase);
  return cachedApp;
}

export function firebaseAuth(): Auth {
  if (cachedAuth) return cachedAuth;
  const auth = getAuth(firebaseApp());
  if (env().useEmulators) {
    // disableWarnings keeps the emulator banner out of a projected demo.
    connectAuthEmulator(auth, env().emulator.authUrl, { disableWarnings: true });
  }
  cachedAuth = auth;
  return auth;
}

export function firestore(): Firestore {
  if (cachedFirestore) return cachedFirestore;
  const db = getFirestore(firebaseApp());
  if (env().useEmulators) {
    connectFirestoreEmulator(db, env().emulator.firestoreHost, env().emulator.firestorePort);
  }
  cachedFirestore = db;
  return db;
}

/**
 * Forgets the memoised handles. Tests only: a browser never needs this, and
 * calling it mid-session would leave live listeners pointing at a dead app.
 */
export function resetFirebaseForTests(): void {
  cachedApp = null;
  cachedAuth = null;
  cachedFirestore = null;
  cachedEnv = null;
}
