'use client';

import { useEffect } from 'react';
import { client } from '@/lib/generated-api/client.gen';
import { useSession } from 'next-auth/react';
import { baseUrl } from '@/lib/api';
import { posthog } from '@/lib/posthog';

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

  useEffect(() => {
    if (session.status === 'authenticated' && session.data?.user?.email) {
      posthog.identify(session.data.user.email, {
        email: session.data.user.email,
        name: session.data.user.name,
      });
    } else if (session.status === 'unauthenticated') {
      posthog.reset();
    }
  }, [session.status, session.data?.user?.email, session.data?.user?.name]);

  return null;
}
