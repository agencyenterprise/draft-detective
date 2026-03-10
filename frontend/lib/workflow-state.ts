import {
  AbbreviationScanState,
  AbbreviationScanV2State,
  AboutAuthorsState,
  AboutThisState,
  AdvocacyToneState,
  ChunkSplittingState,
  CitationDetectionState,
  CitationSuggesterState,
  ClaimExtractionState,
  ClaimReferenceValidationState,
  DocumentProcessingState,
  DocumentSummarizationState,
  FootnoteExtractionState,
  HumanApprovalState,
  InferenceValidationState,
  InferenceValidationV2State,
  LiteratureReviewState,
  LiveReportsState,
  MethodologicalAlignmentState,
  ReferenceDownloaderState,
  ReferenceExtractionState,
  ReferenceFileMatchingState,
  ReferenceValidationState,
  ResultsExtractionState,
  Reviewer2State,
  WorkflowError,
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
  [WorkflowRunType.ChunkSplitting]: ChunkSplittingState;
  [WorkflowRunType.DocumentSummarization]: DocumentSummarizationState;
  [WorkflowRunType.ReferenceExtraction]: ReferenceExtractionState;
  [WorkflowRunType.ReferenceFileMatching]: ReferenceFileMatchingState;
  [WorkflowRunType.HumanApproval]: HumanApprovalState;
  [WorkflowRunType.FootnoteExtraction]: FootnoteExtractionState;
  [WorkflowRunType.ClaimExtraction]: ClaimExtractionState;
  [WorkflowRunType.CitationDetection]: CitationDetectionState;
  [WorkflowRunType.MethodologicalAlignment]: MethodologicalAlignmentState;
  [WorkflowRunType.ReferenceDownloader]: ReferenceDownloaderState;
  [WorkflowRunType.LiteratureReview]: LiteratureReviewState;
  [WorkflowRunType.LiveReports]: LiveReportsState;
  [WorkflowRunType.ReferenceValidation]: ReferenceValidationState;
  [WorkflowRunType.CitationSuggester]: CitationSuggesterState;
  [WorkflowRunType.ResultsExtraction]: ResultsExtractionState;
  [WorkflowRunType.InferenceValidation]: InferenceValidationState;
  [WorkflowRunType.InferenceValidationV2]: InferenceValidationV2State;
  [WorkflowRunType.ClaimReferenceValidation]: ClaimReferenceValidationState;
  [WorkflowRunType.AbbreviationScan]: AbbreviationScanState;
  [WorkflowRunType.AbbreviationScanV2]: AbbreviationScanV2State;
  [WorkflowRunType.AdvocacyTone]: AdvocacyToneState;
  [WorkflowRunType.AboutAuthors]: AboutAuthorsState;
  [WorkflowRunType.AboutThis]: AboutThisState;
  [WorkflowRunType.Reviewer2]: Reviewer2State;
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
 * Check if a workflow run has errors from the current run only.
 * Used to determine if a run should be displayed as "failed".
 */
export function hasCurrentRunErrors(workflowRun: WorkflowRunDetail): boolean {
  const errors = workflowRun.state?.errors ?? [];
  const runId = workflowRun.run.id;
  return filterErrorsToCurrentRun(errors, runId).length > 0;
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
 * Display status type that includes "failed" for completed runs with errors.
 */
export type DisplayStatus = WorkflowRunStatus | 'failed';

/**
 * Get the display status for a workflow run.
 * Returns "failed" if completed with errors, otherwise returns the actual status.
 */
export function getDisplayStatus(workflowRun: WorkflowRunDetail): DisplayStatus {
  if (workflowRun.run.status === WorkflowRunStatus.Completed && hasCurrentRunErrors(workflowRun)) {
    return 'failed';
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

export function getChunkErrors(workflowRuns: WorkflowRunDetail[], chunkIndex: number): WorkflowError[] {
  return workflowRuns
    .flatMap((result) => {
      const errors = result?.state?.errors ?? [];
      return filterErrorsToCurrentRun(errors, result.run.id);
    })
    .filter((error) => error.chunk_index === chunkIndex);
}

export function isWorkflowProcessing(workflowRun: WorkflowRunDetail | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Running || workflowRun.run.status === WorkflowRunStatus.Pending;
}

export function isAnyWorkflowProcessing(workflowRuns: WorkflowRunDetail[]): boolean {
  return workflowRuns.some((workflowRun) => isWorkflowProcessing(workflowRun));
}

/**
 * Checks if a project needs wizard completion (step 2).
 *
 * A project needs completion when:
 * - It has DOCUMENT_PROCESSING workflow (started via step 1)
 * - It has NO other user-visible analysis workflows started
 *
 * This indicates the user created a project in step 1 but didn't complete step 2.
 *
 * @param workflowRuns - The workflow runs to check
 * @param internalTypes - Set of workflow types that are internal (from API)
 */
export function needsWizardCompletion(workflowRuns: WorkflowRunDetail[], internalTypes: Set<WorkflowRunType>): boolean {
  if (workflowRuns.length === 0) return false;

  const hasDocProcessing = workflowRuns.some((w) => w.run.type === WorkflowRunType.DocumentProcessing);
  const hasUserWorkflows = workflowRuns.some((w) => !internalTypes.has(w.run.type));

  return hasDocProcessing && !hasUserWorkflows;
}

/**
 * Checks if a project is waiting for human approval (step 3).
 *
 * A project needs human approval when:
 * - It has a HumanApproval workflow run
 * - The HumanApproval workflow has not been approved yet
 *
 * @param workflowRuns - The workflow runs to check
 */
export function needsHumanApproval(workflowRuns: WorkflowRunDetail[]): boolean {
  const humanApprovalRun = workflowRuns.find((w) => w.run.type === WorkflowRunType.HumanApproval);

  if (!humanApprovalRun) return false;

  const state = humanApprovalRun.state as HumanApprovalState | null;
  return !state?.approved;
}
