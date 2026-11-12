'use client';

import { AppBar } from '@/components/results/app-bar';
import { WizardProvider, useWizard } from '@/components/analysis-wizard/wizard-context';
import { StepIndicator } from '@/components/analysis-wizard/step-indicator';
import { StepUpload } from '@/components/analysis-wizard/step-upload';
import { StepAnalyses } from '@/components/analysis-wizard/step-analyses';
import { StepApiKeyConfig } from '@/components/analysis-wizard/step-api-key-config';
import { wizardGate } from '@/components/analysis-wizard/wizard-gate';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';

const REQUIRE_API_KEY_CONFIG = process.env.NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG === 'true';

function WizardContent() {
  const wizard = useWizard();
  const { data: user, isError, isFetching, refetch } = useUserMe();
  const gate = wizardGate({
    requireApiKeyConfig: REQUIRE_API_KEY_CONFIG,
    user,
    userLookupFailed: isError,
    currentStep: wizard.currentStep,
  });

  if (gate.kind === 'lookup-failed') return <UserLookupError retrying={isFetching} onRetry={() => refetch()} />;
  if (gate.kind === 'loading') {
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
        <StepIndicator currentStep={gate.currentIndicatorStep} steps={gate.steps} />
      </div>

      {gate.kind === 'api-key' && <StepApiKeyConfig />}
      {gate.kind === 'wizard' && wizard.currentStep === 1 && <StepUpload onComplete={wizard.nextStep} />}
      {gate.kind === 'wizard' && wizard.currentStep === 2 && <StepAnalyses />}
    </>
  );
}

function UserLookupError({ retrying, onRetry }: { retrying: boolean; onRetry: () => void }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
      <p className="text-sm text-muted-foreground">We couldn&apos;t load your account details.</p>
      <Button variant="outline" onClick={onRetry} disabled={retrying}>
        {retrying && <Loader2 className="size-4 animate-spin" />}
        Try again
      </Button>
    </main>
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
