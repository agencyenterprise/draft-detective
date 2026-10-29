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
  // Components import stylesheets; tests never look at them, so skip the
  // Tailwind PostCSS pipeline instead of loading postcss.config.mjs.
  css: { postcss: {} },
  test: {
    environment: 'jsdom',
    // Tests import from `vitest` explicitly, so the tsconfig needs no `types` entry.
    globals: false,
    include: ['**/*.test.{ts,tsx}'],
    exclude: ['**/node_modules/**', '**/.next/**'],
    coverage: {
      provider: 'v8',
      // Every hand-written module; generated clients, tests and tool configs would skew the numbers.
      include: ['**/*.{ts,tsx}'],
      exclude: [
        '**/node_modules/**',
        '**/.next/**',
        '**/*.d.ts',
        '**/*.test.{ts,tsx}',
        'lib/generated-api/**',
        'lib/test-render.tsx',
        'vitest.config.ts',
        'openapi-ts.config.ts',
      ],
    },
  },
});
