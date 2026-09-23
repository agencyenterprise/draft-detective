import { afterEach, describe, expect, it, vi } from 'vitest';

// baseUrl is read from NEXT_PUBLIC_API_URL when the module loads, so each case
// stubs the env and loads a fresh copy.
async function baseUrlWith(apiUrl: string | undefined) {
  vi.stubEnv('NEXT_PUBLIC_API_URL', apiUrl);
  vi.resetModules();
  return (await import('./api')).baseUrl;
}

describe('baseUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([
    ['https://api.example.com', 'https://api.example.com'],
    ['https://api.example.com/', 'https://api.example.com'],
    [undefined, 'http://localhost:8000'],
  ])('turns API URL %s into %s so appended paths never double the slash', async (apiUrl, expected) => {
    const baseUrl = await baseUrlWith(apiUrl);

    expect(baseUrl).toBe(expected);
    expect(`${baseUrl}/mcp`).not.toContain('//mcp');
  });
});
