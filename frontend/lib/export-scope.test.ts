import { describe, expect, it } from 'vitest';
import { editsPhrase, exportCounts, issuesInExport } from './export-scope';
import { Issue, IssueEditRead, IssueEditStatus, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';

function edit(status: IssueEditStatus = IssueEditStatus.Proposed): IssueEditRead {
  return {
    id: 'e',
    issue_id: 'i',
    original_text: 'a',
    replacement_text: 'b',
    start_line: 1,
    end_line: 1,
    rationale: 'r',
    status,
  };
}

function issue(overrides: Partial<Issue>): Issue {
  return {
    id: 'i',
    project_id: 'p',
    workflow_run_id: 'w',
    issue_hash: 'h',
    title: 't',
    description: 'd',
    severity: SeverityEnum.Medium,
    workflow_type: WorkflowRunType.AdvocacyToneV2,
    status: 'active',
    revision: 1,
    edits: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Issue;
}

const NO_FILTER = { severity: [], workflowType: [], showPassing: false };

const ISSUES = [
  issue({ id: 'high', severity: SeverityEnum.High, edits: [edit(), edit(IssueEditStatus.Rejected)] }),
  issue({ id: 'medium-figures', workflow_type: WorkflowRunType.FiguresTablesCheck, edits: [edit()] }),
  issue({ id: 'resolved', resolved_at: new Date('2026-01-02T00:00:00Z'), edits: [edit()] }),
  issue({ id: 'passing', severity: SeverityEnum.None }),
];

describe('issuesInExport', () => {
  it('drops resolved issues and passing checks by default', () => {
    expect(issuesInExport(ISSUES, NO_FILTER).map((i) => i.id)).toEqual(['high', 'medium-figures']);
  });

  it('keeps passing checks when the filter shows them', () => {
    expect(issuesInExport(ISSUES, { ...NO_FILTER, showPassing: true }).map((i) => i.id)).toContain('passing');
  });

  it('narrows by severity and by assessment', () => {
    expect(issuesInExport(ISSUES, { ...NO_FILTER, severity: [SeverityEnum.High] }).map((i) => i.id)).toEqual(['high']);
    expect(
      issuesInExport(ISSUES, { ...NO_FILTER, workflowType: [WorkflowRunType.FiguresTablesCheck] }).map((i) => i.id),
    ).toEqual(['medium-figures']);
  });
});

describe('exportCounts', () => {
  it('counts included issues and their non-rejected edits', () => {
    expect(exportCounts(ISSUES, NO_FILTER)).toEqual({ issues: 2, edits: 2 });
  });

  it('follows the filters', () => {
    expect(exportCounts(ISSUES, { ...NO_FILTER, severity: [SeverityEnum.High] })).toEqual({ issues: 1, edits: 1 });
  });
});

describe('editsPhrase', () => {
  it('names tracked changes when the option is on', () => {
    expect(editsPhrase(1, true)).toBe('1 proposed edit as a tracked change');
    expect(editsPhrase(4, true)).toBe('4 proposed edits as tracked changes');
  });

  it('points at the comments when the option is off', () => {
    expect(editsPhrase(1, false)).toBe('1 proposed edit described in a comment');
    expect(editsPhrase(4, false)).toBe('4 proposed edits described in comments');
  });

  it('says nothing about where an edit goes when there are none', () => {
    expect(editsPhrase(0, true)).toBe('0 proposed edits');
    expect(editsPhrase(0, false)).toBe('0 proposed edits');
  });
});
