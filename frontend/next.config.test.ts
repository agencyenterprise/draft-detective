import { describe, expect, it } from 'vitest';

import nextConfig from './next.config';

describe('next.config redirects', () => {
  it('sends slashless /mcp to the API MCP endpoint, keeping the method', async () => {
    const redirects = (await nextConfig.redirects?.()) ?? [];

    expect(redirects).toContainEqual({
      source: '/mcp',
      destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/mcp/`,
      permanent: false,
    });
  });
});
