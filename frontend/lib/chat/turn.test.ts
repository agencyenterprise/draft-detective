import { convertLangChainMessages } from '@assistant-ui/react-langgraph';
import { describe, expect, it } from 'vitest';
import type { ChatStreamEvent } from './stream';
import { convertChatMessage, TurnAccumulator, userMessage, type ChatMessage } from './turn';

function turnOf(...events: ChatStreamEvent[]): TurnAccumulator {
  const turn = new TurnAccumulator(userMessage('Check this', []));
  for (const event of events) turn.apply(event);
  return turn;
}

function resumed(event: { name?: string }): ChatMessage[] {
  const turn = new TurnAccumulator(userMessage('', []));
  turn.apply({ t: 'tool_result', id: 'c1', result: 'Applied 7 of 8.', mid: 't1', ...event });
  return turn.assistantMessages;
}

describe('TurnAccumulator', () => {
  it('joins streamed deltas into one block per kind, in the order they came', () => {
    const turn = turnOf(
      { t: 'message', id: 'a1' },
      { t: 'reasoning', v: 'Look' },
      { t: 'reasoning', v: 'ing' },
      { t: 'text', v: 'Hel' },
      { t: 'text', v: 'lo' },
    );

    expect(turn.assistantMessages).toEqual([
      {
        id: 'a1',
        type: 'ai',
        content: [
          { type: 'reasoning', summary: [{ type: 'summary_text', text: 'Looking' }] },
          { type: 'text', text: 'Hello' },
        ],
        tool_calls: [],
      },
    ]);
  });

  it('stores each message under the final id message_end sends, and opens the next one apart', () => {
    const turn = turnOf(
      { t: 'message', id: 'chunk-id' },
      { t: 'text', v: 'One' },
      { t: 'message_end', id: 'stored-id' },
      { t: 'message', id: 'a2' },
      { t: 'text', v: 'Two' },
    );

    expect(turn.assistantMessages.map((m) => [m.id, m.content])).toEqual([
      ['stored-id', [{ type: 'text', text: 'One' }]],
      ['a2', [{ type: 'text', text: 'Two' }]],
    ]);
  });

  it('opens a message of its own for deltas that arrive before any message event', () => {
    const [message] = turnOf({ t: 'text', v: 'Hi' }).assistantMessages;

    expect(message.id).toMatch(/^local-assistant-/);
    expect(message.content).toEqual([{ type: 'text', text: 'Hi' }]);
  });

  it("settles a tool's result after the message that called it, named after its call", () => {
    const turn = turnOf(
      { t: 'message', id: 'a1' },
      { t: 'tool', id: 'c1', name: 'search', args: { query: 'x' } },
      { t: 'tool_result', id: 'c1', result: { hits: 2 }, mid: 't1' },
    );

    expect(turn.assistantMessages).toEqual([
      { id: 'a1', type: 'ai', content: [], tool_calls: [{ id: 'c1', name: 'search', args: { query: 'x' } }] },
      { id: 't1', type: 'tool', tool_call_id: 'c1', name: 'search', content: '{"hits":2}', status: 'success' },
    ]);
  });

  it('keeps a string result as it is, and marks a failed one', () => {
    const [, result] = turnOf(
      { t: 'tool', id: 'c1', name: 'search' },
      { t: 'tool_result', id: 'c1', result: 'Timed out', isError: true },
    ).assistantMessages;

    expect(result).toMatchObject({ type: 'tool', content: 'Timed out', status: 'error' });
    expect(result.id).toMatch(/^local-tool-/);
  });

  it('names the result of a call made before the stream began, as the backend sends it', () => {
    const [result] = resumed({ name: 'ask_to_apply' });

    expect(result).toMatchObject({ type: 'tool', tool_call_id: 'c1', name: 'ask_to_apply' });
  });

  it('ends the open message with the error, keeping what it streamed', () => {
    const [message] = turnOf(
      { t: 'message', id: 'a1' },
      { t: 'text', v: 'Part' },
      { t: 'error', v: 'Rate limited' },
    ).assistantMessages;

    expect(message).toMatchObject({
      id: 'a1',
      content: [{ type: 'text', text: 'Part' }],
      status: { type: 'incomplete', reason: 'error', error: 'Rate limited' },
    });
  });

  it('shows an error that arrives before any message on a message of its own', () => {
    const messages = turnOf({ t: 'error', v: 'Model unavailable' }).assistantMessages;

    expect(messages).toHaveLength(1);
    expect(messages[0]).toMatchObject({ type: 'ai', status: { reason: 'error', error: 'Model unavailable' } });
  });

  it('marks only an open message as cancelled', () => {
    expect(turnOf({ t: 'message', id: 'a1' }).cancel()[1]).toMatchObject({
      status: { type: 'incomplete', reason: 'cancelled' },
    });

    const ended = turnOf({ t: 'message', id: 'a1' }, { t: 'message_end', id: 'a1' });
    const before = ended.messages;
    expect(ended.cancel()).toEqual(before);
  });

  it('puts the user message first in messages and leaves it out of assistantMessages', () => {
    const user = userMessage('Check this', [{ name: 'notes.md' }]);
    const turn = new TurnAccumulator(user);
    turn.apply({ t: 'text', v: 'Hi' });

    expect(turn.messages[0]).toBe(user);
    expect(turn.assistantMessages).toEqual(turn.messages.slice(1));
  });

  // React and the message converter's identity cache only see a change through new objects.
  it('returns a new snapshot on every event and never changes an earlier one', () => {
    const turn = turnOf({ t: 'message', id: 'a1' }, { t: 'text', v: 'Hel' });
    const before = turn.messages;
    const openBefore = before[1];

    const after = turn.apply({ t: 'text', v: 'lo' });

    expect(after).not.toBe(before);
    expect(after[1]).not.toBe(openBefore);
    expect(after[0]).toBe(before[0]);
    expect(openBefore).toMatchObject({ content: [{ type: 'text', text: 'Hel' }] });
  });
});

describe('convertChatMessage', () => {
  it("shows a user message's attachments and passes them on to the document panel", () => {
    const attachments = [{ name: 'notes.md', path: 'chat/notes.md', chars: 120 }];
    const converted = convertChatMessage(
      { id: 'u1', type: 'human', content: 'Read this', additional_kwargs: { attachments } },
      {},
    );

    expect(converted).toMatchObject({
      role: 'user',
      attachments: [{ id: 'u1-attachment-0', type: 'document', name: 'notes.md' }],
      metadata: { custom: { attachments } },
    });
  });

  it('leaves a message without attachments as the LangChain converter made it', () => {
    const message: ChatMessage = { id: 'u1', type: 'human', content: 'Hi' };

    expect(convertChatMessage(message, {})).toEqual(convertLangChainMessages(message, {}));
  });
});
