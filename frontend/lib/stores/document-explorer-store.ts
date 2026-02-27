import { Issue, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { create } from 'zustand';
import { getChunkIssuesByIndices, sortIssueBySeverity } from '../severity';

export interface DocumentExplorerFilter {
  severity: SeverityEnum[];
  workflowType: WorkflowRunType[];
  showResolved: boolean;
  showPassing: boolean;
}

export const DEFAULT_FILTER: DocumentExplorerFilter = {
  severity: [],
  workflowType: [],
  showResolved: false,
  showPassing: false,
};

interface DocumentExplorerState {
  selectedChunkIndices: number[];
  selectChunkIndices: (indices: number[]) => void;
  toggleChunk: (chunkIndex: number) => void;
  clearChunkSelection: () => void;

  filter: DocumentExplorerFilter;
  setFilter: (partial: Partial<DocumentExplorerFilter>) => void;
  clearFilters: () => void;
}

export const useDocumentExplorerStore = create<DocumentExplorerState>((set) => ({
  selectedChunkIndices: [],
  selectChunkIndices: (indices) => set({ selectedChunkIndices: indices }),
  toggleChunk: (chunkIndex) =>
    set((state) => ({
      selectedChunkIndices:
        state.selectedChunkIndices.length === 1 && state.selectedChunkIndices[0] === chunkIndex ? [] : [chunkIndex],
    })),
  clearChunkSelection: () => set({ selectedChunkIndices: [] }),

  filter: DEFAULT_FILTER,
  setFilter: (partial) => set((state) => ({ filter: { ...state.filter, ...partial } })),
  clearFilters: () => set({ filter: DEFAULT_FILTER }),
}));

/**
 * Count of non-passing issues (excludes severity "None").
 * Use for display labels so passing issues don't inflate the count.
 */
export function getIssueCount(issues: Issue[]): number {
  return issues.filter((issue) => issue.severity !== SeverityEnum.None).length;
}

export function hasActiveFilters(filter: DocumentExplorerFilter): boolean {
  return filter.severity.length > 0 || filter.workflowType.length > 0 || filter.showResolved || filter.showPassing;
}

/**
 * Check if an issue has been resolved.
 */
export function isIssueResolved(issue: Issue): boolean {
  return !!issue.resolved_at;
}

function filterBySeverity(issues: Issue[], severity: SeverityEnum[]): Issue[] {
  if (severity.length === 0) return issues;
  return issues.filter((issue) => severity.includes(issue.severity));
}

function filterByWorkflowType(issues: Issue[], workflowType: WorkflowRunType[]): Issue[] {
  if (workflowType.length === 0) return issues;
  return issues.filter((issue) => workflowType.includes(issue.workflow_type));
}

/**
 * Visible issues are the issues that are displayed in the document explorer,
 * filtered by the showResolved and showPassing toggles.
 */
export function getVisibleIssues(allIssues: Issue[], filter: DocumentExplorerFilter) {
  return allIssues
    .filter((issue) => filter.showPassing || issue.severity !== SeverityEnum.None)
    .filter((issue) => filter.showResolved || !isIssueResolved(issue))
    .sort((a, b) => (a.chunk_indices?.[0] ?? 0) - (b.chunk_indices?.[0] ?? 0))
    .sort(sortIssueBySeverity);
}

export function getPassingCount(allIssues: Issue[]): number {
  return allIssues.filter((issue) => issue.severity === SeverityEnum.None).length;
}

/**
 * Count of resolved issues, optionally scoped to specific chunks.
 */
export function getResolvedCount(allIssues: Issue[], selectedChunkIndices: number[]): number {
  return allIssues
    .filter((issue) => issue.severity !== SeverityEnum.None)
    .filter(isIssueResolved)
    .filter(
      (issue) =>
        selectedChunkIndices.length === 0 || selectedChunkIndices.some((idx) => issue.chunk_indices?.includes(idx)),
    ).length;
}

/**
 * Issues filtered by severity and workflow type (excludes chunk selection).
 * Used for document highlights.
 */
export function getHighlightIssues(visibleIssues: Issue[], filter: DocumentExplorerFilter): Issue[] {
  return filterBySeverity(filterByWorkflowType(visibleIssues, filter.workflowType), filter.severity);
}

/**
 * Issues filtered by all active filters including chunk selection.
 */
export function getFilteredIssues(
  visibleIssues: Issue[],
  filter: DocumentExplorerFilter,
  selectedChunkIndices: number[],
): Issue[] {
  let result = getHighlightIssues(visibleIssues, filter);

  if (selectedChunkIndices.length > 0) {
    result = getChunkIssuesByIndices(result, selectedChunkIndices);
  }

  return result;
}
