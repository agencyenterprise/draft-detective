'use client';

import { UploadSection } from '@/components/analysis-form/upload-section';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { startAnalysisApiStartAnalysisPost, WorkflowRunType } from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ExtractionProcessing } from './extraction-processing';
import { ExtractionResults } from './extraction-results';
import { useReferenceExtraction } from '../hooks/use-reference-extraction';

export function ReferenceExtractorTool() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectIdFromUrl = searchParams.get('projectId');

  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = useState<File[]>([]);
  const [projectId, setProjectId] = useState<string | null>(projectIdFromUrl);

  const { results, isProcessing: isWorkflowProcessing, reset: resetWorkflow } = useReferenceExtraction(projectId);

  // Update URL when projectId changes
  useEffect(() => {
    if (projectId && !projectIdFromUrl) {
      const params = new URLSearchParams(searchParams.toString());
      params.set('projectId', projectId);
      router.replace(`?${params.toString()}`, { scroll: false });
    }
  }, [projectId, projectIdFromUrl, router, searchParams]);

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
            required={true}
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
            multiple={true}
            files={supportingDocuments}
            fileType="supporting"
            onRemoveFile={(index) => setSupportingDocuments((prev) => prev.filter((_, i) => i !== index))}
          />
        </div>

        <Button onClick={handleExtract} disabled={!mainDocument} className="w-full">
          Extract References
        </Button>
      </Card>
    </div>
  );
}
