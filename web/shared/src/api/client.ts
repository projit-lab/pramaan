/**
 * The typed API client for signed-in pages.
 *
 * Generated from contracts/openapi.yaml with openapi-typescript, called with
 * openapi-fetch. Screens call the API only through this client; there are no
 * hand-written URLs anywhere in the web lane, which is why `paths` is imported
 * from the generated file and the base URL comes from VITE_API_BASE.
 *
 * This module imports Firebase Auth, so pages with nobody signed in should deep
 * import `@pramaan/shared/api/public` instead and ship no auth SDK at all.
 *
 * Run `npm run gen:api` in web/ after any change to contracts/openapi.yaml.
 */

import createClient, { type Middleware } from 'openapi-fetch';
import { readEnv } from '../env';
import { firebaseAuth } from '../firebase/app';
import type { paths } from './schema';

export type { PramaanClient } from './public';
export { publicApi } from './public';
export { type Problem, fieldErrors, problemMessage, toProblem } from './problem';

let currentDevUser: string = 'clerk';

/** Set the short user name sent in X-Dev-User during demo mode ('clerk' or 'cfo'). */
export function setDevUser(user: string): void {
  currentDevUser = user;
}

export function getDevUser(): string {
  return currentDevUser;
}

/**
 * Attaches a fresh Firebase ID token to every request, or in demo mode sends
 * X-Dev-User instead of the Bearer token.
 *
 * Requests to endpoints that carry `security: []` in the contract work without a
 * token too: when nobody is signed in, no header is added and the request goes
 * out anyway.
 */
const authMiddleware: Middleware = {
  async onRequest({ request }) {
    if (readEnv().demoMode) {
      request.headers.set('X-Dev-User', getDevUser());
      request.headers.delete('Authorization');
      return request;
    }
    const user = firebaseAuth().currentUser;
    if (!user) return request;
    try {
      const token = await user.getIdToken();
      request.headers.set('Authorization', `Bearer ${token}`);
    } catch {
      // A token we could not refresh is no token. Let the server answer 401
      // rather than guessing here.
    }
    return request;
  },
};

let cached: ReturnType<typeof createClient<paths>> | null = null;

/**
 * The client. Memoised, so every screen shares one instance and one middleware
 * chain.
 */
export function api(): ReturnType<typeof createClient<paths>> {
  if (cached) return cached;
  const client = createClient<paths>({
    baseUrl: readEnv().apiBase,
    headers: { Accept: 'application/json' },
  });
  client.use(authMiddleware);
  cached = client;
  return cached;
}

/** Resets the memoised client. Tests only. */
export function resetApiForTests(): void {
  cached = null;
}
