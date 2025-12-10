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
        Authorization: `Bearer ${accessToken}`,
      },
    });
  }, [accessToken]);

  return null;
}
