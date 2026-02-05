import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';

/**
 * Checks if any of the selected workflow types require web search.
 */
export function hasWebSearchRequirement(
  selectedTypes: WorkflowRunType[],
  workflowTypes?: WorkflowTypeDescription[],
): boolean {
  return selectedTypes.some((type) => workflowTypes?.find((wt) => wt.type === type)?.needs_web_search);
}

/**
 * Workflow types that require a publication date to be specified.
 */
const WORKFLOWS_REQUIRING_PUBLICATION_DATE: WorkflowRunType[] = [
  WorkflowRunType.LiteratureReview,
  WorkflowRunType.LiveReports,
];

/**
 * Checks if any of the selected workflow types require a publication date.
 */
export function hasPublicationDateRequirement(selectedTypes: WorkflowRunType[]): boolean {
  return selectedTypes.some((type) => WORKFLOWS_REQUIRING_PUBLICATION_DATE.includes(type));
}

/**
 * Workflow types that require supporting documents.
 */
export const WORKFLOWS_REQUIRING_SUPPORTING_DOCUMENTS: WorkflowRunType[] = [
  WorkflowRunType.ClaimReferenceValidation,
  WorkflowRunType.CitationSuggester,
];

/**
 * Checks if any of the selected workflow types require supporting documents.
 */
export function hasSupportingDocumentsRequirement(selectedTypes: WorkflowRunType[]): boolean {
  return selectedTypes.some((type) => WORKFLOWS_REQUIRING_SUPPORTING_DOCUMENTS.includes(type));
}
