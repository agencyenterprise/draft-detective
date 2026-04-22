import { Issue, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';
import { create } from 'zustand';
import { sortIssueBySeverity } from '../severity';

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

export type LineRange = [number, number];

interface DocumentExplorerState {
  selectedLineRange: LineRange | null;
  selectLineRange: (range: LineRange | null) => void;
  clearLineSelection: () => void;

  filter: DocumentExplorerFilter;
  setFilter: (partial: Partial<DocumentExplorerFilter>) => void;
  clearFilters: () => void;
}

export const useDocumentExplorerStore = create<DocumentExplorerState>((set) => ({
  selectedLineRange: null,
  selectLineRange: (range) => set({ selectedLineRange: range }),
  clearLineSelection: () => set({ selectedLineRange: null }),

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

function getIssueStartLine(issue: Issue): number | null {
  const start = (issue as Issue & { start_line?: number | null }).start_line;
  return typeof start === 'number' ? start : null;
}

function getIssueEndLine(issue: Issue): number | null {
  const end = (issue as Issue & { end_line?: number | null }).end_line;
  return typeof end === 'number' ? end : null;
}

function issueOverlapsRange(issue: Issue, range: LineRange): boolean {
  const start = getIssueStartLine(issue);
  const end = getIssueEndLine(issue);
  if (start === null || end === null) return false;
  const [rangeStart, rangeEnd] = range;
  return start <= rangeEnd && end >= rangeStart;
}

/**
 * Visible issues are the issues that are displayed in the document explorer,
 * filtered by the showResolved and showPassing toggles.
 */
export function getVisibleIssues(allIssues: Issue[], filter: DocumentExplorerFilter) {
  return allIssues
    .filter((issue) => filter.showPassing || issue.severity !== SeverityEnum.None)
    .filter((issue) => filter.showResolved || !isIssueResolved(issue))
    .sort((a, b) => (getIssueStartLine(a) ?? 0) - (getIssueStartLine(b) ?? 0))
    .sort(sortIssueBySeverity);
}

export function getPassingCount(allIssues: Issue[]): number {
  return allIssues.filter((issue) => issue.severity === SeverityEnum.None).length;
}

/**
 * Count of resolved issues, optionally scoped to a selected line range.
 */
export function getResolvedCount(allIssues: Issue[], selectedLineRange: LineRange | null): number {
  return allIssues
    .filter((issue) => issue.severity !== SeverityEnum.None)
    .filter(isIssueResolved)
    .filter((issue) => selectedLineRange === null || issueOverlapsRange(issue, selectedLineRange)).length;
}

/**
 * Issues filtered by severity and workflow type (excludes line-range selection).
 * Used for document highlights.
 */
export function getHighlightIssues(visibleIssues: Issue[], filter: DocumentExplorerFilter): Issue[] {
  return filterBySeverity(filterByWorkflowType(visibleIssues, filter.workflowType), filter.severity);
}

/**
 * Issues filtered by all active filters including line-range selection.
 */
export function getFilteredIssues(
  visibleIssues: Issue[],
  filter: DocumentExplorerFilter,
  selectedLineRange: LineRange | null,
): Issue[] {
  let result = getHighlightIssues(visibleIssues, filter);

  if (selectedLineRange) {
    result = result.filter((issue) => issueOverlapsRange(issue, selectedLineRange)).sort(sortIssueBySeverity);
  }

  return result;
}
