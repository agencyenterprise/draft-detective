'use client';

import { useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { WizardProvider, useWizard, WizardStep } from '@/components/analysis-wizard/wizard-context';
import { StepIndicator } from '@/components/analysis-wizard/step-indicator';
import { StepUpload } from '@/components/analysis-wizard/step-upload';
import { StepAnalyses } from '@/components/analysis-wizard/step-analyses';
import { StepReferences } from '@/components/analysis-wizard/step-references';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useSearchParams } from 'next/navigation';

function WizardContent() {
  const wizard = useWizard();

  const steps = useMemo(() => {
    const baseSteps = [
      { label: 'Your Document', completed: wizard.currentStep > 1 },
      { label: 'Choose Analyses', completed: wizard.currentStep > 2 },
    ];
    if (wizard.needsReferencesStep) {
      baseSteps.push({ label: 'Add Sources', completed: false });
    }
    return baseSteps;
  }, [wizard.currentStep, wizard.needsReferencesStep]);

  const cardWidthClass = wizard.currentStep === 3 ? 'max-w-8xl' : 'max-w-2xl';

  return (
    <div className="space-y-8">
      <StepIndicator currentStep={wizard.currentStep} steps={steps} className="mb-8" />

      <Card className={`${cardWidthClass} mx-auto transition-all duration-300`}>
        <CardContent className="py-8">
          {wizard.currentStep === 1 && <StepUpload onComplete={wizard.nextStep} />}
          {wizard.currentStep === 2 && <StepAnalyses />}
          {wizard.currentStep === 3 && <StepReferences />}
        </CardContent>
      </Card>
    </div>
  );
}

export default function New() {
  const searchParams = useSearchParams();
  const projectIdFromUrl = searchParams.get('projectId');
  const stepFromUrl = searchParams.get('step');
  const [storedApiKey] = useSessionStorage<string>('openai-api-key', '');

  const initialStep: WizardStep | undefined =
    stepFromUrl && ['1', '2', '3'].includes(stepFromUrl) ? (parseInt(stepFromUrl, 10) as WizardStep) : undefined;

  return (
    <WizardProvider initialApiKey={storedApiKey} initialProjectId={projectIdFromUrl} initialStep={initialStep}>
      <WizardContent />
    </WizardProvider>
  );
}
