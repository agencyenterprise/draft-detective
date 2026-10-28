import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { streamWordChatResume, streamWordChatTurn, withDocumentOnRequest } from '@/lib/addin/word-chat-stream';
import { baseUrl } from '@/lib/api';
import { ApiError } from '@/lib/api-error';
import type { ChatStreamEvent } from '@/lib/chat/stream';
import type {
  BodyStreamTurnApiMicrosoftWordChatThreadStreamPost,
  ResumeTurnApiMicrosoftWordChatThreadResumePostData,
  StreamTurnApiMicrosoftWordChatThreadStreamPostData,
  WordChatResumeRequest,
} from '@/lib/generated-api';

// The pane builds these requests by hand rather than through the generated SDK, so
// the paths and bodies are typed against the generated schema: a renamed backend
// field fails the type check once the client is regenerated.
const STREAM_PATH: StreamTurnApiMicrosoftWordChatThreadStreamPostData['url'] = '/api/microsoft/word/chat/thread/stream';
const RESUME_PATH: ResumeTurnApiMicrosoftWordChatThreadResumePostData['url'] = '/api/microsoft/word/chat/thread/resume';
const URL = 'https://contoso.sharepoint.com/Draft.docx';

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
});

function events(...sent: ChatStreamEvent[]): Response {
  return new Response(sent.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''), { status: 200 });
}

async function collect(stream: AsyncGenerator<ChatStreamEvent>): Promise<ChatStreamEvent[]> {
  const out: ChatStreamEvent[] = [];
  for await (const event of stream) out.push(event);
  return out;
}

function sent(): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls[0];
  return { url: String(url), init: init ?? {} };
}

describe('streamWordChatTurn', () => {
  it('posts the form the backend reads, and yields the events it streams back', async () => {
    fetchMock.mockResolvedValue(events({ t: 'text', v: 'Hi' }));
    const document = new Blob(['docx bytes']);
    const { signal } = new AbortController();

    const out = await collect(
      streamWordChatTurn({
        authorization: 'Bearer tok',
        url: URL,
        message: 'Is this right?',
        messageId: 'm-1',
        document,
        selection: 'the only option',
        signal,
      }),
    );

    const { url, init } = sent();
    expect(url).toBe(`${baseUrl}${STREAM_PATH}`);
    expect(init.method).toBe('POST');
    // No Content-Type: the browser has to set the multipart boundary itself.
    expect(init.headers).toEqual({ Accept: 'text/event-stream', Authorization: 'Bearer tok' });
    // The pane's Stop button aborts through it.
    expect(init.signal).toBe(signal);
    const form = init.body as FormData;
    const sentDocument = await (form.get('document') as File).text();
    expect({ ...Object.fromEntries(form.entries()), document: sentDocument }).toEqual({
      url: URL,
      message: 'Is this right?',
      message_id: 'm-1',
      selection: 'the only option',
      document: 'docx bytes',
    } satisfies Record<keyof BodyStreamTurnApiMicrosoftWordChatThreadStreamPost, string>);
    expect(out).toEqual([{ t: 'text', v: 'Hi' }]);
  });

  it('leaves the document and selection out when there are none, so the agent keeps its copy', async () => {
    fetchMock.mockResolvedValue(events());

    await collect(streamWordChatTurn({ authorization: 'Bearer tok', url: URL, message: 'hello', messageId: 'm-1' }));

    const form = sent().init.body as FormData;
    expect([...form.keys()]).toEqual(['url', 'message', 'message_id']);
  });

  it('turns a refusal into an ApiError carrying its status and detail', async () => {
    fetchMock.mockResolvedValue(Response.json({ detail: 'send the document' }, { status: 409 }));

    await expect(
      collect(streamWordChatTurn({ authorization: 'Bearer tok', url: URL, message: 'hi', messageId: 'm-1' })),
    ).rejects.toMatchObject({ name: 'ApiError', status: 409, detail: 'send the document' });
  });
});

describe('streamWordChatResume', () => {
  it('posts the document URL as JSON, and yields the events it streams back', async () => {
    fetchMock.mockResolvedValue(events({ t: 'text', v: 'Applied.' }));

    const { signal } = new AbortController();
    const out = await collect(streamWordChatResume({ authorization: 'Bearer tok', url: URL, signal }));

    const { url, init } = sent();
    expect(url).toBe(`${baseUrl}${RESUME_PATH}`);
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: 'Bearer tok',
    });
    expect(init.signal).toBe(signal);
    expect(JSON.parse(init.body as string)).toEqual({ url: URL } satisfies WordChatResumeRequest);
    expect(out).toEqual([{ t: 'text', v: 'Applied.' }]);
  });

  it('turns a refused sign-in into an ApiError, so the pane can sign in again', async () => {
    fetchMock.mockResolvedValue(new Response('', { status: 401 }));

    await expect(collect(streamWordChatResume({ authorization: 'Bearer old', url: URL }))).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
    });
  });
});

describe('withDocumentOnRequest', () => {
  const answer = { t: 'text', v: 'Answer' } as const;

  it('sends the turn again with the document when the conversation does not have it', async () => {
    const open = vi.fn(async function* (withDocument: boolean): AsyncGenerator<ChatStreamEvent> {
      if (!withDocument) throw new ApiError(409);
      yield answer;
    });

    expect(await collect(withDocumentOnRequest(open, false, true))).toEqual([answer]);
    expect(open.mock.calls).toEqual([[false], [true]]);
  });

  it.each([
    // Part of the first try already ran and was stored; sending it again would repeat it.
    {
      case: 'after the first event',
      status: 409,
      before: [{ t: 'message', id: 'a-1' } as const],
      withDocument: false,
      canAdd: true,
    },
    // Already sent: asking again would loop.
    { case: 'when the document was already sent', status: 409, before: [], withDocument: true, canAdd: true },
    { case: 'when there is no document to add', status: 409, before: [], withDocument: false, canAdd: false },
    { case: 'for any other refusal', status: 500, before: [], withDocument: false, canAdd: true },
  ])('does not send again $case', async ({ status, before, withDocument, canAdd }) => {
    const open = vi.fn(async function* (): AsyncGenerator<ChatStreamEvent> {
      yield* before;
      throw new ApiError(status);
    });

    await expect(collect(withDocumentOnRequest(open, withDocument, canAdd))).rejects.toMatchObject({ status });
    expect(open).toHaveBeenCalledTimes(1);
  });
});
