import { describe, expect, it } from 'vitest';
import { WorkflowRunType, type WorkflowCategoryOrder, type WorkflowTypeDescription } from '@/lib/generated-api';
import type { VisibleWorkflowGroup } from '@/lib/hooks/use-visible-workflow-types';
import { filterWorkflowGroups } from './workflow-search';

function workflowType(type: WorkflowRunType, name: string, description = ''): WorkflowTypeDescription {
  return {
    type,
    name,
    description,
    needs_web_search: false,
    is_experimental: false,
    is_internal: false,
    category: 'x',
    gates: [],
  };
}

function group(slug: string, label: string, workflows: WorkflowTypeDescription[]): VisibleWorkflowGroup {
  return { category: { slug, label } as WorkflowCategoryOrder, workflows };
}

const GROUPS = [
  group('language', 'Language', [
    workflowType(WorkflowRunType.AbbreviationScanV2, 'Abbreviations', 'Checks acronyms are defined'),
    workflowType(WorkflowRunType.AdvocacyToneV2, 'Advocacy Tone'),
  ]),
  group('references', 'References', [
    workflowType(WorkflowRunType.ReferenceValidationV2, 'Reference Validation'),
    workflowType(WorkflowRunType.LiteratureReviewV2, 'Literature Review'),
  ]),
];

const typesOf = (groups: VisibleWorkflowGroup[]) => groups.flatMap((g) => g.workflows.map((wt) => wt.type));

describe('filterWorkflowGroups', () => {
  it('returns every group for a blank query', () => {
    expect(filterWorkflowGroups(GROUPS, '   ')).toBe(GROUPS);
  });

  it('matches the name case-insensitively and drops categories left empty', () => {
    const result = filterWorkflowGroups(GROUPS, 'TONE');
    expect(result.map((g) => g.category.slug)).toEqual(['language']);
    expect(typesOf(result)).toEqual([WorkflowRunType.AdvocacyToneV2]);
  });

  it('matches the description', () => {
    expect(typesOf(filterWorkflowGroups(GROUPS, 'acronyms'))).toEqual([WorkflowRunType.AbbreviationScanV2]);
  });

  it('requires every term, in any order', () => {
    expect(typesOf(filterWorkflowGroups(GROUPS, 'val ref'))).toEqual([WorkflowRunType.ReferenceValidationV2]);
  });

  it('keeps a whole category when its label matches', () => {
    expect(typesOf(filterWorkflowGroups(GROUPS, 'references'))).toEqual([
      WorkflowRunType.ReferenceValidationV2,
      WorkflowRunType.LiteratureReviewV2,
    ]);
  });

  it('returns nothing when no assessment matches', () => {
    expect(filterWorkflowGroups(GROUPS, 'zzz')).toEqual([]);
  });
});
