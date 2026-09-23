import { getSession } from 'next-auth/react';

// Callers append paths (`${baseUrl}/mcp`), so drop any trailing slash the env value carries.
export const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

export async function getAuthHeader(): Promise<string | undefined> {
  const session = await getSession();
  return session?.accessToken ? `Bearer ${session.accessToken}` : undefined;
}
