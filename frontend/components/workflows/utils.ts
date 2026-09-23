import { WorkflowGate, WorkflowRunDetail, WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { isWorkflowAwaitingApproval } from '@/lib/workflow-state';

/**
 * Checks if any of the selected workflow types require web search.
 */
/** What keeps a set of assessments from being started, if anything. */
export type StartBlocker = 'metadata-pending' | 'metadata-failed' | 'none-selected' | 'consent-missing';

/**
 * Why a selection cannot be started yet, or null when it can.
 *
 * The consent rule reads each selected assessment's `needs_web_search` flag,
 * so until the workflow-type metadata has arrived nothing can be known about
 * the selection and the answer is "not yet", never "fine": with the metadata
 * missing every flag reads as false, and a web-searching assessment would
 * otherwise start without consent. The wizard's start button and the Run
 * assessments dialog both decide from this.
 */
export function startBlocker({
  selectedTypes,
  workflowTypes,
  metadataPending,
  metadataFailed,
  webSearchConsent,
}: {
  selectedTypes: WorkflowRunType[];
  workflowTypes: WorkflowTypeDescription[];
  metadataPending: boolean;
  metadataFailed: boolean;
  webSearchConsent: boolean;
}): StartBlocker | null {
  if (metadataPending) return 'metadata-pending';
  if (metadataFailed) return 'metadata-failed';
  if (selectedTypes.length === 0) return 'none-selected';
  if (hasWebSearchRequirement(selectedTypes, workflowTypes) && !webSearchConsent) return 'consent-missing';
  return null;
}

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
  WorkflowRunType.LiteratureReviewV2,
  WorkflowRunType.LiveReportsV2,
];

/**
 * Checks if any of the selected workflow types require a publication date.
 */
export function hasPublicationDateRequirement(selectedTypes: WorkflowRunType[]): boolean {
  return selectedTypes.some((type) => WORKFLOWS_REQUIRING_PUBLICATION_DATE.includes(type));
}

/**
 * Whether a workflow type must pass the given gate before it runs. Gates come
 * from the manifest via the workflow types endpoint, dependencies included.
 */
export function requiresGate(type: WorkflowRunType, gate: WorkflowGate, workflowTypes?: WorkflowTypeDescription[]) {
  return workflowTypes?.find((wt) => wt.type === type)?.gates.includes(gate) ?? false;
}

/**
 * Checks if any of the selected workflow types need the user to review the
 * reference list (and supply source files) before they can run.
 */
export function hasReferenceReviewRequirement(
  selectedTypes: WorkflowRunType[],
  workflowTypes?: WorkflowTypeDescription[],
): boolean {
  return selectedTypes.some((type) => requiresGate(type, WorkflowGate.ReferenceReview, workflowTypes));
}

/**
 * Whether the project is waiting on the user's reference review: an assessment
 * gated on it is awaiting approval. Other gates would show up through
 * `needsApproval` in `lib/workflow-state`, not here.
 */
export function needsReferenceReview(
  workflowRuns: WorkflowRunDetail[],
  workflowTypes?: WorkflowTypeDescription[],
): boolean {
  return workflowRuns.some(
    (workflowRun) =>
      isWorkflowAwaitingApproval(workflowRun) &&
      requiresGate(workflowRun.run.type, WorkflowGate.ReferenceReview, workflowTypes),
  );
}

/**
 * Formats an estimated duration (in seconds) into a short, human-friendly
 * ballpark label like "~1 min", "~3 min", or "~1.5 hr". Returns null when there
 * is no estimate to show, so callers can simply skip rendering.
 *
 * Sub-minute durations are floored to "~1 min" — showing seconds is noise at
 * this granularity.
 */
export function formatEstimatedDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds) || seconds <= 0) {
    return null;
  }
  const minutes = seconds / 60;
  if (minutes < 60) {
    return `~${Math.max(1, Math.round(minutes))} min`;
  }
  const hours = minutes / 60;
  // One decimal below 10 hours (e.g. "~1.5 hr"), whole numbers above.
  const rounded = hours < 10 ? Math.round(hours * 10) / 10 : Math.round(hours);
  return `~${rounded} hr`;
}

/**
 * Fallback assessments pre-selected when a project is created, so the wizard
 * opens on a sensible default instead of an empty selection. The user can
 * uncheck any of them.
 *
 * This applies only to users with no assessment history: the wizard prefers the
 * assessments from their most recent project (see `useRecentWorkflowSelection`)
 * and falls back here on a first project or a failed lookup.
 *
 * Callers must intersect this with the assessments actually on offer (see
 * `useVisibleWorkflowTypes`) — an experimental assessment listed here is hidden
 * for users who have not opted in, and pre-selecting a hidden checkbox would
 * start a workflow the user cannot see or uncheck.
 */
export const DEFAULT_SELECTED_WORKFLOW_TYPES: WorkflowRunType[] = [
  WorkflowRunType.ReferenceValidationV2,
  WorkflowRunType.AdvocacyToneV2,
  WorkflowRunType.RecommendationCheck,
];
