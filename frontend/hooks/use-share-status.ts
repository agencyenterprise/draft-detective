import {
  disableProjectSharingApiProjectsProjectIdShareDisablePost,
  enableProjectSharingApiProjectsProjectIdShareEnablePost,
  getProjectShareStatusApiProjectsProjectIdShareGet,
} from '@/lib/generated-api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';

export function useShareStatus(projectId: string) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['shareStatus', projectId],
    queryFn: () => getProjectShareStatusApiProjectsProjectIdShareGet({ path: { project_id: projectId } }),
    staleTime: 30000,
  });

  const enableMutation = useMutation({
    mutationFn: () => enableProjectSharingApiProjectsProjectIdShareEnablePost({ path: { project_id: projectId } }),
    onSuccess: (data) => {
      queryClient.setQueryData(['shareStatus', projectId], data);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to enable sharing');
      setIsDialogOpen(false);
    },
  });

  const disableMutation = useMutation({
    mutationFn: () => disableProjectSharingApiProjectsProjectIdShareDisablePost({ path: { project_id: projectId } }),
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
