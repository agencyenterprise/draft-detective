import {
  CitationDetectionState,
  CitationSuggesterState,
  ClaimExtractionState,
  ClaimReferenceValidationState,
  DocumentProcessingState,
  InferenceValidationState,
  LiteratureReviewState,
  LiveReportsState,
  MethodologicalAlignmentState,
  ReferenceDownloaderState,
  ReferenceExtractionState,
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
  [WorkflowRunType.ReferenceExtraction]: ReferenceExtractionState;
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

const workflowTypeNames: Record<WorkflowRunType, string> = {
  [WorkflowRunType.DocumentProcessing]: 'Document Processing',
  [WorkflowRunType.ReferenceExtraction]: 'Reference Extraction',
  [WorkflowRunType.ClaimReferenceValidation]: 'Claim Reference Validation',
  [WorkflowRunType.MethodologicalAlignment]: 'Methodological Alignment',
  [WorkflowRunType.ReferenceDownloader]: 'Reference Downloader',
  [WorkflowRunType.InferenceValidation]: 'Inference Validation',
  [WorkflowRunType.LiteratureReview]: 'Literature Review',
  [WorkflowRunType.LiveReports]: 'Live Reports',
  [WorkflowRunType.ReferenceValidation]: 'Reference Validation',
  [WorkflowRunType.CitationSuggester]: 'Citation Suggester',
  [WorkflowRunType.ResultsExtraction]: 'Results Extraction',
  [WorkflowRunType.ClaimExtraction]: 'Claim Extraction',
  [WorkflowRunType.CitationDetection]: 'Citation Detection',
};

export function getWorkflowTypeName(type: WorkflowRunType): string {
  return workflowTypeNames[type] || type;
}

export function getWorkflowErrors(workflowRuns: WorkflowRunDetail[]): WorkflowError[] {
  return workflowRuns
    .flatMap((result) => result?.state?.errors ?? [])
    .filter((error) => error.chunk_index === null || error.chunk_index === undefined);
}

export function getChunkErrors(workflowRuns: WorkflowRunDetail[], chunkIndex: number): WorkflowError[] {
  return workflowRuns
    .flatMap((result) => result?.state?.errors ?? [])
    .filter((error) => error.chunk_index === chunkIndex);
}

export function isWorkflowProcessing(workflowRun: WorkflowRunDetail | undefined): boolean {
  if (!workflowRun) return false;
  return workflowRun.run.status === WorkflowRunStatus.Running || workflowRun.run.status === WorkflowRunStatus.Pending;
}

export function isAnyWorkflowProcessing(workflowRuns: WorkflowRunDetail[]): boolean {
  return workflowRuns.some((workflowRun) => isWorkflowProcessing(workflowRun));
}
