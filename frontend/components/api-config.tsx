'use client';

import { useEffect, useLayoutEffect } from 'react';
import { useSession } from 'next-auth/react';
import { setApiAccessToken } from '@/lib/api-client';
import { posthog } from '@/lib/posthog';

export function ApiConfig() {
  const session = useSession();
  const accessToken = session.data?.accessToken;

  // A layout effect, so the token changes only when a render commits. It still precedes every request the app makes
  // on mount: ApiConfig renders before the app's other components, so its layout effect runs before their layout and
  // passive effects.
  useLayoutEffect(() => {
    setApiAccessToken(accessToken);
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
