'use client';

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react';
import { WorkflowRunType } from '@/lib/generated-api';
import { hasSupportingDocumentsRequirement } from '@/components/workflows/utils';

export type PreflightStatus = 'idle' | 'pending' | 'valid' | 'invalid';
export type WizardStep = 1 | 2;

interface WizardState {
  currentStep: WizardStep;
  mainDocument: File | null;
  projectId: string | null;
  preflightStatus: { format: PreflightStatus };
  selectedWorkflowTypes: WorkflowRunType[];
  needsReferencesStep: boolean;
}

interface WizardContextValue extends WizardState {
  setMainDocument: (file: File | null) => void;
  setProjectId: (id: string) => void;
  setPreflightStatus: (status: Partial<WizardState['preflightStatus']>) => void;
  setSelectedWorkflowTypes: (types: WorkflowRunType[]) => void;
  nextStep: () => void;
  goToStep: (step: WizardStep) => void;
}

const WizardContext = createContext<WizardContextValue | null>(null);

interface WizardProviderProps {
  children: ReactNode;
  initialProjectId?: string | null;
  initialStep?: WizardStep;
}

export function WizardProvider({ children, initialProjectId = null, initialStep }: WizardProviderProps) {
  // If initialStep is provided, use it. Otherwise, default to step 2 if we have a projectId, else step 1
  const [currentStep, setCurrentStep] = useState<WizardStep>(initialStep ?? (initialProjectId ? 2 : 1));
  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<string | null>(initialProjectId);
  const [preflightStatus, setPreflightStatusState] = useState<WizardState['preflightStatus']>({
    format: initialProjectId ? 'valid' : 'idle',
  });
  const [selectedWorkflowTypes, setSelectedWorkflowTypes] = useState<WorkflowRunType[]>([]);

  const needsReferencesStep = useMemo(
    () => hasSupportingDocumentsRequirement(selectedWorkflowTypes),
    [selectedWorkflowTypes],
  );

  const setPreflightStatus = useCallback((status: Partial<WizardState['preflightStatus']>) => {
    setPreflightStatusState((prev) => ({ ...prev, ...status }));
  }, []);

  const nextStep = useCallback(() => {
    setCurrentStep((prev) => (prev < 2 ? ((prev + 1) as WizardStep) : prev));
  }, []);

  const goToStep = useCallback((step: WizardStep) => {
    setCurrentStep(step);
  }, []);

  const value = useMemo(
    () => ({
      currentStep,
      mainDocument,
      projectId,
      preflightStatus,
      selectedWorkflowTypes,
      needsReferencesStep,
      setMainDocument,
      setProjectId,
      setPreflightStatus,
      setSelectedWorkflowTypes,
      nextStep,
      goToStep,
    }),
    [
      currentStep,
      mainDocument,
      projectId,
      preflightStatus,
      selectedWorkflowTypes,
      needsReferencesStep,
      setPreflightStatus,
      nextStep,
      goToStep,
    ],
  );

  return <WizardContext.Provider value={value}>{children}</WizardContext.Provider>;
}

export function useWizard() {
  const context = useContext(WizardContext);
  if (!context) throw new Error('useWizard must be used within WizardProvider');
  return context;
}
