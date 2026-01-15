'use client';

import { ResultsVisualization } from '@/components/wizard/results-step/results-visualization';
import { useWorkflowProgressToast } from '@/hooks/use-workflow-progress-toast';
import { DocRenderMode } from '@/lib/constants';
import { ProjectDetailed, updateProjectEndpointApiProjectProjectIdPatch } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { isAnyWorkflowProcessing } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

export default function ResultsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const queryClient = useQueryClient();

  const [viewMode, setViewMode] = useState<DocRenderMode>('markdown');

  const { project, workflowDetails, isLoading, error } = useProjectDetails(projectId);

  const workflowRunIdsToTrack = useMemo(() => {
    if (!isAnyWorkflowProcessing(workflowDetails)) return [];

    return workflowDetails.map((w) => w.run.id);
  }, [workflowDetails]);

  // Show progress in toast
  useWorkflowProgressToast(workflowRunIdsToTrack);

  const updateTitleMutation = useMutation({
    mutationFn: async (newTitle: string) => {
      return await updateProjectEndpointApiProjectProjectIdPatch({
        path: { project_id: projectId },
        body: { title: newTitle },
      });
    },
    onSuccess: (updatedProject) => {
      queryClient.setQueryData(['project', projectId], (curr: ProjectDetailed | undefined) => {
        if (!curr) return curr;
        return {
          ...curr,
          project: updatedProject,
        };
      });
      toast.success('Title updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update title: ${error instanceof Error ? error.message : 'Unknown error'}`);
    },
  });

  const handleTitleSave = async (newTitle: string) => {
    await updateTitleMutation.mutateAsync(newTitle);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading project...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive mb-4">{error.message}</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return null;
  }

  return (
    <ResultsVisualization
      projectDetail={project}
      viewMode={viewMode}
      onViewModeChange={setViewMode}
      onTitleSave={handleTitleSave}
      isTitleSaving={updateTitleMutation.isPending}
    />
  );
}
