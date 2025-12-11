import { getSession } from 'next-auth/react';

export const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function getAuthHeader(): Promise<string | undefined> {
  const session = await getSession();
  return session?.accessToken ? `Bearer ${session.accessToken}` : undefined;
}
