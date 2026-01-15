import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import type { PreflightResult } from '@/lib/generated-api';
import { validatePreflight, PreflightContext } from '../preflight/service';

interface UsePreflightReturn {
  runPreflight: (context: PreflightContext) => Promise<boolean>;
  error: string | undefined;
  isValidating: boolean;
  clearError: () => void;
}

export function usePreflight(): UsePreflightReturn {
  const [error, setError] = useState<string | undefined>(undefined);
  const [isValidating, setIsValidating] = useState(false);

  const runPreflight = useCallback(async (context: PreflightContext): Promise<boolean> => {
    setIsValidating(true);
    setError(undefined);

    try {
      const result: PreflightResult = await validatePreflight(context);

      result.issues?.filter((i) => i.severity === 'warning').forEach((i) => toast.warning(i.message));

      if (!result.valid) {
        const errorMessages = result.issues
          ?.filter((i) => i.severity === 'error')
          .map((i) => i.message)
          .join('\n');
        setError(errorMessages || 'Preflight validation failed');
        return false;
      }

      return true;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Preflight validation failed';
      setError(message);
      return false;
    } finally {
      setIsValidating(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(undefined);
  }, []);

  return { runPreflight, error, isValidating, clearError };
}
