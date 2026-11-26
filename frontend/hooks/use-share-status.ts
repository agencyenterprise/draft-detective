import {
  disableProjectSharingApiProjectsProjectIdShareDisablePost,
  enableProjectSharingApiProjectsProjectIdShareEnablePost,
  ProjectOverview,
  ShareStatusResponse,
} from '@/lib/generated-api';
import { projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useToastMutation } from '@/lib/hooks/use-toast-mutation';
import { writeServerAnswerAndRefresh } from '@/lib/query-cache';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

/** The project's public link, read from the overview (the owner's only) and managed from here. */
export function useShareStatus(overview: ProjectOverview) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const projectId = overview.project.id;

  // The overview is cached per revision, and the link is the project's, so every copy gets it.
  const applyShareStatus = (shareStatus: ShareStatusResponse) =>
    writeServerAnswerAndRefresh<ProjectOverview>(
      queryClient,
      { queryKey: projectQueryKeys.overviews(projectId) },
      (overview) => overview && { ...overview, share_status: shareStatus },
    );

  const enableMutation = useToastMutation({
    mutationFn: () => enableProjectSharingApiProjectsProjectIdShareEnablePost({ path: { project_id: projectId } }),
    errorMessage: 'Failed to enable sharing',
    onSuccess: applyShareStatus,
    onError: () => setIsDialogOpen(false),
  });

  const disableMutation = useToastMutation({
    mutationFn: () => disableProjectSharingApiProjectsProjectIdShareDisablePost({ path: { project_id: projectId } }),
    successMessage: 'Sharing disabled. All existing links are now invalid.',
    errorMessage: 'Failed to disable sharing',
    onSuccess: (data) => {
      applyShareStatus(data);
      setIsDialogOpen(false);
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
