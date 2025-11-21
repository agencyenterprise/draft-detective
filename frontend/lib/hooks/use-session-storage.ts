import { useCallback, useState } from 'react';

export function useSessionStorage<T>(key: string, defaultValue: T) {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return defaultValue;
    }

    const item = window.sessionStorage.getItem(key);
    if (item) {
      return JSON.parse(item);
    }
    return defaultValue;
  });

  const set = useCallback(
    (value: T) => {
      setValue(value);
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(key, JSON.stringify(value));
      }
    },
    [key],
  );

  return [value, set] as const;
}
