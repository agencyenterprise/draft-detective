'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getProjectWorkflowProgressEndpointApiProjectProjectIdWorkflowProgressGet } from '@/lib/generated-api';
import {
  getProgressStatus,
  ToastContent,
  LoadingToastContent,
} from '@/components/workflows/workflow-progress-toast-content';
import { useShare } from '@/context/share-context';

const REFETCH_INTERVAL_MS = 3000;
const TOAST_ID = 'workflow-progress';

export function useWorkflowProgressToast(projectId: string, enabled: boolean = true) {
  const { shareToken } = useShare();
  const [showCompleted, setShowCompleted] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [newlyCompletedIds, setNewlyCompletedIds] = useState<Set<string>>(new Set());
  const seenInProgressRef = useRef<Set<string>>(new Set());
  const isActiveRef = useRef(false);

  const { data: allProgress } = useQuery({
    queryKey: ['project-workflow-progress', projectId],
    queryFn: async () => {
      return getProjectWorkflowProgressEndpointApiProjectProjectIdWorkflowProgressGet({
        path: { project_id: projectId },
        query: { share_token: shareToken },
      });
    },
    enabled,
    refetchInterval: REFETCH_INTERVAL_MS,
  });

  useEffect(() => {
    if (!allProgress) return;

    // Track items currently in progress
    const inProgressIds = allProgress.filter((p) => getProgressStatus(p) === 'in_progress').map((p) => p.id);
    inProgressIds.forEach((id) => seenInProgressRef.current.add(id));

    // Only mark as newly completed if they were previously seen in progress
    const completedIds = allProgress.filter((p) => getProgressStatus(p) === 'completed').map((p) => p.id);
    const newIds = completedIds.filter((id) => seenInProgressRef.current.has(id));

    // Remove completed items from the in-progress tracking
    completedIds.forEach((id) => seenInProgressRef.current.delete(id));

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
    if (enabled && !isActiveRef.current) {
      isActiveRef.current = true;
    }

    if (!enabled && isActiveRef.current) {
      toast.dismiss(TOAST_ID);
      isActiveRef.current = false;
      seenInProgressRef.current = new Set();
      setShowCompleted(false);
      setShowAll(false);
      return;
    }

    if (!enabled) return;

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
  }, [projectId, allProgress, newlyCompletedIds, showCompleted, showAll, enabled]);

  useEffect(() => {
    return () => {
      toast.dismiss(TOAST_ID);
    };
  }, []);
}
