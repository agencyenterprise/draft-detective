'use client';

import { useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { WizardProvider, useWizard, WizardStep } from '@/components/analysis-wizard/wizard-context';
import { StepIndicator } from '@/components/analysis-wizard/step-indicator';
import { StepUpload } from '@/components/analysis-wizard/step-upload';
import { StepAnalyses } from '@/components/analysis-wizard/step-analyses';
import { StepReferences } from '@/components/analysis-wizard/step-references';
import { StepApiKeyConfig } from '@/components/analysis-wizard/step-api-key-config';
import { useSearchParams } from 'next/navigation';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { Loader2 } from 'lucide-react';

const REQUIRE_API_KEY_CONFIG = process.env.NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG === 'true';

function WizardContent() {
  const wizard = useWizard();
  const { data: user, isLoading: isUserLoading } = useUserMe();

  const apiKeyConfigured = user?.has_openai_api_key ?? false;
  // Show the API key form when required and not yet configured.
  // The step always appears in the indicator regardless of configured state.
  const isOnApiKeyStep = REQUIRE_API_KEY_CONFIG && !apiKeyConfigured;

  const steps = useMemo(() => {
    const apiKeyStep = REQUIRE_API_KEY_CONFIG ? [{ label: 'API Key Setup', completed: apiKeyConfigured }] : [];
    const wizardSteps = [
      { label: 'Your Document', completed: wizard.currentStep > 1 },
      { label: 'Choose Analyses', completed: wizard.currentStep > 2 },
    ];
    if (wizard.needsReferencesStep) {
      wizardSteps.push({ label: 'Add Sources', completed: false });
    }
    return [...apiKeyStep, ...wizardSteps];
  }, [apiKeyConfigured, wizard.currentStep, wizard.needsReferencesStep]);

  // When REQUIRE_API_KEY_CONFIG is true, wizard steps are offset by 1 in the indicator.
  const currentIndicatorStep = isOnApiKeyStep ? 1 : wizard.currentStep + (REQUIRE_API_KEY_CONFIG ? 1 : 0);

  const cardWidthClass = !isOnApiKeyStep && wizard.currentStep === 3 ? 'max-w-8xl' : 'max-w-3xl';

  if (REQUIRE_API_KEY_CONFIG && isUserLoading) {
    return (
      <div className="flex justify-center items-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <StepIndicator currentStep={currentIndicatorStep} steps={steps} className="mb-8" />

      <Card className={`${cardWidthClass} mx-auto transition-all duration-300`}>
        <CardContent className="">
          {isOnApiKeyStep && <StepApiKeyConfig />}
          {!isOnApiKeyStep && wizard.currentStep === 1 && <StepUpload onComplete={wizard.nextStep} />}
          {!isOnApiKeyStep && wizard.currentStep === 2 && <StepAnalyses />}
          {!isOnApiKeyStep && wizard.currentStep === 3 && <StepReferences />}
        </CardContent>
      </Card>
    </div>
  );
}

export default function New() {
  const searchParams = useSearchParams();
  const projectIdFromUrl = searchParams.get('projectId');
  const stepFromUrl = searchParams.get('step');

  const initialStep: WizardStep | undefined =
    stepFromUrl && ['1', '2', '3'].includes(stepFromUrl) ? (parseInt(stepFromUrl, 10) as WizardStep) : undefined;

  return (
    <WizardProvider initialProjectId={projectIdFromUrl} initialStep={initialStep}>
      <WizardContent />
    </WizardProvider>
  );
}
