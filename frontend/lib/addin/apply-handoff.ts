import { HandoffComment, HandoffEdit, HandoffView } from '@/lib/generated-api';
import { AppliedItem, HandoffPlan, normalize, planHandoff } from './handoff-plan';
import { Lookup, lookup, rawSpan } from './quote-search';

/**
 * Write a handoff's comments and tracked changes into the open document with Word's own
 * API, and say what landed.
 *
 * Each quote is found with Word's search inside its paragraph; an edit replaces those
 * words with change tracking on, and a comment is added on them. A write takes under a
 * tenth of a second in Word for the web, and touches only the quoted words, so a
 * coauthor's edits elsewhere in the paragraph are left alone.
 *
 * Word records these under the name of whoever applies them, with no way to name another
 * author, so each comment is marked as Draft Detective's in its text. An item Word's
 * search cannot pin down (a quote across a footnote mark, say), or that Word refuses, is
 * reported as not applied.
 */
export async function applyHandoff(handoff: Pick<HandoffView, 'items'>): Promise<AppliedItem[]> {
  const { plan, written } = await write(handoff.items.comments ?? [], handoff.items.edits ?? []);
  return outcomesOf(plan, written, canWrite() ? NOT_WRITTEN : OLD_WORD);
}

export const COMMENT_PREFIX = 'Draft Detective: ';
export const NOT_WRITTEN = 'Word could not find these exact words, or would not change them';
export const OLD_WORD = 'this version of Word cannot add tracked changes or comments';

/** A comment's text, marked once as Draft Detective's even if the agent already did. */
export function signed(comment: string): string {
  return COMMENT_PREFIX + comment.replace(/^\s*draft detective\s*[:\-–—]\s*/i, '');
}

/** Every item's outcome, by its position in the handoff. */
export function outcomesOf(plan: HandoffPlan, written: Set<number>, detail: string): AppliedItem[] {
  const placed = [...plan.paragraphs.values()].flatMap((work) => [
    ...work.edits.map(({ index, edit }) => ({ index, kind: 'edit' as const, quote: edit.quote })),
    ...work.comments.map(({ index, comment }) => ({ index, kind: 'comment' as const, quote: comment.quote })),
  ]);
  const outcomes = placed.map((item): AppliedItem => {
    const applied = written.has(item.index);
    return { ...item, applied, detail: applied ? '' : detail, reason: applied ? undefined : 'refused' };
  });
  return [...plan.unplaced, ...outcomes].sort((a, b) => a.index - b.index);
}

/** Change tracking and comments arrived in WordApi 1.4. */
function canWrite(): boolean {
  return Office.context.requirements.isSetSupported('WordApi', '1.4');
}

type Run = { plan: HandoffPlan; written: Set<number> };
type Item = { index: number; quote: string; paragraph: Word.Paragraph; text: string; at: number };
type Found = { item: Item; lookup: Lookup; hits: Word.RangeCollection };
type Long = { item: Item; head: Word.Range; tails: Word.RangeCollection; tailNth: number };

/** Write the handoff's items through Word's API: the plan from the document's text, and what was written. */
async function write(comments: HandoffComment[], edits: HandoffEdit[]): Promise<Run> {
  return Word.run(async (context) => {
    const paragraphs = context.document.body.paragraphs;
    paragraphs.load('items/text');
    await context.sync();
    const texts = paragraphs.items.map((paragraph) => String(paragraph.text ?? ''));
    const plan = planHandoff(texts, comments, edits);
    const written = new Set<number>();
    if (!canWrite()) return { plan, written };

    const items: Item[] = [...plan.paragraphs.entries()].flatMap(([at, work]) => {
      const where = { paragraph: paragraphs.items[at], text: texts[at], at };
      return [
        ...work.edits.map(({ index, edit }) => ({ index, quote: edit.quote, ...where })),
        ...work.comments.map(({ index, comment }) => ({ index, quote: comment.quote, ...where })),
      ];
    });
    const ranges = await findAll(context, items);
    const replacements = new Map(edits.map((edit, i) => [comments.length + i, edit.replacement]));
    const notes = new Map(comments.map((comment, i) => [i, comment.comment]));

    await withTracking(context, async () => {
      for (const { index } of writeOrder(items, replacements)) {
        const range = ranges.get(index);
        if (!range) continue;
        const replacement = replacements.get(index);
        const queue =
          replacement === undefined
            ? () => range.insertComment(signed(notes.get(index) ?? ''))
            : () => replace(range, replacement);
        if (await wrote(context, queue)) written.add(index);
      }
    });
    return { plan, written };
  });
}

/**
 * Comments first, then edits from the end of each paragraph back to its start.
 *
 * Word for the web keeps a range on the characters it was found at: an edit earlier in
 * the same paragraph does not move it, so a range written after such an edit lands on
 * other words, off by the text the edit added or took away. A comment changes no text,
 * so every range is still right after the comments;
 * an edit only moves text after its own start, so no edit lands after one already made.
 * A comment on words an edit replaces stays on them, as a tracked deletion.
 */
function writeOrder(items: Item[], replacements: Map<number, string>): Item[] {
  const start = (item: Item) => rawSpan(item.text, item.quote)?.start ?? 0;
  const comments = items.filter((item) => !replacements.has(item.index));
  const edits = items.filter((item) => replacements.has(item.index));
  return [...comments, ...edits.sort((a, b) => b.at - a.at || start(b) - start(a))];
}

function replace(range: Word.Range, replacement: string): void {
  if (replacement) range.insertText(replacement, Word.InsertLocation.replace);
  else range.delete();
}

/** One write per sync, so a refusal is pinned on its own item. */
async function wrote(context: Word.RequestContext, queue: () => void): Promise<boolean> {
  try {
    queue();
    await context.sync();
    return true;
  } catch (error) {
    console.info('Word refused a write', error);
    return false;
  }
}

/** With change tracking on for everyone, as Word's own tracked changes need, then as it was. */
async function withTracking(context: Word.RequestContext, work: () => Promise<void>): Promise<void> {
  const document = context.document;
  document.load('changeTrackingMode');
  await context.sync();
  const previous = document.changeTrackingMode;
  const switching = previous !== Word.ChangeTrackingMode.trackAll;
  if (switching) {
    document.changeTrackingMode = Word.ChangeTrackingMode.trackAll;
    await context.sync();
  }
  try {
    await work();
  } finally {
    if (switching) {
      document.changeTrackingMode = previous;
      await context.sync();
    }
  }
}

function queueSearch(item: Item): Found | null {
  const where = lookup(item.text, item.quote);
  if (!where) return null;
  const hits = item.paragraph.search(where.kind === 'whole' ? where.search : where.head, { matchCase: true });
  hits.load('items/text');
  return { item, lookup: where, hits };
}

/**
 * Every search in one round trip. One search Word refuses fails that whole round trip,
 * so then each is asked again on its own, and only the refused one is left out.
 */
async function searchAll(context: Word.RequestContext, items: Item[]): Promise<Found[]> {
  const batch = items.map(queueSearch).filter((found) => found !== null);
  try {
    await context.sync();
    return batch;
  } catch (error) {
    console.info('Word refused a search; searching one at a time', error);
  }
  const found: Found[] = [];
  for (const item of items) {
    const one = queueSearch(item);
    if (!one) continue;
    try {
      await context.sync();
      found.push(one);
    } catch {
      // Reported as not written.
    }
  }
  return found;
}

/** Each item's range, where Word's search agrees with the paragraph's text. */
async function findAll(context: Word.RequestContext, items: Item[]): Promise<Map<number, Word.Range>> {
  const ranges = new Map<number, Word.Range>();
  const long: Long[] = [];
  for (const { item, lookup: where, hits } of await searchAll(context, items)) {
    // A different count means Word reads the paragraph otherwise than its text: not guessed at.
    if (hits.items.length !== where.hits) continue;
    const hit = hits.items[where.nth];
    if (where.kind === 'whole') ranges.set(item.index, hit);
    else {
      const tails = hit.expandTo(item.paragraph.getRange('End')).search(where.tail, { matchCase: true });
      tails.load('items');
      long.push({ item, head: hit, tails, tailNth: where.tailNth });
    }
  }
  if (long.length) await placeLong(context, long, ranges);
  return ranges;
}

/** A long quote runs from its head to its tail, if the words between are the quote's. */
async function placeLong(context: Word.RequestContext, long: Long[], ranges: Map<number, Word.Range>): Promise<void> {
  try {
    await context.sync();
    const spans = long.flatMap(({ item, head, tails, tailNth }) => {
      const tail = tails.items[tailNth];
      if (!tail) return [];
      const span = head.expandTo(tail);
      span.load('text');
      return [{ item, span }];
    });
    await context.sync();
    for (const { item, span } of spans) {
      if (normalize(String(span.text ?? '')) === normalize(item.quote)) ranges.set(item.index, span);
    }
  } catch (error) {
    console.info('Word refused a search for a long quote', error);
  }
}
