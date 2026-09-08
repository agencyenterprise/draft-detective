'use client';

import { Issue } from '@/lib/generated-api';
import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { DocumentIssues } from './document-issues';
import { MarginNote } from './margin-note';
import { Slot, stackNotes } from './margin-stack';

type IssueWithLines = Issue & { start_line?: number | null };

interface MarginLayerProps {
  /** Issues anchored to a line, in the order they appear in the document. */
  issues: IssueWithLines[];
  /** Issues about the document rather than a place in it. */
  documentIssues: Issue[];
  activeIssueId: string | null;
  readOnly: boolean;
  onSelect: (issue: Issue) => void;
}

interface Entry {
  id: string;
  /** The line this note wants to sit beside, or null to ride at the top. */
  line: number | null;
  issue?: Issue;
  group?: Issue[];
}

/**
 * The notes, floating beside the document rather than inside it.
 *
 * They used to live in the third cell of each block's grid row, which made the
 * row as tall as its notes: a one-line paragraph carrying four issues opened a
 * hole in the text column the height of four cards. Word and Google Docs solve
 * this the same way, and so does this — the notes are taken out of the flow and
 * placed against the measured top of the paragraph they belong to, then pushed
 * out of the way only as far as their neighbours require. The open note is the
 * one that stays put; see stackNotes for how the others make room for it.
 *
 * Positions are measured rather than derived: line numbers say nothing about
 * height, and a paragraph's height depends on wrapping, images and maths that
 * only the browser knows.
 */
export function MarginLayer({ issues, documentIssues, activeIssueId, readOnly, onSelect }: MarginLayerProps) {
  const layerRef = useRef<HTMLDivElement>(null);
  const noteRefs = useRef(new Map<string, HTMLElement>());
  const [tops, setTops] = useState<Record<string, number>>({});

  const entries = useMemo<Entry[]>(() => {
    // Sorted by line, not by whatever order the list arrives in. The stack only
    // ever pushes a note *down*, so one out-of-place note near the top would
    // drag every note after it away from the paragraph it belongs to.
    const anchored = issues
      .map((issue) => ({
        id: issue.id,
        line: typeof issue.start_line === 'number' ? issue.start_line : null,
        issue: issue as Issue,
      }))
      .sort((a, b) => (a.line ?? 0) - (b.line ?? 0));
    // The document-level group rides at the top, above the first paragraph's
    // notes, because that is what it is about.
    return documentIssues.length > 0
      ? [{ id: '__document__', line: null, group: documentIssues }, ...anchored]
      : anchored;
  }, [issues, documentIssues]);

  // Read by layout through a ref rather than closed over, so that a change of
  // selection re-runs the layout (below) without rebuilding the observer that
  // watches every note for reflow.
  const activeRef = useRef(activeIssueId);
  activeRef.current = activeIssueId;

  const layout = useCallback(() => {
    const body = layerRef.current?.parentElement;
    if (!body) return;

    const bodyTop = body.getBoundingClientRect().top;

    // Ranges read once per pass rather than per note. Both lists are in
    // document order — owners because the DOM is, entries because they were
    // sorted — so one moving index walks them together instead of rescanning
    // every paragraph for every note.
    const owners = Array.from(body.querySelectorAll<HTMLElement>('[data-block-owner]')).map((element) => ({
      element,
      start: Number(element.dataset.lineStart),
      end: Number(element.dataset.lineEnd),
    }));

    let owner = 0;
    const slots = entries.map<Slot>((entry) => {
      const height = noteRefs.current.get(entry.id)?.offsetHeight ?? 0;
      if (entry.line === null) return { wanted: null, height };

      // Where it would like to be: level with the top of its paragraph.
      while (owner < owners.length && owners[owner].end < entry.line) owner += 1;
      const anchor = owners[owner];
      // Only the paragraph that actually contains the line; a note whose line
      // falls in a gap has no place of its own and rides with its neighbours.
      const owned = anchor !== undefined && entry.line >= anchor.start && entry.line <= anchor.end;
      return { wanted: owned ? anchor.element.getBoundingClientRect().top - bodyTop : null, height };
    });

    const pivot = entries.findIndex((entry) => entry.id === activeRef.current);
    const tops = stackNotes(slots, pivot);
    const next: Record<string, number> = {};
    entries.forEach((entry, index) => {
      next[entry.id] = tops[index];
    });

    setTops((previous) => (sameTops(previous, next) ? previous : next));
  }, [entries]);

  // Watching is separate from laying out, so that choosing a note re-runs the
  // one and leaves the other alone: rebuilding an observation over every note
  // on each change of selection is work for nothing.
  useLayoutEffect(() => {
    const body = layerRef.current?.parentElement;
    if (!body) return;

    const observer = new ResizeObserver(layout);
    observer.observe(body);
    noteRefs.current.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [layout]);

  // A note's height is a function of whether it is the open one, so the layout
  // reacts to that directly rather than waiting to be told about it: the
  // observer is for reflow the component cannot see coming.
  useLayoutEffect(() => {
    layout();
  }, [layout, activeIssueId]);

  if (entries.length === 0) return null;

  return (
    <div
      ref={layerRef}
      // Only the notes take clicks; the column itself must not cover the
      // document's own right edge.
      className="pointer-events-none absolute inset-y-0 right-0 hidden w-[calc(26rem_+_1px)] pl-4 xl:block"
    >
      {entries.map((entry) => (
        <div
          key={entry.id}
          ref={(element) => {
            if (element) noteRefs.current.set(entry.id, element);
            else noteRefs.current.delete(entry.id);
          }}
          style={{ top: tops[entry.id] ?? 0 }}
          className="pointer-events-auto absolute right-0 left-4 transition-[top] duration-150 ease-out"
        >
          {entry.group ? (
            <DocumentIssues
              issues={entry.group}
              activeIssueId={activeIssueId}
              readOnly={readOnly}
              onSelect={onSelect}
            />
          ) : (
            <MarginNote
              issue={entry.issue!}
              active={activeIssueId === entry.issue!.id}
              readOnly={readOnly}
              onSelect={onSelect}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function sameTops(a: Record<string, number>, b: Record<string, number>): boolean {
  const keys = Object.keys(b);
  if (Object.keys(a).length !== keys.length) return false;
  return keys.every((key) => a[key] === b[key]);
}
