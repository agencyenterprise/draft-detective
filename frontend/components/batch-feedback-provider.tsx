'use client';

import type { FeedbackResponse } from '@/lib/generated-api';
import { FeedbackContext, useProjectFeedbackMap } from '@/lib/hooks/use-batch-feedback';
import type { ReactNode } from 'react';

interface FeedbackProviderProps {
  feedbacks: FeedbackResponse[];
  children: ReactNode;
}

/**
 * Provides pre-loaded project feedback to descendant components via context.
 *
 * Receives the feedbacks array from ProjectDetailed and builds a lookup map
 * so that individual useFeedback() calls can resolve feedback in O(1)
 * without any additional HTTP requests.
 */
export function FeedbackProvider({ feedbacks, children }: FeedbackProviderProps) {
  const value = useProjectFeedbackMap(feedbacks);
  return <FeedbackContext.Provider value={value}>{children}</FeedbackContext.Provider>;
}
