import { WorkflowRun, WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowTypeName } from '@/lib/workflow-state';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2Icon, PlayIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from './workflow-config-dialog';

export interface StartWorkflowButtonProps {
  type: WorkflowRunType;
  projectId: string;
  workflow?: WorkflowRun;
  onConfirm: (values: WorkflowConfigFormValues) => Promise<unknown>;
}

export function StartWorkflowButton({ type, projectId, workflow, onConfirm }: StartWorkflowButtonProps) {
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const workflowName = getWorkflowTypeName(type);

  const startWorkflowMutation = useMutation({
    mutationFn: async (values: WorkflowConfigFormValues) => {
      return onConfirm(values);
    },
    onSuccess: () => {
      setIsConfigDialogOpen(false);
      toast.success(`${workflowName} workflow started`);
      // Invalidate project/workflow queries to refresh state
      queryClient.invalidateQueries({
        queryKey: ['project', projectId],
      });
      if (workflow) {
        queryClient.invalidateQueries({
          queryKey: ['workflowRun', workflow.id],
        });
      }
    },
    onError: (error) => {
      console.error(`Failed to start ${workflowName} workflow:`, error);
      toast.error(error instanceof Error ? error.message : `Failed to start ${workflowName} workflow`);
    },
  });

  const publicationDate = type === WorkflowRunType.LiteratureReview || type === WorkflowRunType.LiveReports;
  const webSearchConsent =
    type === WorkflowRunType.LiteratureReview ||
    type === WorkflowRunType.MethodologicalAlignment ||
    type === WorkflowRunType.ReferenceDownloader ||
    type === WorkflowRunType.LiveReports ||
    type === WorkflowRunType.ReferenceValidation;

  return (
    <>
      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        webSearchConsent={webSearchConsent}
        publicationDate={publicationDate}
        onConfirm={(values) => startWorkflowMutation.mutate(values)}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <Button
        size="sm"
        variant="outline"
        onClick={() => setIsConfigDialogOpen(true)}
        disabled={startWorkflowMutation.isPending || workflow?.status === WorkflowRunStatus.Running}
      >
        {startWorkflowMutation.isPending ? (
          <>
            <Loader2Icon className="animate-spin" />
            Starting...
          </>
        ) : workflow?.status === WorkflowRunStatus.Running ? (
          <>
            <Loader2Icon className="animate-spin" />
            Running...
          </>
        ) : (
          <>
            <PlayIcon />
            Start {workflowName}
          </>
        )}
      </Button>
    </>
  );
}
