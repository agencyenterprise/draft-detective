'use client';

import React from 'react';

interface ShareContextType {
  shareToken: string | null;
}

const ShareContext = React.createContext<ShareContextType | undefined>(undefined);

interface ShareProviderProps {
  token: string | null;
  children: React.ReactNode;
}

/**
 * ShareProvider wraps components that need access to a share token.
 * Used in shared project views to enable unauthenticated access.
 */
export function ShareProvider({ token, children }: ShareProviderProps) {
  const value = React.useMemo(() => ({ shareToken: token }), [token]);

  return <ShareContext.Provider value={value}>{children}</ShareContext.Provider>;
}

/**
 * Hook to access share context.
 * Returns the current share token or null if not in a shared context.
 *
 * Safe to use without ShareProvider - will return null for shareToken
 * in authenticated views.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { shareToken } = useShare();
 *   // shareToken will be null in authenticated views, string in shared views
 * }
 * ```
 */
export function useShare(): ShareContextType {
  const context = React.useContext(ShareContext);

  // Return default value if used outside ShareProvider (authenticated views)
  if (context === undefined) {
    return { shareToken: null };
  }

  return context;
}
