import {
  disableProjectSharingApiProjectsProjectIdShareDisablePost,
  enableProjectSharingApiProjectsProjectIdShareEnablePost,
  ProjectOverview,
  ShareStatusResponse,
} from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';

/** The project's public link, read from the overview (the owner's only) and managed from here. */
export function useShareStatus(overview: ProjectOverview) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const projectId = overview.project.id;

  // The overview is cached per revision, and the link is the project's, so every copy gets it.
  // They are then refreshed: that cancels a poll that left before the change and would land
  // with the old status, and restarts it, so a fetch something else awaits still lands.
  const applyShareStatus = (shareStatus: ShareStatusResponse) => {
    const overviews = { queryKey: projectQueryKeys.overviews(projectId) };
    queryClient.setQueriesData(overviews, (curr: ProjectOverview | undefined) =>
      curr ? { ...curr, share_status: shareStatus } : curr,
    );
    void queryClient.invalidateQueries(overviews);
  };

  const enableMutation = useMutation({
    mutationFn: () => enableProjectSharingApiProjectsProjectIdShareEnablePost({ path: { project_id: projectId } }),
    onSuccess: applyShareStatus,
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to enable sharing'));
      setIsDialogOpen(false);
    },
  });

  const disableMutation = useMutation({
    mutationFn: () => disableProjectSharingApiProjectsProjectIdShareDisablePost({ path: { project_id: projectId } }),
    onSuccess: (data) => {
      applyShareStatus(data);
      setIsDialogOpen(false);
      toast.success('Sharing disabled. All existing links are now invalid.');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to disable sharing'));
    },
  });

  const shareStatus = overview.share_status ?? null;

  return {
    isEnabled: shareStatus?.enabled ?? false,
    shareStatus,
    isDialogOpen,
    setIsDialogOpen,
    isEnabling: enableMutation.isPending,
    isDisabling: disableMutation.isPending,
    enable: () => enableMutation.mutateAsync(),
    disable: () => disableMutation.mutate(),
  };
}
