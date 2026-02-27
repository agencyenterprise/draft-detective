import { Issue, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { create } from 'zustand';
import { getChunkIssuesByIndices, sortIssueBySeverity } from '../severity';

interface DocumentExplorerState {
  // Chunk selection
  selectedChunkIndices: number[];
  selectChunkIndices: (indices: number[]) => void;
  toggleChunk: (chunkIndex: number) => void;
  clearChunkSelection: () => void;

  // Severity filter
  severityFilter: SeverityEnum[];
  setSeverityFilter: (value: SeverityEnum[]) => void;

  // Workflow type filter
  workflowTypeFilter: WorkflowRunType[];
  setWorkflowTypeFilter: (value: WorkflowRunType[]) => void;

  // Show resolved
  showResolved: boolean;
  setShowResolved: (value: boolean) => void;

  // Reset all filters
  clearFilters: () => void;
}

export const useDocumentExplorerStore = create<DocumentExplorerState>((set) => ({
  // Chunk selection
  selectedChunkIndices: [],
  selectChunkIndices: (indices) => set({ selectedChunkIndices: indices }),
  toggleChunk: (chunkIndex) =>
    set((state) => ({
      selectedChunkIndices:
        state.selectedChunkIndices.length === 1 && state.selectedChunkIndices[0] === chunkIndex ? [] : [chunkIndex],
    })),
  clearChunkSelection: () => set({ selectedChunkIndices: [] }),

  // Severity filter
  severityFilter: [],
  setSeverityFilter: (value) => set({ severityFilter: value }),

  // Workflow type filter
  workflowTypeFilter: [],
  setWorkflowTypeFilter: (value) => set({ workflowTypeFilter: value }),

  // Show resolved
  showResolved: false,
  setShowResolved: (value) => set({ showResolved: value }),

  // Reset all filters
  clearFilters: () =>
    set({
      severityFilter: [],
      workflowTypeFilter: [],
      showResolved: false,
    }),
}));

/**
 * Check if an issue has been resolved.
 */
export function isIssueResolved(issue: Issue): boolean {
  return !!issue.resolved_at;
}

export function getIssuesFilteredBySeverity(issues: Issue[], severityFilter: SeverityEnum[]): Issue[] {
  if (severityFilter.length === 0) return issues;
  return issues.filter((issue) => severityFilter.includes(issue.severity));
}

export function getIssuesFilteredByWorkflowType(issues: Issue[], workflowTypeFilter: WorkflowRunType[]): Issue[] {
  if (workflowTypeFilter.length === 0) return issues;
  return issues.filter((issue) => workflowTypeFilter.includes(issue.workflow_type));
}

export function getVisibleIssues(allIssues: Issue[], showResolved: boolean, selectedChunkIndices: number[]) {
  const nonNoneIssues = allIssues.filter((issue) => issue.severity !== SeverityEnum.None);

  const resolvedCount = nonNoneIssues
    .filter(isIssueResolved)
    .filter(
      (issue) =>
        selectedChunkIndices.length === 0 || selectedChunkIndices.some((idx) => issue.chunk_indices?.includes(idx)),
    ).length;

  const visibleIssues = nonNoneIssues
    .filter((issue) => showResolved || !isIssueResolved(issue))
    .sort((a, b) => (a.chunk_indices?.[0] ?? 0) - (b.chunk_indices?.[0] ?? 0))
    .sort(sortIssueBySeverity);

  return { visibleIssues, resolvedCount };
}

export function getFilteredIssues(
  visibleIssues: Issue[],
  workflowTypeFilter: WorkflowRunType[],
  severityFilter: SeverityEnum[],
  selectedChunkIndices: number[],
): Issue[] {
  let result = getIssuesFilteredBySeverity(
    getIssuesFilteredByWorkflowType(visibleIssues, workflowTypeFilter),
    severityFilter,
  );

  if (selectedChunkIndices.length > 0) {
    result = getChunkIssuesByIndices(result, selectedChunkIndices);
  }

  return result;
}
