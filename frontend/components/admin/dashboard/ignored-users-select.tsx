'use client';

import { Button } from '@/components/ui/button';
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { DashboardIgnoredUser, listUsersApiUsersGet, UserResponse } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronsUpDown, Loader2, UserX } from 'lucide-react';
import { useState } from 'react';
import { useDebounce } from 'use-debounce';

interface IgnoredUsersSelectProps {
  /** The users currently left out of the figures. */
  value: DashboardIgnoredUser[];
  onChange: (users: DashboardIgnoredUser[]) => void;
}

function toIgnoredUser(user: UserResponse): DashboardIgnoredUser {
  return { user_id: user.id, name: user.name, email: user.email };
}

/**
 * Picks the users whose activity the dashboard should leave out.
 *
 * Multi-select over the user directory: the current selection is listed first
 * so it can be unpicked without searching for it, and everyone else is one
 * search away.
 */
export function IgnoredUsersSelect({ value, onChange }: IgnoredUsersSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search, 400);

  const { data: users, isFetching } = useQuery({
    queryKey: ['admin', 'users', debouncedSearch],
    queryFn: () => listUsersApiUsersGet({ query: { search: debouncedSearch || undefined, limit: 20 } }),
    enabled: open,
  });

  const selectedIds = new Set(value.map((user) => user.user_id));
  const candidates = (users ?? []).filter((user) => !selectedIds.has(user.id));

  const remove = (userId: string) => onChange(value.filter((user) => user.user_id !== userId));
  const add = (user: UserResponse) => onChange([...value, toIgnoredUser(user)]);

  const label =
    value.length === 0 ? 'Ignore users' : `Ignoring ${value.length} ${value.length === 1 ? 'user' : 'users'}`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          role="combobox"
          aria-expanded={open}
          aria-label="Choose users to leave out of the figures"
          className="bg-background font-normal shadow-xs"
        >
          <UserX className="h-4 w-4 text-muted-foreground" />
          <span className="text-xs">{label}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0" align="end">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Search users…" value={search} onValueChange={setSearch} />
          <CommandList>
            {value.length > 0 && (
              <CommandGroup heading="Ignored">
                {value.map((user) => (
                  <CommandItem
                    key={user.user_id}
                    value={`ignored:${user.user_id}`}
                    onSelect={() => remove(user.user_id)}
                  >
                    <Check className="mr-2 h-4 w-4" />
                    <UserLine name={user.name} email={user.email} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            <CommandGroup heading="Everyone else">
              {candidates.map((user) => (
                <CommandItem key={user.id} value={user.id} onSelect={() => add(user)}>
                  <span className="mr-2 h-4 w-4" aria-hidden />
                  <UserLine name={user.name} email={user.email} />
                </CommandItem>
              ))}
              {candidates.length === 0 && (
                <p className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
                  {isFetching ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
                    </>
                  ) : (
                    'No users found.'
                  )}
                </p>
              )}
            </CommandGroup>
          </CommandList>
          {value.length > 0 && (
            <div className="border-t p-1">
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center text-xs text-muted-foreground"
                onClick={() => onChange([])}
              >
                Count everyone
              </Button>
            </div>
          )}
        </Command>
      </PopoverContent>
    </Popover>
  );
}

function UserLine({ name, email }: { name: string; email: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="truncate">{name}</span>
      <span className="truncate text-xs text-muted-foreground">{email}</span>
    </div>
  );
}
