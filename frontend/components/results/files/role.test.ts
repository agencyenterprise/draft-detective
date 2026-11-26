import { describe, expect, it } from 'vitest';

import { FileListItem, FileRole } from '@/lib/generated-api';
import { fileGroup, revisionLabel, sortFiles } from './role';

const file = (id: string, role: FileRole, extra: Partial<FileListItem> = {}) =>
  ({ id, role, file_name: `${id}.pdf`, ...extra }) as FileListItem;

describe('fileGroup', () => {
  it('groups each role the way the Files tab does', () => {
    expect(fileGroup(FileRole.Main)).toBe('main');
    expect(fileGroup(FileRole.ReviewerMemo)).toBe('memo');
    expect(fileGroup(FileRole.ResponseMemo)).toBe('response');
    expect(fileGroup(FileRole.ReviewInput)).toBe('review');
    expect(fileGroup(FileRole.Support)).toBe('source');
  });

  it('reads any other role as a source', () => {
    expect(fileGroup(FileRole.SupportingCandidate)).toBe('source');
    expect(fileGroup(FileRole.ExtractedImage)).toBe('source');
  });
});

describe('revisionLabel', () => {
  it('marks the main document of the current revision as current', () => {
    expect(revisionLabel(file('m', FileRole.Main, { revision: 3 }), 3)).toBe('Revision 3 · current');
  });

  it('marks an older main document as superseded', () => {
    expect(revisionLabel(file('m', FileRole.Main, { revision: 2 }), 3)).toBe('Revision 2 · superseded');
  });

  it('names the revision of any other file without judging it', () => {
    expect(revisionLabel(file('r', FileRole.ReviewerMemo, { revision: 1 }), 3)).toBe('Revision 1');
  });

  it('has no label for a file shared across revisions', () => {
    expect(revisionLabel(file('s', FileRole.Support, { revision: null }), 3)).toBeNull();
    expect(revisionLabel(file('s', FileRole.Support), 3)).toBeNull();
  });
});

describe('sortFiles', () => {
  it('puts main documents first, newest revision first, then memos, review documents and sources', () => {
    const files = [
      file('source', FileRole.Support),
      file('review', FileRole.ReviewInput),
      file('main-1', FileRole.Main, { revision: 1 }),
      file('response', FileRole.ResponseMemo),
      file('main-3', FileRole.Main, { revision: 3 }),
      file('memo', FileRole.ReviewerMemo),
      file('main-2', FileRole.Main, { revision: 2 }),
    ];

    expect(sortFiles(files).map((f) => f.id)).toEqual([
      'main-3',
      'main-2',
      'main-1',
      'memo',
      'response',
      'review',
      'source',
    ]);
  });

  it('orders files of the same kind by name, with roles it does not rank among the sources', () => {
    const files = [
      file('c', FileRole.Support, { file_name: 'Smith 2020.pdf' }),
      file('a', FileRole.ExtractedImage, { file_name: 'figure.png' }),
      file('b', FileRole.Support, { file_name: 'Abbott 2019.pdf' }),
      file('d', FileRole.ReviewerMemo, { file_name: 'z memo.docx' }),
      file('e', FileRole.ReviewerMemo, { file_name: 'a memo.docx' }),
    ];

    expect(sortFiles(files).map((f) => f.id)).toEqual(['e', 'd', 'b', 'a', 'c']);
  });

  it('sorts a file with no name ahead of named ones instead of throwing', () => {
    const files = [file('named', FileRole.Support), file('unnamed', FileRole.Support, { file_name: '' })];

    expect(sortFiles(files).map((f) => f.id)).toEqual(['unnamed', 'named']);
  });

  it('returns a new array and leaves the caller’s list alone', () => {
    const files = [file('source', FileRole.Support), file('main', FileRole.Main, { revision: 1 })];

    const sorted = sortFiles(files);

    expect(sorted.map((f) => f.id)).toEqual(['main', 'source']);
    expect(files.map((f) => f.id)).toEqual(['source', 'main']);
  });
});
