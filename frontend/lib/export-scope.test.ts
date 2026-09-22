import { describe, expect, it } from 'vitest';
import {
  editsPhrase,
  exportCounts,
  exportOutcomeSentence,
  exportScopeSentence,
  issuesInExport,
  passingChecksIncluded,
  shareLinksAvailable,
} from './export-scope';
import { Issue, IssueEditRead, IssueEditStatus, SeverityEnum, WorkflowRunType } from '@/lib/generated-api';

function edit(status: IssueEditStatus = IssueEditStatus.Proposed): IssueEditRead {
  return {
    id: 'e',
    issue_id: 'i',
    original_text: 'a',
    replacement_text: 'b',
    display_text: 'a',
    display_occurrence: 0,
    display_replacement: 'b',
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
  it('counts the edits without saying what becomes of them', () => {
    expect(editsPhrase(0)).toBe('0 proposed edits');
    expect(editsPhrase(1)).toBe('1 proposed edit');
    expect(editsPhrase(4)).toBe('4 proposed edits');
  });
});

describe('exportOutcomeSentence', () => {
  it('names both destinations when tracked changes are on', () => {
    expect(exportOutcomeSentence(true)).toBe(
      'Issues become comments; edits become tracked changes where their text can be matched, and are described in their comments otherwise.',
    );
  });

  it('points only at the comments when they are off', () => {
    expect(exportOutcomeSentence(false)).toBe('Issues become comments; edits are described in their comments.');
  });
});

describe('passingChecksIncluded', () => {
  it('is true only when the toggle is on and no severity is selected', () => {
    expect(passingChecksIncluded({ ...NO_FILTER, showPassing: true })).toBe(true);
    expect(passingChecksIncluded(NO_FILTER)).toBe(false);
  });

  it('is false whenever a severity filter narrows the export', () => {
    expect(passingChecksIncluded({ ...NO_FILTER, showPassing: true, severity: [SeverityEnum.High] })).toBe(false);
    // Even all three named severities leave the passing checks out, because
    // the filter measures `None` against the selection like any other.
    expect(
      passingChecksIncluded({
        ...NO_FILTER,
        showPassing: true,
        severity: [SeverityEnum.High, SeverityEnum.Medium, SeverityEnum.Low],
      }),
    ).toBe(false);
  });

  it('says what issuesInExport does', () => {
    const cases = [
      { ...NO_FILTER, showPassing: true },
      { ...NO_FILTER, showPassing: true, severity: [SeverityEnum.High] },
      { ...NO_FILTER, showPassing: true, severity: [SeverityEnum.High, SeverityEnum.Medium, SeverityEnum.Low] },
      NO_FILTER,
    ];

    for (const filter of cases) {
      const carriesPassing = issuesInExport(ISSUES, filter).some((i) => i.severity === SeverityEnum.None);
      expect(carriesPassing).toBe(passingChecksIncluded(filter));
    }
  });
});

describe('shareLinksAvailable', () => {
  it('is true while the reader is on the current revision', () => {
    expect(shareLinksAvailable(3, 3)).toBe(true);
  });

  it('is true when no revision has been picked, which means the current one', () => {
    expect(shareLinksAvailable(undefined, 3)).toBe(true);
  });

  it('is false for an older revision, whose export the backend strips links from', () => {
    expect(shareLinksAvailable(1, 3)).toBe(false);
    expect(shareLinksAvailable(2, 3)).toBe(false);
  });
});

describe('exportScopeSentence', () => {
  it('says the passing checks are left out, because they are', () => {
    expect(exportScopeSentence({ severity: [], showPassing: false })).toBe(
      'Every unresolved issue except passing checks, from every assessment.',
    );
  });

  it('says they are included once the toggle is on', () => {
    expect(exportScopeSentence({ severity: [], showPassing: true })).toBe(
      'Every unresolved issue including passing checks, from every assessment.',
    );
  });

  it('says they are left out again beside a severity selection, which filters them', () => {
    expect(exportScopeSentence({ severity: [SeverityEnum.High], showPassing: true })).toContain(
      'except passing checks',
    );
  });
});
