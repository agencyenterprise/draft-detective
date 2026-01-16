'use client';

import { useMutation } from '@tanstack/react-query';
import * as React from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToolProjectUrl } from '@/hooks/use-tool-project-url';
import { WorkflowRunType, startWorkflowApiWorkflowsStartPost } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { AlertCircle, Loader2, Play } from 'lucide-react';
import { toast } from 'sonner';
import { ReferenceDownloaderResultsDisplay } from './reference-downloader-results-display';

export function ReferenceDownloaderTool() {
  const [references, setReferences] = React.useState('');
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  const { projectId, setProjectId } = useToolProjectUrl();

  const { workflowDetails, isProcessing: isWorkflowProcessing } = useProjectDetails(projectId);

  const referenceDownloader = getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader);

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
      setProjectId(response.project_id ?? null);
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

  const isProcessing = startWorkflowMutation.isPending || isWorkflowProcessing;
  const fetchedReferences = referenceDownloader?.state?.fetched_references ?? [];
  const hasResults = fetchedReferences.length > 0;

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
              {isWorkflowProcessing ? 'Checking...' : 'Starting...'}
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-2" />
              Find references
            </>
          )}
        </Button>
        {projectId && (
          <span className="text-sm text-muted-foreground">
            Project ID: <code className="text-xs">{projectId}</code>
          </span>
        )}
      </div>

      {isProcessing && (
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

      {!isProcessing && !hasResults && projectId && (
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

      {hasResults && (
        <div className="space-y-4">
          <ReferenceDownloaderResultsDisplay results={fetchedReferences} projectId={projectId} />
        </div>
      )}
    </div>
  );
}
