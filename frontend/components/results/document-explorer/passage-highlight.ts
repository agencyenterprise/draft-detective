import { SeverityEnum, type Issue } from '@/lib/generated-api';
import { ensureStyle, quoteRange, setHighlight, supportsHighlightApi } from './edit-highlight';
import { issueLineRange, rangesOverlap } from './issue-lines';
import { issuePassage } from './proposed-edit';

/**
 * Marking the exact words an issue is about, instead of its whole lines.
 *
 * An issue with a passage that can be found in the page is marked on those
 * words only: dotted at rest, washed in its severity colour while it is open.
 * Everything else -- a legacy issue, an issue about its whole lines, a passage
 * the page does not carry, a browser without the Highlight API -- keeps the
 * block marks it always had. A block keeps them as long as any issue on it has
 * no passage, so a line-level finding is never hidden behind a passage-level
 * one.
 */

/** The registry key the resting dotted underline is filed under. */
export const PASSAGE_HIGHLIGHT_NAME = 'issue-passage';

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

/** Injected at runtime for the reason given on `EDIT_HIGHLIGHT_CSS`. */
const PASSAGE_HIGHLIGHT_CSS = [
  `::highlight(${PASSAGE_HIGHLIGHT_NAME}) {
  text-decoration: underline dotted rgb(115 115 115 / 0.6);
  text-underline-offset: 4px;
}`,
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

/** Where each issue's passage sits in the page, by issue id; issues whose passage is not found are absent. */
export function locatePassages(container: Element, issues: Issue[]): Map<string, Range> {
  const located = new Map<string, Range>();
  if (!supportsHighlightApi()) return located;
  for (const issue of issues) {
    const passage = issuePassage(issue);
    const range = passage && quoteRange(container, passage);
    if (range) located.set(issue.id, range);
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

/** Whether a block still needs its own resting underline: some issue on it has no passage marked. */
export function blockKeepsUnderline(blockIssues: Issue[], located: ReadonlyMap<string, Range>): boolean {
  return blockIssues.some((issue) => !located.has(issue.id));
}

/**
 * Whether a selected block is washed as a whole. Not when every open issue is
 * marked on its passage: the passage carries the colour, and washing its lines
 * too would mark the whole line again.
 */
export function washesBlock(isSelected: boolean, openIssues: Issue[], located: ReadonlyMap<string, Range>): boolean {
  if (!isSelected) return false;
  return openIssues.length === 0 || openIssues.some((issue) => !located.has(issue.id));
}

/**
 * Paints every located passage dotted, and the open issues' passages in their
 * severity colour, replacing whatever was painted before.
 */
export function paintPassages(
  located: ReadonlyMap<string, Range>,
  openIssues: Issue[],
  severityOf: (severity: SeverityEnum) => SeverityEnum,
): void {
  if (!supportsHighlightApi()) return;
  ensureStyle(PASSAGE_STYLE_ID, PASSAGE_HIGHLIGHT_CSS);
  setHighlight(PASSAGE_HIGHLIGHT_NAME, [...located.values()], 0);
  for (const severity of Object.values(SeverityEnum)) {
    const ranges = openIssues
      .filter((issue) => severityOf(issue.severity) === severity)
      .map((issue) => located.get(issue.id))
      .filter((range): range is Range => range !== undefined);
    setHighlight(selectedPassageHighlightName(severity), ranges, 1);
  }
}

/** Takes every passage mark off the document. */
export function clearPassageHighlights(): void {
  if (!supportsHighlightApi()) return;
  CSS.highlights.delete(PASSAGE_HIGHLIGHT_NAME);
  for (const severity of Object.values(SeverityEnum)) CSS.highlights.delete(selectedPassageHighlightName(severity));
}
