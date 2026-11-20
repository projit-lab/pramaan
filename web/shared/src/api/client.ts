/**
 * The typed API client.
 *
 * Generated from contracts/openapi.yaml with openapi-typescript, called with
 * openapi-fetch. Screens call the API only through this client; there are no
 * hand-written URLs anywhere in the web lane, which is why `paths` is imported
 * from the generated file and the base URL comes from VITE_API_BASE.
 *
 * Run `npm run gen:api` in web/ after any change to contracts/openapi.yaml.
 */

import createClient, { type Middleware } from 'openapi-fetch';
import { firebaseAuth } from '../firebase/app';
import { readEnv } from '../env';
import type { paths } from './schema';

/** Problem details, RFC 9457, as every Pramaan error arrives. */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  errors?: Array<{ field: string; detail: string }>;
}

/**
 * Attaches a fresh Firebase ID token to every request.
 *
 * Requests to endpoints that carry `security: []` in the contract (the public
 * mandate verifier, the countersigning key, the sandbox bank payouts) work
 * without a token too: when nobody is signed in, no header is added and the
 * request goes out anyway.
 */
const authMiddleware: Middleware = {
  async onRequest({ request }) {
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

export type PramaanClient = ReturnType<typeof createClient<paths>>;

let cached: PramaanClient | null = null;

/**
 * The client. Memoised, so every screen shares one instance and one middleware
 * chain.
 */
export function api(): PramaanClient {
  if (cached) return cached;
  const client = createClient<paths>({
    baseUrl: readEnv().apiBase,
    headers: { Accept: 'application/json' },
  });
  client.use(authMiddleware);
  cached = client;
  return cached;
}

/**
 * A client with no Firebase dependency at all, for the public verifier page: it
 * must work for an auditor who has never signed in and has no Firebase config.
 */
export function publicApi(): PramaanClient {
  return createClient<paths>({
    baseUrl: readEnv().apiBase,
    headers: { Accept: 'application/json' },
  });
}

/** Resets the memoised client. Tests only. */
export function resetApiForTests(): void {
  cached = null;
}

/**
 * Turns whatever an error branch produced into a Problem a screen can show.
 *
 * Never invents a title: if the server did not send problem details, the message
 * says only that the request failed.
 */
export function toProblem(error: unknown, status?: number): Problem {
  if (error && typeof error === 'object') {
    const candidate = error as Partial<Problem>;
    if (typeof candidate.title === 'string' && typeof candidate.status === 'number') {
      return candidate as Problem;
    }
  }
  return {
    type: 'about:blank',
    title: 'The request failed',
    status: status ?? 0,
    detail:
      status === undefined
        ? 'Pramaan could not reach the API. Check that it is running and that VITE_API_BASE is correct.'
        : undefined,
  };
}

/** The one-line message a screen shows for a problem. */
export function problemMessage(problem: Problem): string {
  return problem.detail ? `${problem.title}. ${problem.detail}` : problem.title;
}

/** Field errors keyed by field name, so a form can show them inline. */
export function fieldErrors(problem: Problem): Record<string, string> {
  const result: Record<string, string> = {};
  for (const entry of problem.errors ?? []) {
    result[entry.field] = entry.detail;
  }
  return result;
}
