import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'http://localhost:8000/openapi.json',
  output: 'lib/generated-api',
  prettier: true,
  plugins: [
    {
      name: '@hey-api/typescript',
      enums: { case: 'PascalCase' },
    },
    {
      name: '@hey-api/sdk',
      responseStyle: 'data',
    },
    {
      name: '@hey-api/transformers',
      dates: true,
    },
    {
      name: '@hey-api/client-fetch',
      throwOnError: true,
    },
  ],
});
