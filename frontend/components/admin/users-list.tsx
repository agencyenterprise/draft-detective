'use client';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { listUsersApiUsersGet, updateRoleApiUsersUserIdRolePatch, UserResponse, UserRole } from '@/lib/generated-api';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Loader2, Search, ShieldCheck, ShieldQuestion, User } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { toast } from 'sonner';
import { useDebounce } from 'use-debounce';

const PAGE_SIZE = 25;

interface PendingRoleChange {
  user: UserResponse;
  newRole: UserRole;
}

export function UsersList() {
  const session = useSession();
  const queryClient = useQueryClient();
  const [pendingChange, setPendingChange] = useState<PendingRoleChange | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch] = useDebounce(searchQuery, 400);
  const [selectedRole, setSelectedRole] = useState<UserRole | 'all'>('all');

  const {
    data: usersData,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['admin', 'users-list', debouncedSearch, selectedRole],
    enabled: !!session.data?.user,
    queryFn: ({ pageParam }) =>
      listUsersApiUsersGet({
        query: {
          search: debouncedSearch || undefined,
          role: selectedRole !== 'all' ? selectedRole : undefined,
          limit: PAGE_SIZE,
          offset: pageParam,
        },
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || lastPage.length < PAGE_SIZE) return undefined;
      return allPages.reduce((acc, page) => acc + page.length, 0);
    },
  });

  const users = usersData?.pages.flat() ?? [];

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      updateRoleApiUsersUserIdRolePatch({
        path: { user_id: userId },
        body: { role },
      }),
    onSuccess: async (updatedUser) => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users-list'] });
      toast.success(`Updated ${updatedUser.name}'s role to ${updatedUser.role}`);
      setPendingChange(null);
    },
    onError: (error) => {
      toast.error(`Failed to update role: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setPendingChange(null);
    },
  });

  const handleRoleSelectChange = (user: UserResponse, newRole: UserRole) => {
    if (newRole !== user.role) {
      setPendingChange({ user, newRole });
    }
  };

  const confirmRoleChange = () => {
    if (pendingChange) {
      updateRoleMutation.mutate({ userId: pendingChange.user.id, role: pendingChange.newRole });
    }
  };

  const cancelRoleChange = () => {
    setPendingChange(null);
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>User Management</CardTitle>
          <CardDescription>
            {isLoading ? 'Loading…' : `Showing ${users.length} user${users.length !== 1 ? 's' : ''}`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="Search by name or email…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={selectedRole} onValueChange={(v) => setSelectedRole(v as UserRole | 'all')}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="All roles" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All roles</SelectItem>
                <SelectItem value={UserRole.User}>User</SelectItem>
                <SelectItem value={UserRole.Rand}>Rand</SelectItem>
                <SelectItem value={UserRole.Admin}>Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-destructive">{error.message}</p>
              <Button variant="outline" onClick={() => window.location.reload()} className="mt-4">
                Retry
              </Button>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">No users found</div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead className="w-[180px]">Change Role</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {user.role === UserRole.Admin ? (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <ShieldCheck className="h-4 w-4 text-primary cursor-help" />
                              </TooltipTrigger>
                              <TooltipContent>Administrator</TooltipContent>
                            </Tooltip>
                          ) : user.role === UserRole.Rand ? (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <ShieldQuestion className="h-4 w-4 text-blue-600 cursor-help" />
                              </TooltipTrigger>
                              <TooltipContent>Rand User</TooltipContent>
                            </Tooltip>
                          ) : (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <User className="h-4 w-4 text-muted-foreground cursor-help" />
                              </TooltipTrigger>
                              <TooltipContent>Regular User</TooltipContent>
                            </Tooltip>
                          )}
                          <span className="font-medium">{user.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{user.email}</TableCell>
                      <TableCell>
                        <span
                          className={
                            user.role === UserRole.Admin
                              ? 'text-primary font-medium'
                              : user.role === UserRole.Rand
                                ? 'text-blue-600 font-medium'
                                : 'text-muted-foreground'
                          }
                        >
                          {user.role}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Select
                          value={user.role}
                          onValueChange={(value) => handleRoleSelectChange(user, value as UserRole)}
                          disabled={updateRoleMutation.isPending}
                        >
                          <SelectTrigger className="w-[140px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value={UserRole.User}>User</SelectItem>
                            <SelectItem value={UserRole.Rand}>Rand</SelectItem>
                            <SelectItem value={UserRole.Admin}>Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {hasNextPage && (
                <div className="flex justify-center pt-2">
                  <Button variant="outline" size="sm" onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
                    {isFetchingNextPage ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <ChevronDown className="h-4 w-4 mr-2" />
                    )}
                    Load more
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!pendingChange} onOpenChange={(open) => !open && cancelRoleChange()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Role Change</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to change <strong>{pendingChange?.user.name}</strong>&apos;s role from{' '}
              <strong>{pendingChange?.user.role}</strong> to <strong>{pendingChange?.newRole}</strong>?
              {pendingChange?.newRole === UserRole.Admin && (
                <span className="block mt-2 text-amber-600">
                  Warning: This will grant full administrative privileges to this user.
                </span>
              )}
              {pendingChange?.newRole === UserRole.Rand && (
                <span className="block mt-2 text-blue-600">Note: This will grant access to QA Screener workflows.</span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={updateRoleMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRoleChange} disabled={updateRoleMutation.isPending}>
              {updateRoleMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                'Confirm'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
