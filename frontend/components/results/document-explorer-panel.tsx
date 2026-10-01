'use client';

import { useProjectView } from '@/components/results/project-view-context';
import { useProjectDocument, useProjectIssues } from '@/lib/hooks/use-project-data';
import { DocumentExplorerTab } from './document-explorer/document-explorer-tab';
import { TabLoading } from './tab-loading';

/**
 * The document explorer as a tab panel. Everything around it — title, tabs,
 * revision switcher, the banners — comes from ProjectShell. The document and
 * its issues are fetched here, so the tab mounts with both in hand and its
 * line-hash navigation has something to land on.
 */
export function DocumentExplorerPanel() {
  const { overview, readOnly, navigateToTab } = useProjectView();
  const { data: document, error: documentError } = useProjectDocument(overview);
  const { data: issues, error: issuesError } = useProjectIssues(overview);

  const error = documentError ?? issuesError;
  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-sm text-destructive">Could not load the document: {error.message}</p>
      </div>
    );
  }

  if (!document || !issues) {
    return <TabLoading label="Loading document..." />;
  }

  return (
    <DocumentExplorerTab
      overview={overview}
      document={document}
      issues={issues}
      // The shell's read-only covers older revisions as well as projects that
      // aren't the reader's, which is what starting a run has to answer to:
      // the start API targets the project's current revision, not the one on
      // screen. Rating and resolving issues is a separate question, answered
      // inside the tab by the access level.
      canRunAssessments={!readOnly}
      onNavigateToAnalyses={() => navigateToTab('analyses')}
    />
  );
}
