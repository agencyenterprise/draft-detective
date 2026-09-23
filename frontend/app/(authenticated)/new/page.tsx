'use client';

import { useMemo } from 'react';
import { AppBar } from '@/components/results/app-bar';
import { WizardProvider, useWizard } from '@/components/analysis-wizard/wizard-context';
import { StepIndicator } from '@/components/analysis-wizard/step-indicator';
import { StepUpload } from '@/components/analysis-wizard/step-upload';
import { StepAnalyses } from '@/components/analysis-wizard/step-analyses';
import { StepApiKeyConfig } from '@/components/analysis-wizard/step-api-key-config';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { Loader2 } from 'lucide-react';

const REQUIRE_API_KEY_CONFIG = process.env.NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG === 'true';

function WizardContent() {
  const wizard = useWizard();
  const { data: user } = useUserMe();

  const apiKeyConfigured = user?.has_openai_api_key ?? false;
  // Show the API key form when required and not yet configured.
  // The step always appears in the indicator regardless of configured state.
  const isOnApiKeyStep = REQUIRE_API_KEY_CONFIG && !apiKeyConfigured;

  const steps = useMemo(() => {
    const apiKeyStep = REQUIRE_API_KEY_CONFIG ? [{ label: 'API Key Setup', completed: apiKeyConfigured }] : [];
    const wizardSteps = [
      { label: 'Your Document', completed: wizard.currentStep > 1 },
      { label: 'Choose Assessments', completed: wizard.currentStep > 2 },
    ];
    return [...apiKeyStep, ...wizardSteps];
  }, [apiKeyConfigured, wizard.currentStep]);

  // When REQUIRE_API_KEY_CONFIG is true, wizard steps are offset by 1 in the indicator.
  const currentIndicatorStep = isOnApiKeyStep ? 1 : wizard.currentStep + (REQUIRE_API_KEY_CONFIG ? 1 : 0);

  // Guard against hydration mismatch: the server renders with no user data while the
  // client immediately begins fetching (isLoading differs between SSR and first client
  // render). Gating on `user === undefined` is consistent across both environments.
  if (REQUIRE_API_KEY_CONFIG && user === undefined) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </main>
    );
  }

  return (
    <>
      {/* The steps sit in the row the projects list uses for its count and
          search, so the wizard keeps the same furniture as the list it came from. */}
      <div className="flex h-10 shrink-0 items-center justify-center border-b px-4">
        <StepIndicator currentStep={currentIndicatorStep} steps={steps} />
      </div>

      {isOnApiKeyStep && <StepApiKeyConfig />}
      {!isOnApiKeyStep && wizard.currentStep === 1 && <StepUpload onComplete={wizard.nextStep} />}
      {!isOnApiKeyStep && wizard.currentStep === 2 && <StepAnalyses />}
    </>
  );
}

/**
 * The new-project wizard, drawn with the same chrome as the projects list: the
 * application row, a toolbar row, and the step below filling the rest of the
 * viewport. Each step scrolls its own body and keeps its actions in a footer.
 */
export default function New() {
  return (
    <div className="bg-background text-foreground flex h-dvh flex-col">
      <AppBar />
      <WizardProvider>
        <WizardContent />
      </WizardProvider>
    </div>
  );
}
