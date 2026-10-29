import { baseUrl } from '@/lib/api';
import { ApiError, isApiError } from '@/lib/api-error';
import { ChatStreamEvent, errorDetail, parseEventStream } from '@/lib/chat/stream';

type WordChatTurnOptions = {
  authorization: string;
  /** The document URL Word reports, or `chatDocumentKey`'s `unsaved:<id>` for a document never saved. */
  url: string;
  message: string;
  /** The id the pane already shows the message under; the backend stores it as given. */
  messageId: string;
  /** The document's .docx, when it changed since it was last sent in this thread. */
  document?: Blob;
  selection?: string;
  signal?: AbortSignal;
};

/**
 * Stream one turn of the add-in's chat, as the same events the /chat page reads
 * (`lib/chat/stream.ts`). Signed in as the pane's Microsoft account rather than a
 * Draft Detective session, so the header is passed in. A refusal is an `ApiError`, so a
 * 401 can send the pane back to sign in.
 */
export async function* streamWordChatTurn({
  authorization,
  url,
  message,
  messageId,
  document,
  selection,
  signal,
}: WordChatTurnOptions): AsyncGenerator<ChatStreamEvent> {
  const form = new FormData();
  form.append('url', url);
  form.append('message', message);
  form.append('message_id', messageId);
  if (selection) form.append('selection', selection);
  if (document) form.append('document', document, 'document.docx');
  const response = await fetch(`${baseUrl}/api/microsoft/word/chat/thread/stream`, {
    method: 'POST',
    // No Content-Type: the browser sets the multipart boundary itself.
    headers: { Accept: 'text/event-stream', Authorization: authorization },
    body: form,
    signal,
  });
  if (!response.ok || !response.body) throw new ApiError(response.status, await errorDetail(response));
  yield* parseEventStream(response.body);
}

/**
 * Carry on an answer that paused on its card, once the card is applied or dismissed.
 * The same events as a turn; the agent reads the card's outcome itself.
 */
export async function* streamWordChatResume({
  authorization,
  url,
  signal,
}: {
  authorization: string;
  url: string;
  signal?: AbortSignal;
}): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(`${baseUrl}/api/microsoft/word/chat/thread/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', Authorization: authorization },
    body: JSON.stringify({ url }),
    signal,
  });
  if (!response.ok || !response.body) throw new ApiError(response.status, await errorDetail(response));
  yield* parseEventStream(response.body);
}

/**
 * A turn's events, sent again with the document when the server answers that the
 * conversation does not have it (409). The pane only knows what it sent, not which
 * conversation the message lands in: a document just saved, another account, or a chat
 * cleared in another pane each start one without the document.
 *
 * Only before the first event: the refusal comes before anything runs, so nothing of
 * the first try is stored.
 */
export async function* withDocumentOnRequest(
  open: (withDocument: boolean) => AsyncGenerator<ChatStreamEvent>,
  withDocument: boolean,
  canAddDocument: boolean,
): AsyncGenerator<ChatStreamEvent> {
  let started = false;
  try {
    for await (const event of open(withDocument)) {
      started = true;
      yield event;
    }
  } catch (error) {
    if (started || withDocument || !canAddDocument || !isApiError(error, 409)) throw error;
    yield* open(true);
  }
}
