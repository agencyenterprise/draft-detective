'use client';

import { getErrorMessage } from '@/lib/api-error';
import { AccessLevel, ProjectOverview, updateProjectEndpointApiProjectProjectIdPatch } from '@/lib/generated-api';
import { projectQueryKeys, useProjectOverview } from '@/lib/hooks/use-project-data';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';
import { toast } from 'sonner';

/**
 * Everything the project chrome needs that is not chrome: the project itself,
 * which revision is being viewed, and saving the title.
 */
export function useProjectShellState(projectId: string) {
  const queryClient = useQueryClient();

  // null means "follow the latest revision"
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null);

  const { data: overview, isLoading, error } = useProjectOverview(projectId, selectedRevision);

  const currentRevision = overview?.project?.current_revision ?? 1;
  const effectiveRevision = selectedRevision ?? currentRevision;

  const handleRevisionChange = useCallback((rev: number) => {
    setSelectedRevision(rev);
  }, []);

  // After a new revision is created, drop back to "follow latest" so the view and
  // switcher move to the newly created revision.
  const handleRevisionCreated = useCallback(() => {
    setSelectedRevision(null);
  }, []);

  const updateTitleMutation = useMutation({
    mutationFn: async (newTitle: string) => {
      return await updateProjectEndpointApiProjectProjectIdPatch({
        path: { project_id: projectId },
        body: { title: newTitle },
      });
    },
    onSuccess: (updatedProject) => {
      // The overview is keyed per revision, so patch every cached revision of it.
      // Only the overviews: the other queries under ['project', id] are not shaped like one.
      queryClient.setQueriesData(
        { queryKey: projectQueryKeys.overviews(projectId) },
        (curr: ProjectOverview | undefined) => (curr ? { ...curr, project: updatedProject } : curr),
      );
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      toast.success('Title updated successfully');
    },
    onError: (mutationError) => {
      toast.error(`Failed to update title: ${getErrorMessage(mutationError, 'Unknown error')}`);
    },
  });

  const handleTitleSave = useCallback(
    async (newTitle: string) => {
      await updateTitleMutation.mutateAsync(newTitle);
    },
    [updateTitleMutation],
  );

  const isReadOnly = overview ? overview.access_level !== AccessLevel.Write : false;
  const isViewingOldRevision = effectiveRevision < currentRevision;

  return {
    overview,
    isLoading,
    error,
    effectiveRevision,
    handleRevisionChange,
    handleRevisionCreated,
    handleTitleSave,
    isTitleSaving: updateTitleMutation.isPending,
    readOnly: isReadOnly || isViewingOldRevision,
    isReadOnly,
    isViewingOldRevision,
  };
}
