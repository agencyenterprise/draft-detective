import { describe, expect, it } from 'vitest';
import { ApiError } from '@/lib/api-error';
import type { ChatMessage } from '@/lib/chat/turn';
import { conversationOf, loadFailure } from './use-live-report';

describe('loadFailure', () => {
  it('is not found for a missing thread, or one that is not a live report', () => {
    expect(loadFailure(new ApiError(404, 'Not found'), undefined)).toBe('not-found');
    expect(loadFailure(null, 'chat')).toBe('not-found');
  });

  it('is a retryable error for any other failed read', () => {
    expect(loadFailure(new ApiError(500, 'boom'), undefined)).toBe('error');
    expect(loadFailure(new Error('offline'), 'live_report')).toBe('error');
  });

  it('is nothing for a live report read cleanly, or one still loading', () => {
    expect(loadFailure(null, 'live_report')).toBeNull();
    expect(loadFailure(null, undefined)).toBeNull();
  });
});

describe('conversationOf', () => {
  const message = (fields: Partial<ChatMessage>) => fields as ChatMessage;

  it("keeps the person's messages and the agent's replies, not its tool traffic", () => {
    const conversation = conversationOf([
      message({ type: 'human', content: 'Please bring this report up to date.' }),
      message({ type: 'ai', content: 'Reading it.', tool_calls: [{ id: '1', name: 'read_file', args: {} }] }),
      message({ type: 'tool', content: 'the report' }),
      message({ type: 'ai', content: [{ type: 'text', text: 'Intake written.' }] }),
      message({ type: 'ai', content: '  ' }),
    ]);
    expect(conversation).toEqual([
      { from: 'you', text: 'Please bring this report up to date.' },
      { from: 'agent', text: 'Intake written.' },
    ]);
  });
});
