import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

/** The project root, so `@/...` resolves the way `tsconfig.json` maps it. */
const projectRoot = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{ find: /^@\//, replacement: projectRoot }],
  },
  test: {
    environment: 'jsdom',
    // Tests import from `vitest` explicitly, so the tsconfig needs no `types` entry.
    globals: false,
    include: ['**/*.test.{ts,tsx}'],
    exclude: ['**/node_modules/**', '**/.next/**'],
  },
});
