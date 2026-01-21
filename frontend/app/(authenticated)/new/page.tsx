'use client';

import { Card, CardContent } from '@/components/ui/card';
import { WizardProvider, useWizard } from '@/components/analysis-wizard/wizard-context';
import { StepIndicator } from '@/components/analysis-wizard/step-indicator';
import { StepUpload } from '@/components/analysis-wizard/step-upload';
import { StepAnalyses } from '@/components/analysis-wizard/step-analyses';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useSearchParams } from 'next/navigation';

function WizardContent() {
  const wizard = useWizard();

  const steps = [
    { label: 'Upload & Key', completed: wizard.currentStep > 1 },
    { label: 'Select Analyses', completed: false },
    { label: 'Review', completed: false },
  ];

  return (
    <div className="space-y-8">
      <StepIndicator currentStep={wizard.currentStep} steps={steps} className="mb-8" />

      <Card className="max-w-2xl mx-auto">
        <CardContent className="py-8">
          {wizard.currentStep === 1 && <StepUpload onComplete={wizard.nextStep} />}
          {wizard.currentStep === 2 && <StepAnalyses />}
        </CardContent>
      </Card>
    </div>
  );
}

export default function New() {
  const searchParams = useSearchParams();
  const projectIdFromUrl = searchParams.get('projectId');
  const [storedApiKey] = useSessionStorage<string>('openai-api-key', '');

  return (
    <WizardProvider initialApiKey={storedApiKey} initialProjectId={projectIdFromUrl}>
      <WizardContent />
    </WizardProvider>
  );
}
