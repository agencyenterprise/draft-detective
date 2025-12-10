import {
  ClaimSubstantiationWorkflowDetail,
  ClaimSubstantiatorStateSummary,
  MethodologicalAlignmentState,
  MethodologicalAlignmentWorkflowDetail,
  Project,
  ReferenceDownloaderWorkflowDetail,
  WorkflowRunType,
} from './generated-api';

export type WorkflowRunDetail =
  | ClaimSubstantiationWorkflowDetail
  | MethodologicalAlignmentWorkflowDetail
  | ReferenceDownloaderWorkflowDetail;

/**
 * Type mapping for workflow types to their corresponding workflow detail types
 */
type WorkflowTypeToDetail = {
  [WorkflowRunType.ClaimSubstantiation]: ClaimSubstantiationWorkflowDetail;
  [WorkflowRunType.MethodologicalAlignment]: MethodologicalAlignmentWorkflowDetail;
  [WorkflowRunType.ReferenceDownloader]: ReferenceDownloaderWorkflowDetail;
};

export type WorkflowState = ClaimSubstantiatorStateSummary | MethodologicalAlignmentState;

export interface ProjectDetails {
  project: Project;
  workflowRuns: Array<WorkflowRunDetail>;
}

/**
 * Get a workflow run by type with type-safe return
 *
 * @param workflowRuns - The workflow runs to search through
 * @param type - The type of workflow run to get
 * @returns The workflow run if found, otherwise undefined
 */
export function getWorkflowRunByType<T extends WorkflowRunType>(
  workflowRuns: WorkflowRunDetail[],
  type: T,
): WorkflowTypeToDetail[T] | undefined {
  return workflowRuns.find((workflowRun) => workflowRun.run.type === type) as WorkflowTypeToDetail[T] | undefined;
}

const workflowTypeNames: Record<WorkflowRunType, string> = {
  [WorkflowRunType.ClaimSubstantiation]: 'Claim Substantiation',
  [WorkflowRunType.MethodologicalAlignment]: 'Methodological Alignment',
  [WorkflowRunType.ReferenceDownloader]: 'Reference Downloader',
};

export function getWorkflowTypeName(type: WorkflowRunType): string {
  return workflowTypeNames[type] || type;
}
