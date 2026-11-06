import { SeverityEnum, WorkflowRunType, type Issue } from '@/lib/generated-api';
import { describe, expect, it } from 'vitest';
import {
  formatLineLabel,
  issueLineRange,
  issueScrollRange,
  issueStartLine,
  lineLabel,
  rangesOverlap,
} from './issue-lines';

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
    passage: null,
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

describe('issueScrollRange', () => {
  it('brings a long issue into view at its passage, not its first line', () => {
    const passage = { original_text: 'x', display_text: 'x', display_occurrence: 0, start_line: 100, end_line: 100 };
    expect(issueScrollRange(issue({ start_line: 1, end_line: 100, passage }))).toEqual([100, 100]);
  });

  it('falls back to the issue range without a passage', () => {
    expect(issueScrollRange(issue({ start_line: 4, end_line: 9 }))).toEqual([4, 9]);
    expect(issueScrollRange(issue())).toBeNull();
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

describe('issueStartLine', () => {
  it('reads the start line even when the end is missing', () => {
    expect(issueStartLine(issue({ start_line: 12, end_line: 14 }))).toBe(12);
    expect(issueStartLine(issue({ start_line: 12 }))).toBe(12);
  });

  it('is null when there is no start line', () => {
    expect(issueStartLine(issue())).toBeNull();
    expect(issueStartLine(issue({ start_line: null, end_line: 14 }))).toBeNull();
  });
});

describe('rangesOverlap', () => {
  it('counts shared end lines as overlap', () => {
    expect(rangesOverlap([1, 5], [5, 9])).toBe(true);
    expect(rangesOverlap([5, 9], [1, 5])).toBe(true);
  });

  it('counts containment as overlap', () => {
    expect(rangesOverlap([1, 10], [4, 5])).toBe(true);
    expect(rangesOverlap([4, 5], [1, 10])).toBe(true);
  });

  it('is false for disjoint ranges', () => {
    expect(rangesOverlap([1, 4], [5, 9])).toBe(false);
    expect(rangesOverlap([5, 9], [1, 4])).toBe(false);
  });
});
