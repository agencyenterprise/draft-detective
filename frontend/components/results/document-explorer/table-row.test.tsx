import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown, { type ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { editRanges } from './edit-highlight';
import type { ProposedEdit } from './proposed-edit';
import { TableRow } from './table-row';

/** Stands in for the document view's table block: the owner of its source lines. */
function OwnerTable({ node, children }: React.HTMLAttributes<HTMLTableElement> & ExtraProps) {
  const position = node?.position;
  return (
    <table data-block-owner="" data-line-start={position?.start.line} data-line-end={position?.end.line}>
      {children}
    </table>
  );
}

const MARKDOWN = [
  '# Results',
  '',
  '| Series | Note |',
  '| --- | --- |',
  '| Baseline | See Figure 3 |',
  '| Outcome | See Figure 3 |',
].join('\n');

function render(): HTMLElement {
  const html = renderToStaticMarkup(
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ table: OwnerTable, tr: TableRow }}>
      {MARKDOWN}
    </ReactMarkdown>,
  );
  const container = document.createElement('div');
  container.innerHTML = html;
  return container;
}

function edit(overrides: Partial<ProposedEdit>): ProposedEdit {
  return {
    id: 'e1',
    issue_id: 'i1',
    original_text: 'See Figure 3',
    replacement_text: 'See Figure 2',
    start_line: 6,
    end_line: 6,
    rationale: 'Matches the caption.',
    status: 'proposed',
    ...overrides,
  };
}

describe('TableRow', () => {
  it('stamps every rendered row with its source line', () => {
    const rows = Array.from(render().querySelectorAll('tr'));

    expect(rows.map((row) => row.getAttribute('data-line-start'))).toEqual(['3', '5', '6']);
    expect(rows.map((row) => row.getAttribute('data-line-end'))).toEqual(['3', '5', '6']);
  });

  it('lets an edit highlight land on its own row when another row repeats the quote', () => {
    const container = render();

    const [range] = editRanges(container, [edit({ start_line: 6, end_line: 6 })]);

    expect(range.toString()).toBe('See Figure 3');
    expect(range.startContainer.parentElement?.closest('tr')?.textContent).toContain('Outcome');
  });

  it('still finds the earlier row when the edit is anchored there', () => {
    const container = render();

    const [range] = editRanges(container, [edit({ start_line: 5, end_line: 5 })]);

    expect(range.startContainer.parentElement?.closest('tr')?.textContent).toContain('Baseline');
  });
});
