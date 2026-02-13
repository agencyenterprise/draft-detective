'use client';

import type { FeedbackResponse } from '@/lib/generated-api';
import { getWorkflowFeedbackApiFeedbackWorkflowWorkflowRunIdGet } from '@/lib/generated-api';
import { useQueries } from '@tanstack/react-query';
import { createContext, useContext, useMemo } from 'react';

/**
 * Map from "workflowRunId:serializedEntityPath" to FeedbackResponse
 */
export type FeedbackLookupMap = Map<string, FeedbackResponse>;

export interface BatchFeedbackContextValue {
  feedbackMap: FeedbackLookupMap;
  isLoading: boolean;
}

export const BatchFeedbackContext = createContext<BatchFeedbackContextValue | null>(null);

/**
 * Generates a stable lookup key for a feedback entry
 */
export function makeFeedbackKey(workflowRunId: string, entityPath: Record<string, unknown>): string {
  const sortedPath = JSON.stringify(entityPath, Object.keys(entityPath).sort());
  return `${workflowRunId}:${sortedPath}`;
}

/**
 * Hook that fetches all feedback for multiple workflow runs in batch.
 * Returns a lookup map for O(1) access by workflowRunId + entityPath.
 *
 * Use this with BatchFeedbackContext.Provider to avoid N+1 feedback requests.
 */
export function useBatchFeedback(workflowRunIds: string[]): BatchFeedbackContextValue {
  const uniqueIds = useMemo(() => [...new Set(workflowRunIds.filter(Boolean))], [workflowRunIds]);

  const queries = useQueries({
    queries: uniqueIds.map((id) => ({
      queryKey: ['workflow-feedback', id],
      queryFn: async () => {
        try {
          return await getWorkflowFeedbackApiFeedbackWorkflowWorkflowRunIdGet({
            path: { workflow_run_id: id },
          });
        } catch {
          return [] as FeedbackResponse[];
        }
      },
      staleTime: 30_000,
    })),
  });

  const isLoading = queries.some((q) => q.isLoading);

  const feedbackMap = useMemo(() => {
    const map: FeedbackLookupMap = new Map();

    for (const query of queries) {
      const feedbacks = query.data;
      if (!feedbacks) continue;

      for (const fb of feedbacks) {
        const key = makeFeedbackKey(fb.workflow_run_id, fb.entity_path);
        map.set(key, fb);
      }
    }

    return map;
  }, [queries]);

  return { feedbackMap, isLoading };
}

/**
 * Hook to access batch feedback context.
 * Returns null if not inside a BatchFeedbackProvider (falls back to individual requests).
 */
export function useBatchFeedbackContext(): BatchFeedbackContextValue | null {
  return useContext(BatchFeedbackContext);
}
