#!/usr/bin/env node
/**
 * Grant a Pramaan role to a Google account.
 *
 * There is no sign-up page anywhere in Pramaan. Everyone signs in with Google, and
 * an admin runs this script to set the Firebase Auth custom claim `role`. Without
 * a role, a signed-in account reads nothing and sees the "No access" page.
 *
 * Safe by default: it talks to the Auth emulator unless you pass --real. That way
 * a mistyped command cannot hand somebody the finance role in a live project.
 *
 * Usage
 *   node tools/grant-role.mjs --email cfo@acme.example --role finance
 *   node tools/grant-role.mjs --email clerk@acme.example --role clerk
 *   node tools/grant-role.mjs --email ops@acme.example --role none      (revoke)
 *   node tools/grant-role.mjs --email you@example.com --role finance --real --project pramaan-dev-515306
 *   node tools/grant-role.mjs --list
 *
 * Against a real project it uses your own gcloud credentials
 * (`gcloud auth application-default login`), so no service account key file is
 * needed and none should ever be created for this.
 *
 * The role lands in the next ID token. The console and the ERP listen with
 * onIdTokenChanged, so an open tab picks it up on the next refresh, within an hour
 * or immediately after a sign-out and sign-in.
 */

import process from 'node:process';
import { initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';

const ROLES = ['finance', 'clerk'];

function parseArgs(argv) {
  const args = { real: false, list: false };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--real') args.real = true;
    else if (token === '--list') args.list = true;
    else if (token === '--email') args.email = argv[++index];
    else if (token === '--role') args.role = argv[++index];
    else if (token === '--project') args.project = argv[++index];
    else if (token === '--help' || token === '-h') args.help = true;
    else {
      console.error(`Unknown argument: ${token}`);
      process.exit(2);
    }
  }
  return args;
}

function usage() {
  console.log(`
Grant a Pramaan role to a Google account.

  --email <address>   the account to change
  --role  <role>      ${ROLES.join(' | ')} | none
  --list              list every account that has a role
  --project <id>      Google Cloud project id (default: $GCLOUD_PROJECT or pramaan-dev-515306)
  --real              act on the real project instead of the Auth emulator

Examples
  node tools/grant-role.mjs --email cfo@acme.example --role finance
  node tools/grant-role.mjs --email you@example.com --role finance --real --project pramaan-dev-515306
`);
}

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  usage();
  process.exit(0);
}

const projectId = args.project ?? process.env.GCLOUD_PROJECT ?? 'pramaan-dev-515306';

if (!args.real) {
  // The Admin SDK talks to the emulator purely through this variable.
  process.env.FIREBASE_AUTH_EMULATOR_HOST ??= '127.0.0.1:9099';
  console.log(`Emulator mode: ${process.env.FIREBASE_AUTH_EMULATOR_HOST} (project ${projectId})`);
  console.log('Pass --real to act on the real project instead.\n');
} else {
  delete process.env.FIREBASE_AUTH_EMULATOR_HOST;
  console.log(`REAL PROJECT: ${projectId}`);
  console.log('Using your gcloud application-default credentials.\n');
}

initializeApp({ projectId });
const auth = getAuth();

async function listRoles() {
  const withRole = [];
  let pageToken;
  do {
    const page = await auth.listUsers(1000, pageToken);
    for (const user of page.users) {
      const role = user.customClaims?.role;
      if (role) withRole.push({ email: user.email ?? user.uid, role });
    }
    pageToken = page.pageToken;
  } while (pageToken);

  if (withRole.length === 0) {
    console.log('No account has a role yet.');
    return;
  }
  console.log('Accounts with a role:');
  for (const entry of withRole.sort((a, b) => a.email.localeCompare(b.email))) {
    console.log(`  ${entry.role.padEnd(8)} ${entry.email}`);
  }
}

async function grant(email, role) {
  let user;
  try {
    user = await auth.getUserByEmail(email);
  } catch (error) {
    if (error?.code !== 'auth/user-not-found') throw error;

    if (args.real) {
      // In a real project, the account must sign in with Google once first, so
      // that Firebase holds the identity Google vouched for. Creating it here
      // would make an account this script invented.
      console.error(`No account for ${email} in ${projectId}.`);
      console.error('Ask them to sign in with Google once, then run this again.');
      process.exit(1);
    }

    // On the emulator there is no real Google to sign in with, so creating the
    // account here is how local testing works at all.
    console.log(`No account for ${email} on the emulator. Creating one for testing.`);
    user = await auth.createUser({ email, emailVerified: true, displayName: email });
  }

  const existing = user.customClaims ?? {};
  if (role === 'none') {
    const { role: _removed, ...rest } = existing;
    await auth.setCustomUserClaims(user.uid, rest);
    console.log(`Removed the role from ${email}. They will see "No access".`);
  } else {
    await auth.setCustomUserClaims(user.uid, { ...existing, role });
    console.log(`${email} now has the ${role} role.`);
  }

  // Forcing a token refresh is what makes the change take effect promptly.
  await auth.revokeRefreshTokens(user.uid);
  console.log('Refresh tokens revoked, so the new role applies on the next sign-in.');
}

try {
  if (args.list) {
    await listRoles();
  } else if (!args.email || !args.role) {
    console.error('Both --email and --role are required. Use --help for examples.\n');
    usage();
    process.exit(2);
  } else if (![...ROLES, 'none'].includes(args.role)) {
    console.error(`--role must be one of: ${ROLES.join(', ')}, none`);
    process.exit(2);
  } else {
    await grant(args.email, args.role);
  }
  process.exit(0);
} catch (error) {
  console.error('\nFailed.');
  console.error(error?.message ?? error);
  if (!args.real && String(error?.message ?? '').includes('ECONNREFUSED')) {
    console.error('\nIs the Auth emulator running? Start it with:  npm run emulators');
  }
  process.exit(1);
}
