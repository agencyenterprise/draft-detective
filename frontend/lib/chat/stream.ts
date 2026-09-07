import { baseUrl, getAuthHeader } from '@/lib/api';
import type { ChatAttachment } from '@/lib/generated-api';

/**
 * One event of a streamed chat turn, as the backend emits it
 * (`lib/services/chat/events.py`).
 */
export type ChatStreamEvent =
  /** An assistant message opens, under the id it is stored as. */
  | { t: 'message'; id: string }
  /** The assistant message closes; `id` is its final stored id. */
  | { t: 'message_end'; id: string }
  | { t: 'text'; v: string }
  | { t: 'reasoning'; v: string }
  | { t: 'tool'; id: string; name: string; args?: Record<string, unknown> }
  /** `mid` is the stored id of the tool message carrying the result. */
  | { t: 'tool_result'; id: string; result: unknown; isError?: boolean; mid?: string }
  | { t: 'error'; v: string };

interface StreamChatTurnOptions {
  threadId: string;
  /** A model id from `GET /api/chat/models`; the backend falls back to its default. */
  model?: string;
  /** The user's new message. The thread's history is the backend's; it is not resent. */
  message: string;
  /** The id the page already shows the message under; the backend stores it as given. */
  messageId?: string;
  attachments?: ChatAttachment[];
  signal?: AbortSignal;
}

/**
 * Stream one turn from the backend's chat agent.
 *
 * Talks to FastAPI directly, like the rest of the app, rather than through a
 * Next.js route. The response is server-sent events: each `data:` line is one
 * JSON `ChatStreamEvent`; comment lines are heartbeats and are skipped.
 */
export async function* streamChatTurn({
  threadId,
  model,
  message,
  messageId,
  attachments = [],
  signal,
}: StreamChatTurnOptions): AsyncGenerator<ChatStreamEvent> {
  const authorization = await getAuthHeader();
  const response = await fetch(`${baseUrl}/api/chat/threads/${threadId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(authorization ? { Authorization: authorization } : {}),
    },
    body: JSON.stringify({ model, message, message_id: messageId, attachments }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(await errorDetail(response));
  }

  yield* parseEventStream(response.body);
}

async function errorDetail(response: Response): Promise<string> {
  const fallback = `Chat request failed with status ${response.status}`;
  const text = await response.text().catch(() => '');
  if (!text) return fallback;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    return typeof parsed.detail === 'string' ? parsed.detail : fallback;
  } catch {
    return text;
  }
}

/** Parse an SSE body into events, ignoring heartbeats and blank lines. */
export async function* parseEventStream(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const takeLines = (flush: boolean): string[] => {
    const lines: string[] = [];
    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
      lines.push(buffer.slice(0, newlineIndex));
      buffer = buffer.slice(newlineIndex + 1);
    }
    if (flush && buffer) {
      lines.push(buffer);
      buffer = '';
    }
    return lines;
  };

  const toEvents = (lines: string[]): ChatStreamEvent[] =>
    lines
      .map((line) => line.trim())
      .filter((line) => line.startsWith('data:'))
      .map((line) => JSON.parse(line.slice('data:'.length).trim()) as ChatStreamEvent);

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    yield* toEvents(takeLines(false));
  }
  // Flush the decoder: a final chunk can end mid-way through a multibyte character.
  buffer += decoder.decode();
  yield* toEvents(takeLines(true));
}
