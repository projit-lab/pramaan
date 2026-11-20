#!/usr/bin/env node
/**
 * Seed the Firestore emulator from data/firestore-seed.json.
 *
 * The seed follows contracts/firestore.md, so the console's live screens work
 * from the first minute without Prajit's projector existing yet.
 *
 * Emulator only by default, and it refuses to touch a real project unless you
 * pass --real. Seeding a live Firestore with fictional holds would be a bad day.
 *
 * Usage
 *   node tools/seed-firestore.mjs
 *   node tools/seed-firestore.mjs --clear          wipe the seeded collections first
 *   node tools/seed-firestore.mjs --project pramaan-dev-515306
 */

import { readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { initializeApp } from 'firebase-admin/app';
import { Timestamp, getFirestore } from 'firebase-admin/firestore';

const here = path.dirname(fileURLToPath(import.meta.url));
const SEED_FILE = path.resolve(here, '../../data/firestore-seed.json');

/** A full ISO 8601 timestamp with an offset, which the seed uses for every time. */
const ISO_WITH_OFFSET =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function parseArgs(argv) {
  const args = { real: false, clear: false };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--real') args.real = true;
    else if (token === '--clear') args.clear = true;
    else if (token === '--project') args.project = argv[++index];
    else if (token === '--help' || token === '-h') args.help = true;
    else {
      console.error(`Unknown argument: ${token}`);
      process.exit(2);
    }
  }
  return args;
}

/** Converts every ISO timestamp string into a Firestore Timestamp, at any depth. */
function convertTimes(value) {
  if (typeof value === 'string') {
    return ISO_WITH_OFFSET.test(value) ? Timestamp.fromDate(new Date(value)) : value;
  }
  if (Array.isArray(value)) return value.map(convertTimes);
  if (value && typeof value === 'object') {
    const result = {};
    for (const [key, nested] of Object.entries(value)) {
      result[key] = convertTimes(nested);
    }
    return result;
  }
  return value;
}

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  console.log(`
Seed the Firestore emulator from data/firestore-seed.json.

  --clear             delete the seeded collections before writing
  --project <id>      project id (default: $GCLOUD_PROJECT or pramaan-dev-515306)
  --real              write to the real project instead of the emulator
`);
  process.exit(0);
}

const projectId = args.project ?? process.env.GCLOUD_PROJECT ?? 'pramaan-dev-515306';

if (!args.real) {
  process.env.FIRESTORE_EMULATOR_HOST ??= '127.0.0.1:8080';
  console.log(`Emulator mode: ${process.env.FIRESTORE_EMULATOR_HOST} (project ${projectId})`);
} else {
  delete process.env.FIRESTORE_EMULATOR_HOST;
  console.log(`REAL PROJECT: ${projectId}. This writes fictional demo data to a live database.`);
}

initializeApp({ projectId });
const db = getFirestore();

/** Deletes a collection in batches, including each document's subcollections. */
async function deleteCollection(name) {
  let deleted = 0;
  for (;;) {
    const snapshot = await db.collection(name).limit(200).get();
    if (snapshot.empty) break;

    for (const document of snapshot.docs) {
      for (const sub of await document.ref.listCollections()) {
        const subDocs = await sub.get();
        const subBatch = db.batch();
        for (const subDoc of subDocs.docs) subBatch.delete(subDoc.ref);
        await subBatch.commit();
      }
    }

    const batch = db.batch();
    for (const document of snapshot.docs) batch.delete(document.ref);
    await batch.commit();
    deleted += snapshot.size;
  }
  return deleted;
}

try {
  const raw = await readFile(SEED_FILE, 'utf8');
  const seed = JSON.parse(raw);
  const collections = seed.collections ?? {};

  if (args.clear) {
    console.log('\nClearing:');
    for (const name of Object.keys(collections)) {
      const count = await deleteCollection(name);
      console.log(`  ${name}: deleted ${count}`);
    }
  }

  console.log('\nWriting:');
  let documents = 0;
  let subDocuments = 0;

  for (const [name, docs] of Object.entries(collections)) {
    const entries = Object.entries(docs ?? {});
    if (entries.length === 0) {
      console.log(`  ${name}: nothing to write (empty on purpose)`);
      continue;
    }

    for (const [id, entry] of entries) {
      // Accept both { data, subcollections } and a bare document.
      const data = entry?.data ?? entry;
      const subcollections = entry?.subcollections ?? {};

      await db.collection(name).doc(id).set(convertTimes(data));
      documents += 1;

      for (const [subName, subDocs] of Object.entries(subcollections)) {
        for (const [subId, subData] of Object.entries(subDocs ?? {})) {
          await db
            .collection(name)
            .doc(id)
            .collection(subName)
            .doc(subId)
            .set(convertTimes(subData));
          subDocuments += 1;
        }
      }
    }
    console.log(`  ${name}: ${entries.length}`);
  }

  console.log(`\nSeeded ${documents} documents and ${subDocuments} subcollection documents.`);
  console.log('The console holds board should now show the seeded holds.');
  process.exit(0);
} catch (error) {
  console.error('\nSeeding failed.');
  console.error(error?.message ?? error);
  if (String(error?.message ?? '').includes('ENOENT')) {
    console.error(`\nExpected the seed file at: ${SEED_FILE}`);
  }
  if (!args.real) {
    console.error('\nIs the Firestore emulator running? Start it with:  npm run emulators');
  }
  process.exit(1);
}
