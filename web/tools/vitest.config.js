import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    include: ['tests/**/*.test.{js,mjs}'],
    // The rules tests talk to the Firestore emulator over the network, which is
    // slower than a unit test and slowest on the very first connection.
    testTimeout: 20_000,
    hookTimeout: 60_000,
    // One emulator, one rules test environment: running files in parallel would
    // have them clearing each other's seeded documents.
    fileParallelism: false,
  },
});
