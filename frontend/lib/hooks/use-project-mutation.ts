'use client';

import { getErrorMessage } from '@/lib/api-error';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useMutation, useQueryClient, type UseMutationOptions } from '@tanstack/react-query';
import { toast } from 'sonner';

export interface ProjectMutationOptions<TData, TVariables> extends UseMutationOptions<TData, Error, TVariables> {
  /** Toasted on success. Leave it out when the caller says it some other way. */
  successMessage?: string;
  /** Toasted on failure when the server gives no reason. */
  errorMessage: string;
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
 * A mutation that changes a project. On success it toasts `successMessage`,
 * runs the caller's `onSuccess`, then refreshes everything cached for the
 * project. On failure it toasts the server's reason, or `errorMessage`, then
 * runs the caller's `onError`.
 */
export function useProjectMutation<TData = unknown, TVariables = void>(
  projectId: string,
  {
    successMessage,
    errorMessage,
    waitForRefresh = false,
    onSuccess,
    onError,
    ...options
  }: ProjectMutationOptions<TData, TVariables>,
) {
  const queryClient = useQueryClient();
  return useMutation<TData, Error, TVariables>({
    ...options,
    onSuccess: async (...args) => {
      if (successMessage) toast.success(successMessage);
      try {
        await onSuccess?.(...args);
      } finally {
        // The change landed on the server either way, so the cache follows it.
        const refresh = queryClient.invalidateQueries({ queryKey: projectQueryKeys.all(projectId) });
        if (waitForRefresh) await refresh;
      }
    },
    onError: (...args) => {
      toast.error(getErrorMessage(args[0], errorMessage));
      return onError?.(...args);
    },
  });
}
