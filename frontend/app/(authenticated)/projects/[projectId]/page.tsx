'use client';

import { ResultsVisualization } from '@/components/results/results-visualization';
import { useWorkflowProgressToast } from '@/hooks/use-workflow-progress-toast';
import { getErrorMessage, isApiError } from '@/lib/api-error';
import { AccessLevel, ProjectDetailed, updateProjectEndpointApiProjectProjectIdPatch } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { isAnyWorkflowProcessing, needsHumanApproval, needsWizardCompletion } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FileXIcon, LockIcon } from 'lucide-react';
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
  const { workflowTypes } = useWorkflowTypes();

  const isProcessing = isAnyWorkflowProcessing(workflowDetails);
  const awaitingHumanApproval = needsHumanApproval(workflowDetails);
  // HumanApproval stays Pending/Running until the user approves, which keeps isProcessing true even though
  // the pipeline is intentionally paused. The progress API then has no active step → "Going to next step...".
  const showWorkflowProgressToast = isProcessing && !awaitingHumanApproval;

  // Build internal types set from API data
  const internalTypes = useMemo(() => {
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
  }, [fromWizard, isLoading, workflowDetails, projectId, router, internalTypes]);

  // Show progress in toast when automated workflows are running (not while waiting on reference review / approve)
  useWorkflowProgressToast(projectId, showWorkflowProgressToast);

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
      toast.error(`Failed to update title: ${getErrorMessage(error, 'Unknown error')}`);
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

  if (isApiError(error, 403)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center max-w-sm">
          <LockIcon className="h-10 w-10 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">Access Denied</h2>
          <p className="text-muted-foreground text-sm">
            You don&apos;t have permission to view this project. Contact the project owner to request access.
          </p>
        </div>
      </div>
    );
  }

  if (isApiError(error, 404)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center max-w-sm">
          <FileXIcon className="h-10 w-10 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold mb-2">Project Not Found</h2>
          <p className="text-muted-foreground text-sm">This project doesn&apos;t exist or may have been deleted.</p>
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

  const isReadOnly = project.access_level !== AccessLevel.Write;

  return (
    <ResultsVisualization
      projectDetail={project}
      readOnly={isReadOnly}
      onTitleSave={isReadOnly ? undefined : handleTitleSave}
      isTitleSaving={isReadOnly ? undefined : updateTitleMutation.isPending}
      needsReferenceReview={!isReadOnly && needsHumanApproval(workflowDetails)}
    />
  );
}
