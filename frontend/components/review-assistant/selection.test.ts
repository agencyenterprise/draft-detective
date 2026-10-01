import { describe, expect, it } from 'vitest';
import { FileListItem, FileRole, WorkflowRunType } from '@/lib/generated-api';
import { outputDefinition } from './outputs';
import { defaultSelection, selectionProblems, toRequestInputs } from './selection';

function file(id: string, role: FileRole, revision: number | null): FileListItem {
  return { id, role, revision, file_name: `${id}.docx` } as unknown as FileListItem;
}

const PLAN = outputDefinition(WorkflowRunType.RevisionPlanningSummary);
const COVERAGE = outputDefinition(WorkflowRunType.ReviewerCoverageReport);

const FILES = [
  file('main-1', FileRole.Main, 1),
  file('main-2', FileRole.Main, 2),
  file('memo-a', FileRole.ReviewerMemo, 1),
  file('memo-old', FileRole.ReviewerMemo, null),
  file('reply-a', FileRole.ResponseMemo, 2),
  file('source', FileRole.Support, null),
];

describe('defaultSelection', () => {
  it('starts from the reviewed revision, the current draft and its responses', () => {
    expect(defaultSelection(COVERAGE, FILES, 2)).toEqual({
      reviewed_draft: 1,
      revised_draft: 2,
      reviewer_memos: ['memo-a'],
      response_memos: ['reply-a'],
    });
  });

  it('leaves the revised draft empty while the reviewed draft is still current', () => {
    const files = FILES.filter((f) => f.id !== 'main-2' && f.id !== 'reply-a');
    const selection = defaultSelection(COVERAGE, files, 1);
    expect(selection.revised_draft).toBeUndefined();
    expect(selection.response_memos).toEqual([]);
  });

  it('only fills the slots the output reads', () => {
    const selection = defaultSelection(PLAN, FILES, 2);
    expect(selection.revised_draft).toBeUndefined();
    expect(selection.response_memos).toEqual([]);
  });
});

describe('selectionProblems', () => {
  it('names every missing required input', () => {
    expect(selectionProblems(COVERAGE, { reviewer_memos: [], response_memos: [] })).toEqual([
      'Choose the reviewed draft.',
      'Choose the reviewer memos.',
      'Choose the revised draft.',
    ]);
  });

  it('does not require optional inputs', () => {
    const selection = { reviewed_draft: 1, revised_draft: 2, reviewer_memos: ['memo-a'], response_memos: [] };
    expect(selectionProblems(COVERAGE, selection)).toEqual([]);
  });

  it('rejects the same revision as both drafts', () => {
    const selection = { reviewed_draft: 2, revised_draft: 2, reviewer_memos: ['memo-a'], response_memos: [] };
    expect(selectionProblems(COVERAGE, selection)).toEqual([
      'The reviewed and revised drafts must be different revisions.',
    ]);
  });
});

describe('toRequestInputs', () => {
  it('sends each draft as its main file and drops inputs the output does not read', () => {
    const selection = { reviewed_draft: 1, revised_draft: 2, reviewer_memos: ['source'], response_memos: ['reply-a'] };
    expect(toRequestInputs(PLAN, selection, FILES)).toEqual({
      reviewed_draft: 'main-1',
      revised_draft: null,
      reviewer_memos: ['source'],
      response_memos: [],
    });
    expect(toRequestInputs(COVERAGE, selection, FILES)).toMatchObject({
      reviewed_draft: 'main-1',
      revised_draft: 'main-2',
    });
  });
});
