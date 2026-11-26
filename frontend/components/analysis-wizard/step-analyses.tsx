'use client';

import { useRouter } from 'next/navigation';
import { Info, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { WorkflowTypeSelector } from '@/components/workflows/workflow-type-selector';
import { WebSearchConsentCheckbox } from '@/components/workflows/web-search-consent-checkbox';
import { GroupBySeveritySwitch, useSaveGroupBySeverity } from './group-by-severity-switch';
import { useWizard } from './wizard-context';
import { StepHeading, StepLayout } from './step-layout';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';
import { hasWebSearchRequirement, startBlocker, StartBlocker } from '@/components/workflows/utils';
import { startMultipleWorkflowsApiWorkflowsStartMultiplePost } from '@/lib/generated-api';
import { useToastMutation } from '@/lib/hooks/use-toast-mutation';

/** The start button says how many it will start, so the count is confirmed where it matters. */
function startLabel(selectedCount: number): string {
  if (selectedCount === 0) return 'Start assessments';
  return selectedCount === 1 ? 'Start 1 assessment' : `Start ${selectedCount} assessments`;
}

/** The footer's hint for each reason the start button is off. */
const BLOCKER_HINTS: Record<StartBlocker, string> = {
  'metadata-pending': 'Loading the available assessments…',
  'metadata-failed': 'The available assessments could not be loaded. Reload the page, or skip for now.',
  'none-selected': 'Select at least one assessment, or skip for now.',
  'consent-missing': 'Consent to web search to start the selected assessments.',
};

export function StepAnalyses() {
  const router = useRouter();
  const wizard = useWizard();
  const { workflowTypes, isPending: isMetadataPending, isError: isMetadataFailed } = useWorkflowTypes();
  const { selectedWorkflowTypes, setSelectedWorkflowTypes } = wizard;
  const [webSearchConsent, setWebSearchConsent] = useWebSearchConsent(wizard.projectId);

  const needsWebSearch = hasWebSearchRequirement(selectedWorkflowTypes, workflowTypes);
  const selectedCount = selectedWorkflowTypes.length;

  const startAnalysisMutation = useToastMutation({
    mutationFn: async () => {
      if (!wizard.projectId) throw new Error('No project ID');
      if (blocker !== null) throw new Error('The selection is not ready to start');

      return startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: wizard.projectId,
          workflow_types: selectedWorkflowTypes,
        },
      });
    },
    successMessage: 'Assessment started! Redirecting to your project...',
    errorMessage: 'Failed to start assessment',
    onSuccess: () => router.push(`/projects/${wizard.projectId}`),
  });

  const isSubmitting = startAnalysisMutation.isPending || startAnalysisMutation.isSuccess;
  const saveGroupBySeverity = useSaveGroupBySeverity();
  // Leaving the step while the setting saves would open the project on the old value.
  const isSaving = saveGroupBySeverity.isPending;

  const handleStartAnalysis = () => {
    if (isSubmitting || isSaving) return;
    startAnalysisMutation.mutate();
  };

  const goToProject = () => router.push(`/projects/${wizard.projectId}`);

  // Why the start button is off, said in the footer where the button is. A hint
  // rather than an error: nothing has been done wrong yet, the step has simply
  // not been finished, so it reads in the muted tone until it is.
  const blocker = startBlocker({
    selectedTypes: selectedWorkflowTypes,
    workflowTypes,
    metadataPending: isMetadataPending,
    metadataFailed: isMetadataFailed,
    webSearchConsent,
  });

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
            {BLOCKER_HINTS[blocker]}
          </p>
        )}
        <div className="flex flex-col-reverse gap-2 sm:ml-auto sm:flex-row">
          <Button variant="outline" onClick={goToProject} disabled={isSubmitting || isSaving}>
            Skip for now
          </Button>
          <Button onClick={handleStartAnalysis} disabled={blocker !== null || isSubmitting || isSaving}>
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
          <>
            <WorkflowTypeSelector
              projectId={wizard.projectId ?? undefined}
              selectedTypes={selectedWorkflowTypes}
              onSelectionChange={setSelectedWorkflowTypes}
            />
            <GroupBySeveritySwitch
              checked={wizard.groupBySeverity}
              onCheckedChange={(value) => saveGroupBySeverity.mutate(value)}
              disabled={!wizard.projectId || isSaving}
            />
          </>
        )}
      </div>
    </StepLayout>
  );
}
