'use client';

import { PROTOTYPE_MODE } from '@/lib/prototype-mode';
import { cn } from '@/lib/utils';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react';
import { CircleUserRoundIcon, LogInIcon, MenuIcon, XIcon } from 'lucide-react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '../ui/button';
import { MobileProfileMenu, ProfileDropdown } from './profile-dropdown';

function getNavigation() {
  if (PROTOTYPE_MODE) {
    return [
      { name: 'Projects', href: '/' },
      { name: 'Start new project', href: '/' },
    ];
  }
  return [
    { name: 'Projects', href: '/projects' },
    { name: 'Start new project', href: '/new' },
  ];
}
const navigation = getNavigation();

export interface ApplicationShellProps {
  children: React.ReactNode;
}

export function ApplicationShell({ children }: ApplicationShellProps) {
  const session = useSession();
  const isLoadingUser = !PROTOTYPE_MODE && session.status === 'loading';
  const user = PROTOTYPE_MODE ? { name: 'Demo User', email: 'demo@ai-reviewer.local' } : session.data?.user;
  const pathname = usePathname();

  const navigationWithCurrent = navigation.map((item) => ({
    ...item,
    current: pathname.startsWith(item.href),
  }));

  if (pathname.startsWith('/addin')) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-full">
      <Disclosure as="nav" className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-15 justify-between">
            <div className="flex">
              <div className="flex shrink-0 items-center">
                <Link href="/" className="text-xl font-bold text-primary">
                  AI Reviewer
                </Link>
              </div>
              <div className="hidden sm:-my-px sm:ml-6 sm:flex sm:space-x-8">
                {navigationWithCurrent.map((item) => (
                  <a
                    key={item.name}
                    href={item.href}
                    aria-current={item.current ? 'page' : undefined}
                    className={cn(
                      item.current
                        ? 'border-primary text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
                      'inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium text',
                    )}
                  >
                    {item.name}
                  </a>
                ))}
              </div>
            </div>
            <div className="hidden sm:ml-6 sm:flex sm:items-center">
              {PROTOTYPE_MODE ? (
                <div className="flex items-center gap-2 rounded-full border border-border bg-muted/60 px-3 py-2 text-sm font-medium text-foreground">
                  <CircleUserRoundIcon className="h-4 w-4 text-primary" />
                  Demo User
                </div>
              ) : user ? (
                <ProfileDropdown user={user} />
              ) : !isLoadingUser ? (
                <Button asChild variant="outline">
                  <Link href="/api/auth/signin">
                    <LogInIcon className="w-4 h-4" />
                    Sign in
                  </Link>
                </Button>
              ) : null}
            </div>
            <div className="-mr-2 flex items-center sm:hidden">
              {/* Mobile menu button */}
              <DisclosureButton className="group relative inline-flex items-center justify-center rounded-md bg-white p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500 focus:outline-2 focus:outline-offset-2 focus:outline-primary">
                <span className="absolute -inset-0.5" />
                <span className="sr-only">Open main menu</span>
                <MenuIcon aria-hidden="true" className="block size-6 group-data-open:hidden" />
                <XIcon aria-hidden="true" className="hidden size-6 group-data-open:block" />
              </DisclosureButton>
            </div>
          </div>
        </div>

        <DisclosurePanel className="sm:hidden">
          <div className="space-y-1 pt-2 pb-3">
            {navigationWithCurrent.map((item) => (
              <DisclosureButton
                key={item.name}
                as="a"
                href={item.href}
                aria-current={item.current ? 'page' : undefined}
                className={cn(
                  item.current
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-transparent text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-800',
                  'block border-l-4 py-2 pr-4 pl-3 text-base font-medium',
                )}
              >
                {item.name}
              </DisclosureButton>
            ))}
          </div>
          <div className="border-t border-gray-200 pt-4 pb-3">
            {user ? (
              <MobileProfileMenu user={user} />
            ) : !isLoadingUser ? (
              <div className="px-4">
                <DisclosureButton
                  as="a"
                  href="/api/auth/signin"
                  className="block w-full rounded-md bg-primary px-3 py-2 text-center text-base font-medium text-white hover:bg-primary/90"
                >
                  Sign in
                </DisclosureButton>
              </div>
            ) : null}
          </div>
        </DisclosurePanel>
      </Disclosure>

      <main>
        <div className="mx-auto max-w-7xl p-4 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
