/**
 * Just enough of Word for the web's API for `applyHandoff`, for tests.
 *
 * Like the real one, a range keeps the characters it was found at: an edit earlier in its
 * paragraph does not move it. A tracked edit puts its new words before the old ones,
 * which stay in the paragraph as a deletion. Each write records the words it landed on.
 */

export type FakeWrite = { kind: 'edit' | 'comment'; words: string; text: string };

export type FakeWord = { writes: FakeWrite[]; paragraphs: string[]; word: unknown; office: unknown };

class FakeRange {
  constructor(
    private readonly fake: FakeWord,
    private readonly at: number,
    private readonly start: number,
    private readonly end: number,
  ) {}

  get text(): string {
    return this.fake.paragraphs[this.at].slice(this.start, this.end);
  }

  load(): void {}

  search(needle: string): { items: FakeRange[]; load: () => void } {
    const items: FakeRange[] = [];
    const within = this.text;
    for (let at = within.indexOf(needle); at >= 0; at = within.indexOf(needle, at + needle.length)) {
      items.push(new FakeRange(this.fake, this.at, this.start + at, this.start + at + needle.length));
    }
    return { items, load: () => {} };
  }

  expandTo(other: FakeRange): FakeRange {
    return new FakeRange(this.fake, this.at, Math.min(this.start, other.start), Math.max(this.end, other.end));
  }

  getRange(where: 'End'): FakeRange {
    return where === 'End' ? new FakeRange(this.fake, this.at, this.end, this.end) : this;
  }

  insertText(text: string): void {
    this.fake.writes.push({ kind: 'edit', words: this.text, text });
    const paragraph = this.fake.paragraphs[this.at];
    this.fake.paragraphs[this.at] = paragraph.slice(0, this.start) + text + paragraph.slice(this.start);
  }

  delete(): void {
    this.fake.writes.push({ kind: 'edit', words: this.text, text: '' });
  }

  insertComment(text: string): void {
    this.fake.writes.push({ kind: 'comment', words: this.text, text });
  }
}

/** A document of `paragraphs`, as the `Word` and `Office` globals to stub. */
export function fakeWord(paragraphs: string[]): FakeWord {
  const fake: FakeWord = { writes: [], paragraphs: [...paragraphs], word: null, office: null };
  const items = paragraphs.map((_, at) => new FakeRange(fake, at, 0, fake.paragraphs[at].length));
  const document = { changeTrackingMode: 'Off', load: () => {}, body: { paragraphs: { items, load: () => {} } } };
  const context = { document, sync: async () => {} };
  fake.word = {
    run: <T>(work: (context: unknown) => Promise<T>) => work(context),
    InsertLocation: { replace: 'Replace' },
    ChangeTrackingMode: { trackAll: 'TrackAll', off: 'Off' },
  };
  fake.office = { context: { requirements: { isSetSupported: () => true } } };
  return fake;
}
