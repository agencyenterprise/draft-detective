import { disableSharing, enableSharing, getShareStatus } from '@/lib/services/share-service';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';

export function useShareStatus(projectId: string) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['shareStatus', projectId],
    queryFn: () => getShareStatus(projectId),
    staleTime: 30000,
  });

  const enableMutation = useMutation({
    mutationFn: () => enableSharing(projectId),
    onSuccess: (data) => {
      queryClient.setQueryData(['shareStatus', projectId], data);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to enable sharing');
      setIsDialogOpen(false);
    },
  });

  const disableMutation = useMutation({
    mutationFn: () => disableSharing(projectId),
    onSuccess: (data) => {
      queryClient.setQueryData(['shareStatus', projectId], data);
      setIsDialogOpen(false);
      toast.success('Sharing disabled. All existing links are now invalid.');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to disable sharing');
    },
  });

  return {
    isEnabled: query.data?.enabled ?? false,
    shareStatus: query.data ?? null,
    isDialogOpen,
    setIsDialogOpen,
    isEnabling: enableMutation.isPending,
    isDisabling: disableMutation.isPending,
    enable: () => enableMutation.mutate(),
    disable: () => disableMutation.mutate(),
  };
}
