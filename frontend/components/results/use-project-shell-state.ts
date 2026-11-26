'use client';

import { AccessLevel } from '@/lib/generated-api';
import { useProjectOverview } from '@/lib/hooks/use-project-data';
import { useUpdateProject } from '@/lib/hooks/use-update-project';
import { useCallback, useState } from 'react';

/**
 * Everything the project chrome needs that is not chrome: the project itself,
 * which revision is being viewed, and saving the title.
 */
export function useProjectShellState(projectId: string) {
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

  const updateTitleMutation = useUpdateProject(projectId, {
    successMessage: 'Title updated successfully',
    errorMessage: 'Failed to update title',
  });

  const handleTitleSave = useCallback(
    async (newTitle: string) => {
      await updateTitleMutation.mutateAsync({ title: newTitle });
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
