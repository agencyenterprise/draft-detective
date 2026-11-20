'use client';

import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { convertChatMessage, type ChatMessage } from '@/lib/chat/turn';
import { AssistantRuntimeProvider, useExternalMessageConverter, useExternalStoreRuntime } from '@assistant-ui/react';
import { MessagesSquare } from 'lucide-react';

/**
 * The conversation behind the buttons, read-only and rendered as /chat renders
 * it: the messages the buttons sent, the agent's replies, and every step it took
 * (tool calls, subagents, reasoning). For following a run and debugging it.
 */
export function ConversationSheet({ messages, running }: { messages: ChatMessage[]; running: boolean }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          <MessagesSquare className="size-4" /> Show the conversation
        </Button>
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-2xl">
        <SheetHeader className="border-b">
          <SheetTitle>The conversation</SheetTitle>
          <SheetDescription>
            What the buttons sent, the agent&apos;s replies, and each step it took. Read-only.
          </SheetDescription>
        </SheetHeader>
        {/* The chat page's size: its thread root sets text-sm; ReadonlyThread does not. */}
        <div className="min-h-0 flex-1 text-sm">
          <Transcript messages={withoutImages(messages)} running={running} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** A markdown image, `![alt](url)`, which a browser would fetch as soon as it shows. */
const IMAGE = /!\[([^\]]*)\]\(([^)\s]*)[^)]*\)/g;

/**
 * The messages with every markdown image turned into a plain link, in any text
 * they carry (replies, reasoning, tool results). The guided view shows no images
 * either: a web page a researcher read could plant one whose URL carries data out.
 */
export function withoutImages(messages: ChatMessage[]): ChatMessage[] {
  const clean = (value: unknown): unknown => {
    if (typeof value === 'string') return value.replace(IMAGE, '[$1]($2)');
    if (Array.isArray(value)) return value.map(clean);
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value).map(([key, inner]) => [key, clean(inner)]));
    }
    return value;
  };
  return messages.map((message) => clean(message) as ChatMessage);
}

function Transcript({ messages, running }: { messages: ChatMessage[]; running: boolean }) {
  // The chat page's converter: tool results join their calls, attachments show as chips.
  const threadMessages = useExternalMessageConverter<ChatMessage>({
    callback: convertChatMessage,
    messages,
    isRunning: running,
  });
  const runtime = useExternalStoreRuntime({ messages: threadMessages, isRunning: running, onNew: async () => {} });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ReadonlyThread />
    </AssistantRuntimeProvider>
  );
}
