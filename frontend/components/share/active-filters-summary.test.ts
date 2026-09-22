import { describe, expect, it } from 'vitest';
import { hasActiveFilters } from './active-filters-summary';
import { SeverityEnum, WorkflowRunType } from '@/lib/generated-api';

const NONE = { severity: [], workflowType: [], showPassing: false };
const ALL_SEVERITIES = [SeverityEnum.High, SeverityEnum.Medium, SeverityEnum.Low];

describe('hasActiveFilters', () => {
  it('is false when nothing narrows the export', () => {
    expect(hasActiveFilters(NONE)).toBe(false);
    // Every severity selected is the same scope as selecting none.
    expect(hasActiveFilters({ ...NONE, severity: ALL_SEVERITIES })).toBe(false);
  });

  it('is true for a partial severity or an assessment filter', () => {
    expect(hasActiveFilters({ ...NONE, severity: [SeverityEnum.High] })).toBe(true);
    expect(hasActiveFilters({ ...NONE, workflowType: [WorkflowRunType.FiguresTablesCheck] })).toBe(true);
  });

  it('counts the passing toggle only when it changes the export', () => {
    expect(hasActiveFilters({ ...NONE, showPassing: true })).toBe(true);
    // A severity selection drops the passing checks again, so the toggle adds
    // nothing to describe.
    expect(hasActiveFilters({ ...NONE, showPassing: true, severity: ALL_SEVERITIES })).toBe(false);
    expect(hasActiveFilters({ ...NONE, showPassing: true, severity: [SeverityEnum.High] })).toBe(true);
  });
});
