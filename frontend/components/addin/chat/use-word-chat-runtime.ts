import { AddinSession } from '@/components/addin/addin-sign-in';
import { documentFile, fingerprint, selectedText } from '@/lib/addin/pane-document';
import { streamWordChatResume, streamWordChatTurn, withDocumentOnRequest } from '@/lib/addin/word-chat-stream';
import { getErrorMessage, isApiError } from '@/lib/api-error';
import type { ChatStreamEvent } from '@/lib/chat/stream';
import { ChatMessage, convertChatMessage, TurnAccumulator, userMessage } from '@/lib/chat/turn';
import {
  clearThreadApiMicrosoftWordChatThreadClearPost,
  getThreadApiMicrosoftWordChatThreadGet,
} from '@/lib/generated-api';
import {
  AppendMessage,
  AssistantRuntime,
  useExternalMessageConverter,
  useExternalStoreRuntime,
} from '@assistant-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useRef, useState } from 'react';

type PaneDocument = { file: Blob; fingerprint: string };

/** The conversation as the backend holds it, and the card its answer is paused on. */
export type PaneHistory = { messages: ChatMessage[]; pendingSuggestionId: string | null };

const EMPTY: PaneHistory = { messages: [], pendingSuggestionId: null };

const inWord = () => typeof Office !== 'undefined' && !!Office.context?.document;

/**
 * The document and selection to send with a message. Outside Word there are neither.
 * Inside Word a failed read stops the message: sending without the document would let
 * the agent answer from an older copy, as if nothing had been edited.
 */
async function readPane(): Promise<{ document: PaneDocument | null; selection: string }> {
  try {
    const file = await documentFile();
    const selection = await selectedText().catch(() => '');
    return { document: { file, fingerprint: await fingerprint(file) }, selection };
  } catch (error) {
    if (inWord()) throw new Error('Could not read the document from Word. Try again.', { cause: error });
    return { document: null, selection: '' };
  }
}

function messageText(message: AppendMessage): string {
  return message.content.map((part) => (part.type === 'text' ? part.text : '')).join('');
}

/**
 * The runtime for the pane's one conversation about this document.
 *
 * Built like the /chat page's (`components/chat/chat-assistant.tsx`): the history is
 * the backend's, the turn in flight is accumulated from the stream and replaced by the
 * server's copy once it ends. There is no thread list: one conversation per document,
 * which `clear` sets aside.
 *
 * The document goes with a message only when it changed since it was last sent in
 * this conversation. After a reload nothing is known to have been sent, so the first
 * message sends it again.
 *
 * An answer can pause on its card (the agent's `ask_to_apply`): the stream ends with an
 * `interrupt`, the history names the card it waits on, and `resume` carries the answer
 * on once the card is applied or dismissed.
 */
export function useWordChatRuntime(
  session: AddinSession,
  documentUrl: string,
  // The key as it is now: a first save or Save As changes it while the pane is open,
  // and nothing re-renders the pane when it does, so a message reads it as it is sent.
  currentDocumentUrl: () => string = () => documentUrl,
) {
  const { email, authorize, expire } = session;
  const queryClient = useQueryClient();
  const keyFor = (url: string) => ['addin-chat', email, url] as const;
  const queryKey = useMemo(() => ['addin-chat', email, documentUrl] as const, [email, documentUrl]);

  const fetchHistory = async (url: string = documentUrl): Promise<PaneHistory> => {
    try {
      const history = await getThreadApiMicrosoftWordChatThreadGet({
        query: { url },
        headers: { Authorization: await authorize() },
      });
      return {
        messages: history.messages as ChatMessage[],
        pendingSuggestionId: history.pending_suggestion_id ?? null,
      };
    } catch (error) {
      if (isApiError(error, 401)) expire();
      throw error;
    }
  };

  const history = useQuery({ queryKey, queryFn: () => fetchHistory(), staleTime: Infinity, retry: false });
  const [inflight, setInflight] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  // The card the answer was paused on while it carries on, null when it is not.
  const [resumedCard, setResumedCard] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sentRef = useRef<string | null>(null);

  const messages = useMemo(() => [...(history.data?.messages ?? []), ...inflight], [history.data, inflight]);
  const threadMessages = useExternalMessageConverter({ callback: convertChatMessage, messages, isRunning });

  /**
   * Stream one run of the agent into the thread: a new message, or the rest of a paused
   * answer. The stored copy replaces the local one once it ends, as on /chat.
   */
  const run = async (
    turn: TurnAccumulator,
    open: (signal: AbortSignal) => Promise<AsyncGenerator<ChatStreamEvent>>,
    shown: (turn: TurnAccumulator) => ChatMessage[],
    url: string = documentUrl,
  ) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setInflight(shown(turn));
    setIsRunning(true);

    let completed = false;
    try {
      for await (const event of await open(controller.signal)) {
        turn.apply(event);
        setInflight(shown(turn));
        if (event.t === 'error') throw new Error(event.v);
      }
      completed = true;
    } catch (error) {
      if (isApiError(error, 401)) expire();
      if (controller.signal.aborted) turn.cancel();
      else turn.fail(getErrorMessage(error, 'The turn failed.'));
      setInflight(shown(turn));
    } finally {
      // As on /chat: the stored turn replaces the local one in a single render, and
      // after a failure only the assistant side, with its status, stays local.
      const stored = await fetchHistory(url).catch(() => null);
      if (stored) queryClient.setQueryData(keyFor(url), stored);
      setInflight(completed && stored ? [] : stored ? turn.assistantMessages : shown(turn));
      setIsRunning(false);
    }
  };

  const onNew = async (message: AppendMessage) => {
    const text = messageText(message);
    const user = userMessage(text, []);
    const url = currentDocumentUrl();
    // Another key is another conversation, which has not been sent this document.
    if (url !== documentUrl) sentRef.current = null;
    await run(
      new TurnAccumulator(user),
      async (signal) => {
        const { document, selection } = await readPane();
        const changed = !!document && document.fingerprint !== sentRef.current;
        const authorization = await authorize();
        const open = (withDocument: boolean) =>
          streamWordChatTurn({
            authorization,
            url,
            message: text,
            messageId: user.id,
            document: withDocument ? document?.file : undefined,
            selection,
            signal,
          });
        return markSent(withDocumentOnRequest(open, changed, !!document), document);
      },
      (turn) => turn.messages,
      url,
    );
  };

  /** The document is mounted before the first event, so from then on it counts as sent. */
  async function* markSent(events: AsyncGenerator<ChatStreamEvent>, document: PaneDocument | null) {
    for await (const event of events) {
      if (document) sentRef.current = document.fingerprint;
      yield event;
    }
  }

  /** Carry the paused answer on: its card has been applied or dismissed. */
  const resume = async () => {
    // The question is already stored; only the agent's side of the rest is shown.
    const placeholder = userMessage('', []);
    setResumedCard(history.data?.pendingSuggestionId ?? '');
    try {
      await run(
        new TurnAccumulator(placeholder),
        async (signal) => streamWordChatResume({ authorization: await authorize(), url: documentUrl, signal }),
        (turn) => turn.assistantMessages,
      );
    } finally {
      setResumedCard(null);
    }
  };

  const clear = useMutation({
    mutationFn: async () =>
      clearThreadApiMicrosoftWordChatThreadClearPost({
        body: { url: documentUrl },
        headers: { Authorization: await authorize() },
      }),
    onSuccess: () => {
      sentRef.current = null;
      setInflight([]);
      queryClient.setQueryData(queryKey, EMPTY);
    },
    onError: (error) => {
      if (isApiError(error, 401)) expire();
    },
  });

  const runtime: AssistantRuntime = useExternalStoreRuntime({
    isRunning,
    isLoading: history.isLoading,
    messages: threadMessages,
    onNew,
    onCancel: async () => abortRef.current?.abort(),
  });
  return {
    runtime,
    clear,
    resume,
    resuming: resumedCard !== null,
    resumedCard: resumedCard || null,
    pendingSuggestionId: isRunning ? null : (history.data?.pendingSuggestionId ?? null),
    historyError: history.error,
  };
}
