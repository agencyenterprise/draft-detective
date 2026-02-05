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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { listUsersApiUsersGet, updateRoleApiUsersUserIdRolePatch, UserResponse, UserRole } from '@/lib/generated-api';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2, ShieldCheck, ShieldQuestion, User } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { toast } from 'sonner';

interface PendingRoleChange {
  user: UserResponse;
  newRole: UserRole;
}

export function UsersList() {
  const session = useSession();
  const [pendingChange, setPendingChange] = useState<PendingRoleChange | null>(null);

  const {
    data: users,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['admin', 'users'],
    enabled: !!session.data?.user,
    queryFn: () => listUsersApiUsersGet(),
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      updateRoleApiUsersUserIdRolePatch({
        path: { user_id: userId },
        body: { role },
      }),
    onSuccess: async (updatedUser) => {
      await refetch();
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

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>User Management</CardTitle>
          <CardDescription>Manage user roles and permissions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>User Management</CardTitle>
          <CardDescription>Manage user roles and permissions</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p className="text-destructive">{error.message}</p>
            <Button variant="outline" onClick={() => window.location.reload()} className="mt-4">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>User Management</CardTitle>
          <CardDescription>
            {users?.length ?? 0} user{users?.length !== 1 ? 's' : ''} registered
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!users || users.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">No users found</div>
          ) : (
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
