import { SeverityEnum, type Issue } from '@/lib/generated-api';
import { ensureStyle, setHighlight, supportsHighlightApi } from './edit-highlight';
import { severityRank } from '@/lib/severity';
import { issueLineRange, rangesOverlap } from './issue-lines';

/**
 * Marking the exact words an issue is about, instead of its whole lines.
 *
 * An issue with a passage that can be found in the page is marked on those
 * words only: dotted at rest, washed in its severity colour while it is open.
 * Everything else -- a legacy issue, an issue about its whole lines, a passage
 * the page does not carry, a browser without the Highlight API -- is marked on
 * the paragraph its lines start in, which is also where it is clicked (see
 * `lineTargets`), so a line-level finding is never hidden behind a
 * passage-level one.
 */

/** The registry key for the resting dotted underline of one severity's passages. */
export function restPassageHighlightName(severity: SeverityEnum): string {
  return `issue-passage-rest-${severity}`;
}

/** The registry key for the passage under the pointer. */
export const PASSAGE_HOVER_NAME = 'issue-passage-hover';

/** The registry key for the open issues' passages of one severity. */
export function selectedPassageHighlightName(severity: SeverityEnum): string {
  return `issue-passage-${severity}`;
}

const PASSAGE_STYLE_ID = 'issue-passage-highlight-style';

/** Tailwind's 100 and 950 shades, a step stronger than the block wash: a few words need more colour than a paragraph. */
const WASH: Record<SeverityEnum, { light: string; dark: string }> = {
  [SeverityEnum.High]: { light: 'rgb(254 226 226)', dark: 'rgb(69 10 10 / 0.6)' },
  [SeverityEnum.Medium]: { light: 'rgb(254 243 199)', dark: 'rgb(69 26 3 / 0.6)' },
  [SeverityEnum.Low]: { light: 'rgb(219 234 254)', dark: 'rgb(23 37 84 / 0.6)' },
  [SeverityEnum.None]: { light: 'rgb(220 252 231)', dark: 'rgb(5 46 22 / 0.6)' },
};

/** Tailwind's 500 shades, the severity dots' colour, for the dotted underline of a passage at rest. */
const UNDERLINE: Record<SeverityEnum, string> = {
  [SeverityEnum.High]: 'rgb(239 68 68)',
  [SeverityEnum.Medium]: 'rgb(245 158 11)',
  [SeverityEnum.Low]: 'rgb(59 130 246)',
  [SeverityEnum.None]: 'rgb(34 197 94)',
};

/** Injected at runtime for the reason given on `EDIT_HIGHLIGHT_CSS`. */
const PASSAGE_HIGHLIGHT_CSS = [
  `::highlight(${PASSAGE_HOVER_NAME}) { background-color: rgb(120 113 108 / 0.14); }
.dark ::highlight(${PASSAGE_HOVER_NAME}) { background-color: rgb(214 211 209 / 0.14); }`,
  ...Object.values(SeverityEnum).map(
    (severity) => `::highlight(${restPassageHighlightName(severity)}) {
  text-decoration: underline dotted ${UNDERLINE[severity]};
  text-decoration-thickness: 1.5px;
  text-underline-offset: 4px;
}`,
  ),
  ...Object.values(SeverityEnum).map(
    (severity) => `::highlight(${selectedPassageHighlightName(severity)}) { background-color: ${WASH[severity].light}; }
.dark ::highlight(${selectedPassageHighlightName(severity)}) { background-color: ${WASH[severity].dark}; }`,
  ),
].join('\n');

/**
 * The colour an issue's passage is washed in, as the project shows severities:
 * with grouping off every finding takes the medium colour, as in `severityStyle`.
 */
export function passageSeverity(severity: SeverityEnum, groupBySeverity: boolean): SeverityEnum {
  return groupBySeverity || severity === SeverityEnum.None ? severity : SeverityEnum.Medium;
}

/**
 * Where each issue's passage sits in the page, by issue id; issues whose
 * passage is not found are absent. `range` is a `PassageResolver`'s, so the
 * marks, the click targets and the margin all use the same lookup.
 */
export function locatePassages(issues: Issue[], range: (issue: Issue) => Range | null): Map<string, Range> {
  const located = new Map<string, Range>();
  for (const issue of issues) {
    const found = range(issue);
    if (found) located.set(issue.id, found);
  }
  return located;
}

/** The issues whose lines overlap `[start, end]`. */
export function issuesOnLines(issues: Issue[], start: number, end: number): Issue[] {
  return issues.filter((issue) => {
    const lines = issueLineRange(issue);
    return lines !== null && rangesOverlap(lines, [start, end]);
  });
}

/**
 * The issue whose colour a selected block is washed in, or null for no wash.
 *
 * It is the open issue the block is washed for: one without a passage marked,
 * the most severe if several are open. Not the block's most severe issue -- a
 * paragraph opened for a low finding is washed in the low colour even when it
 * also carries a high one. No wash when every open issue is marked on its
 * passage: the passage carries the colour, and washing its lines too would
 * mark the whole line again. With no issue open (a host that selects lines
 * rather than issues) the block's own `fallback` colours it.
 */
export function blockWash(
  isSelected: boolean,
  openIssues: Issue[],
  located: ReadonlyMap<string, Range>,
  fallback: Issue,
): Issue | null {
  if (!isSelected) return null;
  if (openIssues.length === 0) return fallback;
  const unmarked = openIssues.filter((issue) => !located.has(issue.id));
  if (unmarked.length === 0) return null;
  return unmarked.reduce((top, issue) => (severityRank(issue.severity) > severityRank(top.severity) ? issue : top));
}

/**
 * Paints every located passage dotted in its issue's severity colour, and the
 * open issues' passages washed in it, replacing whatever was painted before.
 * The underline is the passage's only severity mark: the paragraph carries none.
 */
export function paintPassages(
  located: ReadonlyMap<string, Range>,
  issues: Issue[],
  openIssues: Issue[],
  severityOf: (severity: SeverityEnum) => SeverityEnum,
): void {
  if (!supportsHighlightApi()) return;
  ensureStyle(PASSAGE_STYLE_ID, PASSAGE_HIGHLIGHT_CSS);
  for (const severity of Object.values(SeverityEnum)) {
    const resting = issues
      .filter((issue) => severityOf(issue.severity) === severity)
      .map((issue) => located.get(issue.id))
      .filter((range): range is Range => range !== undefined);
    setHighlight(restPassageHighlightName(severity), resting, 0);
  }
  for (const severity of Object.values(SeverityEnum)) {
    const ranges = openIssues
      .filter((issue) => severityOf(issue.severity) === severity)
      .map((issue) => located.get(issue.id))
      .filter((range): range is Range => range !== undefined);
    setHighlight(selectedPassageHighlightName(severity), ranges, 2);
  }
}

/** Marks the passage under the pointer, or none; below the open passage's wash. */
export function setPassageHover(range: Range | null): void {
  if (!supportsHighlightApi()) return;
  ensureStyle(PASSAGE_STYLE_ID, PASSAGE_HIGHLIGHT_CSS);
  setHighlight(PASSAGE_HOVER_NAME, range ? [range] : [], 1);
}

/**
 * Takes the resting and open passage marks off the document. Not the hover
 * mark: that one follows the pointer, and `usePassageTargets` owns it.
 */
export function clearPassageHighlights(): void {
  if (!supportsHighlightApi()) return;
  for (const severity of Object.values(SeverityEnum)) CSS.highlights.delete(restPassageHighlightName(severity));
  for (const severity of Object.values(SeverityEnum)) CSS.highlights.delete(selectedPassageHighlightName(severity));
}
