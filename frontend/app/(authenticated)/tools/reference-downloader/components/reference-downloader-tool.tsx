'use client';

import * as React from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';

import { toast } from 'sonner';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertCircle, Loader2, Play } from 'lucide-react';
import {
  WorkflowRunStatus,
  WorkflowRunType,
  getWorkflowStateApiWorkflowsWorkflowRunIdGet,
  startWorkflowApiWorkflowsStartPost,
  ReferenceDownloaderState,
} from '@/lib/generated-api';
import { ReferenceDownloaderResultsDisplay } from './reference-downloader-results-display';

const REFETCH_INTERVAL_MS = 3000;

export function ReferenceDownloaderTool() {
  const [references, setReferences] = React.useState('');
  const [workflowRunId, setWorkflowRunId] = React.useState<string | null>(null);
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  // Query for workflow state
  const { data: workflowDetail } = useQuery({
    queryKey: ['referenceCheckWorkflow', workflowRunId],
    queryFn: async () => {
      if (!workflowRunId) return null;
      return await getWorkflowStateApiWorkflowsWorkflowRunIdGet({
        path: { workflow_run_id: workflowRunId },
      });
    },
    enabled: !!workflowRunId,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.run.status === WorkflowRunStatus.Running || data?.run.status === WorkflowRunStatus.Pending
        ? REFETCH_INTERVAL_MS
        : false;
    },
  });

  const startWorkflowMutation = useMutation({
    mutationFn: async (references: string[]) => {
      return await startWorkflowApiWorkflowsStartPost({
        body: {
          type: WorkflowRunType.ReferenceDownloader,
          project_id: null,
          openai_api_key: openaiApiKey || null,
          references,
        },
      });
    },
    onSuccess: (response) => {
      setWorkflowRunId(response.workflow_run_id ?? null);
      toast.success('Workflow started');
    },
    onError: (error) => {
      console.error('Failed to start workflow:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to start workflow');
    },
  });

  const handleSubmit = () => {
    if (!references.trim()) {
      toast.error('Please enter at least one reference');
      return;
    }

    // Parse references - one per line, filter empty lines
    const referenceList = references
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    if (referenceList.length === 0) {
      toast.error('Please enter at least one reference');
      return;
    }

    startWorkflowMutation.mutate(referenceList);
  };

  const isProcessing =
    startWorkflowMutation.isPending ||
    workflowDetail?.run.status === WorkflowRunStatus.Running ||
    workflowDetail?.run.status === WorkflowRunStatus.Pending;
  const state = workflowDetail?.state as ReferenceDownloaderState | undefined;
  const results = state?.fetched_references ?? [];
  const hasResults = results.length > 0;
  const isCompleted = workflowDetail?.run.status === WorkflowRunStatus.Completed;
  const projectId = workflowDetail?.run.project_id;

  return (
    <div className="space-y-6">
      {!hideOpenaiApiKeyInput && (
        <div className="space-y-2">
          <Label htmlFor="openai-api-key">
            OpenAI API Key <span className="text-destructive ml-1">*</span>
          </Label>
          <Input
            id="openai-api-key"
            type="text"
            placeholder="sk-..."
            value={openaiApiKey}
            onChange={(e) => setOpenaiApiKey(e.target.value)}
            disabled={isProcessing}
            required={true}
          />
          <p className="text-xs text-muted-foreground">
            Your OpenAI API key will be used only for this workflow and will not be stored in our database.
          </p>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="references-textarea">References</Label>
        <Textarea
          id="references-textarea"
          placeholder="Ablon, Lillian, and Andy Bogart, Zero Days, Thousands of Nights: The Life and Times of Zero-Day Vulnerabilities and Their Exploits, RAND Corporation, RR-1751-RC, 2017."
          value={references}
          onChange={(e) => setReferences(e.target.value)}
          rows={4}
          disabled={isProcessing}
          className="font-mono text-sm"
        />
        <p className="text-xs text-muted-foreground">Enter one reference per line. Empty lines will be ignored.</p>
      </div>

      <div className="flex items-center gap-2">
        <Button onClick={handleSubmit} disabled={isProcessing || !references.trim()} className="min-w-[140px]">
          {isProcessing ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              {workflowDetail?.run.status === WorkflowRunStatus.Running ? 'Checking...' : 'Starting...'}
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              Find references
            </>
          )}
        </Button>
        {workflowRunId && (
          <span className="text-sm text-muted-foreground">
            Workflow ID: <code className="text-xs">{workflowRunId}</code>
          </span>
        )}
      </div>

      {isProcessing && !hasResults && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="flex items-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <div>
              <p className="font-medium text-blue-900">Checking references...</p>
              <p className="text-sm text-blue-700">Searching for and verifying reference sources</p>
            </div>
          </div>
        </div>
      )}

      {isCompleted && !hasResults && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-yellow-600" />
            <div>
              <p className="font-medium text-yellow-900">No results available</p>
              <p className="text-sm text-yellow-700">The reference check completed but no results were found.</p>
            </div>
          </div>
        </div>
      )}

      {hasResults && <ReferenceDownloaderResultsDisplay results={results} projectId={projectId} />}
    </div>
  );
}
