import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useState } from 'react';

/**
 * Hook for managing projectId URL parameter synchronization in tool pages.
 * Manages projectId state and automatically syncs with URL query parameters.
 *
 * On mount, initializes state from URL if present.
 * When setProjectId is called, updates both state and URL atomically.
 *
 * @returns Object containing projectId state and setProjectId setter
 */
export function useToolProjectUrl() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const projectIdFromUrl = searchParams.get('projectId');

  const [projectId, setProjectIdState] = useState<string | null>(projectIdFromUrl);

  const setProjectId = useCallback(
    (newProjectId: string | null) => {
      setProjectIdState(newProjectId);

      // Update URL to match state
      const params = new URLSearchParams(searchParams.toString());
      if (newProjectId) {
        params.set('projectId', newProjectId);
        router.replace(`${pathname}?${params.toString()}`, { scroll: false });
      } else {
        params.delete('projectId');
        const newUrl = params.toString() ? `${pathname}?${params.toString()}` : pathname;
        router.replace(newUrl, { scroll: false });
      }
    },
    [pathname, router, searchParams],
  );

  return { projectId, setProjectId };
}
