import { describe, expect, it } from 'vitest';
import {
  FileListItem,
  FileRole,
  ProjectDetailed,
  WorkflowRunDetail,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { derivePeerReviewFacts } from './peer-review-derive';

let nextId = 0;

function file(role: FileRole, revision: number, createdAt = '2026-09-30T10:00:00Z'): FileListItem {
  nextId += 1;
  return { id: `file-${nextId}`, role, revision, created_at: createdAt } as unknown as FileListItem;
}

function run(type: WorkflowRunType, createdAt: string): WorkflowRunDetail {
  return {
    run: { id: `run-${type}`, type, status: WorkflowRunStatus.Completed, created_at: createdAt },
    state: null,
  } as unknown as WorkflowRunDetail;
}

function project(files: FileListItem[], currentRevision: number, workflowRuns: WorkflowRunDetail[] = []) {
  return {
    project: { id: 'project', current_revision: currentRevision },
    revision: currentRevision,
    files,
    workflow_runs: workflowRuns,
  } as unknown as ProjectDetailed;
}

/** A reviewed draft on revision 1, its memo, and a revised draft on revision 2. */
function reviewedAndRevised(): FileListItem[] {
  return [file(FileRole.Main, 1), file(FileRole.ReviewerMemo, 1), file(FileRole.Main, 2)];
}

describe('derivePeerReviewFacts — response memos', () => {
  it('reads only the response memos on the current revision', () => {
    const stale = file(FileRole.ResponseMemo, 1);
    const current = file(FileRole.ResponseMemo, 2);
    const facts = derivePeerReviewFacts(project([...reviewedAndRevised(), stale, current], 2));

    expect(facts.responseMemos).toEqual([stale, current]);
    expect(facts.activeResponseMemos).toEqual([current]);
  });

  it('allows uploads only once a revised draft exists', () => {
    const beforeRevision = derivePeerReviewFacts(project([file(FileRole.Main, 1), file(FileRole.ReviewerMemo, 1)], 1));
    const afterRevision = derivePeerReviewFacts(project(reviewedAndRevised(), 2));

    expect(beforeRevision.canUploadResponses).toBe(false);
    expect(afterRevision.canUploadResponses).toBe(true);
  });

  it('flags response memos that arrived after the coverage report started', () => {
    const coverage = run(WorkflowRunType.ReviewerCoverageReport, '2026-09-30T12:00:00Z');
    const before = file(FileRole.ResponseMemo, 2, '2026-09-30T11:00:00Z');
    const after = file(FileRole.ResponseMemo, 2, '2026-09-30T13:00:00Z');

    const upToDate = derivePeerReviewFacts(project([...reviewedAndRevised(), before], 2, [coverage]));
    const behind = derivePeerReviewFacts(project([...reviewedAndRevised(), before, after], 2, [coverage]));

    expect(upToDate.responsesNewerThanCoverage).toBe(false);
    expect(behind.responsesNewerThanCoverage).toBe(true);
  });

  it('never flags staleness without a coverage report', () => {
    const facts = derivePeerReviewFacts(project([...reviewedAndRevised(), file(FileRole.ResponseMemo, 2)], 2));
    expect(facts.responsesNewerThanCoverage).toBe(false);
  });
});
