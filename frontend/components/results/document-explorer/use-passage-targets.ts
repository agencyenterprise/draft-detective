import type { Issue } from '@/lib/generated-api';
import type React from 'react';
import { RefObject, useEffect, useMemo, useState } from 'react';
import { setPassageHover } from './passage-highlight';
import { createPassageResolver, issuesAtPoint, nextTarget, passageBoxes, PassageResolver } from './passage-targets';

interface PassageTargets {
  resolver: PassageResolver;
  /** The issue whose passage is under the pointer, for its note to answer. */
  hoveredIssueId: string | null;
  /** Spread onto the document's scrolling container. */
  handlers: Pick<React.HTMLAttributes<HTMLDivElement>, 'onClick' | 'onMouseMove' | 'onMouseLeave'>;
}

/**
 * Passages as the document's click targets, and paragraphs only as the
 * fallback for issues without one.
 *
 * One listener on the container rather than one per block: a highlight takes
 * no events of its own, so a click is placed by testing its point against the
 * passages of the block it landed in. A click that hits no passage falls back
 * to the nearest paragraph marked with `data-line-targets` (see
 * `lineTargets`). Clicks in the margin are the notes' own business.
 *
 * `activeId` is the open issue; a host without an issue queue passes the
 * single issue on its selected lines, so a second click still closes it.
 */
export function usePassageTargets(
  containerRef: RefObject<HTMLDivElement | null>,
  markdown: string,
  issues: Issue[],
  activeId: string | null,
  onIssueSelect: (issue: Issue | null) => void,
): PassageTargets {
  // A new rendering means new text nodes, so the ranges are looked up again.
  const resolver = useMemo(() => createPassageResolver(containerRef, markdown), [containerRef, markdown]);
  const [hoveredIssueId, setHoveredIssueId] = useState<string | null>(null);
  // The whole-paragraph target under the pointer, when that is what it is on.
  const [hoveredParagraph, setHoveredParagraph] = useState<HTMLElement | null>(null);
  const byId = useMemo(() => new Map(issues.map((issue) => [issue.id, issue])), [issues]);

  /** The issues whose passage is under the pointer, narrowest first; only the block's own are measured. */
  const hitsAt = (event: React.MouseEvent): string[] => {
    const block = (event.target as Element).closest<HTMLElement>('[data-block-owner]');
    if (!block || (event.target as Element).closest('[data-margin-layer]')) return [];
    const start = Number(block.dataset.lineStart);
    const end = Number(block.dataset.lineEnd);
    const ranges = new Map<string, Range>();
    for (const issue of issues) {
      const line = issue.passage?.start_line;
      if (line === undefined || line < start || line > end) continue;
      const range = resolver.range(issue);
      if (range) ranges.set(issue.id, range);
    }
    return issuesAtPoint(passageBoxes(ranges), event.clientX, event.clientY);
  };

  const select = (id: string | null) => onIssueSelect(id ? (byId.get(id) ?? null) : null);

  const onClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as Element;
    if (target.closest('[data-margin-layer]')) return;
    // A drag that selected text is reading, not choosing an issue.
    if (window.getSelection()?.toString()) return;
    const hits = hitsAt(event);
    if (hits.length > 0) return select(nextTarget(hits, activeId));
    const paragraph = target.closest<HTMLElement>('[data-line-targets]');
    if (paragraph) select(nextTarget(paragraph.dataset.lineTargets!.split(' '), activeId));
  };

  const hover = (id: string | null, paragraph: HTMLElement | null = null) => {
    if (id !== hoveredIssueId) setHoveredIssueId(id);
    if (paragraph !== hoveredParagraph) setHoveredParagraph(paragraph);
  };

  /** What the pointer is on: a passage first, else a paragraph that is a target of its own. */
  const pointAt = (event: React.MouseEvent) => {
    const hit = hitsAt(event)[0];
    if (hit) return hover(hit);
    const paragraph = (event.target as Element).closest<HTMLElement>('[data-line-targets]');
    if (paragraph && !(event.target as Element).closest('[data-margin-layer]')) {
      return hover(paragraph.dataset.lineTargets!.split(' ')[0], paragraph);
    }
    hover(null);
  };

  // A paragraph target answers the pointer the way a passage does, washed
  // grey (see FLAGGED_CLASSES in document-view.tsx).
  useEffect(() => {
    hoveredParagraph?.setAttribute('data-hovered', '');
    return () => hoveredParagraph?.removeAttribute('data-hovered');
  }, [hoveredParagraph]);

  // The hover mark follows the hovered and the open issue rather than being
  // painted from the pointer handler: the document's other marks are repainted
  // whenever an issue opens or the issues refresh, and a mark painted only when
  // the pointer moved onto a passage would be lost until it moved onto another.
  // The open passage carries its wash instead.
  useEffect(() => {
    const issue = hoveredIssueId && hoveredIssueId !== activeId ? byId.get(hoveredIssueId) : undefined;
    setPassageHover(issue ? resolver.range(issue) : null);
    return () => setPassageHover(null);
  }, [hoveredIssueId, activeId, byId, resolver]);

  return {
    resolver,
    hoveredIssueId,
    handlers: {
      onClick,
      onMouseMove: pointAt,
      onMouseLeave: () => hover(null),
    },
  };
}
