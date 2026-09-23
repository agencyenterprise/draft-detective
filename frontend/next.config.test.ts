import { afterEach, describe, expect, it, vi } from 'vitest';

// next.config reads NEXT_PUBLIC_API_URL when it loads, so each case stubs the
// env and loads a fresh copy.
async function redirectsWith(apiUrl: string | undefined) {
  vi.stubEnv('NEXT_PUBLIC_API_URL', apiUrl);
  vi.resetModules();
  const { default: nextConfig } = await import('./next.config');
  return (await nextConfig.redirects?.()) ?? [];
}

describe('next.config redirects', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([
    ['https://api.example.com', 'https://api.example.com/mcp/'],
    ['https://api.example.com/', 'https://api.example.com/mcp/'],
    [undefined, 'http://localhost:8000/mcp/'],
  ])('sends slashless /mcp from API URL %s to %s, keeping the method', async (apiUrl, destination) => {
    expect(await redirectsWith(apiUrl)).toContainEqual({ source: '/mcp', destination, permanent: false });
  });
});
