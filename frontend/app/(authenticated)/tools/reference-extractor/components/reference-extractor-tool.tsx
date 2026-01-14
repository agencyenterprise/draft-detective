'use client';

import { UploadSection } from '@/components/analysis-form/upload-section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { startAnalysisApiStartAnalysisPost, WorkflowRunType } from '@/lib/generated-api';
import { useToolProjectUrl } from '@/hooks/use-tool-project-url';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { ExtractionProcessing } from './extraction-processing';
import { ExtractionResults } from './extraction-results';
import { useReferenceExtraction } from '../hooks/use-reference-extraction';

export function ReferenceExtractorTool() {
  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  const { projectId, setProjectId } = useToolProjectUrl();

  const { results, isProcessing: isWorkflowProcessing } = useReferenceExtraction(projectId);

  const startWorkflowMutation = useMutation({
    mutationFn: async () => {
      return await startAnalysisApiStartAnalysisPost({
        body: {
          main_document: mainDocument!,
          workflow_types: `${WorkflowRunType.DocumentProcessing},${WorkflowRunType.ReferenceExtraction}`,
          openai_api_key: openaiApiKey || null,
        },
      });
    },
    onSuccess: (response) => {
      setProjectId(response.project_id!);
      toast.success('Documents uploaded, processing...');
    },
    onError: (error) => {
      console.error('Error extracting references:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to extract references');
    },
  });

  const handleExtract = () => {
    if (!mainDocument) return;
    toast.info('Uploading documents...');
    startWorkflowMutation.mutate();
  };

  const handleReset = () => {
    setProjectId(null);
    setMainDocument(null);
  };

  const isProcessing = startWorkflowMutation.isPending || isWorkflowProcessing;

  // Show results
  if (results) {
    return <ExtractionResults results={results} onReset={handleReset} />;
  }

  // Show processing state
  if (isProcessing) {
    return <ExtractionProcessing />;
  }

  const isSubmitDisabled = !mainDocument || (!hideOpenaiApiKeyInput && !openaiApiKey);

  // Show upload form
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
            required={true}
          />
          <p className="text-xs text-muted-foreground">
            Your OpenAI API key will be used only for this workflow and will not be stored in our database.
          </p>
        </div>
      )}

      <UploadSection
        title="Main Document"
        description='Document containing a "references" section (or equivalent) from which reference items will be extracted.'
        required
        onFilesChange={(files) => setMainDocument(files[0] || null)}
        multiple={false}
        files={mainDocument ? [mainDocument] : []}
        fileType="main"
        onRemoveFile={() => setMainDocument(null)}
      />

      <Button onClick={handleExtract} disabled={isSubmitDisabled} className="w-full">
        Extract References
      </Button>
    </div>
  );
}
