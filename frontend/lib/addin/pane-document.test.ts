import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { chatDocumentKey, documentFile, fingerprint } from './pane-document';

type Callback<T> = (result: { status: string; value?: T; error?: Error }) => void;

/**
 * Office's compressed-file API over `slices`, one byte array each. A slice listed in
 * `failing` is refused, and closing waits for `release()` when `holdClose` is set.
 */
function fakeOffice(slices: number[][], { failing = -1, holdClose = false } = {}) {
  const calls: string[] = [];
  let release = () => {};
  const file = {
    sliceCount: slices.length,
    getSliceAsync: (index: number, done: Callback<{ data: number[] }>) => {
      calls.push(`slice ${index}`);
      if (index === failing) done({ status: 'failed', error: new Error('slice refused') });
      else done({ status: 'succeeded', value: { data: slices[index] } });
    },
    closeAsync: (done: () => void) => {
      calls.push('close');
      if (holdClose) release = done;
      else done();
    },
  };
  vi.stubGlobal('Office', {
    FileType: { Compressed: 'compressed' },
    AsyncResultStatus: { Succeeded: 'succeeded' },
    context: {
      document: {
        getFileAsync: (_type: string, _options: unknown, done: Callback<typeof file>) => {
          calls.push('open');
          done({ status: 'succeeded', value: file });
        },
      },
    },
  });
  return { calls, release: () => release() };
}

afterEach(() => vi.unstubAllGlobals());

describe('documentFile', () => {
  it('joins the slices in order into a .docx', async () => {
    const office = fakeOffice([[1, 2], [3], [4, 5]]);

    const file = await documentFile();

    expect([...new Uint8Array(await file.arrayBuffer())]).toEqual([1, 2, 3, 4, 5]);
    expect(file.type).toBe('application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    expect(office.calls).toEqual(['open', 'slice 0', 'slice 1', 'slice 2', 'close']);
  });

  it('closes the file when a slice is refused, so the next read can open it', async () => {
    const office = fakeOffice([[1], [2], [3]], { failing: 1 });

    await expect(documentFile()).rejects.toThrow('slice refused');

    expect(office.calls).toEqual(['open', 'slice 0', 'slice 1', 'close']);
  });

  it('does not hand the file over until Office has closed it', async () => {
    const office = fakeOffice([[7]], { holdClose: true });
    let settled = false;

    const reading = documentFile().then((file) => {
      settled = true;
      return file;
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(settled).toBe(false);

    office.release();
    expect((await reading).size).toBe(1);
  });

  it('fails when Office will not open the document', async () => {
    vi.stubGlobal('Office', {
      FileType: { Compressed: 'compressed' },
      AsyncResultStatus: { Succeeded: 'succeeded' },
      context: {
        document: {
          getFileAsync: (_type: string, _options: unknown, done: Callback<never>) =>
            done({ status: 'failed', error: new Error('file busy') }),
        },
      },
    });

    await expect(documentFile()).rejects.toThrow('file busy');
  });
});

describe('fingerprint', () => {
  it('is the SHA-256 of the file, so the same bytes match and any change does not', async () => {
    const abc = await fingerprint(new Blob(['abc']));

    expect(abc).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
    expect(await fingerprint(new Blob(['abc']))).toBe(abc);
    expect(await fingerprint(new Blob(['abd']))).not.toBe(abc);
  });
});

describe('chatDocumentKey', () => {
  beforeEach(() => sessionStorage.clear());

  it('is the URL Word reports for a saved document', () => {
    expect(chatDocumentKey('https://contoso.sharepoint.com/Draft.docx')).toBe(
      'https://contoso.sharepoint.com/Draft.docx',
    );
  });

  it('gives an unsaved document a key of its own pane, kept across reloads', () => {
    const first = chatDocumentKey('');

    expect(first).toMatch(/^unsaved:[0-9a-f-]{36}$/);
    expect(chatDocumentKey('  ')).toBe(first);
    sessionStorage.clear();
    expect(chatDocumentKey('')).not.toBe(first);
  });

  it('keeps one key for as long as the pane is open when sessionStorage is unavailable', () => {
    vi.stubGlobal('sessionStorage', {
      getItem: () => {
        throw new DOMException('denied', 'SecurityError');
      },
    });

    const first = chatDocumentKey('');

    expect(first).toMatch(/^unsaved:[0-9a-f-]{36}$/);
    expect(chatDocumentKey('')).toBe(first);
  });
});
