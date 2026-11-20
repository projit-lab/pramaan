import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// envDir points at web/, so one web/.env.local serves every app in the workspace.
export default defineConfig({
  plugins: [react()],
  envDir: '..',
  server: { port: 5173, strictPort: false },
  preview: { port: 5173 },
  build: { outDir: 'dist', sourcemap: true },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
