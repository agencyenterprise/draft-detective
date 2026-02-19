'use client';

import type { FeedbackResponse } from '@/lib/generated-api';
import { createContext, useContext, useMemo } from 'react';

/**
 * Map from "workflowRunId:serializedEntityPath" to FeedbackResponse
 */
export type FeedbackLookupMap = Map<string, FeedbackResponse>;

export interface FeedbackContextValue {
  feedbackMap: FeedbackLookupMap;
}

export const FeedbackContext = createContext<FeedbackContextValue | null>(null);

/**
 * Generates a stable lookup key for a feedback entry.
 */
export function makeFeedbackKey(workflowRunId: string, entityPath: Record<string, unknown>): string {
  const sortedPath = JSON.stringify(entityPath, Object.keys(entityPath).sort());
  return `${workflowRunId}:${sortedPath}`;
}

/**
 * Builds a FeedbackLookupMap from an array of FeedbackResponse objects
 * (as returned in ProjectDetailed.feedbacks).
 */
export function buildFeedbackMap(feedbacks: FeedbackResponse[]): FeedbackLookupMap {
  const map: FeedbackLookupMap = new Map();
  for (const fb of feedbacks) {
    const key = makeFeedbackKey(fb.workflow_run_id, fb.entity_path);
    map.set(key, fb);
  }
  return map;
}

/**
 * Hook to build a FeedbackContextValue from project feedbacks.
 * Memoises the map so it only rebuilds when feedbacks change.
 */
export function useProjectFeedbackMap(feedbacks: FeedbackResponse[]): FeedbackContextValue {
  const feedbackMap = useMemo(() => buildFeedbackMap(feedbacks), [feedbacks]);
  return { feedbackMap };
}

/**
 * Hook to access feedback context.
 * Returns null if not inside a FeedbackProvider.
 */
export function useFeedbackContext(): FeedbackContextValue | null {
  return useContext(FeedbackContext);
}
