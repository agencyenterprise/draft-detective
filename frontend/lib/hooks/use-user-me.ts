import { useQuery } from '@tanstack/react-query';
import { getCurrentUserInfoApiUsersMeGet, UserResponse } from '../generated-api';
import { useSession } from 'next-auth/react';

export const USER_ME_QUERY_KEY = ['user', 'me'] as const;

/**
 * Hook to fetch the current authenticated user's information.
 * Uses React Query for caching and automatic refetching.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { data: user, isLoading, error } = useUserMe();
 *   if (isLoading) return <Loading />;
 *   if (user?.role === UserRole.Admin) {
 *     // Show admin content
 *   }
 * }
 * ```
 */
export function useUserMe() {
  const session = useSession();

  return useQuery({
    enabled: session.status === 'authenticated',
    queryKey: USER_ME_QUERY_KEY,
    queryFn: () => getCurrentUserInfoApiUsersMeGet(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false, // Don't retry on auth failures
  });
}

export type { UserResponse };
