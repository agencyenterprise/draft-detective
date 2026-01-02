'use client';

import { UploadSection } from '@/components/analysis-form/upload-section';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { startAnalysisApiStartAnalysisPost, WorkflowRunType } from '@/lib/generated-api';
import { useToolProjectUrl } from '@/hooks/use-tool-project-url';
import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';
import { ExtractionProcessing } from './extraction-processing';
import { ExtractionResults } from './extraction-results';
import { useReferenceExtraction } from '../hooks/use-reference-extraction';

export function ReferenceExtractorTool() {
  const router = useRouter();
  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = useState<File[]>([]);

  const { projectId, setProjectId } = useToolProjectUrl();

  const { results, isProcessing: isWorkflowProcessing, reset: resetWorkflow } = useReferenceExtraction(projectId);

  const startWorkflowMutation = useMutation({
    mutationFn: async () => {
      return await startAnalysisApiStartAnalysisPost({
        body: {
          main_document: mainDocument!,
          supporting_documents: supportingDocuments.length > 0 ? supportingDocuments : undefined,
          workflow_types: `${WorkflowRunType.DocumentProcessing},${WorkflowRunType.ReferenceExtraction}`,
        },
      });
    },
    onSuccess: (response) => {
      setProjectId(response.project_id!);
      resetWorkflow();
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
    resetWorkflow();
    setProjectId(null);
    setMainDocument(null);
    setSupportingDocuments([]);
    router.replace(window.location.pathname);
  };

  const removeSupporting = (index?: number) => {
    if (index !== undefined) {
      setSupportingDocuments((prev) => prev.filter((_, i) => i !== index));
    }
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

  // Show upload form
  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Documents</h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <UploadSection
            title="Main Document"
            description="Academic document with bibliography"
            required
            onFilesChange={(files) => setMainDocument(files[0] || null)}
            multiple={false}
            files={mainDocument ? [mainDocument] : []}
            fileType="main"
            onRemoveFile={() => setMainDocument(null)}
          />

          <UploadSection
            title="Supporting Documents"
            description="Optional - for matching references with sources"
            required={false}
            onFilesChange={setSupportingDocuments}
            multiple
            files={supportingDocuments}
            fileType="supporting"
            onRemoveFile={removeSupporting}
          />
        </div>

        <Button onClick={handleExtract} disabled={!mainDocument} className="w-full">
          Extract References
        </Button>
      </Card>
    </div>
  );
}
