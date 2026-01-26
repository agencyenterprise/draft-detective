'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { UploadSection } from '@/components/analysis-form/upload-section';
import { WorkflowTypeSelector } from '@/components/workflows/workflow-type-selector';
import { WebSearchConsentCheckbox } from '@/components/workflows/web-search-consent-checkbox';
import { useWizard } from './wizard-context';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { hasSupportingDocumentsRequirement, hasWebSearchRequirement } from '@/components/workflows/utils';
import {
  WorkflowRunType,
  addFilesToProjectApiProjectProjectIdFilesPost,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  updateProjectEndpointApiProjectProjectIdPatch,
} from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

export function StepAnalyses() {
  const router = useRouter();
  const wizard = useWizard();
  const { data: workflowTypes } = useWorkflowTypes();
  const [storedApiKey] = useSessionStorage<string>('openai-api-key', '');

  const [selectedWorkflowTypes, setSelectedWorkflowTypes] = useState<WorkflowRunType[]>([]);
  const [supportingDocuments, setSupportingDocuments] = useState<File[]>([]);
  const [domain, setDomain] = useState('');
  const [targetAudience, setTargetAudience] = useState('');
  const [webSearchConsent, setWebSearchConsent] = useState(false);

  const showSupportingDocs = hasSupportingDocumentsRequirement(selectedWorkflowTypes);
  const needsWebSearch = hasWebSearchRequirement(selectedWorkflowTypes, workflowTypes);
  const needsReferenceReview = showSupportingDocs && supportingDocuments.length > 0;

  const { setNeedsReferencesStep } = wizard;
  useEffect(() => {
    setNeedsReferencesStep(showSupportingDocs);
  }, [showSupportingDocs, setNeedsReferencesStep]);

  const startAnalysisMutation = useMutation({
    mutationFn: async () => {
      if (!wizard.projectId) throw new Error('No project ID');
      if (selectedWorkflowTypes.length === 0) throw new Error('No workflow types selected');

      const projectId = wizard.projectId;

      if (supportingDocuments.length > 0) {
        await addFilesToProjectApiProjectProjectIdFilesPost({
          path: { project_id: projectId },
          body: { files: supportingDocuments, role: 'support' },
        });
      }

      if (domain || targetAudience) {
        await updateProjectEndpointApiProjectProjectIdPatch({
          path: { project_id: projectId },
          body: {
            domain: domain || undefined,
            target_audience: targetAudience || undefined,
          },
        });
      }

      // Re-run DOCUMENT_PROCESSING for new supporting docs
      const workflowsToStart =
        supportingDocuments.length > 0
          ? [WorkflowRunType.DocumentProcessing, ...selectedWorkflowTypes]
          : selectedWorkflowTypes;

      const apiKey = wizard.openaiApiKey || storedApiKey;
      return startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectId,
          workflow_types: workflowsToStart,
          openai_api_key: apiKey || undefined,
        },
      });
    },
    onSuccess: () => {
      if (needsReferenceReview) {
        toast.success('Analysis started! Review your references...');
        wizard.goToStep(3);
      } else {
        toast.success('Analysis started! Redirecting to your project...');
        router.push(`/projects/${wizard.projectId}?fromWizard=true`);
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to start analysis');
    },
  });

  const handleRemoveSupportingFile = (index?: number) => {
    if (typeof index === 'number') {
      setSupportingDocuments((files) => files.filter((_, i) => i !== index));
    }
  };

  const handleStartAnalysis = () => {
    if (startAnalysisMutation.isPending || startAnalysisMutation.isSuccess) return;
    startAnalysisMutation.mutate();
  };

  const canContinue = selectedWorkflowTypes.length > 0 && (!needsWebSearch || webSearchConsent);
  const isSubmitting = startAnalysisMutation.isPending || startAnalysisMutation.isSuccess;

  if (isSubmitting) {
    return (
      <Card className="max-w-xl mx-auto">
        <CardContent className="py-12">
          <div className="flex flex-col items-center justify-center space-y-4">
            <Loader2 className="w-12 h-12 animate-spin text-primary" />
            <div className="text-center space-y-2">
              <h2 className="text-xl font-semibold">Starting Analysis</h2>
              <p className="text-sm text-muted-foreground">
                {supportingDocuments.length > 0
                  ? 'Uploading supporting documents and starting workflows...'
                  : 'Starting workflows...'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">What do you want to analyze today?</h1>
      </div>

      <WorkflowTypeSelector
        workflowTypes={workflowTypes?.filter((wt) => !wt.is_internal && wt.can_be_triggered_by_user)}
        selectedTypes={selectedWorkflowTypes}
        onSelectionChange={setSelectedWorkflowTypes}
        headerDescription="Select which types of analyses to perform"
      />

      {needsWebSearch && <WebSearchConsentCheckbox checked={webSearchConsent} onCheckedChange={setWebSearchConsent} />}

      {showSupportingDocs && (
        <UploadSection
          title="Supporting Documents"
          description="Reference documents cited in your main document's reference section (e.g., PDFs of cited papers or news websites). These enable validation of claims against their cited sources."
          required={true}
          onFilesChange={setSupportingDocuments}
          multiple={true}
          files={supportingDocuments}
          fileType="supporting"
          onRemoveFile={handleRemoveSupportingFile}
        />
      )}

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="domain">
            Domain <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
          </Label>
          <Input
            id="domain"
            placeholder="e.g., Healthcare, Technology, Finance..."
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
          />
          <p className="text-sm text-muted-foreground">
            The subject area or field of expertise to contextualize the analysis. This helps tailor the evaluation to
            domain-specific standards and terminology.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="target-audience">
            Target Audience <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
          </Label>
          <Input
            id="target-audience"
            placeholder="e.g., General public, Experts, Students..."
            value={targetAudience}
            onChange={(e) => setTargetAudience(e.target.value)}
          />
          <p className="text-sm text-muted-foreground">
            The intended readers of the document. Specifying the audience helps adjust the analysis to match appropriate
            complexity level and expectations.
          </p>
        </div>
      </div>

      <Button onClick={handleStartAnalysis} disabled={!canContinue} size="lg" className="w-full">
        Continue
      </Button>
    </div>
  );
}
