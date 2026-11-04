import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ThreadMessage } from '@assistant-ui/react';
import type { ChatAttachmentMeta } from '@/lib/chat/turn';
import { readThreadFileContentApiChatThreadsThreadIdFilesGet } from '@/lib/generated-api';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { DocumentPanel } from './document-panel';

// The slice of assistant-ui's state the panel reads: the thread's messages and
// the backend id of the thread (undefined until its first turn creates it).
const auiState: { thread: { messages: ThreadMessage[] }; threadListItem: { remoteId: string | undefined } } = {
  thread: { messages: [] },
  threadListItem: { remoteId: undefined },
};

vi.mock('@assistant-ui/react', async (original) => ({
  ...(await original<typeof import('@assistant-ui/react')>()),
  useAuiState: <T,>(selector: (state: typeof auiState) => T) => selector(auiState),
}));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  readThreadFileContentApiChatThreadsThreadIdFilesGet: vi.fn(),
}));

const readFile = vi.mocked(readThreadFileContentApiChatThreadsThreadIdFilesGet);

/** A message as `convertChatMessage` leaves it: the attachments ride in `metadata.custom`. */
function message(attachments?: ChatAttachmentMeta[]): ThreadMessage {
  return { metadata: { custom: attachments ? { attachments } : {} } } as unknown as ThreadMessage;
}

let rendered: Rendered | null = null;
let client = testQueryClient();

async function renderPanel(messages: ThreadMessage[], remoteId?: string): Promise<HTMLElement> {
  auiState.thread.messages = messages;
  auiState.threadListItem.remoteId = remoteId;
  rendered = await renderInto(withQueryClient(client, <DocumentPanel />));
  await flush();
  return rendered.container;
}

/** The document text the panel shows, or null when it shows none. */
function shownText(container: HTMLElement): string | null {
  return container.querySelector('pre')?.textContent ?? null;
}

beforeEach(() => {
  readFile.mockReset();
  client = testQueryClient();
});

afterEach(async () => {
  await rendered?.unmount();
  rendered = null;
});

describe('DocumentPanel', () => {
  it('shows nothing and reads no file before a document is attached', async () => {
    const container = await renderPanel([message(), message([])], 'thread-1');

    expect(shownText(container)).toBeNull();
    expect(container.textContent).toContain('Nothing uploaded yet');
    expect(readFile).not.toHaveBeenCalled();
  });

  it('shows the text of a document attached in the turn still in flight, without reading the file', async () => {
    const container = await renderPanel(
      [message([{ name: 'draft.docx', path: '/uploads/draft.md', text: 'Local text.' }])],
      'thread-1',
    );

    expect(shownText(container)).toBe('Local text.');
    expect(readFile).not.toHaveBeenCalled();
  });

  it("reads a stored document from the thread's files", async () => {
    readFile.mockResolvedValue({ content: 'Stored text.' } as never);

    const container = await renderPanel([message([{ name: 'draft.docx', path: '/uploads/draft.md' }])], 'thread-1');

    expect(readFile).toHaveBeenCalledWith({ path: { thread_id: 'thread-1' }, query: { path: '/uploads/draft.md' } });
    expect(shownText(container)).toBe('Stored text.');
  });

  it('switches to the stored document once the turn that attached it has finished', async () => {
    readFile.mockResolvedValue({ content: 'Stored text.' } as never);
    await renderPanel([message([{ name: 'draft.docx', path: '/uploads/draft.md', text: 'Local text.' }])], 'thread-1');
    expect(readFile).not.toHaveBeenCalled();

    // The finished turn is reloaded from the backend, which keeps the path but not the text.
    auiState.thread.messages = [message([{ name: 'draft.docx', path: '/uploads/draft.md' }])];
    await rendered!.rerender(withQueryClient(client, <DocumentPanel />));
    await flush();

    expect(readFile).toHaveBeenCalledWith({ path: { thread_id: 'thread-1' }, query: { path: '/uploads/draft.md' } });
    expect(shownText(rendered!.container)).toBe('Stored text.');
  });

  it('shows the first document attached in the thread, not a later one', async () => {
    readFile.mockResolvedValue({ content: 'First text.' } as never);

    await renderPanel(
      [
        message(),
        message([
          { name: 'first.docx', path: '/uploads/first.md' },
          { name: 'second.docx', path: '/uploads/second.md' },
        ]),
        message([{ name: 'third.docx', path: '/uploads/third.md' }]),
      ],
      'thread-1',
    );

    expect(readFile).toHaveBeenCalledTimes(1);
    expect(readFile).toHaveBeenCalledWith(expect.objectContaining({ query: { path: '/uploads/first.md' } }));
  });

  it('reads no file until the thread exists on the backend', async () => {
    const container = await renderPanel([message([{ name: 'draft.docx', path: '/uploads/draft.md' }])]);

    expect(readFile).not.toHaveBeenCalled();
    expect(shownText(container)).toBeNull();
  });

  it('reads no file for an attachment the agent never stored', async () => {
    await renderPanel([message([{ name: 'draft.docx' }])], 'thread-1');

    expect(readFile).not.toHaveBeenCalled();
  });

  it('says the document could not be loaded when the read fails', async () => {
    readFile.mockRejectedValue(new Error('404'));

    const container = await renderPanel([message([{ name: 'draft.docx', path: '/uploads/gone.md' }])], 'thread-1');

    expect(shownText(container)).toBeNull();
    expect(container.textContent).toContain('Could not load the document.');
  });
});
