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
}

/**
 * A mutation that changes a project. On success it toasts `successMessage`,
 * runs the caller's `onSuccess`, then refreshes everything cached for the
 * project. On failure it toasts the server's reason, or `errorMessage`, then
 * runs the caller's `onError`.
 *
 * The mutation stays pending until the refresh lands, so a control bound to
 * `isPending` goes straight from "Starting…" to what the overview now shows,
 * with no idle moment in between to invite a second click. Callbacks passed to
 * `mutate` itself run after the refresh, when the cache already holds the change.
 */
export function useProjectMutation<TData = unknown, TVariables = void>(
  projectId: string,
  { successMessage, errorMessage, onSuccess, onError, ...options }: ProjectMutationOptions<TData, TVariables>,
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
        await queryClient.invalidateQueries({ queryKey: projectQueryKeys.all(projectId) });
      }
    },
    onError: (...args) => {
      toast.error(getErrorMessage(args[0], errorMessage));
      return onError?.(...args);
    },
  });
}
