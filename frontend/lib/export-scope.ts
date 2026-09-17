import { Issue, IssueEditStatus, SeverityEnum } from '@/lib/generated-api';
import type { DocumentExplorerFilter } from '@/lib/stores/document-explorer-store';
import { isIssueResolved } from '@/lib/stores/document-explorer-store';

export interface ExportCounts {
  issues: number;
  edits: number;
}

/**
 * The issues a DOCX export will carry under the current filters.
 *
 * Mirrors the backend's export filtering, so the number shown in the dialog is
 * the number of comments the file will hold: resolved issues are left out,
 * passing checks only come along when the filter shows them, and the severity
 * and assessment filters narrow the rest. `showResolved` is a display toggle
 * and does not affect the export.
 */
export function issuesInExport(
  issues: Issue[],
  filter: Pick<DocumentExplorerFilter, 'severity' | 'workflowType' | 'showPassing'>,
): Issue[] {
  return issues
    .filter((issue) => !isIssueResolved(issue))
    .filter((issue) => filter.showPassing || issue.severity !== SeverityEnum.None)
    .filter((issue) => filter.severity.length === 0 || filter.severity.includes(issue.severity))
    .filter((issue) => filter.workflowType.length === 0 || filter.workflowType.includes(issue.workflow_type));
}

/** Issue and proposed-edit counts for the export; rejected edits are never applied. */
export function exportCounts(
  issues: Issue[],
  filter: Pick<DocumentExplorerFilter, 'severity' | 'workflowType' | 'showPassing'>,
): ExportCounts {
  const included = issuesInExport(issues, filter);
  const edits = included.reduce(
    (total, issue) => total + issue.edits.filter((edit) => edit.status !== IssueEditStatus.Rejected).length,
    0,
  );
  return { issues: included.length, edits };
}
