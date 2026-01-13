'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getWorkflowProgressEndpointApiProgressWorkflowWorkflowRunIdProgressGet } from '@/lib/generated-api';
import {
  getProgressStatus,
  ToastContent,
  LoadingToastContent,
} from '@/components/workflows/workflow-progress-toast-content';

const REFETCH_INTERVAL_MS = 2000;
const TOAST_ID = 'workflow-progress';

export function useWorkflowProgressToast(workflowRunIds: string[]) {
  const sortedIds = useMemo(() => [...workflowRunIds].sort(), [workflowRunIds]);
  const [showCompleted, setShowCompleted] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [newlyCompletedIds, setNewlyCompletedIds] = useState<Set<string>>(new Set());
  const prevCompletedIdsRef = useRef<Set<string>>(new Set());
  const isActiveRef = useRef(false);

  const { data: allProgress } = useQuery({
    queryKey: ['workflows-progress', sortedIds.join(',')],
    queryFn: async () => {
      if (sortedIds.length === 0) return [];

      const results = await Promise.all(
        sortedIds.map((id) =>
          getWorkflowProgressEndpointApiProgressWorkflowWorkflowRunIdProgressGet({
            path: { workflow_run_id: id },
          }),
        ),
      );

      return results.flat().sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    },
    enabled: sortedIds.length > 0,
    refetchInterval: REFETCH_INTERVAL_MS,
  });

  useEffect(() => {
    if (!allProgress) return;

    const currentCompleted = new Set(allProgress.filter((p) => getProgressStatus(p) === 'completed').map((p) => p.id));
    const newIds = [...currentCompleted].filter((id) => !prevCompletedIdsRef.current.has(id));

    prevCompletedIdsRef.current = currentCompleted;

    if (newIds.length > 0) {
      setNewlyCompletedIds((prev) => new Set([...prev, ...newIds]));
      const timer = setTimeout(() => {
        setNewlyCompletedIds((prev) => {
          const next = new Set(prev);
          newIds.forEach((id) => next.delete(id));
          return next;
        });
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [allProgress]);

  useEffect(() => {
    const hasWorkflows = sortedIds.length > 0;

    if (hasWorkflows && !isActiveRef.current) {
      isActiveRef.current = true;
    }

    if (!hasWorkflows && isActiveRef.current) {
      toast.dismiss(TOAST_ID);
      isActiveRef.current = false;
      setShowCompleted(false);
      setShowAll(false);
      return;
    }

    if (!hasWorkflows) return;

    const hasProgress = allProgress && allProgress.length > 0;

    toast.custom(
      () =>
        hasProgress ? (
          <ToastContent
            progress={allProgress}
            newlyCompletedIds={newlyCompletedIds}
            showCompleted={showCompleted}
            showAll={showAll}
            onToggleCompleted={() => setShowCompleted((p) => !p)}
            onShowAll={() => setShowAll(true)}
          />
        ) : (
          <LoadingToastContent />
        ),
      { id: TOAST_ID, duration: Infinity },
    );
  }, [sortedIds, allProgress, newlyCompletedIds, showCompleted, showAll]);

  useEffect(() => {
    return () => {
      toast.dismiss(TOAST_ID);
    };
  }, []);
}
