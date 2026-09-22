import type { Issue } from '@/lib/generated-api';

/**
 * Where an issue sits in the document, or nowhere.
 *
 * Read off the issue defensively: the lines are not part of the API type, and a
 * finding about the document rather than a place in it carries none at all.
 */
export function issueLineRange(issue: Issue): [number, number] | null {
  const { start_line: start, end_line: end } = issue as Issue & {
    start_line?: number | null;
    end_line?: number | null;
  };
  if (typeof start !== 'number' || typeof end !== 'number') return null;
  return [start, end];
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
