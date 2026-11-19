import type { Issue } from '@/lib/generated-api';
import { issueStartLine } from './issue-lines';

export interface OutlineEntry {
  id: string;
  level: number;
  text: string;
  line: number;
  /** Line the next heading starts on, or Infinity for the last one. */
  endLine: number;
}

const HEADING = /^(#{1,3})\s+(.*\S)\s*$/;
// Any indent: a list item's fence sits as deep as the item, and the outline doesn't
// track list nesting. No `$`: a CRLF document's lines end in `\r`, which `.` won't match.
const FENCE = /^\s*(`{3,}|~{3,})(.*)/;

/**
 * Reads the document outline straight off the markdown source so heading line
 * numbers match the ones the renderer puts in the gutter. Only levels 1–3, since
 * deeper headings make the rail unreadable on a long report.
 */
export function extractOutline(markdown: string): OutlineEntry[] {
  const entries: OutlineEntry[] = [];
  // The delimiter that opened the current fence, or null outside one. Markdown
  // closes a fence only on a bare run of the same character, at least as long as
  // the opener, so a ~~~ or ```js line inside a ``` block is content rather than
  // the end of it.
  let fence: { char: string; length: number } | null = null;

  markdown.split('\n').forEach((raw, index) => {
    const [, delimiter, rest] = FENCE.exec(raw) ?? [];
    if (delimiter) {
      if (!fence) {
        fence = { char: delimiter[0], length: delimiter.length };
        return;
      }
      if (delimiter[0] === fence.char && delimiter.length >= fence.length && !rest.trim()) {
        fence = null;
        return;
      }
    }
    if (fence) return;

    const match = HEADING.exec(raw);
    if (!match) return;

    entries.push({
      id: `outline-${index + 1}`,
      level: match[1].length,
      // Strip the inline markdown that would otherwise show up as literal syntax.
      text: match[2].replace(/[*_`]/g, '').trim(),
      line: index + 1,
      endLine: Infinity,
    });
  });

  entries.forEach((entry, i) => {
    entry.endLine = i + 1 < entries.length ? entries[i + 1].line - 1 : Infinity;
  });

  return entries;
}

/** Issues whose start line falls inside a section, for the rail's severity dots. */
export function issuesInSection(issues: Issue[], entry: OutlineEntry): Issue[] {
  return issues.filter((issue) => {
    const line = issueStartLine(issue);
    return line !== null && line >= entry.line && line <= entry.endLine;
  });
}
