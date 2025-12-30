import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';

interface WorkflowStatusConfig {
  type: WorkflowRunType;
  status?: WorkflowRunStatus;
  messages: {
    running?: string;
    pending?: string;
    completed?: string;
  };
}

interface UseWorkflowStatusNotificationsProps {
  workflows: WorkflowStatusConfig[];
  onCompleted?: (type: WorkflowRunType) => void;
}

/**
 * Custom hook to handle workflow status notifications with toast messages.
 * Tracks status changes and shows appropriate messages for each workflow.
 */
export function useWorkflowStatusNotifications({ workflows, onCompleted }: UseWorkflowStatusNotificationsProps) {
  const prevStatusesRef = useRef<Map<WorkflowRunType, WorkflowRunStatus>>(new Map());

  useEffect(() => {
    workflows.forEach((workflow) => {
      const { type, status, messages } = workflow;
      if (!status) return;

      const prevStatus = prevStatusesRef.current.get(type);

      // Show status-specific messages
      if (status === WorkflowRunStatus.Running && messages.running) {
        toast.info(messages.running, { id: `${type}-progress` });
      } else if (status === WorkflowRunStatus.Pending && messages.pending) {
        toast.info(messages.pending, { id: `${type}-progress` });
      }

      // Handle completion
      if (status === WorkflowRunStatus.Completed && prevStatus !== WorkflowRunStatus.Completed) {
        toast.dismiss(`${type}-progress`);
        if (messages.completed) {
          toast.success(messages.completed);
        }
        onCompleted?.(type);
      }

      prevStatusesRef.current.set(type, status);
    });
  }, [workflows, onCompleted]);
}
