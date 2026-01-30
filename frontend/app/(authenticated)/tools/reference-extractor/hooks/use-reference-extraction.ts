import { ReferenceExtractionState, WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';
import { useToolWorkflow } from '@/hooks/use-tool-workflow';
import { getWorkflowErrors } from '@/lib/workflow-state';
import { useEffect, useMemo, useRef } from 'react';
import { toast } from 'sonner';

type ExtractionResults = Pick<ReferenceExtractionState, 'detected_sections' | 'extracted_references'>;

export function useReferenceExtraction(projectId: string | null) {
  // Track which run IDs we've shown toasts for (to avoid duplicate toasts)
  const toastedRunIdRef = useRef<string | null>(null);

  const { workflowDetails, allWorkflowDetails, isProcessing } = useToolWorkflow(projectId, [
    WorkflowRunType.DocumentProcessing,
    WorkflowRunType.ReferenceExtraction,
  ]);

  const docProcessingRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.DocumentProcessing),
    [workflowDetails],
  );

  const refExtractionRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.ReferenceExtraction),
    [workflowDetails],
  );

  // Derive results directly from workflow state
  const results = useMemo<ExtractionResults | null>(() => {
    if (refExtractionRun?.run.status !== WorkflowRunStatus.Completed) {
      return null;
    }
    const state = refExtractionRun.state as ReferenceExtractionState;
    return {
      detected_sections: state.detected_sections || [],
      extracted_references: state.extracted_references || [],
    };
  }, [refExtractionRun]);

  // Show toast only once per completed run
  useEffect(() => {
    const runId = refExtractionRun?.run.id;
    if (results && runId && toastedRunIdRef.current !== runId) {
      toastedRunIdRef.current = runId;
      toast.success(
        `Extracted ${results.extracted_references?.length || 0} references from ${results.detected_sections?.length || 0} section(s)!`,
      );
    }
  }, [results, refExtractionRun?.run.id]);

  // Show error toast if workflow completed with errors
  useEffect(() => {
    const runId = refExtractionRun?.run.id;
    if (!runId || refExtractionRun?.run.status !== WorkflowRunStatus.Completed) return;

    const errors = getWorkflowErrors(allWorkflowDetails);
    if (errors.length > 0) {
      toast.error(`Processing completed with errors: ${errors[0]?.error || 'Unknown error'}`);
    }
  }, [allWorkflowDetails, refExtractionRun]);

  return {
    results,
    isProcessing,
    docProcessingRun,
    refExtractionRun,
  };
}
