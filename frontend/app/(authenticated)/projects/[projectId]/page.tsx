'use client';

import { ResultsVisualization } from '@/components/results/results-visualization';
import { useWorkflowProgressToast } from '@/hooks/use-workflow-progress-toast';
import { ProjectDetailed, updateProjectEndpointApiProjectProjectIdPatch, WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { isAnyWorkflowProcessing, needsHumanApproval, needsWizardCompletion } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo } from 'react';
import { toast } from 'sonner';

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const queryClient = useQueryClient();

  // Skip redirect check if coming from wizard (prevents race condition)
  const fromWizard = searchParams.get('fromWizard') === 'true';

  const { project, workflowDetails, isLoading, error } = useProjectDetails(projectId);
  const { data: workflowTypes } = useWorkflowTypes();

  const isProcessing = isAnyWorkflowProcessing(workflowDetails);

  // Build internal types set from API data
  const internalTypes = useMemo(() => {
    if (!workflowTypes) return new Set<WorkflowRunType>();
    return new Set(workflowTypes.filter((wt) => wt.is_internal).map((wt) => wt.type));
  }, [workflowTypes]);

  // Redirect to wizard step 2 if project only has document processing started
  // Skip if we just came from the wizard (workflows may not be in DB yet)
  useEffect(() => {
    if (fromWizard || isLoading || workflowDetails.length === 0) {
      return;
    }

    if (needsWizardCompletion(workflowDetails, internalTypes)) {
      router.replace(`/new?projectId=${projectId}`);
      return;
    }

    if (needsHumanApproval(workflowDetails)) {
      router.replace(`/new?projectId=${projectId}&step=3`);
      return;
    }
  }, [fromWizard, isLoading, workflowDetails, projectId, router, internalTypes]);

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
      onTitleSave={handleTitleSave}
      isTitleSaving={updateTitleMutation.isPending}
    />
  );
}
