import type { Issue, IssueEditRead, IssuePassageRead } from '@/lib/generated-api';

/** One concrete change an assessment proposes to the document, as served by the API. */
export type ProposedEdit = IssueEditRead;

/**
 * Words quoted from one line of the document and located when the issue was
 * reported: an issue's passage, or the text an edit replaces. Both are found in
 * the rendered page the same way, by `quoteRange`.
 */
export type LocatedQuote = Pick<IssuePassageRead, 'display_text' | 'display_occurrence' | 'start_line' | 'end_line'>;

/** An issue's proposed edits, in the order the agent proposed them. */
export function issueEdits(issue: Issue): ProposedEdit[] {
  return issue.edits;
}

/** The exact words an issue is about, or null when it concerns its whole lines. */
export function issuePassage(issue: Issue): IssuePassageRead | null {
  return issue.passage ?? null;
}

/**
 * Whether an edit removes its quote outright rather than replacing it.
 *
 * Exactly the empty string, as the backend contract defines a deletion. A
 * whitespace-only replacement is a real replacement and is shown as one.
 */
export function isDeletion(edit: ProposedEdit): boolean {
  return edit.replacement_text === '';
}
