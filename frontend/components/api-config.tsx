'use client';

import { useEffect } from 'react';
import { client } from '@/lib/generated-api/client.gen';
import { useSession } from 'next-auth/react';
import { baseUrl } from '@/lib/api';

export function ApiConfig() {
  const session = useSession();
  const accessToken = session.data?.accessToken;

  useEffect(() => {
    client.setConfig({
      baseUrl,
      headers: {
        Authorization: accessToken ? `Bearer ${accessToken}` : undefined,
      },
    });
  }, [accessToken]);

  useEffect(() => {
    // Refresh the session every X minutes to keep the access token valid
    const interval = setInterval(
      async () => {
        await session.update();
      },
      1000 * 60 * 5, // X = 5 minutes
    );

    return () => clearInterval(interval);
  }, [session]);

  return null;
}
