/**
 * Firestore security rules tests.
 *
 * Two claims these tests exist to prove, because the whole live read model rests
 * on them:
 *
 *   1. No client can write to Firestore. Ever. Only the API writes, through the
 *      Admin SDK, which bypasses rules entirely.
 *   2. Reading needs a role. `finance` reads everything the console shows;
 *      `clerk` reads only what the mock ERP needs; anyone else reads nothing.
 *
 * Requires the Firestore emulator. Start it first:
 *     npm run emulators          (from web/)
 * then:
 *     npm run rules:test         (from web/)
 *
 * The emulator needs Java 21 or later on the PATH.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from '@firebase/rules-unit-testing';
import { collection, doc, getDoc, getDocs, setDoc, deleteDoc } from 'firebase/firestore';
import { afterAll, beforeAll, beforeEach, describe, it } from 'vitest';

const here = path.dirname(fileURLToPath(import.meta.url));
const RULES_FILE = path.resolve(here, '../../../infra/firestore.rules');

const HOST = process.env.FIRESTORE_EMULATOR_HOST?.split(':')[0] ?? '127.0.0.1';
const PORT = Number.parseInt(process.env.FIRESTORE_EMULATOR_HOST?.split(':')[1] ?? '8080', 10);

const INTENT_ID = 'pi_01JD2XBOSSSCAM0001';
const DEVICE_ID = 'dv_01JD2XCFOPHONE001';
const AGENT_REQUEST_ID = 'ag_01JD2XPOISONED001';
const PAYOUT_ID = 'po_01JD2XGENUINE0001';

let testEnv;

beforeAll(async () => {
  try {
    testEnv = await initializeTestEnvironment({
      projectId: 'pramaan-rules-test',
      firestore: {
        rules: readFileSync(RULES_FILE, 'utf8'),
        host: HOST,
        port: PORT,
      },
    });
  } catch (error) {
    throw new Error(
      `Could not reach the Firestore emulator at ${HOST}:${PORT}.\n` +
        'Start it with "npm run emulators" from web/, then run this again.\n' +
        'It needs Java 21 or later on the PATH.\n\n' +
        `Original error: ${error?.message ?? error}`,
    );
  }
});

afterAll(async () => {
  await testEnv?.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();

  // Seed with rules switched off, which is how the API writes in production.
  await testEnv.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore();
    await setDoc(doc(db, 'holds', INTENT_ID), {
      intentId: INTENT_ID,
      status: 'held',
      tier: 2,
      amountPaise: '465000000',
      payeeName: 'Global Trade Solutions',
    });
    await setDoc(doc(db, 'holds', INTENT_ID, 'steps', '001'), {
      n: 1,
      step: 'created',
      detail: 'Payment created in Acme ERP',
    });
    await setDoc(doc(db, 'devices', DEVICE_ID), {
      deviceId: DEVICE_ID,
      approver: 'cfo@acme.example',
      keySecurityLevel: 'StrongBox',
      revoked: false,
    });
    await setDoc(doc(db, 'agentRequests', AGENT_REQUEST_ID), {
      agentRequestId: AGENT_REQUEST_ID,
      agentId: 'payables-agent-01',
      status: 'flagged',
    });
    await setDoc(doc(db, 'payouts', PAYOUT_ID), {
      payoutId: PAYOUT_ID,
      mandateId: 'pm_01JD2XGENUINE0001',
      amountPaise: '98000000',
      status: 'paid',
    });
    await setDoc(doc(db, 'secrets', 'anything'), { nothing: 'to see' });
  });
});

/** A signed-in user carrying the given role claim. */
const asRole = (role) => testEnv.authenticatedContext('user-1', { role }).firestore();
/** Signed in with Google, but no role granted yet. */
const asNoRole = () => testEnv.authenticatedContext('user-2', {}).firestore();
/** Not signed in at all. */
const asAnonymous = () => testEnv.unauthenticatedContext().firestore();

describe('the finance role, which the console needs', () => {
  it('reads a hold', async () => {
    await assertSucceeds(getDoc(doc(asRole('finance'), 'holds', INTENT_ID)));
  });

  it('reads the holds board', async () => {
    await assertSucceeds(getDocs(collection(asRole('finance'), 'holds')));
  });

  it('reads the payment timeline', async () => {
    await assertSucceeds(getDocs(collection(asRole('finance'), 'holds', INTENT_ID, 'steps')));
  });

  it('reads approver phones', async () => {
    await assertSucceeds(getDoc(doc(asRole('finance'), 'devices', DEVICE_ID)));
  });

  it('reads agent requests', async () => {
    await assertSucceeds(getDoc(doc(asRole('finance'), 'agentRequests', AGENT_REQUEST_ID)));
  });

  it('reads payouts', async () => {
    await assertSucceeds(getDoc(doc(asRole('finance'), 'payouts', PAYOUT_ID)));
  });
});

describe('the clerk role, which the mock ERP needs', () => {
  it('reads the status of a payment it raised', async () => {
    await assertSucceeds(getDoc(doc(asRole('clerk'), 'holds', INTENT_ID)));
  });

  it('reads the payment timeline', async () => {
    await assertSucceeds(getDocs(collection(asRole('clerk'), 'holds', INTENT_ID, 'steps')));
  });

  it('reads the agent run it started', async () => {
    await assertSucceeds(getDoc(doc(asRole('clerk'), 'agentRequests', AGENT_REQUEST_ID)));
  });

  it('reads payouts, for the sandbox bank', async () => {
    await assertSucceeds(getDoc(doc(asRole('clerk'), 'payouts', PAYOUT_ID)));
  });

  it('cannot read approver phones, which are none of a clerk’s business', async () => {
    await assertFails(getDoc(doc(asRole('clerk'), 'devices', DEVICE_ID)));
  });
});

describe('a signed-in account with no role', () => {
  it('reads nothing', async () => {
    const db = asNoRole();
    await assertFails(getDoc(doc(db, 'holds', INTENT_ID)));
    await assertFails(getDocs(collection(db, 'holds')));
    await assertFails(getDoc(doc(db, 'devices', DEVICE_ID)));
    await assertFails(getDoc(doc(db, 'agentRequests', AGENT_REQUEST_ID)));
    await assertFails(getDoc(doc(db, 'payouts', PAYOUT_ID)));
  });

  it('is not let in by an invented role', async () => {
    const db = asRole('admin');
    await assertFails(getDoc(doc(db, 'holds', INTENT_ID)));
    await assertFails(getDoc(doc(db, 'devices', DEVICE_ID)));
  });
});

describe('nobody signed in', () => {
  it('reads nothing, including the payouts the public bank page wants', async () => {
    const db = asAnonymous();
    await assertFails(getDoc(doc(db, 'holds', INTENT_ID)));
    await assertFails(getDoc(doc(db, 'payouts', PAYOUT_ID)));
  });
});

describe('no client writes, at any role', () => {
  it('refuses a finance user creating a hold', async () => {
    await assertFails(
      setDoc(doc(asRole('finance'), 'holds', 'pi_forged'), { status: 'released' }),
    );
  });

  it('refuses a finance user changing a hold to released', async () => {
    await assertFails(
      setDoc(doc(asRole('finance'), 'holds', INTENT_ID), { status: 'released' }),
    );
  });

  it('refuses a finance user deleting a hold', async () => {
    await assertFails(deleteDoc(doc(asRole('finance'), 'holds', INTENT_ID)));
  });

  it('refuses a clerk writing a step into the timeline', async () => {
    await assertFails(
      setDoc(doc(asRole('clerk'), 'holds', INTENT_ID, 'steps', '099'), {
        n: 99,
        step: 'released',
      }),
    );
  });

  it('refuses a clerk inventing a payout, which is the money-moved claim', async () => {
    await assertFails(
      setDoc(doc(asRole('clerk'), 'payouts', 'po_forged'), {
        mandateId: 'pm_forged',
        amountPaise: '100000000',
        status: 'paid',
      }),
    );
  });

  it('refuses a finance user enrolling or revoking a device', async () => {
    await assertFails(
      setDoc(doc(asRole('finance'), 'devices', DEVICE_ID), { revoked: true }),
    );
  });

  it('refuses an anonymous write', async () => {
    await assertFails(setDoc(doc(asAnonymous(), 'holds', 'pi_forged'), { status: 'released' }));
  });
});

describe('everything else is closed', () => {
  it('refuses reads of a collection no rule mentions', async () => {
    await assertFails(getDoc(doc(asRole('finance'), 'secrets', 'anything')));
    await assertFails(getDoc(doc(asRole('clerk'), 'secrets', 'anything')));
    await assertFails(getDoc(doc(asAnonymous(), 'secrets', 'anything')));
  });

  it('refuses writes to a collection no rule mentions', async () => {
    await assertFails(setDoc(doc(asRole('finance'), 'secrets', 'new'), { a: 1 }));
  });

  it('refuses reads of mandates, which are served by the API and not Firestore', async () => {
    await assertFails(getDoc(doc(asRole('finance'), 'mandates', 'pm_01JD2XGENUINE0001')));
  });
});
