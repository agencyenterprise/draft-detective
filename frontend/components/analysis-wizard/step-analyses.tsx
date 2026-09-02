'use client';

import { useRouter } from 'next/navigation';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Callout } from '@/components/ui/callout';
import { WorkflowTypeSelector } from '@/components/workflows/workflow-type-selector';
import { WebSearchConsentCheckbox } from '@/components/workflows/web-search-consent-checkbox';
import { useWizard } from './wizard-context';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';
import { hasWebSearchRequirement, hasReferenceReviewRequirement } from '@/components/workflows/utils';
import { startMultipleWorkflowsApiWorkflowsStartMultiplePost } from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import { getErrorMessage } from '@/lib/api-error';
import { toast } from 'sonner';

export function StepAnalyses() {
  const router = useRouter();
  const wizard = useWizard();
  const { workflowTypes } = useWorkflowTypes();
  const { selectedWorkflowTypes, setSelectedWorkflowTypes } = wizard;
  const [webSearchConsent, setWebSearchConsent] = useWebSearchConsent(wizard.projectId);

  const needsWebSearch = hasWebSearchRequirement(selectedWorkflowTypes, workflowTypes);
  const needsSupportingDocs = hasReferenceReviewRequirement(selectedWorkflowTypes, workflowTypes);

  const startAnalysisMutation = useMutation({
    mutationFn: async () => {
      if (!wizard.projectId) throw new Error('No project ID');
      if (selectedWorkflowTypes.length === 0) throw new Error('No workflow types selected');

      return startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: wizard.projectId,
          workflow_types: selectedWorkflowTypes,
        },
      });
    },
    onSuccess: () => {
      toast.success('Assessment started! Redirecting to your project...');
      router.push(`/projects/${wizard.projectId}`);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to start assessment'));
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
              <h2 className="text-xl font-semibold">Starting Assessment</h2>
              <p className="text-sm text-muted-foreground">Starting assessments...</p>
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
          Select the assessments that matter most for your document.{' '}
          <strong>You can also trigger assessments later</strong>, after project is created, so you can skip this step
          for now if you want.
        </p>
      </div>

      <WorkflowTypeSelector
        projectId={wizard.projectId ?? undefined}
        selectedTypes={selectedWorkflowTypes}
        onSelectionChange={setSelectedWorkflowTypes}
        headerDescription=""
      />

      {needsSupportingDocs && (
        <Callout variant="info" icon={AlertCircle} title="Source documents required">
          Some selected assessments need reference documents to verify claims. After the project is created, go to the{' '}
          <strong>References tab</strong> to upload sources or fetch them from the web, then approve to start the
          analysis.
        </Callout>
      )}

      {needsWebSearch && <WebSearchConsentCheckbox checked={webSearchConsent} onCheckedChange={setWebSearchConsent} />}

      <div className="flex flex-col gap-3">
        <Button onClick={handleStartAnalysis} disabled={!canContinue} size="lg" className="w-full">
          Start Assessment
        </Button>
        <Button
          variant="outline"
          size="lg"
          className="w-full"
          onClick={() => router.push(`/projects/${wizard.projectId}`)}
        >
          Skip for now
        </Button>
      </div>
    </div>
  );
}
