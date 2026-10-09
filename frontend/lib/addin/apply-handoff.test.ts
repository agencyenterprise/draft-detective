import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HandoffView } from '@/lib/generated-api';

const word = vi.hoisted(() => ({
  paragraphTexts: vi.fn(),
  readParagraphMarkup: vi.fn(),
  writeParagraphMarkup: vi.fn(),
}));
const api = vi.hoisted(() => ({
  annotateApiMicrosoftWordCommentsAnnotatePost: vi.fn(),
  applySuggestionsApiMicrosoftWordSuggestionsApplyPost: vi.fn(),
}));

vi.mock('./word-writes', () => word);
vi.mock('@/lib/generated-api', () => api);

import { applyHandoff } from './apply-handoff';
import { AMBIGUOUS, NOT_FOUND } from './handoff-plan';

const PARAGRAPHS = ['Introduction', 'We recieve funding and this is the only option.', 'Funding is discussed below.'];

function handoff(items: HandoffView['items']): HandoffView {
  return {
    id: 'h1',
    document_name: 'Draft.docx',
    document_url: 'https://x',
    items,
    created_at: '2026-10-09T00:00:00Z',
  } as unknown as HandoffView;
}

beforeEach(() => {
  vi.resetAllMocks();
  word.paragraphTexts.mockResolvedValue(PARAGRAPHS);
  word.readParagraphMarkup.mockResolvedValue('<in/>');
  api.applySuggestionsApiMicrosoftWordSuggestionsApplyPost.mockResolvedValue({
    applied: 1,
    ooxml: '<edited/>',
    edits: [{ quote: 'recieve', applied: true, detail: '' }],
  });
  api.annotateApiMicrosoftWordCommentsAnnotatePost.mockResolvedValue({
    anchored: true,
    ooxml: '<edited-and-commented/>',
    detail: '',
  });
});

describe('applyHandoff', () => {
  it('writes edits then comments into one paragraph, with one read and one write', async () => {
    const outcome = await applyHandoff(
      handoff({
        comments: [{ quote: 'the only option', comment: 'Overclaims.' }],
        edits: [{ quote: 'recieve', replacement: 'receive' }],
      }),
      'Bearer t',
    );

    expect(word.readParagraphMarkup).toHaveBeenCalledTimes(1);
    expect(word.readParagraphMarkup).toHaveBeenCalledWith(1);
    // The comment is written into the markup the edits produced, not the original.
    expect(api.annotateApiMicrosoftWordCommentsAnnotatePost.mock.calls[0][0].body.ooxml).toBe('<edited/>');
    expect(api.annotateApiMicrosoftWordCommentsAnnotatePost.mock.calls[0][0].headers).toEqual({
      Authorization: 'Bearer t',
    });
    expect(word.writeParagraphMarkup).toHaveBeenCalledTimes(1);
    expect(word.writeParagraphMarkup).toHaveBeenCalledWith(1, '<edited-and-commented/>');
    expect(outcome.items?.map((item) => [item.kind, item.applied])).toEqual([
      ['edit', true],
      ['comment', true],
    ]);
  });

  it('reports words that are gone or ambiguous without calling the service', async () => {
    const outcome = await applyHandoff(
      handoff({ comments: [{ quote: 'unding', comment: 'x' }], edits: [{ quote: 'vanished', replacement: 'y' }] }),
      'Bearer t',
    );

    expect(api.applySuggestionsApiMicrosoftWordSuggestionsApplyPost).not.toHaveBeenCalled();
    expect(word.writeParagraphMarkup).not.toHaveBeenCalled();
    expect(outcome.items?.map((item) => item.detail)).toEqual([NOT_FOUND, AMBIGUOUS]);
  });

  it('writes nothing when nothing landed', async () => {
    api.annotateApiMicrosoftWordCommentsAnnotatePost.mockResolvedValue({ anchored: false, detail: 'no text' });

    const outcome = await applyHandoff(handoff({ comments: [{ quote: 'the only option', comment: 'x' }] }), 'Bearer t');

    expect(word.writeParagraphMarkup).not.toHaveBeenCalled();
    expect(outcome.items?.[0]).toMatchObject({ applied: false, detail: 'no text' });
  });

  it('an edit the service withheld is not reported as applied, and nothing is written', async () => {
    api.applySuggestionsApiMicrosoftWordSuggestionsApplyPost.mockResolvedValue({
      applied: 0,
      ooxml: null,
      edits: [{ quote: 'recieve', applied: true, detail: '' }],
      detail: 'The change would have altered text it should not have',
    });

    const outcome = await applyHandoff(handoff({ edits: [{ quote: 'recieve', replacement: 'receive' }] }), 'Bearer t');

    expect(outcome.items?.[0]).toMatchObject({
      applied: false,
      detail: 'The change would have altered text it should not have',
    });
    expect(word.writeParagraphMarkup).not.toHaveBeenCalled();
  });

  it('reports every item in a paragraph Word refused', async () => {
    word.writeParagraphMarkup.mockRejectedValue(new Error('GeneralException'));
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const outcome = await applyHandoff(
      handoff({
        comments: [{ quote: 'the only option', comment: 'x' }],
        edits: [{ quote: 'recieve', replacement: 'receive' }],
      }),
      'Bearer t',
    );

    expect(outcome.items?.every((item) => !item.applied)).toBe(true);
    expect(outcome.items).toHaveLength(2);
  });

  it('reports a paragraph that moved away before it could be written', async () => {
    word.paragraphTexts.mockResolvedValueOnce(PARAGRAPHS).mockResolvedValueOnce(['Introduction', 'Rewritten.']);

    const outcome = await applyHandoff(handoff({ edits: [{ quote: 'recieve', replacement: 'receive' }] }), 'Bearer t');

    expect(word.readParagraphMarkup).not.toHaveBeenCalled();
    expect(outcome.items?.[0]).toMatchObject({ applied: false, detail: NOT_FOUND });
  });
});
