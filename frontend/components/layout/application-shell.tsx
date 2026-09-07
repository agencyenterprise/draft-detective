'use client';

import { AppBar } from '@/components/results/app-bar';
import { usePathname } from 'next/navigation';

/** Routes whose pages render the AppBar (or, for the add-in, no chrome at all) themselves. */
const OWN_CHROME_ROUTES = ['/projects', '/share', '/addin'];

function rendersOwnChrome(pathname: string): boolean {
  return pathname === '/' || OWN_CHROME_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export interface ApplicationShellProps {
  children: React.ReactNode;
}

/**
 * The application row over whichever page you are on. The home page, the
 * project views and the add-in draw their own chrome edge to edge; every other
 * page gets the same row here, so the furniture never changes between them.
 */
export function ApplicationShell({ children }: ApplicationShellProps) {
  const pathname = usePathname();

  if (rendersOwnChrome(pathname)) {
    return <>{children}</>;
  }

  // Chat uses the full page width (no centered max-width container or padding).
  const isFullBleed = pathname.startsWith('/chat');

  return (
    <div className="bg-background text-foreground flex h-dvh flex-col">
      <AppBar />
      {isFullBleed ? (
        <main className="flex min-h-0 min-w-0 flex-1 flex-col">{children}</main>
      ) : (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl p-4 sm:px-6 lg:px-8">{children}</div>
        </main>
      )}
    </div>
  );
}
