'use client';

import { AnalysisForm } from '@/components/analysis-form';
import { AnalysisFormData } from '@/components/analysis-form/types';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { usePreflight } from '@/lib/hooks/use-preflight';
import { uploadOrchestrator } from '@/lib/services/upload-orchestrator';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React from 'react';
import { toast } from 'sonner';

export default function New() {
  const router = useRouter();
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [processingStage, setProcessingStage] = React.useState<'idle' | 'uploading' | 'complete'>('idle');
  const [mainDocument, setMainDocument] = React.useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = React.useState<File[]>([]);

  const { runPreflight, error: preflightError, isValidating, clearError } = usePreflight();

  const uploadMutation = useMutation({
    mutationFn: async (data: AnalysisFormData) => {
      return uploadOrchestrator.startAnalysisWithProgress(
        {
          mainDocument: data.mainDocument,
          supportingDocuments: data.supportingDocuments,
          config: {
            domain: data.config.domain || undefined,
            target_audience: data.config.target_audience || undefined,
            openai_api_key: data.config.openai_api_key,
            publication_date: data.config.publication_date || undefined,
            workflow_types: data.config.workflow_types,
          },
        },
        {
          onProgress: setUploadProgress,
          onStageChange: setProcessingStage,
        },
      );
    },
    onSuccess: (response) => {
      toast.success('Upload complete! Redirecting to your project...');
      router.push(`/projects/${response.project_id}`);
    },
  });

  const handleSubmit = async (data: AnalysisFormData) => {
    clearError();
    setMainDocument(data.mainDocument);
    setSupportingDocuments(data.supportingDocuments);

    const isValid = await runPreflight({
      mainDocument: data.mainDocument,
      supportingDocuments: data.supportingDocuments,
      openaiApiKey: data.config.openai_api_key ?? undefined,
    });

    if (!isValid) return;

    uploadMutation.mutate(data);
  };

  const getStageInfo = () => {
    if (isValidating) {
      return {
        title: 'Validating',
        description: 'Checking your configuration...',
        detail: 'Please wait',
      };
    }
    switch (processingStage) {
      case 'uploading':
        return {
          title: 'Uploading Documents',
          description: 'Uploading and converting your files...',
          detail: 'This may take a moment for large PDF files',
        };
      case 'complete':
        return {
          title: 'Upload Complete',
          description: 'Documents uploaded successfully',
          detail: 'Redirecting to analysis...',
        };
      default:
        return {
          title: 'Starting',
          description: 'Preparing your analysis...',
          detail: 'Please wait',
        };
    }
  };

  const isProcessing = isValidating || uploadMutation.isPending || uploadMutation.isSuccess;
  const error = preflightError || uploadMutation.error?.message;
  const stageInfo = getStageInfo();

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">Start a new project</h1>
        <p className="text-muted-foreground text-sm">
          Upload your documents and configure your settings to receive a comprehensive review.
        </p>
      </div>

      {/* Loading overlay - shown on top when processing */}
      {isProcessing && (
        <Card className="max-w-xl mx-auto">
          <CardContent className="py-8">
            <div className="space-y-4">
              <div className="text-center space-y-2">
                <Loader2 className="w-10 h-10 mx-auto animate-spin text-primary" />
                <h2 className="text-lg font-semibold">{stageInfo.title}</h2>
                <p className="text-sm text-muted-foreground">{stageInfo.description}</p>
              </div>

              <Progress value={uploadProgress} className="w-full" />
              <p className="text-sm text-center text-muted-foreground">{stageInfo.detail}</p>

              {processingStage === 'uploading' && uploadProgress > 0 && (
                <div className="text-center">
                  <p className="text-2xl font-semibold text-primary">{Math.round(uploadProgress)}%</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Uploading {mainDocument?.name}
                    {supportingDocuments.length > 0 &&
                      ` and ${supportingDocuments.length} supporting file${supportingDocuments.length > 1 ? 's' : ''}`}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <div
        className={`bg-background backdrop-blur-sm border border-border/50 rounded-2xl p-8 shadow-sm max-w-5xl mx-auto ${
          isProcessing ? 'hidden' : ''
        }`}
      >
        <AnalysisForm isPending={isProcessing} error={error} onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
