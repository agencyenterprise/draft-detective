'use client';

import { AssessmentsPanel } from '@/components/results/assessments-panel';
import { ReactNode } from 'react';

/**
 * The assessments tab lives in the layout, not the pages, so that picking an
 * assessment (which changes the `[workflowType]` segment) swaps the page but
 * leaves the rail mounted: its scroll offset and folded sections survive.
 */
export default function AnalysesLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <AssessmentsPanel />
      {children}
    </>
  );
}
