import { useCallback } from 'react';
import { useLocalStorage } from './use-local-storage';

type WebSearchConsentMap = Record<string, boolean>;

export function useWebSearchConsent(projectId: string | null) {
  const [consents, setConsents] = useLocalStorage<WebSearchConsentMap>('web-search-consents', {});

  const hasConsent = projectId ? (consents[projectId] ?? false) : false;

  const setConsent = useCallback(
    (value: boolean) => {
      if (!projectId) return;
      setConsents({ ...consents, [projectId]: value });
    },
    [projectId, consents, setConsents],
  );

  return [hasConsent, setConsent] as const;
}
