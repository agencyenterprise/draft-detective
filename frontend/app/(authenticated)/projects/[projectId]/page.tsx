'use client';

import { ResultsVisualization } from '@/components/wizard/results-step/results-visualization';
import { useWorkflowProgressToast } from '@/hooks/use-workflow-progress-toast';
import { DocRenderMode } from '@/lib/constants';
import { ProjectDetailed, updateProjectEndpointApiProjectProjectIdPatch } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { isAnyWorkflowProcessing, needsWizardCompletion } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const queryClient = useQueryClient();

  // Skip redirect check if coming from wizard (prevents race condition)
  const fromWizard = searchParams.get('fromWizard') === 'true';

  const [viewMode, setViewMode] = useState<DocRenderMode>('markdown');

  const { project, workflowDetails, isLoading, error } = useProjectDetails(projectId);

  const isProcessing = isAnyWorkflowProcessing(workflowDetails);

  // Redirect to wizard step 2 if project only has document processing started
  // Skip if we just came from the wizard (workflows may not be in DB yet)
  useEffect(() => {
    if (!fromWizard && !isLoading && workflowDetails.length > 0 && needsWizardCompletion(workflowDetails)) {
      router.replace(`/new?projectId=${projectId}`);
    }
  }, [fromWizard, isLoading, workflowDetails, projectId, router]);

  // Show progress in toast when workflows are processing
  useWorkflowProgressToast(projectId, isProcessing);

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
