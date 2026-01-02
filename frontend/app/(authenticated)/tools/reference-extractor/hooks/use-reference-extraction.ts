import { ReferenceExtractionState, WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

type ExtractionResults = Pick<ReferenceExtractionState, 'detected_sections' | 'references'>;

export function useReferenceExtraction(projectId: string | null) {
  const [results, setResults] = useState<ExtractionResults | null>(null);
  const { workflowDetails, isProcessing: isWorkflowProcessing } = useProjectDetails(projectId!, !!projectId);

  const docProcessingRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.DocumentProcessing),
    [workflowDetails],
  );

  const refExtractionRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.ReferenceExtraction),
    [workflowDetails],
  );

  const isProcessing = projectId ? isWorkflowProcessing : false;

  // Extract results when workflow completes
  useEffect(() => {
    if (refExtractionRun?.run.status === WorkflowRunStatus.Completed && !results) {
      const state = refExtractionRun.state as ReferenceExtractionState;
      setResults({
        detected_sections: state.detected_sections || [],
        references: state.references || [],
      });
      toast.success(
        `Extracted ${state.references?.length || 0} references from ${state.detected_sections?.length || 0} section(s)!`,
      );
    }
  }, [refExtractionRun, results]);

  // Handle errors
  useEffect(() => {
    const hasErrors = workflowDetails.some(
      (w) => w.state?.errors && Array.isArray(w.state.errors) && w.state.errors.length > 0,
    );

    if (hasErrors && refExtractionRun?.run.status === WorkflowRunStatus.Completed) {
      const errors = workflowDetails.flatMap((w) => w.state?.errors || []);
      toast.error(`Processing completed with errors: ${errors[0]?.error || 'Unknown error'}`);
    }
  }, [workflowDetails, refExtractionRun]);

  const reset = () => {
    setResults(null);
  };

  return {
    results,
    isProcessing,
    docProcessingRun,
    refExtractionRun,
    reset,
  };
}
