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
import { ReactNode, useState } from 'react';
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
import { projectQueryKeys } from '@/lib/hooks/use-project-data';

export interface StartWorkflowButtonProps {
  type: WorkflowRunType;
  projectId: string;
  workflow?: WorkflowRun;
  onConfirm: (values: WorkflowConfigFormValues) => Promise<unknown>;
  /** Overrides the idle label, e.g. "Re-run Abbreviation Scan". */
  startLabel?: ReactNode;
  /** Shown on hover while the button is idle. */
  tooltip?: React.ReactNode;
}

export function StartWorkflowButton({
  type,
  projectId,
  workflow,
  onConfirm,
  startLabel,
  tooltip,
}: StartWorkflowButtonProps) {
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
        queryKey: projectQueryKeys.all(projectId),
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
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all(projectId) });
    },
    onError: (error) => {
      console.error(`Failed to cancel ${workflowName} workflow:`, error);
      toast.error(getErrorMessage(error, `Failed to cancel ${workflowName} workflow`));
    },
  });

  const isActive = workflow?.status === WorkflowRunStatus.Running || workflow?.status === WorkflowRunStatus.Pending;

  const startButton = (
    <Button
      size="xs"
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
          {startLabel ?? `Start ${workflowName}`}
        </>
      )}
    </Button>
  );

  return (
    <>
      <AlertDialog open={isCancelDialogOpen} onOpenChange={setIsCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel {workflowName}?</AlertDialogTitle>
            <AlertDialogDescription>
              This stops the run in progress. Any assessment waiting on it is cancelled too. You can run it again at any
              time.
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
        {tooltip && !startWorkflowMutation.isPending && !isActive ? (
          <Tooltip>
            <TooltipTrigger asChild>{startButton}</TooltipTrigger>
            <TooltipContent className="max-w-xs">{tooltip}</TooltipContent>
          </Tooltip>
        ) : (
          startButton
        )}

        {isActive && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setIsCancelDialogOpen(true)}
                disabled={cancelWorkflowMutation.isPending}
              >
                {cancelWorkflowMutation.isPending ? <Loader2Icon className="animate-spin" /> : <XIcon />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Cancel this run</TooltipContent>
          </Tooltip>
        )}
      </div>
    </>
  );
}
