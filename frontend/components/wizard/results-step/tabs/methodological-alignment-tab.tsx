import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { workflowsApi } from '@/lib/api';
import {
  MethodologicalAlignmentWorkflowDetail,
  MethodologyComparisonResponse,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, Loader2, PlayIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { TabWithLoadingStates } from './tab-with-loading-states';

interface MethodologicalAlignmentTabProps {
  results: MethodologicalAlignmentWorkflowDetail | undefined;
  isProcessing?: boolean;
  projectId: string;
}

export function MethodologicalAlignmentTab({ results, projectId }: MethodologicalAlignmentTabProps) {
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);

  const startWorkflowMutation = useMutation({
    mutationFn: async (values: WorkflowConfigFormValues) => {
      return await workflowsApi.startMethodologicalAlignmentWorkflowApiWorkflowsMethodologicalAlignmentStartPost({
        methodologicalAlignmentWorkflowConfig: {
          type: WorkflowRunType.MethodologicalAlignment,
          projectId,
          openaiApiKey: values.openaiApiKey || '',
        },
      });
    },
    onSuccess: (_data, variables, context, { client }) => {
      setIsConfigDialogOpen(false);
      toast.success('Methodological alignment workflow started');
      // Invalidate queries to refresh the project data
      client.invalidateQueries({
        queryKey: ['project', projectId],
      });
      client.invalidateQueries({
        queryKey: ['workflowRun', results?.run.id],
      });
    },
    onError: (error) => {
      console.error('Failed to start methodological alignment workflow:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to start methodological alignment workflow');
    },
  });

  const handleTriggerWorkflowConfirm = (values: WorkflowConfigFormValues) => {
    startWorkflowMutation.mutate(values);
  };

  return (
    <div>
      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        webSearchConsent={true}
        onConfirm={handleTriggerWorkflowConfirm}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <TabWithLoadingStates<MethodologyComparisonResponse>
        title="Methodological Alignment"
        data={results?.state.methodologyComparison}
        isProcessing={results?.run.status === WorkflowRunStatus.Running}
        hasData={(comparison) => !!comparison?.comparison}
        loadingMessage={{
          title: 'Analyzing methodological alignment...',
          description: 'Comparing the document methodology with typical methods in the field',
        }}
        emptyMessage={{
          icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
          title: 'No methodological alignment analysis available',
          description: 'The methodological alignment agent was not enabled for this analysis',
        }}
        emptyStateChildren={
          <div className="text-sm text-muted-foreground text-left max-w-md">
            <p className="mb-2">This may be because:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>The methodological alignment option was not selected during upload</li>
              <li>An error occurred during the methodological alignment process</li>
            </ul>
          </div>
        }
        skeletonType="paragraphs"
        skeletonCount={6}
        triggerButton={
          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsConfigDialogOpen(true)}
            disabled={startWorkflowMutation.isPending || results?.run.status === WorkflowRunStatus.Running}
          >
            <PlayIcon />
            {startWorkflowMutation.isPending ? 'Starting...' : 'Start Methodological Alignment'}
            {results?.run.status === WorkflowRunStatus.Running && <Loader2 className="animate-spin" />}
          </Button>
        }
      >
        {(methodologyComparison) => {
          return (
            <div className="border-t pt-4">
              <div className="space-y-2 text-sm">
                <Markdown>{methodologyComparison.comparison}</Markdown>
              </div>
            </div>
          );
        }}
      </TabWithLoadingStates>
    </div>
  );
}
