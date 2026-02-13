'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { DocumentIssuesList } from '@/components/wizard/results-step/components/document-issues-list';
import { ProjectFeedbackProvider } from '@/lib/contexts/project-feedback-context';
import { DocumentExplorerSidebarFilter } from '@/components/wizard/results-step/components/document-explorer-sidebar-filter';
import { filterIssuesBySeverity } from '@/components/wizard/results-step/components/severity-filter';
import { filterIssuesByWorkflowType } from '@/components/wizard/results-step/components/workflow-type-filter';
import { Issue, getSharedResourceApiPublicShareTokenGet, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { isIssueResolved } from '@/lib/severity';
import { addIssueMarkers, jumpToChunk } from '@/lib/addin/office-utils';
import { useOfficeInit } from '@/lib/addin/use-office-init';
import { RotateCwIcon } from 'lucide-react';

export default function AddinPage() {
  const { token, currentParagraphIndex, isInitialized } = useOfficeInit();
  const [issuesPerParagraph, setIssuesPerParagraph] = useState<Map<number, Issue[]>>(new Map());
  const [severityFilter, setSeverityFilter] = useState<SeverityEnum[]>([]);
  const [workflowTypeFilter, setWorkflowTypeFilter] = useState<WorkflowRunType[]>([]);
  const [showResolved, setShowResolved] = useState(false);

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

  const resolvedCount = useMemo(() => activeIssues.filter(isIssueResolved).length, [activeIssues]);

  const filteredIssues = useMemo(() => {
    let result = filterIssuesByWorkflowType(filterIssuesBySeverity(activeIssues, severityFilter), workflowTypeFilter);
    if (!showResolved) {
      result = result.filter((issue) => !isIssueResolved(issue));
    }
    return result;
  }, [activeIssues, severityFilter, workflowTypeFilter, showResolved]);

  const hasActiveFilters = severityFilter.length > 0 || workflowTypeFilter.length > 0 || !showResolved;

  if (!isInitialized) return <div className="p-4 text-center">Loading Add-in...</div>;

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 p-4 flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-sm text-gray-600 max-w-md">No project associated with this document.</div>
        </div>
      </div>
    );
  }

  return (
    <ProjectFeedbackProvider projectId={undefined}>
      <div className="flex flex-col h-screen bg-white">
        <div className="border-b p-3 flex flex-col items-center bg-gray-50">
          <div className="flex items-center justify-between gap-2 w-full">
            <h1 className="font-semibold text-sm">Review Issues</h1>
            <Button variant="ghost" size="icon" onClick={() => refetch()} disabled={isLoading} title="Refresh">
              <RotateCwIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          <div className="flex items-center justify-between gap-2 w-full flex-wrap">
            <span className="text-xs text-muted-foreground">
              {project?.issues &&
                project.issues.length > 0 &&
                (filteredIssues.length === project.issues.length
                  ? `${project.issues.length} issues`
                  : `${filteredIssues.length} of ${project.issues.length} issues`)}
            </span>
            {project?.issues && project.issues.length > 0 && (
              <div className="text-right flex flex-row flex-wrap gap-1">
                {isParagraphView && (
                  <Button variant="outline" size="sm" className="text-xs h-6 px-2 gap-1 shadow-xs bg-white">
                    Paragraph #{currentParagraphIndex}
                  </Button>
                )}
                <DocumentExplorerSidebarFilter
                  issues={isParagraphView ? paragraphIssues : project.issues}
                  severityFilter={severityFilter}
                  onSeverityFilterChange={setSeverityFilter}
                  workflowTypeFilter={workflowTypeFilter}
                  onWorkflowTypeFilterChange={setWorkflowTypeFilter}
                  resolvedCount={resolvedCount}
                  showResolved={showResolved}
                  onShowResolvedChange={setShowResolved}
                />
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-4 text-sm">
          {error ? (
            <div className="text-red-500 text-sm">Failed to load issues. Please check your settings.</div>
          ) : null}

          {isLoading ? (
            <div className="text-sm text-gray-500">Loading...</div>
          ) : (
            <>
              <DocumentIssuesList
                issues={filteredIssues}
                onSelect={(issue) => jumpToChunk(issue.chunk_index ?? issue.chunk_indices?.[0] ?? 0)}
                jumpToAlias="paragraph"
              />
              {hasActiveFilters && filteredIssues.length === 0 && (
                <div className="text-xs text-gray-500 pt-2 mt-2">No issues found for your filters</div>
              )}
            </>
          )}
        </div>
      </div>
    </ProjectFeedbackProvider>
  );
}
