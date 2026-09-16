import { SeverityEnum, WorkflowRunType, type Issue } from '@/lib/generated-api';
import { describe, expect, it } from 'vitest';
import { formatLineLabel, issueLineRange, lineLabel } from './issue-lines';

function issue(overrides: Partial<Issue> = {}): Issue {
  return {
    id: 'issue-1',
    project_id: 'project-1',
    workflow_run_id: 'run-1',
    issue_hash: 'hash-1',
    title: 'A finding',
    description: 'Something to look at',
    severity: SeverityEnum.Medium,
    workflow_type: WorkflowRunType.AdvocacyToneV2,
    created_at: new Date('2026-01-01T00:00:00Z'),
    updated_at: new Date('2026-01-01T00:00:00Z'),
    edits: [],
    ...overrides,
  };
}

describe('formatLineLabel', () => {
  it('labels a single line without a range', () => {
    expect(formatLineLabel(12, 12)).toBe('L12');
  });

  it('labels a range with an en dash', () => {
    expect(formatLineLabel(12, 14)).toBe('L12–14');
    // Spelled out, since an en dash and a hyphen look alike in source.
    expect(formatLineLabel(12, 14)).toBe('L12\u201314');
    expect(formatLineLabel(12, 14)).not.toContain('-');
  });
});

describe('issueLineRange', () => {
  it('reads the range off the issue', () => {
    expect(issueLineRange(issue({ start_line: 12, end_line: 14 }))).toEqual([12, 14]);
  });

  it('returns null when the issue carries no lines', () => {
    expect(issueLineRange(issue())).toBeNull();
  });

  it('returns null when only one end of the range is present', () => {
    expect(issueLineRange(issue({ start_line: 12 }))).toBeNull();
    expect(issueLineRange(issue({ end_line: 14 }))).toBeNull();
  });

  it('returns null when the lines are explicitly null', () => {
    expect(issueLineRange(issue({ start_line: null, end_line: null }))).toBeNull();
  });
});

describe('lineLabel', () => {
  it('words the issue range the way a proposed edit is worded', () => {
    expect(lineLabel(issue({ start_line: 12, end_line: 14 }))).toBe(formatLineLabel(12, 14));
    expect(lineLabel(issue({ start_line: 12, end_line: 12 }))).toBe('L12');
  });

  it('returns null when the issue has no lines', () => {
    expect(lineLabel(issue())).toBeNull();
  });
});
