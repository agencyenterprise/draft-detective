import {
  annotateApiMicrosoftWordCommentsAnnotatePost,
  applySuggestionsApiMicrosoftWordSuggestionsApplyPost,
  HandoffOutcome,
  HandoffView,
  ItemOutcome,
} from '@/lib/generated-api';
import { NOT_FOUND, ParagraphWork, planHandoff, relocate } from './handoff-plan';
import { paragraphTexts, readParagraphMarkup, writeParagraphMarkup } from './word-writes';

/**
 * Write a handoff from Teams into the open document, and say what landed.
 *
 * One read and one write per paragraph however many items it has, because each write
 * is a chance for Word to reject the package. Edits go before comments: a comment whose
 * words an edit removed falls back to the whole paragraph, whereas an edit whose words
 * now carry comment markers is still found.
 */
export async function applyHandoff(handoff: HandoffView, authorization: string): Promise<HandoffOutcome> {
  const headers = { Authorization: authorization };
  const plan = planHandoff(await paragraphTexts(), handoff.items.comments ?? [], handoff.items.edits ?? []);
  const outcomes: ItemOutcome[] = [...plan.unplaced];

  for (const work of plan.paragraphs.values()) {
    outcomes.push(...(await applyToParagraph(work, headers)));
  }
  return { items: outcomes };
}

function failed(work: ParagraphWork, detail: string): ItemOutcome[] {
  return [
    ...work.edits.map((edit): ItemOutcome => ({ kind: 'edit', quote: edit.quote, applied: false, detail })),
    ...work.comments.map((comment): ItemOutcome => ({ kind: 'comment', quote: comment.quote, applied: false, detail })),
  ];
}

async function applyToParagraph(work: ParagraphWork, headers: Record<string, string>): Promise<ItemOutcome[]> {
  const index = relocate(await paragraphTexts(), work);
  if (index === null) return failed(work, NOT_FOUND);

  try {
    const read = await readParagraphMarkup(index);
    if (!read) return failed(work, NOT_FOUND);
    let markup: string = read;
    const outcomes: ItemOutcome[] = [];

    if (work.edits.length) {
      const applied = await applySuggestionsApiMicrosoftWordSuggestionsApplyPost({
        body: { ooxml: markup, edits: work.edits },
        headers,
      });
      markup = applied.ooxml ?? markup;
      // No markup back means nothing was written, whatever each edit says.
      const written = !!applied.ooxml;
      for (const edit of applied.edits ?? []) {
        outcomes.push({
          kind: 'edit',
          quote: edit.quote,
          applied: written && edit.applied,
          detail: written ? (edit.detail ?? '') : edit.detail || applied.detail || 'the change was not written',
        });
      }
    }

    for (const comment of work.comments) {
      const anchored = await annotateApiMicrosoftWordCommentsAnnotatePost({
        body: { ooxml: markup, quote: comment.quote, comment: comment.comment },
        headers,
      });
      markup = anchored.ooxml ?? markup;
      outcomes.push({
        kind: 'comment',
        quote: comment.quote,
        applied: anchored.anchored,
        detail: anchored.detail ?? '',
      });
    }

    if (outcomes.some((outcome) => outcome.applied)) {
      await writeParagraphMarkup(index, markup);
    }
    return outcomes;
  } catch (error) {
    console.error('Could not apply to paragraph', index, error);
    return failed(work, 'Word or the service refused the change');
  }
}
