'use client';

import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { UserRole } from '@/lib/generated-api';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { Menu, MenuButton, MenuItem, MenuItems, MenuSection, MenuSeparator } from '@headlessui/react';
import { ChevronDown } from 'lucide-react';
import Image from 'next/image';
import { Switch } from '../ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

const userNavigation = [
  { name: 'Settings', href: '/account' },
  { name: 'MCP Server', href: '/connect' },
  { name: 'Help improve accuracy', href: '/annotate' },
  // An explicit destination: without one, Auth.js returns to whatever the last sign-in
  // asked for, which after a Word add-in sign-in on this domain is the add-in's page.
  { name: 'Sign out', href: '/api/auth/signout?callbackUrl=%2F' },
];
const adminNavigation = [
  { name: 'Usage Dashboard', href: '/dashboard' },
  { name: 'Manage Users', href: '/users' },
  { name: 'User Feedback', href: '/feedbacks' },
  { name: 'Annotation Results', href: '/annotation-results' },
  { name: 'Logs', href: '/logs' },
];

interface User {
  name?: string | null;
  email?: string | null;
  image?: string | null;
}

interface ProfileDropdownProps {
  user: User;
}

/** Avatar diameter in px. */
const AVATAR_SIZE = 26;

/** Initials from a name or email, for accounts with no picture. */
function initialsOf(name?: string | null, email?: string | null): string {
  const source = name?.trim() || email?.split('@')[0] || '';
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return '?';
  return (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase();
}

export function ProfileDropdown({ user }: ProfileDropdownProps) {
  const { showExperimentalFeatures, setShowExperimentalFeatures, isUpdating } = useExperimentalFeatures();
  const { data: userMe } = useUserMe();

  return (
    <Menu as="div" className="relative ml-3">
      <MenuButton className="relative flex max-w-xs items-center gap-1 rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
        <span className="absolute -inset-1.5" />
        <span className="sr-only">Open user menu</span>
        {user.image ? (
          <Image
            alt={user.name ?? 'User'}
            src={user.image}
            className="rounded-full outline -outline-offset-1 outline-black/5"
            width={AVATAR_SIZE}
            height={AVATAR_SIZE}
            style={{ width: AVATAR_SIZE, height: AVATAR_SIZE }}
          />
        ) : (
          <span
            aria-hidden
            className="flex items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground"
            style={{ width: AVATAR_SIZE, height: AVATAR_SIZE, fontSize: Math.round(AVATAR_SIZE * 0.4) }}
          >
            {initialsOf(user.name, user.email)}
          </span>
        )}
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </MenuButton>

      <MenuItems
        transition
        className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-popover py-1 shadow-lg outline outline-border transition data-closed:scale-95 data-closed:transform data-closed:opacity-0 data-enter:duration-200 data-enter:ease-out data-leave:duration-75 data-leave:ease-in"
      >
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <MenuItem>
                <label className="flex items-center justify-between px-4 py-2 text-sm text-popover-foreground cursor-pointer data-focus:bg-accent data-focus:outline-hidden">
                  <span>Alpha features</span>
                  <Switch
                    checked={showExperimentalFeatures}
                    onCheckedChange={setShowExperimentalFeatures}
                    disabled={isUpdating}
                  />
                </label>
              </MenuItem>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs">
              Enable early access to new features that are still in development. These may be unstable or change without
              notice.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <MenuSeparator className="my-1 h-px bg-border" />
        {userNavigation.map((item) => (
          <MenuItem key={item.name}>
            <a
              href={item.href}
              className="block px-4 py-2 text-sm text-popover-foreground data-focus:bg-accent data-focus:outline-hidden"
            >
              {item.name}
            </a>
          </MenuItem>
        ))}
        {userMe?.role === UserRole.Admin && (
          <>
            <MenuSeparator className="my-1 h-px bg-border" />

            <MenuSection>
              <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Admin only
              </div>
              {adminNavigation.map((item) => (
                <MenuItem key={item.name}>
                  <a
                    href={item.href}
                    className="block px-4 py-2 text-sm text-popover-foreground data-focus:bg-accent data-focus:outline-hidden"
                  >
                    {item.name}
                  </a>
                </MenuItem>
              ))}
            </MenuSection>
          </>
        )}
      </MenuItems>
    </Menu>
  );
}
