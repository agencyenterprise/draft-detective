import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

/**
 * Hook for managing projectId URL parameter synchronization in tool pages.
 * Manages projectId state and automatically syncs with URL query parameters.
 *
 * On mount, initializes state from URL if present.
 * When state changes, updates the URL to reflect the current projectId.
 *
 * @returns Object containing projectId state and setProjectId setter
 */
export function useToolProjectUrl() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectIdFromUrl = searchParams.get('projectId');

  const [projectId, setProjectId] = useState<string | null>(projectIdFromUrl);

  useEffect(() => {
    if (!projectId && projectIdFromUrl) {
      setProjectId(projectIdFromUrl);
    }
  }, [projectId, projectIdFromUrl]);

  useEffect(() => {
    if (projectId && !projectIdFromUrl) {
      const params = new URLSearchParams(searchParams.toString());
      params.set('projectId', projectId);
      router.replace(`?${params.toString()}`, { scroll: false });
    }
  }, [projectId, projectIdFromUrl, router, searchParams]);

  return { projectId, setProjectId };
}
