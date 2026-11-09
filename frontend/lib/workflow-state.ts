import {
  WorkflowError,
  WorkflowErrorSeverity,
  WorkflowRunPublic,
  WorkflowRunStatus,
  WorkflowRunType,
} from './generated-api';

export interface WorkflowRunDetailTyped<T> {
  run: WorkflowRunPublic;
  state: T;
}

/**
 * What the status helpers read from a run: the run itself and its errors.
 * A `WorkflowRunSummary` carries the run's own errors in `errors`; a full
 * `WorkflowRunDetail` carries every error of its thread in `state.errors`.
 */
export interface RunWithErrors {
  run: WorkflowRunPublic;
  errors?: WorkflowError[];
  state?: { errors?: WorkflowError[] | null } | null;
}

type RunLike = { run: WorkflowRunPublic };

/** The run of one type among the overview's runs or any other run list. */
export function findRunByType<T extends RunLike>(runs: T[], type: WorkflowRunType): T | undefined {
  return runs.find((workflowRun) => workflowRun.run.type === type);
}

/**
 * Filter errors to only include those from the current workflow run.
 * Only errors with matching workflow_run_id are included.
 * Errors without workflow_run_id are excluded to prevent showing accumulated errors from previous runs.
 */
function filterErrorsToCurrentRun(errors: WorkflowError[], runId: string): WorkflowError[] {
  return errors.filter((error) => error.workflow_run_id === runId);
}

/**
 * Whether an error cost the run part of its output, as opposed to one the
 * workflow recovered from. Errors persisted before severity existed have no
 * `severity` field and count as blocking.
 */
export function isBlockingError(error: WorkflowError): boolean {
  return error.severity !== WorkflowErrorSeverity.Warning;
}

/**
 * Check if a workflow run has errors from the current run only, of any severity.
 * Used to decide whether to surface error messages at all.
 */
export function hasCurrentRunErrors(workflowRun: RunWithErrors): boolean {
  return getCurrentRunErrors(workflowRun).length > 0;
}

/**
 * Check if a workflow run has errors that cost it output.
 * Used to determine if a run should be displayed as "failed".
 */
export function hasBlockingErrors(workflowRun: RunWithErrors): boolean {
  return getCurrentRunErrors(workflowRun).some(isBlockingError);
}

/**
 * Get errors filtered to only include those from the current workflow run.
 * Used for displaying errors in the UI.
 */
export function getCurrentRunErrors(workflowRun: RunWithErrors): WorkflowError[] {
  const errors = workflowRun.errors ?? workflowRun.state?.errors ?? [];
  return filterErrorsToCurrentRun(errors, workflowRun.run.id);
}

/**
 * Display status for a workflow run. Mirrors `WorkflowRunStatus`, but `Completed`
 * runs that lost output to an error collapse to `Failed` for UI purposes.
 */
export type DisplayStatus = WorkflowRunStatus;

/**
 * Get the display status for a workflow run.
 * Returns "failed" if completed with blocking errors, otherwise the actual
 * status. Warnings — failures the workflow recovered from — leave the run
 * completed; they are surfaced as messages rather than as a failed run.
 */
export function getDisplayStatus(workflowRun: RunWithErrors): DisplayStatus {
  if (workflowRun.run.status === WorkflowRunStatus.Completed && hasBlockingErrors(workflowRun)) {
    return WorkflowRunStatus.Failed;
  }
  return workflowRun.run.status;
}

function getWorkflowErrors(workflowRuns: RunWithErrors[]): WorkflowError[] {
  return workflowRuns
    .flatMap(getCurrentRunErrors)
    .filter((error) => error.chunk_index === null || error.chunk_index === undefined);
}

/**
 * Workflow-level errors that cost the run output. Use for banners that tell the
 * user something went wrong, so recovered failures do not trigger them.
 */
export function getBlockingWorkflowErrors(workflowRuns: RunWithErrors[]): WorkflowError[] {
  return getWorkflowErrors(workflowRuns).filter(isBlockingError);
}

export function isWorkflowProcessing(workflowRun: RunLike | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Running || workflowRun.run.status === WorkflowRunStatus.Pending;
}

/**
 * Whether a run is awaiting approval of a consent gate. Nothing happens to it
 * until the user approves, so it is neither processing nor finished.
 */
export function isWorkflowAwaitingApproval(workflowRun: RunLike | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.AwaitingApproval;
}

export function isWorkflowCancelled(workflowRun: RunLike | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Cancelled;
}

export function isWorkflowFailed(workflowRun: RunLike | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Failed;
}

/**
 * Why the document could not be processed, or null while processing has not
 * failed. Every assessment depends on document processing, so its failure
 * explains the empty document and the stopped assessments.
 */
export function getDocumentProcessingFailure(workflowRuns: RunLike[]): string | null {
  const documentProcessing = findRunByType(workflowRuns, WorkflowRunType.DocumentProcessing);
  if (!documentProcessing || !isWorkflowFailed(documentProcessing)) return null;
  return documentProcessing.run.failure_message || 'Try uploading the document again.';
}

/**
 * Whether assessments are actively working, as opposed to waiting on the user.
 * A run in AwaitingApproval is not processing, so it doesn't count.
 */
export function isAnyWorkflowActive(workflowRuns: RunLike[]): boolean {
  return workflowRuns.some((workflowRun) => isWorkflowProcessing(workflowRun));
}
