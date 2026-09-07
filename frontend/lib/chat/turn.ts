import { convertLangChainMessages, type LangChainMessage } from '@assistant-ui/react-langgraph';
import type { useExternalMessageConverter } from '@assistant-ui/react';
import type { ChatStreamEvent } from '@/lib/chat/stream';

/**
 * A message of a chat thread, in the shape the backend serves history in and
 * `@assistant-ui/react-langgraph` renders (`lib/services/chat/history.py`).
 */
export type ChatMessage = LangChainMessage;

/** An attachment as recorded on a user message. `text` is client-side only, for the turn in flight. */
export interface ChatAttachmentMeta {
  name: string;
  path?: string;
  chars?: number;
  text?: string;
}

type AiMessage = Extract<ChatMessage, { type: 'ai' }>;
type AiContentBlock = Exclude<AiMessage['content'], string>[number];
type ToolCall = NonNullable<AiMessage['tool_calls']>[number];

const localId = (kind: string) => `local-${kind}-${crypto.randomUUID()}`;

/**
 * The user's message for a turn. The id is generated here and sent along, so the
 * stored copy and this one are the same message to assistant-ui.
 */
export function userMessage(text: string, attachments: ChatAttachmentMeta[]): ChatMessage & { id: string } {
  return {
    id: crypto.randomUUID(),
    type: 'human',
    content: text,
    additional_kwargs: { attachments },
  };
}

/**
 * Builds the assistant side of a turn from the backend's stream events, as
 * immutable snapshots: every `apply` returns a fresh array with fresh objects
 * for anything that changed, which is what React and the message converter's
 * identity cache need to notice the update.
 *
 * Shapes and ids mirror `to_ui_messages` on the backend, so a turn is the same
 * set of messages while it streams and after it is reloaded from the
 * checkpointer, and swapping one for the other does not create branches.
 */
export class TurnAccumulator {
  private settled: ChatMessage[] = [];
  private open: AiMessage | null = null;

  constructor(private readonly user: ChatMessage) {}

  /** The turn so far, user message first. */
  get messages(): ChatMessage[] {
    return [this.user, ...this.settled, ...(this.open ? [this.open] : [])];
  }

  /** The turn without the user message, for after the server has stored that itself. */
  get assistantMessages(): ChatMessage[] {
    return [...this.settled, ...(this.open ? [this.open] : [])];
  }

  apply(event: ChatStreamEvent): ChatMessage[] {
    switch (event.t) {
      case 'message':
        this.close();
        this.open = { id: event.id, type: 'ai', content: [], tool_calls: [] };
        break;
      case 'message_end':
        if (this.open && event.id) this.open = { ...this.open, id: event.id };
        this.close();
        break;
      case 'text':
        this.appendBlock({ type: 'text', text: event.v }, (last) =>
          last.type === 'text' ? { type: 'text', text: last.text + event.v } : null,
        );
        break;
      case 'reasoning':
        this.appendBlock({ type: 'reasoning', summary: [{ type: 'summary_text', text: event.v }] }, (last) =>
          last.type === 'reasoning'
            ? { type: 'reasoning', summary: [{ type: 'summary_text', text: (last.summary[0]?.text ?? '') + event.v }] }
            : null,
        );
        break;
      case 'tool': {
        const current = this.ensureOpen();
        // Tool arguments are JSON by construction; the event type is just looser about it.
        const call: ToolCall = { id: event.id, name: event.name, args: (event.args ?? {}) as ToolCall['args'] };
        this.open = { ...current, tool_calls: [...(current.tool_calls ?? []), call] };
        break;
      }
      case 'tool_result': {
        const name = this.callName(event.id);
        this.close();
        this.settled = [
          ...this.settled,
          {
            id: event.mid ?? localId('tool'),
            type: 'tool',
            tool_call_id: event.id,
            name,
            content: typeof event.result === 'string' ? event.result : JSON.stringify(event.result),
            status: event.isError ? 'error' : 'success',
          },
        ];
        break;
      }
      case 'error':
        this.fail(event.v);
        break;
    }
    return this.messages;
  }

  /** Mark the turn as ended early, with the reason shown on the assistant message. */
  fail(reason: string): ChatMessage[] {
    const current = this.ensureOpen();
    this.open = { ...current, status: { type: 'incomplete', reason: 'error', error: reason } };
    return this.messages;
  }

  cancel(): ChatMessage[] {
    if (this.open) this.open = { ...this.open, status: { type: 'incomplete', reason: 'cancelled' } };
    return this.messages;
  }

  private ensureOpen(): AiMessage {
    if (!this.open) this.open = { id: localId('assistant'), type: 'ai', content: [], tool_calls: [] };
    return this.open;
  }

  private callName(callId: string): string {
    for (const message of [this.open, ...this.settled]) {
      const call = message?.type === 'ai' ? message.tool_calls?.find((c) => c.id === callId) : undefined;
      if (call) return call.name;
    }
    return 'tool';
  }

  private close(): void {
    if (this.open) this.settled = [...this.settled, this.open];
    this.open = null;
  }

  private appendBlock(block: AiContentBlock, merge: (last: AiContentBlock) => AiContentBlock | null): void {
    const current = this.ensureOpen();
    const content = typeof current.content === 'string' ? [] : [...current.content];
    const last = content[content.length - 1];
    const merged = last ? merge(last) : null;
    if (merged) content[content.length - 1] = merged;
    else content.push(block);
    this.open = { ...current, content };
  }
}

function attachmentsOf(message: ChatMessage): ChatAttachmentMeta[] {
  if (message.type !== 'human') return [];
  const listed = message.additional_kwargs?.attachments;
  return Array.isArray(listed) ? (listed as ChatAttachmentMeta[]) : [];
}

/**
 * `convertLangChainMessages`, plus the attachment chips on user messages. The
 * attachment list also rides along in `metadata.custom` so the document panel
 * can find what to show.
 */
export const convertChatMessage: useExternalMessageConverter.Callback<ChatMessage> = (message, metadata) => {
  const converted = convertLangChainMessages(message, metadata);
  const attachments = attachmentsOf(message);
  if (attachments.length === 0 || Array.isArray(converted) || converted.role !== 'user') return converted;
  return {
    ...converted,
    attachments: attachments.map((attachment, index) => ({
      id: `${message.id ?? 'user'}-attachment-${index}`,
      type: 'document' as const,
      name: attachment.name,
      contentType: 'text/markdown',
      status: { type: 'complete' as const },
      content: [],
    })),
    metadata: { ...converted.metadata, custom: { ...converted.metadata?.custom, attachments } },
  };
};
