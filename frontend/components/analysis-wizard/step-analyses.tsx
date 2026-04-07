'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Callout } from '@/components/ui/callout';
import { WorkflowTypeSelector } from '@/components/workflows/workflow-type-selector';
import { WebSearchConsentCheckbox } from '@/components/workflows/web-search-consent-checkbox';
import { useWizard } from './wizard-context';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';
import { hasWebSearchRequirement, hasSupportingDocumentsRequirement } from '@/components/workflows/utils';
import {
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  updateProjectEndpointApiProjectProjectIdPatch,
  WorkflowRunType,
} from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import { getErrorMessage } from '@/lib/api-error';
import { toast } from 'sonner';

export function StepAnalyses() {
  const router = useRouter();
  const wizard = useWizard();
  const { workflowTypes } = useWorkflowTypes();
  const { selectedWorkflowTypes, setSelectedWorkflowTypes, needsReferencesStep } = wizard;
  const [domain, setDomain] = useState('');
  const [targetAudience, setTargetAudience] = useState('');
  const [webSearchConsent, setWebSearchConsent] = useWebSearchConsent(wizard.projectId);

  const needsWebSearch = hasWebSearchRequirement(selectedWorkflowTypes, workflowTypes);
  const needsSupportingDocs = hasSupportingDocumentsRequirement(selectedWorkflowTypes);

  const startAnalysisMutation = useMutation({
    mutationFn: async () => {
      if (!wizard.projectId) throw new Error('No project ID');
      if (selectedWorkflowTypes.length === 0) throw new Error('No workflow types selected');

      const projectId = wizard.projectId;

      if (domain || targetAudience) {
        await updateProjectEndpointApiProjectProjectIdPatch({
          path: { project_id: projectId },
          body: {
            domain: domain || undefined,
            target_audience: targetAudience || undefined,
          },
        });
      }

      return startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectId,
          workflow_types: needsReferencesStep
            ? [...selectedWorkflowTypes, WorkflowRunType.HumanApproval]
            : selectedWorkflowTypes,
        },
      });
    },
    onSuccess: () => {
      toast.success('Analysis started! Redirecting to your project...');
      router.push(`/projects/${wizard.projectId}?fromWizard=true`);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to start analysis'));
    },
  });

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
              <p className="text-sm text-muted-foreground">Starting workflows...</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">What would you like to check?</h1>
        <p className="text-muted-foreground">
          Select the analyses that matter most for your document. <strong>You can also trigger analyses later</strong>,
          after project is created, so you can skip this step for now if you want.
        </p>
      </div>

      <WorkflowTypeSelector
        selectedTypes={selectedWorkflowTypes}
        onSelectionChange={setSelectedWorkflowTypes}
        headerDescription=""
      />

      {needsSupportingDocs && (
        <Callout variant="info" icon={AlertCircle} title="Source documents required">
          Some selected analyses need reference documents to verify claims. After the project is created, go to the{' '}
          <strong>References tab</strong> to upload sources or fetch them from the web, then approve to start the
          analysis.
        </Callout>
      )}

      {needsWebSearch && <WebSearchConsentCheckbox checked={webSearchConsent} onCheckedChange={setWebSearchConsent} />}

      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold">Help us understand your context</h3>
          <p className="text-sm text-muted-foreground">Optional, but helps tailor the analysis.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="domain">What field is this document about?</Label>
          <Input
            id="domain"
            placeholder="e.g., Healthcare, Criminal Justice, Education..."
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="target-audience">Who&apos;s the intended reader?</Label>
          <Input
            id="target-audience"
            placeholder="e.g., Policymakers, Researchers, General public..."
            value={targetAudience}
            onChange={(e) => setTargetAudience(e.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <Button onClick={handleStartAnalysis} disabled={!canContinue} size="lg" className="w-full">
          Start Analysis
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="w-full"
          onClick={() => router.push(`/projects/${wizard.projectId}?fromWizard=true`)}
        >
          Skip for now
        </Button>
      </div>
    </div>
  );
}
