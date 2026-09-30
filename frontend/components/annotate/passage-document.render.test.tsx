import { afterEach, describe, expect, it } from 'vitest';
import { renderInto, Rendered } from '@/lib/test-render';
import { PassageDocument } from './passage-document';

const DOCUMENT = [
  '# Scope',
  '',
  'We surveyed three states.',
  '',
  'Off-grid approaches, sometimes called bridge power,[[9]](#footnote-10) were not considered.',
].join('\n');

let rendered: Rendered | null = null;
afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
});

function washedLines(container: HTMLElement): string[] {
  return [...container.querySelectorAll<HTMLElement>('[data-block-owner].bg-amber-50')].map(
    (block) => block.dataset.lineStart ?? '',
  );
}

describe('PassageDocument', () => {
  it('washes the paragraph of an anchor quoted with a footnote link', async () => {
    rendered = await renderInto(
      <PassageDocument
        document={DOCUMENT}
        anchor="Off-grid approaches, sometimes called bridge power,[[9]](#footnote-10) were not considered"
        line={5}
      />,
    );
    expect(washedLines(rendered.container)).toEqual(['5']);
  });

  it('falls back to the source line when the anchor cannot be found', async () => {
    rendered = await renderInto(<PassageDocument document={DOCUMENT} anchor="text that is not there" line={3} />);
    expect(washedLines(rendered.container)).toEqual(['3']);
  });

  it('marks the exact words when they sit in one run of text', async () => {
    rendered = await renderInto(<PassageDocument document={DOCUMENT} anchor="three states" line={3} />);
    expect(rendered.container.querySelector('mark[data-annotation-anchor]')?.textContent).toBe('three states');
    expect(washedLines(rendered.container)).toEqual(['3']);
  });
});
