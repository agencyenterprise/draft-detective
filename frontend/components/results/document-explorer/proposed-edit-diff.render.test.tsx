import { describe, expect, it } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ProposedEdit } from './proposed-edit';
import { ProposedEdits } from './proposed-edit-diff';

function edit(overrides: Partial<ProposedEdit> = {}): ProposedEdit {
  return {
    id: 'e1',
    issue_id: 'i1',
    original_text: 'The quick brown fox',
    replacement_text: 'The quick grey fox',
    start_line: 4,
    end_line: 4,
    rationale: 'Grey is the documented colour.',
    status: 'proposed',
    ...overrides,
  };
}

function render(edits: ProposedEdit[]): HTMLElement {
  const container = document.createElement('div');
  container.innerHTML = renderToStaticMarkup(<ProposedEdits edits={edits} />);
  return container;
}

describe('ProposedEdits markup', () => {
  it('marks removed words as del and inserted words as ins, leaving the rest plain', () => {
    const root = render([edit()]);

    expect(Array.from(root.querySelectorAll('del')).map((el) => el.textContent)).toEqual(['brown']);
    expect(Array.from(root.querySelectorAll('ins')).map((el) => el.textContent)).toEqual(['grey']);
    const text = root.querySelector('del')?.closest('p');
    const plain = Array.from(text?.childNodes ?? [])
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent);
    expect(plain).toEqual(['The quick ', ' fox']);
  });

  it('renders a deletion as one del over the whole quote', () => {
    const root = render([edit({ replacement_text: '' })]);

    expect(Array.from(root.querySelectorAll('del')).map((el) => el.textContent)).toEqual(['The quick brown fox']);
    expect(root.querySelectorAll('ins')).toHaveLength(0);
    expect(root.textContent).toContain('Delete');
  });

  it('shows the rationale and, for a single edit, the line in the header', () => {
    const root = render([edit()]);

    expect(root.textContent).toContain('Grey is the documented colour.');
    expect(root.textContent).toContain('L4');
  });
});
