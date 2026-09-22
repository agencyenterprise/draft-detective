'use client';

import { useRouter } from 'next/navigation';
import { Info, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { WorkflowTypeSelector } from '@/components/workflows/workflow-type-selector';
import { WebSearchConsentCheckbox } from '@/components/workflows/web-search-consent-checkbox';
import { useWizard } from './wizard-context';
import { StepHeading, StepLayout } from './step-layout';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';
import { hasWebSearchRequirement } from '@/components/workflows/utils';
import { startMultipleWorkflowsApiWorkflowsStartMultiplePost } from '@/lib/generated-api';
import { useMutation } from '@tanstack/react-query';
import { getErrorMessage } from '@/lib/api-error';
import { toast } from 'sonner';

/** The start button says how many it will start, so the count is confirmed where it matters. */
function startLabel(selectedCount: number): string {
  if (selectedCount === 0) return 'Start assessments';
  return selectedCount === 1 ? 'Start 1 assessment' : `Start ${selectedCount} assessments`;
}

export function StepAnalyses() {
  const router = useRouter();
  const wizard = useWizard();
  const { workflowTypes } = useWorkflowTypes();
  const { selectedWorkflowTypes, setSelectedWorkflowTypes } = wizard;
  const [webSearchConsent, setWebSearchConsent] = useWebSearchConsent(wizard.projectId);

  const needsWebSearch = hasWebSearchRequirement(selectedWorkflowTypes, workflowTypes);
  const selectedCount = selectedWorkflowTypes.length;

  const startAnalysisMutation = useMutation({
    mutationFn: async () => {
      if (!wizard.projectId) throw new Error('No project ID');
      if (selectedCount === 0) throw new Error('No workflow types selected');

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

  const isSubmitting = startAnalysisMutation.isPending || startAnalysisMutation.isSuccess;

  const handleStartAnalysis = () => {
    if (isSubmitting) return;
    startAnalysisMutation.mutate();
  };

  const goToProject = () => router.push(`/projects/${wizard.projectId}`);

  // Why the start button is off, said in the footer where the button is. A hint
  // rather than an error: nothing has been done wrong yet, the step has simply
  // not been finished, so it reads in the muted tone until it is.
  const blocker =
    selectedCount === 0
      ? 'Select at least one assessment, or skip for now.'
      : needsWebSearch && !webSearchConsent
        ? 'Consent to web search to start the selected assessments.'
        : null;

  const footer = (
    <>
      {needsWebSearch && (
        <WebSearchConsentCheckbox
          checked={webSearchConsent}
          onCheckedChange={setWebSearchConsent}
          disabled={isSubmitting}
        />
      )}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
        {blocker && !isSubmitting && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground sm:mr-auto" aria-live="polite">
            <Info aria-hidden className="size-3.5 shrink-0" />
            {blocker}
          </p>
        )}
        <div className="flex flex-col-reverse gap-2 sm:ml-auto sm:flex-row">
          <Button variant="outline" onClick={goToProject} disabled={isSubmitting}>
            Skip for now
          </Button>
          <Button onClick={handleStartAnalysis} disabled={blocker !== null || isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Starting…
              </>
            ) : (
              startLabel(selectedCount)
            )}
          </Button>
        </div>
      </div>
    </>
  );

  return (
    <StepLayout footer={footer}>
      <div className="space-y-6">
        <StepHeading title="What would you like to check?">
          Pick the assessments that matter for this draft. You can run more later from the project, so it is fine to
          skip this step for now.
        </StepHeading>

        {isSubmitting ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <Loader2 className="size-8 animate-spin text-primary" />
            <div className="space-y-1">
              <p className="text-sm font-medium">Starting assessments</p>
              <p className="text-xs text-muted-foreground">Taking you to the project once they are under way.</p>
            </div>
          </div>
        ) : (
          <WorkflowTypeSelector
            projectId={wizard.projectId ?? undefined}
            selectedTypes={selectedWorkflowTypes}
            onSelectionChange={setSelectedWorkflowTypes}
          />
        )}
      </div>
    </StepLayout>
  );
}
