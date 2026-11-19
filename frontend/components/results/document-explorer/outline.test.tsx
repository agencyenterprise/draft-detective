import type { ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown, { type ExtraProps } from 'react-markdown';
import { describe, expect, it } from 'vitest';
import { SeverityEnum, WorkflowRunType, type Issue } from '@/lib/generated-api';
import { REMARK_PLUGINS } from './document-view';
import { extractOutline, issuesInSection, type OutlineEntry } from './outline';

/** The outline as level, line and text, which is what the rail shows and jumps to. */
function headings(markdown: string): [number, number, string][] {
  return extractOutline(markdown).map((entry) => [entry.level, entry.line, entry.text]);
}

/**
 * The headings the document view renders, with the source line it puts in the
 * gutter (the `position` that becomes `data-line-start`).
 */
function renderedHeadings(markdown: string): [number, number][] {
  const found: [number, number][] = [];
  const heading =
    (level: number) =>
    ({ node }: ExtraProps & { children?: ReactNode }) => {
      const line = node?.position?.start.line;
      if (line !== undefined) found.push([level, line]);
      return null;
    };
  renderToStaticMarkup(
    <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={{ h1: heading(1), h2: heading(2), h3: heading(3) }}>
      {markdown}
    </ReactMarkdown>,
  );
  return found;
}

describe('extractOutline', () => {
  it('lists levels 1 to 3 with their 1-based line, leaving deeper headings out', () => {
    const markdown = ['# Report', 'Intro.', '## Methods', '### Sampling', '#### Too deep', '## Results'].join('\n');

    expect(headings(markdown)).toEqual([
      [1, 1, 'Report'],
      [2, 3, 'Methods'],
      [3, 4, 'Sampling'],
      [2, 6, 'Results'],
    ]);
  });

  it('ends each section on the line before the next heading, and the last one never', () => {
    const outline = extractOutline(['# One', 'a', 'b', '## Two', '#### Deep', 'c', '# Three', 'd'].join('\n'));

    // A heading the outline leaves out does not end a section.
    expect(outline.map((entry) => [entry.line, entry.endLine])).toEqual([
      [1, 3],
      [4, 6],
      [7, Infinity],
    ]);
  });

  it('shows heading text without its inline markup', () => {
    expect(headings('## **Bold** _and_ `code`  ')).toEqual([[2, 1, 'Bold and code']]);
  });

  it.each(['#NoSpace', '\\# Escaped', '#', 'Plain text'])('reads %j as no heading', (line) => {
    expect(headings(line)).toEqual([]);
  });

  it('keeps line numbers on a document with Windows line endings', () => {
    expect(headings('# A\r\ntext\r\n## B\r\n')).toEqual([
      [1, 1, 'A'],
      [2, 3, 'B'],
    ]);
  });

  it.each([
    ['backticks', ['```', '# not a heading', '```', '# After'].join('\n')],
    ['tildes', ['~~~', '# not a heading', '~~~', '# After'].join('\n')],
    ['an indented fence', ['  ```python', '# comment', '  ```', '# After'].join('\n')],
  ])('skips headings inside a code block fenced with %s', (_, markdown) => {
    expect(headings(markdown)).toEqual([[1, 4, 'After']]);
  });

  it('keeps a fence open across a line of the other fence character', () => {
    const markdown = ['```', '~~~', '# not a heading', '```', '# After'].join('\n');

    expect(headings(markdown)).toEqual([[1, 5, 'After']]);
  });

  it('keeps a fence open across a shorter run of its own character', () => {
    const markdown = ['````', '```', '# not a heading', '````', '# After'].join('\n');

    expect(headings(markdown)).toEqual([[1, 5, 'After']]);
  });

  it('lists nothing after a fence that never closes', () => {
    expect(headings(['# Before', '```', '# inside'].join('\n'))).toEqual([[1, 1, 'Before']]);
  });

  // The rail jumps to `entry.line`, which only lands on the heading when it is
  // the line the document view numbers that heading with.
  it('puts each heading on the line the document view gives it', () => {
    const markdown = [
      '# Report',
      '',
      'Some **text** with a [link](https://example.com).',
      '',
      '## Code',
      '',
      '```python',
      '# a comment, not a heading',
      '~~~',
      '```',
      '',
      '````',
      '```js',
      '# still code',
      '```',
      '````',
      '',
      '### Table',
      '',
      '| a | b |',
      '| - | - |',
      '| 1 | 2 |',
      '',
      '#### Too deep for the outline',
      '',
      '## `Inline` _markup_',
      '',
      '$$',
      'x^2',
      '$$',
      '',
      '# Conclusion',
    ].join('\n');

    const outline = extractOutline(markdown).map((entry): [number, number] => [entry.level, entry.line]);

    expect(outline).toEqual(renderedHeadings(markdown));
    expect(outline).toHaveLength(5);
  });
});

function issue(id: string, startLine: number | null): Issue {
  return {
    id,
    project_id: 'project-1',
    workflow_run_id: 'run-1',
    issue_hash: `hash-${id}`,
    title: 'A finding',
    description: 'Something to look at',
    severity: SeverityEnum.Medium,
    workflow_type: WorkflowRunType.AdvocacyToneV2,
    created_at: new Date('2026-01-01T00:00:00Z'),
    updated_at: new Date('2026-01-01T00:00:00Z'),
    edits: [],
    passage: null,
    start_line: startLine,
    end_line: startLine,
  };
}

describe('issuesInSection', () => {
  const section: OutlineEntry = { id: 'outline-4', level: 2, text: 'Methods', line: 4, endLine: 9 };

  it('counts the issues that start on the heading, inside the section and on its last line', () => {
    const issues = [issue('heading', 4), issue('inside', 6), issue('last', 9)];

    expect(issuesInSection(issues, section).map((i) => i.id)).toEqual(['heading', 'inside', 'last']);
  });

  it('leaves out issues before or after the section and those with no line', () => {
    const issues = [issue('before', 3), issue('after', 10), issue('nowhere', null)];

    expect(issuesInSection(issues, section)).toEqual([]);
  });

  it('runs the last section to the end of the document', () => {
    const last: OutlineEntry = { ...section, endLine: Infinity };

    expect(issuesInSection([issue('far', 5000)], last).map((i) => i.id)).toEqual(['far']);
  });
});
