'use client';

import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useToastMutation, type ToastMutationOptions } from '@/lib/hooks/use-toast-mutation';
import { useQueryClient } from '@tanstack/react-query';

export interface ProjectMutationOptions<TData, TVariables> extends ToastMutationOptions<TData, TVariables> {
  /**
   * Stay pending until the project's refresh lands, so a control bound to
   * `isPending` goes straight from "Starting…" to what the overview now shows,
   * with no idle moment in between to invite a second click. Callbacks passed
   * to `mutate` then also wait for the refresh. Off by default: the mutation
   * settles as soon as the server answers, and the refresh follows.
   */
  waitForRefresh?: boolean;
}

/**
 * A mutation that changes a project. It toasts like `useToastMutation`, and
 * after the caller's `onSuccess` refreshes everything cached for the project.
 */
export function useProjectMutation<TData = unknown, TVariables = void>(
  projectId: string,
  { waitForRefresh = false, onSuccess, ...options }: ProjectMutationOptions<TData, TVariables>,
) {
  const queryClient = useQueryClient();
  return useToastMutation<TData, TVariables>({
    ...options,
    onSuccess: async (...args) => {
      try {
        await onSuccess?.(...args);
      } finally {
        // The change landed on the server either way, so the cache follows it.
        const refresh = queryClient.invalidateQueries({ queryKey: projectQueryKeys.all(projectId) });
        if (waitForRefresh) await refresh;
      }
    },
  });
}
