import type { Issue } from '@/lib/generated-api';
import { quoteRange, supportsHighlightApi } from './edit-highlight';
import { issuesOnLines } from './passage-highlight';
import { issuePassage } from './proposed-edit';

/**
 * What a click in the document opens, now that passages are the targets.
 *
 * An issue with a passage the page carries is opened from its words, the way
 * Word opens a comment from its highlighted text. A highlight receives no
 * events, so the point of a click is tested against each passage's boxes on
 * screen. A paragraph is a target only for the issues that have no passage on
 * the page -- a whole-line finding, a legacy issue -- and only from the
 * paragraph their lines start on.
 */

/** Where each issue's passage sits in the rendered document, looked up once per rendering. */
export interface PassageResolver {
  /** The markdown this resolver's ranges were located in. */
  rendering: string;
  /** The passage's range, or null when the issue has none or the page does not carry it. */
  range(issue: Issue): Range | null;
}

/**
 * A resolver over one rendering of the document. Ranges point at the rendered
 * text nodes, so a new rendering needs a new resolver; until then each issue's
 * passage is located once and remembered, by everything that asks.
 *
 * `rendering` is the markdown the container shows. It is not read: it names
 * which rendering the cached ranges belong to, so a caller memoizing on it
 * gets a fresh resolver exactly when the text nodes change.
 */
export function createPassageResolver(
  container: { readonly current: Element | null },
  rendering: string,
): PassageResolver {
  const cache = new Map<string, Range | null>();
  return {
    rendering,
    range(issue) {
      if (cache.has(issue.id)) return cache.get(issue.id)!;
      // Read when a range is first asked for, after the document is laid out.
      const root = container.current;
      const passage = issuePassage(issue);
      if (!root) return null;
      const found = passage && supportsHighlightApi() ? quoteRange(root, passage) : null;
      cache.set(issue.id, found);
      return found;
    },
  };
}

/** A box on screen, as `getClientRects` reports one. */
export interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/**
 * The issues whose passage covers the point, narrowest first.
 *
 * Narrowest first, so a passage nested inside a longer one (*Five Forces
 * model* inside *Porters' Five Forces model*) is reachable at all: the outer
 * one is still a click away, see `nextTarget`.
 */
export function issuesAtPoint(
  boxes: ReadonlyMap<string, { boxes: Box[]; length: number }>,
  x: number,
  y: number,
): string[] {
  const hits: { id: string; length: number }[] = [];
  for (const [id, entry] of boxes) {
    const inside = entry.boxes.some(
      (box) => x >= box.left - 1 && x <= box.right + 1 && y >= box.top - 2 && y <= box.bottom + 2,
    );
    if (inside) hits.push({ id, length: entry.length });
  }
  return hits.sort((a, b) => a.length - b.length).map((hit) => hit.id);
}

/**
 * The issue a click opens among those under it, or null to close the open one.
 *
 * The first click opens the narrowest. Clicking again on the same words steps
 * to the next issue they carry, and past the last one closes it, the way a
 * click on the selected paragraph always has.
 */
export function nextTarget(hits: string[], activeId: string | null): string | null {
  if (hits.length === 0) return null;
  const at = activeId ? hits.indexOf(activeId) : -1;
  if (at === -1) return hits[0];
  return at + 1 < hits.length ? hits[at + 1] : null;
}

/**
 * The issues a paragraph is the target for: those with no passage on the page
 * whose lines start in it, most severe first. A finding spread over several
 * paragraphs is opened from its first, so the paragraphs after it stay free
 * for the passages they carry.
 */
export function lineTargets(
  issues: Issue[],
  located: ReadonlySet<string>,
  start: number,
  end: number,
  rank: (issue: Issue) => number,
): Issue[] {
  return issuesOnLines(issues, start, end)
    .filter((issue) => !located.has(issue.id) && issue.start_line! >= start && issue.start_line! <= end)
    .sort((a, b) => rank(b) - rank(a));
}

/** Each located passage's boxes on screen now, for hit-testing a point. */
export function passageBoxes(ranges: ReadonlyMap<string, Range>): Map<string, { boxes: Box[]; length: number }> {
  return new Map(
    [...ranges].map(([id, range]) => [
      id,
      { boxes: Array.from(range.getClientRects()), length: range.toString().length },
    ]),
  );
}
