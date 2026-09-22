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

/**
 * Whether the export really carries the passing checks.
 *
 * The passing toggle only adds the `None`-severity issues back; the severity
 * filter then runs over everything, so any severity selection at all drops
 * them again -- including a selection of all three named severities, which
 * `includes` still measures `None` against. Saying "passing checks included"
 * beside a severity filter would be a promise the export does not keep.
 */
export function passingChecksIncluded(filter: Pick<DocumentExplorerFilter, 'severity' | 'showPassing'>): boolean {
  return filter.showPassing && filter.severity.length === 0;
}

/**
 * Whether this export can carry links back to Draft Detective.
 *
 * A share link opens the shared page, and that page has no revision of its own
 * to show -- it shows the current one. So the backend leaves the links out of a
 * historical export rather than sending the reader to a different document than
 * the comment beside it. Offering the option there would ask the author to make
 * a private project public for links the file will not have.
 *
 * No selected revision means the current one, which is what the document
 * explorer shows before a reader picks an older revision.
 */
export function shareLinksAvailable(selectedRevision: number | undefined, currentRevision: number): boolean {
  return selectedRevision === undefined || selectedRevision === currentRevision;
}

/** How many proposed edits the export carries, as a plain noun phrase. */
export function editsPhrase(count: number): string {
  return `${count} proposed edit${count === 1 ? '' : 's'}`;
}

/**
 * What the export does with what it carries, in one sentence.
 *
 * The counts are a selection, not a promise: the backend leaves out an issue
 * it cannot tie to a paragraph, and an edit whose quoted text no longer
 * matches gets described in its comment instead of redlined. So the sentence
 * says what happens to each kind rather than implying every count lands as a
 * tracked change. Every edit is described in its issue's comment either way --
 * the checkbox only decides whether the fix is also in the margin.
 */
export function exportOutcomeSentence(includeEdits: boolean): string {
  if (includeEdits) {
    return 'Issues become comments; edits become tracked changes where their text can be matched, and are described in their comments otherwise.';
  }
  return 'Issues become comments; edits are described in their comments.';
}

/**
 * What an export with no narrowing filter carries, in one sentence.
 *
 * "Every unresolved issue" on its own overstates it: a passing check is an
 * issue of severity `None`, and the export leaves those out unless the
 * document explorer's passing toggle is on. The sentence names which of the
 * two it is, since that is the difference between a file with one comment per
 * finding and one that also confirms every rule that held.
 */
export function exportScopeSentence(filter: Pick<DocumentExplorerFilter, 'severity' | 'showPassing'>): string {
  const passing = passingChecksIncluded(filter) ? 'including' : 'except';
  return `Every unresolved issue ${passing} passing checks, from every assessment.`;
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
