import { describe, expect, it } from 'vitest';

import { FileListItem, FileRole } from '@/lib/generated-api';
import { Lens, countByLens, filterFiles, isFiltered, listedFiles } from './filter';

const file = (id: string, role: FileRole, extra: Partial<FileListItem> = {}) =>
  ({ id, role, file_name: `${id}.pdf`, ...extra }) as FileListItem;

const ids = (files: FileListItem[]) => files.map((f) => f.id);

const noReferences = new Map<string, { text: string }>();

const project = [
  file('draft', FileRole.Main, { revision: 2 }),
  file('memo', FileRole.ReviewerMemo),
  file('reply', FileRole.ResponseMemo),
  file('markup', FileRole.ReviewInput),
  file('smith', FileRole.Support, { file_name: 'Smith 2020.pdf', description: 'Survey of housing costs' }),
  file('jones', FileRole.Support, { file_name: 'paper.pdf' }),
  file('figure', FileRole.ExtractedImage),
];

describe('listedFiles', () => {
  it('leaves out supporting candidates and keeps every other role', () => {
    const candidate = file('candidate', FileRole.SupportingCandidate);
    expect(ids(listedFiles([...project, candidate]))).toEqual(ids(project));
  });
});

describe('countByLens', () => {
  it('counts each kind, with every file under "all"', () => {
    expect(countByLens(project)).toEqual({ all: 7, main: 1, source: 3, memo: 1, response: 1, review: 1 });
  });

  it('counts zero for a kind the project has none of', () => {
    expect(countByLens([file('draft', FileRole.Main)])).toEqual({
      all: 1,
      main: 1,
      source: 0,
      memo: 0,
      response: 0,
      review: 0,
    });
  });

  it('gives each lens the number of rows that lens shows', () => {
    const counts = countByLens(project);
    for (const lens of Object.keys(counts) as Lens[]) {
      expect(filterFiles(project, lens, '', noReferences)).toHaveLength(counts[lens]);
    }
  });
});

describe('isFiltered', () => {
  it('is off for every file and an empty search', () => {
    expect(isFiltered('all', '')).toBe(false);
    expect(isFiltered('all', '   ')).toBe(false);
  });

  it('is on once a kind is picked or a search is typed', () => {
    expect(isFiltered('source', '')).toBe(true);
    expect(isFiltered('all', 'smith')).toBe(true);
  });
});

describe('filterFiles', () => {
  it('shows every file, in the order given, with no lens or search', () => {
    expect(ids(filterFiles(project, 'all', '', noReferences))).toEqual(ids(project));
    expect(ids(filterFiles([...project].reverse(), 'all', '', noReferences))).toEqual(ids(project).reverse());
  });

  it('treats a search of only spaces as no search', () => {
    expect(ids(filterFiles(project, 'all', '   ', noReferences))).toEqual(ids(project));
  });

  it('narrows to the files of one kind', () => {
    expect(ids(filterFiles(project, 'main', '', noReferences))).toEqual(['draft']);
    expect(ids(filterFiles(project, 'memo', '', noReferences))).toEqual(['memo']);
    expect(ids(filterFiles(project, 'response', '', noReferences))).toEqual(['reply']);
    expect(ids(filterFiles(project, 'review', '', noReferences))).toEqual(['markup']);
    expect(ids(filterFiles(project, 'source', '', noReferences))).toEqual(['smith', 'jones', 'figure']);
  });

  it('finds a file by name, ignoring case and surrounding spaces', () => {
    expect(ids(filterFiles(project, 'all', '  SMITH 20 ', noReferences))).toEqual(['smith']);
  });

  it('finds a file by its description', () => {
    expect(ids(filterFiles(project, 'all', 'housing', noReferences))).toEqual(['smith']);
  });

  it('finds a file by the text of the reference it backs', () => {
    const references = new Map([['jones', { text: 'Jones, A. (2019). Rents in Ohio.' }]]);
    expect(ids(filterFiles(project, 'all', 'rents in ohio', references))).toEqual(['jones']);
  });

  it('applies the lens and the search together', () => {
    expect(ids(filterFiles(project, 'source', 'pdf', noReferences))).toEqual(['smith', 'jones', 'figure']);
    expect(ids(filterFiles(project, 'main', 'smith', noReferences))).toEqual([]);
  });

  it('matches nothing on a file with no description and no reference', () => {
    const bare = [file('bare', FileRole.Support, { file_name: 'a.pdf', description: null })];
    expect(filterFiles(bare, 'all', 'zzz', noReferences)).toEqual([]);
  });
});
