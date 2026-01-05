import { ReferenceDownloaderState, WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';
import { useToolWorkflow } from '@/hooks/use-tool-workflow';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

export function useReferenceDownloader(projectId: string | null) {
  const [results, setResults] = useState<ReferenceDownloaderState | null>(null);

  const { workflowDetails, allWorkflowDetails, isProcessing } = useToolWorkflow(projectId, [
    WorkflowRunType.ReferenceDownloader,
  ]);

  const downloaderRun = useMemo(
    () => workflowDetails.find((w) => w.run.type === WorkflowRunType.ReferenceDownloader),
    [workflowDetails],
  );

  useEffect(() => {
    if (downloaderRun?.run.status === WorkflowRunStatus.Completed && !results) {
      const state = downloaderRun.state as ReferenceDownloaderState;
      setResults(state);
      const count = state.fetched_references?.length || 0;
      toast.success(`Checked ${count} reference${count !== 1 ? 's' : ''}!`);
    }
  }, [downloaderRun, results]);

  useEffect(() => {
    const hasErrors = allWorkflowDetails.some(
      (w) => w.state?.errors && Array.isArray(w.state.errors) && w.state.errors.length > 0,
    );

    if (hasErrors && downloaderRun?.run.status === WorkflowRunStatus.Completed) {
      const errors = allWorkflowDetails.flatMap((w) => w.state?.errors || []);
      if (errors.length > 0) {
        toast.error(`Processing completed with errors: ${errors[0]?.error || 'Unknown error'}`);
      }
    }
  }, [allWorkflowDetails, downloaderRun]);

  const reset = () => {
    setResults(null);
  };

  return {
    results,
    isProcessing,
    downloaderRun,
    reset,
  };
}
