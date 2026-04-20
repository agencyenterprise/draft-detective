'use client';

import { updatePreferencesApiUsersMePreferencesPatch, UserResponse } from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { USER_ME_QUERY_KEY, useUserMe } from '@/lib/hooks/use-user-me';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import React from 'react';
import { toast } from 'sonner';

interface ExperimentalFeaturesContextType {
  showExperimentalFeatures: boolean;
  setShowExperimentalFeatures: (value: boolean) => void;
  isUpdating: boolean;
}

const ExperimentalFeaturesContext = React.createContext<ExperimentalFeaturesContextType | undefined>(undefined);

interface ExperimentalFeaturesProviderProps {
  children: React.ReactNode;
}

/**
 * Provider for experimental features toggle state.
 * Reads initial value from the useUserMe hook and persists changes to the backend.
 */
export function ExperimentalFeaturesProvider({ children }: ExperimentalFeaturesProviderProps) {
  const queryClient = useQueryClient();
  const { data: user } = useUserMe();

  const showExperimentalFeatures = user?.show_experimental_features ?? false;

  const mutation = useMutation({
    mutationFn: (newValue: boolean) =>
      updatePreferencesApiUsersMePreferencesPatch({
        body: { show_experimental_features: newValue },
      }),
    onMutate: async (newValue) => {
      await queryClient.cancelQueries({ queryKey: USER_ME_QUERY_KEY });
      queryClient.setQueryData<UserResponse>(USER_ME_QUERY_KEY, (old) =>
        old ? { ...old, show_experimental_features: newValue } : old,
      );
    },
    onError: (error) => {
      toast.error(`Failed to update preference: ${getErrorMessage(error, 'Unknown error')}`);
    },
    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: USER_ME_QUERY_KEY });
    },
  });

  const setShowExperimentalFeatures = React.useCallback(
    (value: boolean) => {
      mutation.mutate(value);
    },
    [mutation],
  );

  const value = React.useMemo(
    () => ({
      showExperimentalFeatures,
      setShowExperimentalFeatures,
      isUpdating: mutation.isPending,
    }),
    [showExperimentalFeatures, setShowExperimentalFeatures, mutation.isPending],
  );

  return <ExperimentalFeaturesContext.Provider value={value}>{children}</ExperimentalFeaturesContext.Provider>;
}

/**
 * Hook to access experimental features state.
 * Must be used within ExperimentalFeaturesProvider.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { showExperimentalFeatures, setShowExperimentalFeatures } = useExperimentalFeatures();
 *   // ...
 * }
 * ```
 */
export function useExperimentalFeatures(): ExperimentalFeaturesContextType {
  const context = React.useContext(ExperimentalFeaturesContext);

  if (context === undefined) {
    throw new Error('useExperimentalFeatures must be used within ExperimentalFeaturesProvider');
  }

  return context;
}
