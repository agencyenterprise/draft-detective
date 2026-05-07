'use client';

import { ReadonlyThread } from '@/components/assistant-ui/readonly-thread';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { AssistantRuntimeProvider, useExternalMessageConverter, useExternalStoreRuntime } from '@assistant-ui/react';
import { convertLangChainMessages, LangChainMessage } from '@assistant-ui/react-langgraph';

interface AgentMessagesDialogProps {
  messages: Array<{ [key: string]: unknown }>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
}

export function AgentMessagesDialog({ messages, open, onOpenChange, title }: AgentMessagesDialogProps) {
  const threadMessages = useExternalMessageConverter<LangChainMessage>({
    callback: convertLangChainMessages,
    messages: messages as unknown as LangChainMessage[],
    isRunning: false,
  });

  const runtime = useExternalStoreRuntime({
    messages: threadMessages,
    isRunning: false,
    onNew: async () => {},
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-base">{title ?? 'Agent Messages'}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 min-h-0">
          <AssistantRuntimeProvider runtime={runtime}>
            <ReadonlyThread />
          </AssistantRuntimeProvider>
        </div>
      </DialogContent>
    </Dialog>
  );
}
