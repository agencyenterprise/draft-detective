'use client';

import { AnalysisForm } from '@/components/analysis-form';
import { AnalysisFormData } from '@/components/analysis-form/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { uploadOrchestrator } from '@/lib/services/upload-orchestrator';
import { useMutation } from '@tanstack/react-query';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React from 'react';

export default function New() {
  const router = useRouter();
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [processingStage, setProcessingStage] = React.useState<'idle' | 'uploading' | 'complete'>('idle');
  const [mainDocument, setMainDocument] = React.useState<File | null>(null);
  const [supportingDocuments, setSupportingDocuments] = React.useState<File[]>([]);

  const analysisMutation = useMutation({
    mutationFn: async (data: AnalysisFormData) => {
      return uploadOrchestrator.startAnalysisWithProgress(
        {
          mainDocument: data.mainDocument,
          supportingDocuments: data.supportingDocuments,
          config: {
            domain: data.config.domain || undefined,
            target_audience: data.config.targetAudience || undefined,
            openai_api_key: data.config.openaiApiKey,
            publication_date: data.config.publicationDate || undefined,
            workflow_types: data.config.workflowTypes,
          },
        },
        {
          onProgress: (progress) => {
            setUploadProgress(progress);
          },
          onStageChange: (stage) => {
            setProcessingStage(stage);
          },
        },
      );
    },
    onSuccess: (response) => {
      router.push(`/projects/${response.project_id}`);
    },
  });

  const getStageInfo = () => {
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
          title: 'Preparing Upload',
          description: 'Getting ready to upload your documents...',
          detail: 'Please wait',
        };
    }
  };

  if (analysisMutation.isPending) {
    const stageInfo = getStageInfo();

    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Start a new project</h1>
          <p className="text-muted-foreground text-sm">
            Upload your documents and configure your settings to receive a comprehensive review.
          </p>
        </div>

        <div className="text-center space-y-4">
          <Loader2 className="w-12 h-12 mx-auto animate-spin text-primary" />
          <h2 className="text-2xl font-bold">{stageInfo.title}</h2>
          <p className="text-muted-foreground max-w-md mx-auto">{stageInfo.description}</p>
        </div>
        <Card className="max-w-xl mx-auto">
          <CardContent className="py-8">
            <div className="space-y-4">
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
      </div>
    );
  }

  if (analysisMutation.isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Start a new project</h1>
          <p className="text-muted-foreground text-sm">
            Upload your documents and configure your settings to receive a comprehensive review.
          </p>
        </div>

        <Card className="max-w-4xl mx-auto border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Analysis Failed
            </CardTitle>
            <CardDescription>There was an error processing your files</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm text-destructive whitespace-pre-line">
                {analysisMutation.error?.message || 'Failed to start analysis'}
              </p>
            </div>

            <Button
              onClick={() => {
                analysisMutation.reset();
                setUploadProgress(0);
                setProcessingStage('idle');
              }}
              variant="outline"
              className="w-full"
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">Start a new project</h1>
        <p className="text-muted-foreground text-sm">
          Upload your documents and configure your settings to receive a comprehensive review.
        </p>
      </div>

      <div className="bg-background backdrop-blur-sm border border-border/50 rounded-2xl p-8 shadow-sm max-w-5xl mx-auto">
        <AnalysisForm
          isPending={analysisMutation.isPending}
          onSubmit={(data) => {
            setMainDocument(data.mainDocument);
            setSupportingDocuments(data.supportingDocuments);
            analysisMutation.mutate(data);
          }}
        />
      </div>
    </div>
  );
}
