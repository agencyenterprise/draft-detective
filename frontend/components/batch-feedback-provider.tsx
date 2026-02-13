'use client';

import { BatchFeedbackContext, useBatchFeedback } from '@/lib/hooks/use-batch-feedback';
import type { ReactNode } from 'react';

interface BatchFeedbackProviderProps {
  workflowRunIds: string[];
  children: ReactNode;
}

/**
 * Wraps children with batch feedback context.
 *
 * Fetches ALL feedback for the given workflow run IDs in a single request
 * per workflow run, then provides a lookup map via context so that
 * individual useFeedback() calls don't make separate HTTP requests.
 */
export function BatchFeedbackProvider({ workflowRunIds, children }: BatchFeedbackProviderProps) {
  const batchFeedback = useBatchFeedback(workflowRunIds);

  return <BatchFeedbackContext.Provider value={batchFeedback}>{children}</BatchFeedbackContext.Provider>;
}
