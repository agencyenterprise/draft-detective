'use client';

import { cn } from '@/lib/utils';
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react';
import { LogInIcon, MenuIcon, XIcon } from 'lucide-react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '../ui/button';
import { MobileProfileMenu, ProfileDropdown } from './profile-dropdown';

const navigation = [
  { name: 'Projects', href: '/projects' },
  { name: 'About', href: '/about' },
];

export interface ApplicationShellProps {
  children: React.ReactNode;
}

export function ApplicationShell({ children }: ApplicationShellProps) {
  const session = useSession();
  const isLoadingUser = session.status === 'loading';
  const user = session.data?.user;
  const pathname = usePathname();

  const navigationWithCurrent = navigation.map((item) => ({
    ...item,
    current: pathname.startsWith(item.href),
  }));

  if (pathname.startsWith('/addin') || pathname.startsWith('/stitch') || pathname.startsWith('/prototype')) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-full">
      <Disclosure as="nav" className="border-b border-border bg-background">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-15 justify-between">
            <div className="flex">
              <div className="flex shrink-0 items-center">
                <Link href="/" className="text-xl font-bold text-primary">
                  Draft Detective
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
                        ? 'border-primary text-foreground'
                        : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground',
                      'inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium text',
                    )}
                  >
                    {item.name}
                  </a>
                ))}
              </div>
              <div className="hidden sm:ml-8 sm:flex sm:items-center">
                <Button asChild size="sm" variant="outline">
                  <Link href="/new">Start new project</Link>
                </Button>
              </div>
            </div>
            <div className="hidden sm:ml-6 sm:flex sm:items-center sm:gap-3">
              {user ? (
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
              <DisclosureButton className="group relative inline-flex items-center justify-center rounded-md bg-background p-2 text-muted-foreground hover:bg-accent hover:text-foreground focus:outline-2 focus:outline-offset-2 focus:outline-primary">
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
                    : 'border-transparent text-muted-foreground hover:border-border hover:bg-accent hover:text-foreground',
                  'block border-l-4 py-2 pr-4 pl-3 text-base font-medium',
                )}
              >
                {item.name}
              </DisclosureButton>
            ))}
          </div>
          <div className="border-t border-border pt-4 pb-3">
            <div className="px-4 pb-3">
              <DisclosureButton
                as="a"
                href="/new"
                className="block w-full rounded-md bg-primary px-3 py-2 text-center text-base font-medium text-primary-foreground hover:bg-primary/90"
              >
                Start new project
              </DisclosureButton>
            </div>
            {user ? (
              <MobileProfileMenu user={user} />
            ) : !isLoadingUser ? (
              <div className="px-4">
                <DisclosureButton
                  as="a"
                  href="/api/auth/signin"
                  className="block w-full rounded-md bg-primary px-3 py-2 text-center text-base font-medium text-primary-foreground hover:bg-primary/90"
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
