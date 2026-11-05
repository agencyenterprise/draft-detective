import type { VisibleWorkflowGroup } from '@/lib/hooks/use-visible-workflow-types';

/**
 * The picker's groups narrowed to the assessments that match `query`.
 *
 * Every whitespace-separated term must appear, case-insensitively, in the
 * assessment's name, its description or its category's label, so "ref val"
 * finds Reference Validation and "language" keeps that whole category.
 * Categories left with no match are dropped. A blank query changes nothing.
 */
export function filterWorkflowGroups(groups: VisibleWorkflowGroup[], query: string): VisibleWorkflowGroup[] {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return groups;

  return groups
    .map((group) => ({
      ...group,
      workflows: group.workflows.filter((wt) => {
        const haystack = [wt.name, wt.description, group.category.label].join(' ').toLowerCase();
        return terms.every((term) => haystack.includes(term));
      }),
    }))
    .filter((group) => group.workflows.length > 0);
}
