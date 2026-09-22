import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown, { type ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { editRanges } from './edit-highlight';
import type { ProposedEdit } from './proposed-edit';

/** Stands in for the document view's paragraph block. */
function OwnerParagraph({ node, children }: React.HTMLAttributes<HTMLParagraphElement> & ExtraProps) {
  const position = node?.position;
  return (
    <p data-block-owner="" data-line-start={position?.start.line} data-line-end={position?.end.line}>
      {children}
    </p>
  );
}

function render(markdown: string): HTMLElement {
  const html = renderToStaticMarkup(
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: OwnerParagraph }}>
      {markdown}
    </ReactMarkdown>,
  );
  const container = document.createElement('div');
  container.innerHTML = html;
  return container;
}

function edit(original_text: string, line: number): ProposedEdit {
  return {
    id: 'e1',
    issue_id: 'i1',
    original_text,
    replacement_text: 'x',
    start_line: line,
    end_line: line,
    rationale: 'r',
    status: 'proposed',
  };
}

describe('edit highlights over real ReactMarkdown output', () => {
  it('finds a quote that ends in a DOCX footnote reference', () => {
    const markdown = 'Intro.\n\nThe protocol was applied to the second cohort [[1]](#footnote-2).';
    const container = render(markdown);

    const [range] = editRanges(container, [edit('second cohort [[1]](#footnote-2)', 3)], markdown.split('\n'));

    expect(range.toString()).toBe('second cohort [1]');
  });

  it('keeps a mid-line year that reads like a list marker', () => {
    const markdown = 'Smith et al. 2019. Annual report.';
    const container = render(markdown);

    const [range] = editRanges(container, [edit('2019. Annual report', 1)], markdown.split('\n'));

    expect(range.toString()).toBe('2019. Annual report');
  });

  it('highlights a literal star the page shows as text', () => {
    // ReactMarkdown renders `2 * 3` with the star intact, so the quote has to
    // keep it too or the highlight lands on nothing.
    const markdown = 'The yield is 2 * 3 per plot.';
    const container = render(markdown);

    expect(container.textContent).toContain('2 * 3');

    const [range] = editRanges(container, [edit('2 * 3', 1)], markdown.split('\n'));

    expect(range.toString()).toBe('2 * 3');
  });

  it('highlights a code span as the page shows it', () => {
    // ReactMarkdown renders the span's contents literally, stars included, so
    // the quote has to keep them too.
    const markdown = 'Set the `**strict**` flag before running.';
    const container = render(markdown);

    expect(container.textContent).toContain('**strict**');

    const [range] = editRanges(container, [edit('`**strict**` flag', 1)], markdown.split('\n'));

    expect(range.toString()).toBe('**strict** flag');
  });

  it('marks the bold repeat rather than the plain one before it', () => {
    const markdown = 'Figure 3 and **Figure 3** close the section.';
    const container = render(markdown);

    const [range] = editRanges(container, [edit('**Figure 3**', 1)], markdown.split('\n'));

    expect(range.startContainer.parentElement?.tagName).toBe('STRONG');
  });
});
