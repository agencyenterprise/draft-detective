import {
  cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost,
  WorkflowRun,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2Icon, PlayIcon, XIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '../ui/tooltip';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from './workflow-config-dialog';

export interface StartWorkflowButtonProps {
  type: WorkflowRunType;
  projectId: string;
  workflow?: WorkflowRun;
  onConfirm: (values: WorkflowConfigFormValues) => Promise<unknown>;
}

export function StartWorkflowButton({ type, projectId, workflow, onConfirm }: StartWorkflowButtonProps) {
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);
  const [isCancelDialogOpen, setIsCancelDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { getWorkflowTypeName } = useWorkflowTypes();
  const workflowName = getWorkflowTypeName(type);

  const startWorkflowMutation = useMutation({
    mutationFn: async (values: WorkflowConfigFormValues) => {
      return onConfirm(values);
    },
    onSuccess: () => {
      setIsConfigDialogOpen(false);
      toast.success(`${workflowName} workflow started`);
      queryClient.invalidateQueries({
        queryKey: ['project', projectId],
      });
    },
    onError: (error) => {
      console.error(`Failed to start ${workflowName} workflow:`, error);
      toast.error(getErrorMessage(error, `Failed to start ${workflowName} workflow`));
    },
  });

  const cancelWorkflowMutation = useMutation({
    mutationFn: () =>
      cancelWorkflowRunEndpointApiWorkflowRunsWorkflowRunIdCancelPost({
        path: { workflow_run_id: workflow!.id },
      }),
    onSuccess: () => {
      toast.success(`${workflowName} workflow cancelled`);
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
    onError: (error) => {
      console.error(`Failed to cancel ${workflowName} workflow:`, error);
      toast.error(getErrorMessage(error, `Failed to cancel ${workflowName} workflow`));
    },
  });

  const isActive = workflow?.status === WorkflowRunStatus.Running || workflow?.status === WorkflowRunStatus.Pending;

  return (
    <>
      <AlertDialog open={isCancelDialogOpen} onOpenChange={setIsCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel {workflowName} workflow?</AlertDialogTitle>
            <AlertDialogDescription>
              This will stop the currently running workflow. Any other workflows that depend on it will also be
              cancelled. You can retrigger it at any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep running</AlertDialogCancel>
            <AlertDialogAction onClick={() => cancelWorkflowMutation.mutate()}>Yes, cancel</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        type={type}
        projectId={projectId}
        onConfirm={(values) => startWorkflowMutation.mutate(values)}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <div className="flex items-center gap-1">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setIsConfigDialogOpen(true)}
          disabled={startWorkflowMutation.isPending || isActive}
        >
          {startWorkflowMutation.isPending ? (
            <>
              <Loader2Icon className="animate-spin" />
              Starting...
            </>
          ) : isActive ? (
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

        {isActive && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                className=""
                onClick={() => setIsCancelDialogOpen(true)}
                disabled={cancelWorkflowMutation.isPending}
              >
                {cancelWorkflowMutation.isPending ? <Loader2Icon className="animate-spin" /> : <XIcon />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Cancel workflow</TooltipContent>
          </Tooltip>
        )}
      </div>
    </>
  );
}
