'use client';

import { Switch } from '@/components/ui/switch';
import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // next-themes resolves the theme on the client, so we render a neutral
  // state until mount to avoid an SSR/CSR hydration mismatch.
  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <Switch
      checked={mounted ? resolvedTheme === 'dark' : false}
      onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
      disabled={!mounted}
      aria-label="Toggle dark mode"
    />
  );
}
