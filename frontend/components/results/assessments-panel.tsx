'use client';

import { useProjectView } from '@/components/results/project-view-context';
import { formatLineHash } from '@/lib/line-hash';
import { useDocumentExplorerStore } from '@/lib/stores/document-explorer-store';
import { AssessmentsTab } from './assessments/assessments-tab';

/** The assessments tab as a tab panel, taking its project from the shell. */
export function AssessmentsPanel() {
  const { overview, readOnly, navigateToTab } = useProjectView();
  const setFilter = useDocumentExplorerStore((s) => s.setFilter);

  return (
    <AssessmentsTab
      overview={overview}
      readOnly={readOnly}
      onNavigateToDocumentExplorer={(lineRange) => {
        setFilter({ workflowType: [] });
        navigateToTab('document-explorer', formatLineHash(lineRange));
      }}
      onNavigateToReferences={() => navigateToTab('references')}
    />
  );
}
