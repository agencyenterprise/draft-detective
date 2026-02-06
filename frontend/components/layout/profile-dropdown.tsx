'use client';

import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { UserRole } from '@/lib/generated-api';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { DisclosureButton, Menu, MenuButton, MenuItem, MenuItems, MenuSection, MenuSeparator } from '@headlessui/react';
import Image from 'next/image';
import { Switch } from '../ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

const userNavigation = [{ name: 'Sign out', href: '/api/auth/signout' }];
const adminNavigation = [
  { name: 'Evaluations', href: '/evals' },
  { name: 'Manage Users', href: '/users' },
];

interface User {
  name?: string | null;
  email?: string | null;
  image?: string | null;
}

interface ProfileDropdownProps {
  user: User;
}

export function ProfileDropdown({ user }: ProfileDropdownProps) {
  const { showExperimentalFeatures, setShowExperimentalFeatures, isUpdating } = useExperimentalFeatures();
  const { data: userMe } = useUserMe();

  return (
    <Menu as="div" className="relative ml-3">
      <MenuButton className="relative flex max-w-xs items-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">
        <span className="absolute -inset-1.5" />
        <span className="sr-only">Open user menu</span>
        <Image
          alt={user.name ?? 'User'}
          src={user.image ?? 'https://ui-avatars.com/api/?name=' + user.name}
          className="size-8 rounded-full outline -outline-offset-1 outline-black/5"
          width={32}
          height={32}
        />
      </MenuButton>

      <MenuItems
        transition
        className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white py-1 shadow-lg outline outline-black/5 transition data-closed:scale-95 data-closed:transform data-closed:opacity-0 data-enter:duration-200 data-enter:ease-out data-leave:duration-75 data-leave:ease-in"
      >
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <MenuItem>
                <label className="flex items-center justify-between px-4 py-2 text-sm text-gray-700 cursor-pointer data-focus:bg-gray-100 data-focus:outline-hidden">
                  <span>Experimental features</span>
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
        <MenuSeparator className="my-1 h-px bg-gray-200" />
        {userNavigation.map((item) => (
          <MenuItem key={item.name}>
            <a
              href={item.href}
              className="block px-4 py-2 text-sm text-gray-700 data-focus:bg-gray-100 data-focus:outline-hidden"
            >
              {item.name}
            </a>
          </MenuItem>
        ))}
        {userMe?.role === UserRole.Admin && (
          <>
            <MenuSeparator className="my-1 h-px bg-gray-200" />

            <MenuSection>
              <div className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">Admin only</div>
              {adminNavigation.map((item) => (
                <MenuItem key={item.name}>
                  <a
                    href={item.href}
                    className="block px-4 py-2 text-sm text-gray-700 data-focus:bg-gray-100 data-focus:outline-hidden"
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

interface MobileProfileMenuProps {
  user: User;
}

export function MobileProfileMenu({ user }: MobileProfileMenuProps) {
  const { showExperimentalFeatures, setShowExperimentalFeatures, isUpdating } = useExperimentalFeatures();
  const { data: userMe } = useUserMe();

  return (
    <>
      <div className="flex items-center px-4">
        <div className="shrink-0">
          <Image
            alt={user.name ?? 'User'}
            src={user.image ?? 'https://ui-avatars.com/api/?name=' + user.name}
            className="size-10 rounded-full outline -outline-offset-1 outline-black/5"
            width={40}
            height={40}
          />
        </div>
        <div className="ml-3">
          <div className="text-base font-medium text-gray-800">{user.name}</div>
          <div className="text-sm font-medium text-gray-500">{user.email}</div>
        </div>
      </div>
      <div className="mt-3 space-y-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <label className="flex items-center justify-between px-4 py-2 text-base font-medium text-gray-500 cursor-pointer">
                <span>Experimental features</span>
                <Switch
                  checked={showExperimentalFeatures}
                  onCheckedChange={setShowExperimentalFeatures}
                  disabled={isUpdating}
                />
              </label>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs">
              Enable early access to new features that are still in development. These may be unstable or change without
              notice.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <div className="my-2 h-px bg-gray-200 mx-4" />
        {userNavigation.map((item) => (
          <DisclosureButton
            key={item.name}
            as="a"
            href={item.href}
            className="block px-4 py-2 text-base font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
          >
            {item.name}
          </DisclosureButton>
        ))}

        {userMe?.role === UserRole.Admin && (
          <>
            <div className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">Admin only</div>
            {adminNavigation.map((item) => (
              <DisclosureButton
                key={item.name}
                as="a"
                href={item.href}
                className="block px-4 py-2 text-base font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
              >
                {item.name}
              </DisclosureButton>
            ))}
            <div className="my-2 h-px bg-gray-200 mx-4" />
          </>
        )}
      </div>
    </>
  );
}
