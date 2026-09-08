'use client';

import type { ChatAttachmentMeta } from '@/lib/chat/turn';
import { readThreadFileContentApiChatThreadsThreadIdFilesGet } from '@/lib/generated-api';
import { useAuiState, type ThreadMessage } from '@assistant-ui/react';
import { useQuery } from '@tanstack/react-query';
import { FileTextIcon } from 'lucide-react';
import { useMemo } from 'react';

/**
 * The first document attached in the thread, as recorded on its user message
 * (see `convertChatMessage`). While the turn that attached it is still in
 * flight the text is local; afterwards it is read from the agent's filesystem.
 */
function findFirstAttachment(messages: readonly ThreadMessage[]): ChatAttachmentMeta | null {
  for (const message of messages) {
    const attachments = message.metadata?.custom?.attachments;
    if (Array.isArray(attachments) && attachments.length > 0) return attachments[0] as ChatAttachmentMeta;
  }
  return null;
}

/**
 * Read-only right-side panel showing the first document uploaded in the current
 * thread. Proof-of-concept: a richer source (revisions, structured view) can be
 * plugged in later.
 */
export function DocumentPanel() {
  const messages = useAuiState((state) => state.thread.messages);
  const remoteId = useAuiState((state) => state.threadListItem.remoteId);
  const attachment = useMemo(() => findFirstAttachment(messages ?? []), [messages]);

  const file = useQuery({
    enabled: remoteId !== undefined && attachment?.path !== undefined && attachment.text === undefined,
    queryKey: ['chat', 'thread', remoteId, 'file', attachment?.path] as const,
    queryFn: () =>
      readThreadFileContentApiChatThreadsThreadIdFilesGet({
        path: { thread_id: remoteId! },
        query: { path: attachment!.path! },
      }),
    staleTime: Infinity,
  });

  const text = attachment?.text ?? file.data?.content;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <h2 className="text-sm font-medium leading-tight">Document</h2>
          {attachment ? (
            <p className="truncate text-xs text-muted-foreground" title={attachment.name}>
              {attachment.name}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">Nothing uploaded yet</p>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {text ? (
          <pre className="font-sans text-xs leading-relaxed whitespace-pre-wrap text-foreground">{text}</pre>
        ) : attachment ? (
          <p className="text-xs text-muted-foreground">{file.isError ? 'Could not load the document.' : 'Loading…'}</p>
        ) : (
          <p className="text-xs text-muted-foreground">
            Upload a PDF or DOCX in the chat and its text will appear here for reference.
          </p>
        )}
      </div>
    </div>
  );
}
