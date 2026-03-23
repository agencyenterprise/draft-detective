'use client';

import { Button } from '@/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { listUsersApiUsersGet, UserResponse } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronsUpDown } from 'lucide-react';
import { useState } from 'react';
import { useDebounce } from 'use-debounce';

const ALL_VALUE = '__all__';

interface UserComboboxProps {
  value: string;
  displayName: string;
  onSelect: (userId: string, userName: string) => void;
  className?: string;
}

export function UserCombobox({ value, displayName, onSelect, className }: UserComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search, 400);

  const { data: users } = useQuery({
    queryKey: ['admin', 'users', debouncedSearch],
    queryFn: () => listUsersApiUsersGet({ query: { search: debouncedSearch || undefined, limit: 20 } }),
    enabled: open,
  });

  const handleSelect = (userId: string, userName: string) => {
    onSelect(userId, userName);
    setSearch('');
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={`w-[200px] justify-between font-normal ${className ?? ''}`}
        >
          <span className="truncate">{displayName || 'All users'}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[260px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Search users…" value={search} onValueChange={setSearch} />
          <CommandList>
            <CommandEmpty>No users found.</CommandEmpty>
            <CommandGroup>
              <CommandItem value={ALL_VALUE} onSelect={() => handleSelect(ALL_VALUE, '')}>
                <Check className={`mr-2 h-4 w-4 ${value === ALL_VALUE ? 'opacity-100' : 'opacity-0'}`} />
                All users
              </CommandItem>
              {users?.map((u: UserResponse) => (
                <CommandItem key={u.id} value={u.id} onSelect={() => handleSelect(u.id, u.name)}>
                  <Check className={`mr-2 h-4 w-4 ${value === u.id ? 'opacity-100' : 'opacity-0'}`} />
                  <div className="flex flex-col min-w-0">
                    <span className="truncate">{u.name}</span>
                    <span className="text-xs text-muted-foreground truncate">{u.email}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
