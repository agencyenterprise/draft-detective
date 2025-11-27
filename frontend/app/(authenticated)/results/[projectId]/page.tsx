'use client';

import { EditableTitle } from '@/components/ui/editable-title';
import { PublicationDateLabel } from '@/components/wizard/results-step/components/publication-date-label';
import { TabType } from '@/components/wizard/results-step/constants';
import { ResultsVisualization } from '@/components/wizard/results-step/results-visualization';
import { projectsApi } from '@/lib/api';
import { DocRenderMode } from '@/lib/constants';
import { ProjectDetailed, WorkflowRunStatus } from '@/lib/generated-api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export default function ResultsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<TabType>('document-explorer');
  const [viewMode, setViewMode] = useState<DocRenderMode>('markdown');

  const {
    data: project,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['project', projectId],
    refetchInterval: ({ state }) => (state.data?.workflowRun?.run.status === WorkflowRunStatus.Running ? 3000 : false),
    queryFn: () => projectsApi.getProjectEndpointApiProjectProjectIdGet({ projectId }),
  });

  const isProcessing = project?.workflowRun?.run.status === WorkflowRunStatus.Running;

  const updateTitleMutation = useMutation({
    mutationFn: async (newTitle: string) => {
      return await projectsApi.updateProjectEndpointApiProjectProjectIdPatch({
        projectId,
        updateProjectRequest: { title: newTitle },
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

  useEffect(() => {
    let toastId: string | number | undefined;
    if (isProcessing) {
      toastId = toast.loading('Analysis in progress', {
        description: 'Results will update automatically as sections complete',
      });
    }

    return () => {
      if (toastId) {
        toast.dismiss(toastId);
      }
    };
  }, [isProcessing]);

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

  const authors = project.workflowRun?.state?.mainDocumentSummary?.authors;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <hgroup className="w-full space-y-1">
          <EditableTitle
            title={project.project.title}
            titleClassName="text-xl font-bold"
            onSave={handleTitleSave}
            isLoading={updateTitleMutation.isPending}
          />
          <h2 className="text-muted-foreground text-sm">
            {authors && <span>{authors} — </span>}
            <PublicationDateLabel results={project.workflowRun?.state} prefix="Published" suffix=" — " />
            <span>Analysis created {format(project.project.createdAt || new Date(), 'MMM d, yyyy')}</span>
          </h2>
        </hgroup>
      </div>

      <ResultsVisualization
        projectId={projectId}
        results={project.workflowRun?.state || undefined}
        isProcessing={isProcessing}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
    </div>
  );
}
