import { afterEach, describe, expect, it, vi } from 'vitest';
import { writeParagraphMarkup } from './word-writes';

/**
 * A stand-in for Word's object model, enough for one write: a document with a
 * change-tracking mode and one paragraph outside any table.
 */
function fakeWord(mode: string) {
  const modes: string[] = [];
  const range = { insertOoxml: vi.fn() };
  const paragraph = {
    parentTableOrNullObject: { isNullObject: true, load: vi.fn() },
    getRange: () => range,
  };
  const document = {
    load: vi.fn(),
    body: { paragraphs: { items: [paragraph], load: vi.fn() } },
    get changeTrackingMode() {
      return modes.at(-1) ?? mode;
    },
    set changeTrackingMode(value: string) {
      modes.push(value);
    },
  };
  const context = { document, sync: vi.fn().mockResolvedValue(undefined) };
  vi.stubGlobal('Word', {
    run: (callback: (ctx: typeof context) => Promise<unknown>) => callback(context),
    ChangeTrackingMode: { off: 'Off', trackAll: 'TrackAll' },
    InsertLocation: { replace: 'Replace' },
  });
  return { modes, range };
}

afterEach(() => vi.unstubAllGlobals());

describe('writeParagraphMarkup', () => {
  it("turns tracking off for our write and restores the author's setting", async () => {
    const { modes, range } = fakeWord('TrackAll');

    await writeParagraphMarkup(0, '<markup/>');

    expect(range.insertOoxml).toHaveBeenCalledWith('<markup/>', 'Replace');
    expect(modes).toEqual(['Off', 'TrackAll']);
  });

  it('restores the setting even when Word refuses the markup', async () => {
    const { modes, range } = fakeWord('TrackAll');
    range.insertOoxml.mockImplementation(() => {
      throw new Error('GeneralException');
    });

    await expect(writeParagraphMarkup(0, '<markup/>')).rejects.toThrow('GeneralException');
    expect(modes).toEqual(['Off', 'TrackAll']);
  });

  it('leaves tracking alone when it was already off', async () => {
    const { modes } = fakeWord('Off');

    await writeParagraphMarkup(0, '<markup/>');

    expect(modes).toEqual([]);
  });

  it('refuses a paragraph that is no longer there', async () => {
    fakeWord('Off');

    await expect(writeParagraphMarkup(5, '<markup/>')).rejects.toThrow('no longer there');
  });
});
