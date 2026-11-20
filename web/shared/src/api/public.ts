/**
 * The API client for pages with nobody signed in.
 *
 * Separate from client.ts on purpose: this module imports no Firebase, so the
 * public mandate verifier and the sandbox bank page ship no auth SDK. The
 * verifier in particular must work for an auditor who has never heard of us and
 * has no Firebase config at all.
 *
 * Still the generated client, still no hand-written URLs.
 */

import createClient from 'openapi-fetch';
import { readEnv } from '../env';
import type { paths } from './schema';

export type PramaanClient = ReturnType<typeof createClient<paths>>;

/**
 * A client with no credentials and no Firebase dependency.
 *
 * Endpoints marked `security: []` in the contract — GET /mandates/{id},
 * GET /keys/countersign, GET /payouts — answer this client. Anything else will
 * correctly come back 401.
 */
export function publicApi(): PramaanClient {
  return createClient<paths>({
    baseUrl: readEnv().apiBase,
    headers: { Accept: 'application/json' },
  });
}
