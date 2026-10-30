'use client';

import { HelpCenter } from '@/components/help/help-center';
import { ProfileDropdown } from '@/components/layout/profile-dropdown';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useMediaQuery } from '@/lib/use-media-query';
import { cn } from '@/lib/utils';
import { CircleHelp, LogInIcon, Moon, Plus, Sun } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { useTheme } from 'next-themes';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ReactNode, useState } from 'react';

/**
 * Below this the bar is too narrow to float a centred title clear of the
 * wordmark on one side and the account controls on the other.
 */
const WIDE_ENOUGH_TO_CENTRE_TITLE = '(min-width: 52rem)';

const navigation = [
  { name: 'Projects', href: '/projects' },
  { name: 'About', href: '/about' },
];

interface AppBarProps {
  /**
   * Centred in the bar in place of the site nav. Views that are about one
   * project name it here, so the row below is free for that project's tabs.
   */
  title?: ReactNode;
}

/**
 * The application row for the home page, the projects list and the project
 * view: where you are, how to start something new, and who you are, in 44px.
 * Stands in for ApplicationShell's nav on those routes, which is why it carries
 * the same links and account menu.
 */
export function AppBar({ title }: AppBarProps) {
  const session = useSession();
  const pathname = usePathname();
  const { resolvedTheme, setTheme } = useTheme();
  const canCentreTitle = useMediaQuery(WIDE_ENOUGH_TO_CENTRE_TITLE);
  const [helpOpen, setHelpOpen] = useState(false);
  const user = session.data?.user;
  const isLoadingUser = session.status === 'loading';

  return (
    <div className="relative flex h-11 shrink-0 items-center gap-1 border-b px-3">
      {/* px-3 mirrors a tab's own padding, so the wordmark sits on the same
          text axis as the tab labels in the row below. */}
      <Link href="/" className="text-primary px-3 text-[15px] font-bold tracking-tight">
        Draft Detective
      </Link>

      {title ? (
        canCentreTitle ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            {/* A definite width, so the rename input has room to be typed in
                rather than shrinking to fit the finished title. */}
            <div className="pointer-events-auto flex w-full max-w-md min-w-0 items-center justify-center px-2">
              {title}
            </div>
          </div>
        ) : (
          // Too narrow to centre over the bar: the layer would cover the
          // wordmark and the account controls, and swallow their clicks. The
          // title takes its own space in the row instead.
          <div className="ml-1 flex min-w-0 flex-1 items-center">{title}</div>
        )
      ) : (
        <>
          <nav className="flex h-full items-center gap-1" aria-label="Main">
            {navigation.map((item) => {
              const current = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  aria-current={current ? 'page' : undefined}
                  className={cn(
                    'flex h-full items-center border-b-2 px-2 pt-0.5 text-[13px] font-medium transition-colors',
                    current
                      ? 'border-primary text-foreground'
                      : 'border-transparent text-muted-foreground hover:text-foreground',
                  )}
                >
                  {item.name}
                </Link>
              );
            })}
          </nav>

          <Button asChild variant="outline" size="sm" className="ml-2 h-7 px-2.5 text-[12.5px]">
            <Link href="/new">
              <Plus className="size-3.5" />
              New project
            </Link>
          </Button>
        </>
      )}

      <div className="ml-auto flex items-center gap-1.5">
        {/* Help belongs to the application, not to this project, so it sits in
            this row rather than among the project's own actions — and stays
            reachable from every tab. */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="size-7" onClick={() => setHelpOpen(true)} aria-label="Help">
              <CircleHelp className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Help</TooltipContent>
        </Tooltip>

        <HelpCenter open={helpOpen} onOpenChange={setHelpOpen} topic="assessments" />

        {/* Dark mode sits in the bar rather than the account menu: it is a
            preference, not an account setting, and signed-out visitors want it too. */}
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
          aria-label="Toggle dark mode"
        >
          <Moon className="size-4 dark:hidden" />
          <Sun className="hidden size-4 dark:block" />
        </Button>

        {user ? (
          <ProfileDropdown user={user} />
        ) : !isLoadingUser ? (
          <Button asChild variant="outline" size="sm" className="h-7 px-2.5 text-[12.5px]">
            <Link href="/api/auth/signin">
              <LogInIcon className="size-3.5" />
              Sign in
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
