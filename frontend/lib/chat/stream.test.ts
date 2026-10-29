import { getSession } from 'next-auth/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { baseUrl } from '@/lib/api';
import { errorDetail, parseEventStream, streamChatTurn, type ChatStreamEvent } from '@/lib/chat/stream';
import type { ChatStreamRequest, StreamChatTurnApiChatThreadsThreadIdStreamPostData } from '@/lib/generated-api';

vi.mock('next-auth/react', () => ({ getSession: vi.fn() }));

const session = vi.mocked(getSession);
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  session.mockResolvedValue({ accessToken: 'tok', expires: '' } as Awaited<ReturnType<typeof getSession>>);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  session.mockReset();
});

/** A body that arrives in exactly these chunks, the way the network may split it. */
function chunked(...chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === 'string' ? encoder.encode(chunk) : chunk);
      controller.close();
    },
  });
}

/** One SSE frame, as `encode_event` in `lib/services/chat/sse.py` writes it. */
const frame = (event: ChatStreamEvent) => `data: ${JSON.stringify(event)}\n\n`;

async function collect(stream: AsyncGenerator<ChatStreamEvent>): Promise<ChatStreamEvent[]> {
  const out: ChatStreamEvent[] = [];
  for await (const event of stream) out.push(event);
  return out;
}

describe('parseEventStream', () => {
  it('yields one event per data frame and skips the heartbeats between them', async () => {
    const body = chunked(frame({ t: 'message', id: 'a1' }), ': ping\n\n', frame({ t: 'text', v: 'Hi' }), ': ping\n\n');

    await expect(collect(parseEventStream(body))).resolves.toEqual([
      { t: 'message', id: 'a1' },
      { t: 'text', v: 'Hi' },
    ]);
  });

  it('reassembles a frame the network split across chunks', async () => {
    const whole = frame({ t: 'tool', id: 'c1', name: 'search', args: { query: 'x' } });
    const body = chunked(whole.slice(0, 7), whole.slice(7, 30), whole.slice(30));

    await expect(collect(parseEventStream(body))).resolves.toEqual([
      { t: 'tool', id: 'c1', name: 'search', args: { query: 'x' } },
    ]);
  });

  it('keeps a multibyte character whole when a chunk ends inside it', async () => {
    const bytes = new TextEncoder().encode(frame({ t: 'text', v: 'Olá – ✓' }));
    const inside = bytes.indexOf(0xc3) + 1; // between the two bytes of "á"

    await expect(collect(parseEventStream(chunked(bytes.slice(0, inside), bytes.slice(inside))))).resolves.toEqual([
      { t: 'text', v: 'Olá – ✓' },
    ]);
  });

  it('yields a last frame that the stream ends without a newline after', async () => {
    const body = chunked(frame({ t: 'text', v: 'a' }), `data: ${JSON.stringify({ t: 'message_end', id: 'a1' })}`);

    await expect(collect(parseEventStream(body))).resolves.toEqual([
      { t: 'text', v: 'a' },
      { t: 'message_end', id: 'a1' },
    ]);
  });
});

describe('errorDetail', () => {
  it("reads FastAPI's string detail", async () => {
    const response = Response.json({ detail: 'Thread not found' }, { status: 404 });

    await expect(errorDetail(response)).resolves.toBe('Thread not found');
  });

  it('falls back to the status for a validation error, whose detail is a list', async () => {
    const response = Response.json({ detail: [{ loc: ['body', 'message'], msg: 'Field required' }] }, { status: 422 });

    await expect(errorDetail(response)).resolves.toBe('Chat request failed with status 422');
  });

  it('shows a body that is not JSON as it came, such as a proxy error page', async () => {
    const response = new Response('Bad Gateway', { status: 502 });

    await expect(errorDetail(response)).resolves.toBe('Bad Gateway');
  });

  it('falls back to the status for an empty body', async () => {
    await expect(errorDetail(new Response(null, { status: 500 }))).resolves.toBe('Chat request failed with status 500');
  });
});

describe('streamChatTurn', () => {
  // Typed against the generated schema: a renamed backend path fails the type check.
  const STREAM_PATH: StreamChatTurnApiChatThreadsThreadIdStreamPostData['url'] = '/api/chat/threads/{thread_id}/stream';

  it("posts the new message to the thread's stream and yields what comes back", async () => {
    fetchMock.mockResolvedValue(new Response(frame({ t: 'text', v: 'Hi' })));
    const { signal } = new AbortController();
    const attachments = [{ name: 'notes.md', text: '# Notes' }];

    const out = await collect(
      streamChatTurn({ threadId: 't-1', model: 'gpt', message: 'Hello', messageId: 'm-1', attachments, signal }),
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe(`${baseUrl}${STREAM_PATH.replace('{thread_id}', 't-1')}`);
    expect(init?.method).toBe('POST');
    expect(init?.headers).toEqual({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: 'Bearer tok',
    });
    // The Stop button aborts through it.
    expect(init?.signal).toBe(signal);
    expect(JSON.parse(String(init?.body))).toEqual({
      model: 'gpt',
      message: 'Hello',
      message_id: 'm-1',
      attachments,
    } satisfies Required<ChatStreamRequest>);
    expect(out).toEqual([{ t: 'text', v: 'Hi' }]);
  });

  it('sends no Authorization header without a session, and no attachments as an empty list', async () => {
    session.mockResolvedValue(null);
    fetchMock.mockResolvedValue(new Response(''));

    await collect(streamChatTurn({ threadId: 't-1', message: 'Hello' }));

    const init = fetchMock.mock.calls[0][1];
    expect(init?.headers).not.toHaveProperty('Authorization');
    expect(JSON.parse(String(init?.body))).toEqual({ message: 'Hello', attachments: [] });
  });

  it("throws the backend's detail when it refuses the turn", async () => {
    fetchMock.mockResolvedValue(Response.json({ detail: 'A turn is already running' }, { status: 409 }));

    await expect(collect(streamChatTurn({ threadId: 't-1', message: 'Hello' }))).rejects.toThrow(
      'A turn is already running',
    );
  });
});
