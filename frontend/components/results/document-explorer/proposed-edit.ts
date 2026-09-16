import type { Issue, IssueEditRead } from '@/lib/generated-api';

/** One concrete change an assessment proposes to the document, as served by the API. */
export type ProposedEdit = IssueEditRead;

/** An issue's proposed edits, in the order the agent proposed them. */
export function issueEdits(issue: Issue): ProposedEdit[] {
  return issue.edits;
}

/** Whether an edit removes its quote outright rather than replacing it. */
export function isDeletion(edit: ProposedEdit): boolean {
  return edit.replacement_text.trim() === '';
}
