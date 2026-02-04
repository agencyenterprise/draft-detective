import {
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
  LiteratureReviewState,
  LiveReportsState,
  MethodologicalAlignmentState,
  ReferenceDownloaderState,
  ReferenceExtractionState,
  ReferenceFileMatchingState,
  ReferenceValidationState,
  ResultsExtractionState,
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
  [WorkflowRunType.ClaimReferenceValidation]: ClaimReferenceValidationState;
  [WorkflowRunType.MethodologicalAlignment]: MethodologicalAlignmentState;
  [WorkflowRunType.ReferenceDownloader]: ReferenceDownloaderState;
  [WorkflowRunType.InferenceValidation]: InferenceValidationState;
  [WorkflowRunType.LiteratureReview]: LiteratureReviewState;
  [WorkflowRunType.LiveReports]: LiveReportsState;
  [WorkflowRunType.ReferenceValidation]: ReferenceValidationState;
  [WorkflowRunType.CitationSuggester]: CitationSuggesterState;
  [WorkflowRunType.ResultsExtraction]: ResultsExtractionState;
  [WorkflowRunType.ClaimExtraction]: ClaimExtractionState;
  [WorkflowRunType.CitationDetection]: CitationDetectionState;
  [WorkflowRunType.FootnoteExtraction]: FootnoteExtractionState;
  [WorkflowRunType.AboutThis]: AboutThisState;
  [WorkflowRunType.AboutAuthors]: AboutAuthorsState;
  [WorkflowRunType.AdvocacyTone]: AdvocacyToneState;
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
 * Helper to get a completed (non-processing) workflow run for warning status checks.
 * Returns null if workflow not found or still processing.
 */
function getCompletedWorkflow<T extends keyof WorkflowTypeToDetail>(
  workflowRuns: WorkflowRunDetail[],
  type: T,
): WorkflowRunDetailTyped<WorkflowTypeToDetail[T]> | null {
  const workflowRun = getWorkflowRunByType(workflowRuns, type);
  return workflowRun && !isWorkflowProcessing(workflowRun) ? workflowRun : null;
}

/**
 * Checks if the "No References Found" warning should be displayed.
 *
 * The warning only shows when:
 * - At least one Reference Extraction workflow has completed
 * - No Reference Extraction workflow is still processing (pending/running)
 * - The completed workflow found no references
 *
 * This prevents showing stale warnings from old runs while a new extraction is in progress.
 */
export function getReferenceExtractionWarningStatus(workflowRuns: WorkflowRunDetail[]): {
  showWarning: boolean;
  sectionsDetected: boolean;
  hasErrors: boolean;
} | null {
  const workflowRun = getCompletedWorkflow(workflowRuns, WorkflowRunType.ReferenceExtraction);
  if (!workflowRun) return null;

  const { state } = workflowRun;
  if ((state.extracted_references?.length ?? 0) > 0) return null;

  return {
    showWarning: true,
    sectionsDetected: (state.detected_sections?.length ?? 0) > 0,
    hasErrors: hasCurrentRunErrors(workflowRun),
  };
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

/**
 * Checks if the "No Preface Section Found" warning should be displayed.
 *
 * The warning only shows when:
 * - The About This workflow has completed
 * - No About This workflow is still processing (pending/running)
 * - The completed workflow did not find a preface section
 *
 * This prevents showing stale warnings from old runs while a new analysis is in progress.
 */
export function getAboutThisWarningStatus(workflowRuns: WorkflowRunDetail[]): {
  showWarning: boolean;
  hasErrors: boolean;
} | null {
  const workflowRun = getCompletedWorkflow(workflowRuns, WorkflowRunType.AboutThis);
  if (!workflowRun) return null;

  if (workflowRun.state.found_section) return null;

  return {
    showWarning: true,
    hasErrors: (workflowRun.state.errors?.length ?? 0) > 0,
  };
}

/**
 * Checks if the "No Authors Section Found" warning should be displayed.
 *
 * The warning only shows when:
 * - The About Authors workflow has completed
 * - No About Authors workflow is still processing (pending/running)
 * - The completed workflow found no author biographies
 *
 * This prevents showing stale warnings from old runs while a new analysis is in progress.
 */
export function getAboutAuthorsWarningStatus(workflowRuns: WorkflowRunDetail[]): {
  showWarning: boolean;
  hasErrors: boolean;
} | null {
  const workflowRun = getCompletedWorkflow(workflowRuns, WorkflowRunType.AboutAuthors);
  if (!workflowRun) return null;

  if ((workflowRun.state.results?.length ?? 0) > 0) return null;

  return {
    showWarning: true,
    hasErrors: (workflowRun.state.errors?.length ?? 0) > 0,
  };
}
