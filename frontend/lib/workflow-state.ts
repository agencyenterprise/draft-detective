import {
  AbbreviationScanV2State,
  DocumentProcessingState,
  DocumentSummarizationState,
  ReferenceDownloaderState,
  ReferenceExtractionState,
  ReferenceFileMatchingState,
  Reviewer2State,
  SimpleDeepAgentState,
  WorkflowError,
  WorkflowErrorSeverity,
  WorkflowRun,
  WorkflowRunDetail,
  WorkflowRunStatus,
  WorkflowRunType,
} from './generated-api';

/**
 * Type mapping for workflow types to their corresponding workflow detail types
 */
type WorkflowTypeToDetail = {
  [WorkflowRunType.DocumentProcessing]: DocumentProcessingState;
  [WorkflowRunType.DocumentSummarization]: DocumentSummarizationState;
  [WorkflowRunType.ReferenceExtraction]: ReferenceExtractionState;
  [WorkflowRunType.ReferenceFileMatching]: ReferenceFileMatchingState;
  [WorkflowRunType.MethodologicalAlignment]: SimpleDeepAgentState;
  [WorkflowRunType.ReferenceDownloader]: ReferenceDownloaderState;
  [WorkflowRunType.ResultsExtraction]: SimpleDeepAgentState;
  [WorkflowRunType.AbbreviationScanV2]: AbbreviationScanV2State;
  [WorkflowRunType.Reviewer2]: Reviewer2State;
  [WorkflowRunType.DocumentStructure]: SimpleDeepAgentState;
  [WorkflowRunType.FiguresTablesCheck]: SimpleDeepAgentState;
  [WorkflowRunType.InferenceValidationV2]: SimpleDeepAgentState;
  [WorkflowRunType.AdvocacyToneV2]: SimpleDeepAgentState;
  [WorkflowRunType.RecommendationCheck]: SimpleDeepAgentState;
  [WorkflowRunType.LiteratureReviewV2]: SimpleDeepAgentState;
  [WorkflowRunType.LiveReportsV2]: SimpleDeepAgentState;
  [WorkflowRunType.RevisionPlanningSummary]: SimpleDeepAgentState;
  [WorkflowRunType.ReviewerResponseMemos]: SimpleDeepAgentState;
  [WorkflowRunType.ReviewerCoverageReport]: SimpleDeepAgentState;
};

export interface WorkflowRunDetailTyped<T> {
  run: WorkflowRun;
  state: T;
}

/**
 * Get a workflow run by type with type-safe return
 *
 * @param workflowRuns - The workflow runs to search through
 * @param type - The type of workflow run to get
 * @returns The workflow run if found, otherwise undefined
 */
export function getWorkflowRunByType<T extends keyof WorkflowTypeToDetail>(
  workflowRuns: WorkflowRunDetail[],
  type: T,
): WorkflowRunDetailTyped<WorkflowTypeToDetail[T]> | undefined {
  return workflowRuns.find(
    (workflowRun): workflowRun is WorkflowRunDetailTyped<WorkflowTypeToDetail[T]> => workflowRun.run.type === type,
  );
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
export function hasCurrentRunErrors(workflowRun: WorkflowRunDetail): boolean {
  return getCurrentRunErrors(workflowRun).length > 0;
}

/**
 * Check if a workflow run has errors that cost it output.
 * Used to determine if a run should be displayed as "failed".
 */
export function hasBlockingErrors(workflowRun: WorkflowRunDetail): boolean {
  return getCurrentRunErrors(workflowRun).some(isBlockingError);
}

/**
 * Get errors filtered to only include those from the current workflow run.
 * Used for displaying errors in the UI.
 */
export function getCurrentRunErrors(workflowRun: WorkflowRunDetail): WorkflowError[] {
  const errors = workflowRun.state?.errors ?? [];
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
export function getDisplayStatus(workflowRun: WorkflowRunDetail): DisplayStatus {
  if (workflowRun.run.status === WorkflowRunStatus.Completed && hasBlockingErrors(workflowRun)) {
    return WorkflowRunStatus.Failed;
  }
  return workflowRun.run.status;
}

export function getWorkflowErrors(workflowRuns: WorkflowRunDetail[]): WorkflowError[] {
  return workflowRuns
    .flatMap((result) => {
      const errors = result?.state?.errors ?? [];
      return filterErrorsToCurrentRun(errors, result.run.id);
    })
    .filter((error) => error.chunk_index === null || error.chunk_index === undefined);
}

/**
 * Workflow-level errors that cost the run output. Use for banners that tell the
 * user something went wrong, so recovered failures do not trigger them.
 */
export function getBlockingWorkflowErrors(workflowRuns: WorkflowRunDetail[]): WorkflowError[] {
  return getWorkflowErrors(workflowRuns).filter(isBlockingError);
}

export function isWorkflowProcessing(workflowRun: WorkflowRunDetail | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Running || workflowRun.run.status === WorkflowRunStatus.Pending;
}

/**
 * Whether a run is awaiting approval of a consent gate. Nothing happens to it
 * until the user approves, so it is neither processing nor finished.
 */
export function isWorkflowAwaitingApproval(workflowRun: WorkflowRunDetail | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.AwaitingApproval;
}

export function isWorkflowCancelled(workflowRun: WorkflowRunDetail | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Cancelled;
}

export function isWorkflowFailed(workflowRun: WorkflowRunDetail | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Failed;
}

export function isAnyWorkflowProcessing(workflowRuns: WorkflowRunDetail[]): boolean {
  return workflowRuns.some((workflowRun) => isWorkflowProcessing(workflowRun));
}

/**
 * Whether any assessment is waiting on the user to approve a gate.
 *
 * Gate-agnostic: a run in AwaitingApproval could be waiting on any gate. For
 * the reference review specifically, see `needsReferenceReview` in
 * `components/workflows/utils`.
 */
export function needsApproval(workflowRuns: WorkflowRunDetail[]): boolean {
  return workflowRuns.some(isWorkflowAwaitingApproval);
}

/**
 * Whether assessments are actively working, as opposed to waiting on the user.
 *
 * A run in AwaitingApproval is not processing, so this is the same question as
 * `isAnyWorkflowProcessing`; it stays as a named entry point for the places
 * that ask "is the pipeline busy" rather than "is this run busy".
 */
export function isAnyWorkflowActive(workflowRuns: WorkflowRunDetail[]): boolean {
  return isAnyWorkflowProcessing(workflowRuns);
}
