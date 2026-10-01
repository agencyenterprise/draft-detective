'use client';

import { useProjectView } from '@/components/results/project-view-context';
import { ReferencesTab } from './references/references-tab';

/** The references tab as a tab panel, taking its project from the shell. */
export function ReferencesPanel() {
  const { overview, readOnly } = useProjectView();

  return <ReferencesTab overview={overview} readOnly={readOnly} />;
}
