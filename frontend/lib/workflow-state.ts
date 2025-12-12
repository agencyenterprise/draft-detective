import {
  ClaimSubstantiatorStateSummary,
  DocxGenerationState,
  LiteratureReviewState,
  MethodologicalAlignmentState,
  ReferenceDownloaderState,
  WorkflowRun,
  WorkflowRunDetail,
  WorkflowRunType,
} from './generated-api';

/**
 * Type mapping for workflow types to their corresponding workflow detail types
 */
type WorkflowTypeToDetail = {
  [WorkflowRunType.ClaimSubstantiation]: ClaimSubstantiatorStateSummary;
  [WorkflowRunType.MethodologicalAlignment]: MethodologicalAlignmentState;
  [WorkflowRunType.ReferenceDownloader]: ReferenceDownloaderState;
  [WorkflowRunType.DocxGeneration]: DocxGenerationState;
  [WorkflowRunType.LiteratureReview]: LiteratureReviewState;
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
  [WorkflowRunType.ClaimSubstantiation]: 'Claim Substantiation',
  [WorkflowRunType.MethodologicalAlignment]: 'Methodological Alignment',
  [WorkflowRunType.ReferenceDownloader]: 'Reference Downloader',
  [WorkflowRunType.DocxGeneration]: 'DOCX Generation',
  [WorkflowRunType.LiteratureReview]: 'Literature Review',
};

export function getWorkflowTypeName(type: WorkflowRunType): string {
  return workflowTypeNames[type] || type;
}
