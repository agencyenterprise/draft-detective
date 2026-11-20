'use client';

import { getErrorMessage } from '@/lib/api-error';
import { useMutation, type UseMutationOptions } from '@tanstack/react-query';
import { toast } from 'sonner';

export interface ToastMutationOptions<TData, TVariables, TContext = unknown> extends UseMutationOptions<
  TData,
  Error,
  TVariables,
  TContext
> {
  /** Toasted on success. Leave it out when the caller says it some other way. */
  successMessage?: string;
  /** Toasted on failure when the server gives no reason. */
  errorMessage: string;
}

/**
 * A mutation the user started and should hear back from. On success it toasts
 * `successMessage`, then runs the caller's `onSuccess`. On failure it toasts the
 * server's reason, or `errorMessage`, then runs the caller's `onError`.
 */
export function useToastMutation<TData = unknown, TVariables = void, TContext = unknown>({
  successMessage,
  errorMessage,
  onSuccess,
  onError,
  ...options
}: ToastMutationOptions<TData, TVariables, TContext>) {
  return useMutation<TData, Error, TVariables, TContext>({
    ...options,
    onSuccess: (...args) => {
      if (successMessage) toast.success(successMessage);
      return onSuccess?.(...args);
    },
    onError: (...args) => {
      toast.error(getErrorMessage(args[0], errorMessage));
      return onError?.(...args);
    },
  });
}
