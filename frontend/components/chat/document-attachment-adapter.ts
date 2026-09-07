import type { AttachmentAdapter, CompleteAttachment, PendingAttachment } from '@assistant-ui/react';
import { extractAttachmentTextApiChatExtractPost } from '@/lib/generated-api';
import { ApiError } from '@/lib/api-error';

const PDF_TYPE = 'application/pdf';
const DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

/**
 * Attachment adapter for PDF and DOCX documents.
 *
 * Text extraction runs on the backend: `send()` uploads the file to
 * `/api/chat/extract`, which converts it with the same markdown converter the
 * project workflows use, and turns the returned text into a message text part
 * so the chat agent (and the Draft Detective skills) can review the contents.
 */
export class DocumentAttachmentAdapter implements AttachmentAdapter {
  accept = `${PDF_TYPE},.pdf,${DOCX_TYPE},.docx`;

  async add({ file }: { file: File }): Promise<PendingAttachment> {
    return {
      id: crypto.randomUUID(),
      type: 'document',
      name: file.name,
      contentType: file.type,
      file,
      // Defer extraction until the message is sent.
      status: { type: 'requires-action', reason: 'composer-send' },
    };
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    let text: string;
    try {
      ({ text } = await extractAttachmentTextApiChatExtractPost({ body: { file: attachment.file } }));
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : undefined;
      throw new Error(detail || `Could not read "${attachment.name}".`);
    }

    return {
      id: attachment.id,
      type: attachment.type,
      name: attachment.name,
      contentType: attachment.contentType,
      content: [
        {
          type: 'text',
          text: `Attached document "${attachment.name}":\n\n${text}`,
        },
      ],
      status: { type: 'complete' },
    };
  }

  async remove(): Promise<void> {
    // Nothing to clean up — the file is only uploaded on send.
  }
}
