'use client';

import { Issue, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { useLineHashNavigation } from '@/lib/chunk-ids';
import {
  getFilteredIssues,
  getHighlightIssues,
  getPassingCount,
  getResolvedCount,
  getVisibleIssues,
  useDocumentExplorerStore,
} from '@/lib/stores/document-explorer-store';
import {
  getWorkflowErrors,
  getWorkflowRunByType,
  isAnyWorkflowProcessing,
  isWorkflowProcessing,
} from '@/lib/workflow-state';
import { AlertTriangleIcon, Loader2 } from 'lucide-react';
import { useCallback, useMemo, useRef } from 'react';
import { DocumentExplorerSidebar, DocumentExplorerSidebarHandle } from '../components/document-explorer-sidebar';
import { DocumentMarkdownRenderer, DocumentMarkdownRendererHandle } from '../components/document-markdown-renderer';

interface DocumentExplorerTabProps {
  projectDetail: ProjectDetailed;
  readOnly?: boolean;
  onNavigateToAnalyses: () => void;
}

type IssueWithLines = Issue & { start_line?: number | null; end_line?: number | null };

function getIssueLineRange(issue: Issue): [number, number] | null {
  const { start_line, end_line } = issue as IssueWithLines;
  if (typeof start_line !== 'number' || typeof end_line !== 'number') return null;
  return [start_line, end_line];
}

export function DocumentExplorerTab({
  projectDetail,
  readOnly = false,
  onNavigateToAnalyses,
}: DocumentExplorerTabProps) {
  const { selectedLineRange, selectLineRange, clearLineSelection, filter } = useDocumentExplorerStore();

  const mainDocumentMarkdown = projectDetail.main_document_markdown ?? '';

  const workflowDetails = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const issues = useMemo(() => projectDetail.issues ?? [], [projectDetail.issues]);

  const documentProcessing = getWorkflowRunByType(workflowDetails, WorkflowRunType.DocumentProcessing);
  const isDocumentProcessing = isWorkflowProcessing(documentProcessing);
  const isAnyProcessing = isAnyWorkflowProcessing(workflowDetails);

  const sidebarRef = useRef<DocumentExplorerSidebarHandle>(null);
  const markdownRef = useRef<DocumentMarkdownRendererHandle>(null);

  const workflowErrors = useMemo(() => getWorkflowErrors(workflowDetails), [workflowDetails]);
  const visibleIssues = useMemo(() => getVisibleIssues(issues, filter), [issues, filter]);
  const resolvedCount = useMemo(() => getResolvedCount(issues, selectedLineRange), [issues, selectedLineRange]);
  const passingCount = useMemo(() => getPassingCount(issues), [issues]);
  const filteredIssues = useMemo(
    () => getFilteredIssues(visibleIssues, filter, selectedLineRange),
    [visibleIssues, filter, selectedLineRange],
  );
  const highlightIssues = useMemo(() => getHighlightIssues(visibleIssues, filter), [visibleIssues, filter]);

  useLineHashNavigation(selectLineRange);

  const handleSelectIssue = useCallback(
    (issue: Issue) => {
      const range = getIssueLineRange(issue);
      if (range) {
        selectLineRange(range);
        sidebarRef.current?.scrollToIssue(issue);
        markdownRef.current?.scrollToLineRange(range);
      } else {
        clearLineSelection();
      }
    },
    [selectLineRange, clearLineSelection],
  );

  const handleClearSelection = useCallback(() => {
    clearLineSelection();
  }, [clearLineSelection]);

  const handleIssueSelectFromMarkdown = useCallback(
    (issue: Issue | null) => {
      if (!issue) {
        clearLineSelection();
        return;
      }
      const range = getIssueLineRange(issue);
      if (range) {
        selectLineRange(range);
        sidebarRef.current?.scrollToIssue(issue);
      }
    },
    [selectLineRange, clearLineSelection],
  );

  if (isDocumentProcessing && !mainDocumentMarkdown) {
    return (
      <div className="space-y-4">
        {workflowErrors.length > 0 && (
          <div className="bg-red-200/40 p-4 rounded-lg text-sm">
            <div className="flex items-center gap-2">
              <AlertTriangleIcon className="w-4 h-4" />
              <span className="font-medium">Unexpected processing errors occurred.</span>
              <span>Please check the</span>
              <button
                onClick={onNavigateToAnalyses}
                className="text-blue-600 hover:text-blue-800 underline font-medium"
              >
                Assessments tab
              </button>
              <span>for details.</span>
            </div>
          </div>
        )}
        <div className="flex items-center justify-center py-12">
          <div className="text-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
            <p className="text-sm text-muted-foreground">Processing document(s)...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {workflowErrors.length > 0 && (
        <div className="mb-4 bg-red-200/40 py-3 px-4 rounded-lg text-sm">
          <div className="flex items-center gap-2">
            <AlertTriangleIcon className="w-4 h-4" />
            <span className="font-medium">Unexpected processing errors occurred.</span>
            <span>Please check the</span>
            <button
              onClick={onNavigateToAnalyses}
              className="text-blue-600 hover:text-blue-800 underline font-medium cursor-pointer"
            >
              Assessments tab
            </button>
            <span>for details.</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-12 flex-1 min-h-0">
        <div className="col-span-7 leading-relaxed text-sm overflow-hidden flex flex-col">
          <div className="flex-1 overflow-hidden">
            <DocumentMarkdownRenderer
              ref={markdownRef}
              markdown={mainDocumentMarkdown}
              issues={highlightIssues}
              selectedLineRange={selectedLineRange}
              onIssueSelect={handleIssueSelectFromMarkdown}
            />
          </div>
        </div>

        <DocumentExplorerSidebar
          ref={sidebarRef}
          visibleIssues={visibleIssues}
          filteredIssues={filteredIssues}
          resolvedCount={resolvedCount}
          passingCount={passingCount}
          isAnyProcessing={isAnyProcessing}
          projectDetail={projectDetail}
          readOnly={readOnly}
          onSelectIssue={handleSelectIssue}
          onClearSelection={handleClearSelection}
        />
      </div>
    </div>
  );
}
