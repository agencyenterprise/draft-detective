/**
 * Reading and writing one paragraph's markup through Office.js.
 *
 * Draft Detective's comments and tracked changes are written as markup by the backend
 * (`/api/microsoft/word/...`), because Word's API attributes a comment to whoever is
 * signed in and cannot create a tracked change at all. So a write is: read the
 * paragraph's Flat OPC with getOoxml, have the backend change it, put it back with
 * insertOoxml.
 */

/** Every body paragraph's text, in order, including empty ones. */
export async function paragraphTexts(): Promise<string[]> {
  return Word.run(async (context) => {
    const paragraphs = context.document.body.paragraphs;
    paragraphs.load('items/text');
    await context.sync();
    return paragraphs.items.map((paragraph) => String(paragraph.text ?? ''));
  });
}

/**
 * The range getOoxml really works at for this paragraph.
 *
 * A paragraph inside a table comes back as the whole outermost table, and writing a
 * table into a paragraph-sized range fails with a bare GeneralException. So reads and
 * writes both happen at the outermost enclosing table when there is one.
 */
async function rewriteScope(context: Word.RequestContext, paragraph: Word.Paragraph): Promise<Word.Range> {
  let table = paragraph.parentTableOrNullObject;
  table.load('isNullObject');
  await context.sync();
  if (table.isNullObject) return paragraph.getRange();

  for (let depth = 0; depth < 10; depth++) {
    const parent = table.parentTableOrNullObject;
    parent.load('isNullObject');
    await context.sync();
    if (parent.isNullObject) break;
    table = parent;
  }
  return table.getRange();
}

async function paragraphAt(context: Word.RequestContext, index: number): Promise<Word.Paragraph | null> {
  const paragraphs = context.document.body.paragraphs;
  paragraphs.load('items');
  await context.sync();
  return paragraphs.items[index] ?? null;
}

/** The markup for the paragraph at `index`, at the scope it has to be written back at. */
export async function readParagraphMarkup(index: number): Promise<string | null> {
  return Word.run(async (context) => {
    const paragraph = await paragraphAt(context, index);
    if (!paragraph) return null;
    const scope = await rewriteScope(context, paragraph);
    const ooxml = scope.getOoxml();
    await context.sync();
    return ooxml.value;
  });
}

/**
 * Put markup back over the paragraph at `index`, with change tracking off.
 *
 * Left on, Word records our own write as a revision by the signed-in user, wrapping
 * Draft Detective's suggestion inside one of the author's. The author's setting is
 * restored afterwards.
 */
export async function writeParagraphMarkup(index: number, markup: string): Promise<void> {
  await Word.run(async (context) => {
    const paragraph = await paragraphAt(context, index);
    if (!paragraph) throw new Error('the paragraph is no longer there');
    const scope = await rewriteScope(context, paragraph);

    const document = context.document;
    document.load('changeTrackingMode');
    await context.sync();
    const previous = document.changeTrackingMode;
    const tracking = previous && previous !== Word.ChangeTrackingMode.off;
    if (tracking) {
      document.changeTrackingMode = Word.ChangeTrackingMode.off;
      await context.sync();
    }
    try {
      scope.insertOoxml(markup, Word.InsertLocation.replace);
      await context.sync();
    } finally {
      if (tracking) {
        document.changeTrackingMode = previous;
        await context.sync();
      }
    }
  });
}
