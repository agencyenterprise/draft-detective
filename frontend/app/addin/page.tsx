'use client';

import { Button } from '@/components/ui/button';
import { DocumentExplorerSidebarFilter } from '@/components/results/components/document-explorer-sidebar-filter';
import { DocumentIssuesList } from '@/components/results/components/document-issues-list';
import { addIssueMarkers, jumpToIssue } from '@/lib/addin/office-utils';
import { useOfficeInit } from '@/lib/addin/use-office-init';
import { ProjectFeedbackProvider } from '@/lib/contexts/project-feedback-context';
import { getSharedResourceApiPublicShareTokenGet, Issue } from '@/lib/generated-api';
import {
  DEFAULT_FILTER,
  DocumentExplorerFilter,
  getFilteredIssues,
  getIssueCount,
  getPassingCount,
  getResolvedCount,
  getVisibleIssues,
  hasActiveFilters,
} from '@/lib/stores/document-explorer-store';
import { useQuery } from '@tanstack/react-query';
import { RotateCwIcon } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

export default function AddinPage() {
  const { token, currentParagraphIndex, isInitialized } = useOfficeInit();
  const [issuesPerParagraph, setIssuesPerParagraph] = useState<Map<number, Issue[]>>(new Map());
  const [filter, setFilter] = useState<DocumentExplorerFilter>(DEFAULT_FILTER);
  const updateFilter = (partial: Partial<DocumentExplorerFilter>) => setFilter((prev) => ({ ...prev, ...partial }));

  const {
    data: project,
    isLoading,
    error,
    refetch,
  } = useQuery({
    enabled: !!token,
    queryKey: ['share', token],
    // Cache for 10 minutes
    staleTime: 60 * 1000 * 10,
    queryFn: () =>
      getSharedResourceApiPublicShareTokenGet({
        path: { token: token! },
      }),
  });

  useEffect(() => {
    if (project?.issues?.length) {
      addIssueMarkers(project.issues)
        .then(setIssuesPerParagraph)
        .catch((e) => console.error('Error adding markers', e));
    }
  }, [project]);

  const paragraphIssues = useMemo(() => {
    if (!project?.issues || currentParagraphIndex === null) return [];
    return issuesPerParagraph.get(currentParagraphIndex) ?? [];
  }, [project, currentParagraphIndex, issuesPerParagraph]);

  const activeIssues = useMemo(
    () => (paragraphIssues.length > 0 ? paragraphIssues : (project?.issues ?? [])),
    [paragraphIssues, project],
  );
  const isParagraphView = paragraphIssues.length > 0;

  const visibleIssues = useMemo(() => getVisibleIssues(activeIssues, filter), [activeIssues, filter]);
  const resolvedCount = useMemo(() => getResolvedCount(activeIssues, null), [activeIssues]);
  const passingCount = useMemo(() => getPassingCount(activeIssues), [activeIssues]);
  const filteredIssues = useMemo(() => getFilteredIssues(visibleIssues, filter, null), [visibleIssues, filter]);

  const visibleIssueCount = getIssueCount(visibleIssues);
  const filteredIssueCount = getIssueCount(filteredIssues);

  const [scrollContainer, setScrollContainer] = useState<HTMLDivElement | null>(null);

  if (!isInitialized) return <div className="p-4 text-center">Loading Add-in...</div>;

  if (!token) {
    return (
      <div className="min-h-screen bg-muted p-4 flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-sm text-muted-foreground max-w-md">
            No project associated with this document.
          </div>
        </div>
      </div>
    );
  }

  return (
    <ProjectFeedbackProvider projectId={undefined} feedbackVisibility={null}>
      <div className="flex flex-col h-screen bg-card">
        <div className="border-b p-3 flex flex-col items-center bg-muted">
          <div className="flex items-center justify-between gap-2 w-full">
            <h1 className="font-semibold text-sm">Review Issues</h1>
            <Button variant="ghost" size="icon" onClick={() => refetch()} disabled={isLoading} title="Refresh">
              <RotateCwIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          <div className="flex items-center justify-between gap-2 w-full flex-wrap">
            <span className="text-xs text-muted-foreground">
              {visibleIssueCount > 0 &&
                (filteredIssueCount === visibleIssueCount
                  ? `${visibleIssueCount} issues`
                  : `${filteredIssueCount} of ${visibleIssueCount} issues`)}
            </span>
            {project?.issues && project.issues.length > 0 && (
              <div className="text-right flex flex-row flex-wrap gap-1">
                {isParagraphView && (
                  <Button variant="outline" size="sm" className="text-xs h-6 px-2 gap-1 shadow-xs bg-card">
                    Paragraph #{currentParagraphIndex}
                  </Button>
                )}
                <DocumentExplorerSidebarFilter
                  issues={isParagraphView ? paragraphIssues : project.issues}
                  filter={filter}
                  onFilterChange={updateFilter}
                  resolvedCount={resolvedCount}
                  passingCount={passingCount}
                />
              </div>
            )}
          </div>
        </div>

        <div ref={setScrollContainer} className="flex-1 overflow-y-auto p-2 space-y-4 text-sm">
          {error ? (
            <div className="text-red-500 text-sm">Failed to load issues. Please check your settings.</div>
          ) : null}

          {isLoading ? (
            <div className="text-sm text-muted-foreground">Loading...</div>
          ) : (
            <>
              <DocumentIssuesList
                issues={filteredIssues}
                scrollElement={scrollContainer}
                onSelect={(issue) => jumpToIssue(issue)}
              />
              {hasActiveFilters(filter) && filteredIssues.length === 0 && (
                <div className="text-xs text-muted-foreground pt-2 mt-2">No issues found for your filters</div>
              )}
            </>
          )}
        </div>
      </div>
    </ProjectFeedbackProvider>
  );
}
