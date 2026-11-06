import type { Issue } from '@/lib/generated-api';

/**
 * Where an issue sits in the document, or nowhere.
 *
 * A finding about the document rather than a place in it carries no lines, and
 * an issue missing either end has no range.
 */
export function issueLineRange(issue: Issue): [number, number] | null {
  const { start_line: start, end_line: end } = issue;
  if (typeof start !== 'number' || typeof end !== 'number') return null;
  return [start, end];
}

/**
 * Where to bring an issue into view: its passage's line when it has one, since
 * that is where its highlight and margin note sit, else its whole range. The
 * range stays what the issue selects; only the scroll target moves.
 */
export function issueScrollRange(issue: Issue): [number, number] | null {
  const line = issue.passage?.start_line;
  return typeof line === 'number' ? [line, line] : issueLineRange(issue);
}

/** The line an issue starts on, even when its end line is missing. */
export function issueStartLine(issue: Issue): number | null {
  const { start_line: start } = issue;
  return typeof start === 'number' ? start : null;
}

/** Whether two inclusive line ranges share at least one line. */
export function rangesOverlap(a: [number, number], b: [number, number]): boolean {
  return a[0] <= b[1] && a[1] >= b[0];
}

/**
 * `L142`, or `L142–148` over several lines.
 *
 * The one place a line range is worded, so an issue's label and a proposed
 * edit's cannot drift apart.
 */
export function formatLineLabel(start: number, end: number): string {
  return start === end ? `L${start}` : `L${start}–${end}`;
}

export function lineLabel(issue: Issue): string | null {
  const range = issueLineRange(issue);
  if (!range) return null;
  return formatLineLabel(range[0], range[1]);
}
