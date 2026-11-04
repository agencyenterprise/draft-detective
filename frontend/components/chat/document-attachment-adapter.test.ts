import { beforeEach, describe, expect, it, vi } from 'vitest';
import { extractAttachmentTextApiChatExtractPost } from '@/lib/generated-api';
import { ApiError } from '@/lib/api-error';
import { DocumentAttachmentAdapter } from './document-attachment-adapter';

vi.mock('@/lib/generated-api', () => ({ extractAttachmentTextApiChatExtractPost: vi.fn() }));

const extract = vi.mocked(extractAttachmentTextApiChatExtractPost);
const adapter = new DocumentAttachmentAdapter();

const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

function docx(name = 'draft.docx'): File {
  return new File(['binary'], name, { type: DOCX });
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe('DocumentAttachmentAdapter.add', () => {
  it('holds the file until the message is sent, without uploading it', async () => {
    const file = docx();

    const pending = await adapter.add({ file });

    expect(pending).toMatchObject({ type: 'document', name: 'draft.docx', contentType: DOCX, file });
    expect(pending.status).toEqual({ type: 'requires-action', reason: 'composer-send' });
    expect(extract).not.toHaveBeenCalled();
  });

  it('gives each attachment its own id', async () => {
    const [first, second] = await Promise.all([adapter.add({ file: docx() }), adapter.add({ file: docx() })]);

    expect(first.id).not.toBe(second.id);
  });
});

describe('DocumentAttachmentAdapter.send', () => {
  it('uploads the file and turns the extracted text into a labelled text part', async () => {
    extract.mockResolvedValue({ text: '# Findings\n\nThe effect was small.' } as never);
    const pending = await adapter.add({ file: docx() });

    const complete = await adapter.send(pending);

    expect(extract).toHaveBeenCalledWith({ body: { file: pending.file } });
    expect(complete).toEqual({
      id: pending.id,
      type: 'document',
      name: 'draft.docx',
      contentType: DOCX,
      content: [{ type: 'text', text: 'Attached document "draft.docx":\n\n# Findings\n\nThe effect was small.' }],
      status: { type: 'complete' },
    });
  });

  it("shows the backend's reason when it refuses the file", async () => {
    extract.mockRejectedValue(new ApiError(422, 'The document has no text.'));
    const pending = await adapter.add({ file: docx('blank.docx') });

    await expect(adapter.send(pending)).rejects.toThrow('The document has no text.');
  });

  it.each([
    ['an API error without a detail', new ApiError(500)],
    ['a network failure', new TypeError('Failed to fetch')],
  ])('falls back to a message naming the file on %s', async (_, error) => {
    extract.mockRejectedValue(error);
    const pending = await adapter.add({ file: docx('report.pdf') });

    await expect(adapter.send(pending)).rejects.toThrow('Could not read "report.pdf".');
  });
});
