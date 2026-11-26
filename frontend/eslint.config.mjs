import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import prettier from 'eslint-config-prettier/flat';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  prettier,
  {
    // The DOCX export libraries are about 170 KB gzipped: load them with `import()` on demand.
    files: ['**/*.{ts,tsx}'],
    ignores: ['lib/markdown-docx.ts', 'lib/markdown-docx.test.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            { name: '@mohtasham/md-to-docx', message: 'Use `await import(\'@/lib/markdown-docx\')` when the user exports.' },
            { name: '@/lib/markdown-docx', message: 'Load it with `await import()` when the user exports.', allowTypeImports: true },
          ],
        },
      ],
    },
  },
  globalIgnores([
    'node_modules/**',
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
    'lib/generated-api/**',
    // Copied from the assistant-ui registry and kept as upstream ships it, so it is
    // type-checked but not linted. The files that carry our own `Draft Detective:` edits
    // stay linted.
    'components/assistant-ui/elements/**/*',
    '!components/assistant-ui/elements/thread.aui.tsx',
    '!components/assistant-ui/elements/tool-fallback.aui.tsx',
    '!components/assistant-ui/elements/reasoning-panel.tsx',
    'components/assistant-ui/utils/**',
    'hooks/use-attachment-src.ts',
    'hooks/use-copy-to-clipboard.ts',
  ]),
]);
