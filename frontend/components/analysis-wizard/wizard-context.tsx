'use client';

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react';

export type PreflightStatus = 'idle' | 'pending' | 'valid' | 'invalid';
export type WizardStep = 1 | 2 | 3;

interface WizardState {
  currentStep: WizardStep;
  mainDocument: File | null;
  openaiApiKey: string;
  projectId: string | null;
  preflightStatus: { apiKey: PreflightStatus; format: PreflightStatus };
  needsReferencesStep: boolean;
}

interface WizardContextValue extends WizardState {
  setMainDocument: (file: File | null) => void;
  setApiKey: (key: string) => void;
  setProjectId: (id: string) => void;
  setPreflightStatus: (status: Partial<WizardState['preflightStatus']>) => void;
  setNeedsReferencesStep: (needs: boolean) => void;
  nextStep: () => void;
  goToStep: (step: WizardStep) => void;
}

const WizardContext = createContext<WizardContextValue | null>(null);

interface WizardProviderProps {
  children: ReactNode;
  initialApiKey?: string;
  initialProjectId?: string | null;
}

export function WizardProvider({ children, initialApiKey = '', initialProjectId = null }: WizardProviderProps) {
  const [currentStep, setCurrentStep] = useState<WizardStep>(initialProjectId ? 2 : 1);
  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [openaiApiKey, setApiKey] = useState(initialApiKey);
  const [projectId, setProjectId] = useState<string | null>(initialProjectId);
  const [preflightStatus, setPreflightStatusState] = useState<WizardState['preflightStatus']>({
    apiKey: initialProjectId ? 'valid' : 'idle',
    format: initialProjectId ? 'valid' : 'idle',
  });
  const [needsReferencesStep, setNeedsReferencesStep] = useState(false);

  const setPreflightStatus = useCallback((status: Partial<WizardState['preflightStatus']>) => {
    setPreflightStatusState((prev) => ({ ...prev, ...status }));
  }, []);

  const nextStep = useCallback(() => {
    setCurrentStep((prev) => (prev < 3 ? ((prev + 1) as WizardStep) : prev));
  }, []);

  const goToStep = useCallback((step: WizardStep) => {
    setCurrentStep(step);
  }, []);

  const value = useMemo(
    () => ({
      currentStep,
      mainDocument,
      openaiApiKey,
      projectId,
      preflightStatus,
      needsReferencesStep,
      setMainDocument,
      setApiKey,
      setProjectId,
      setPreflightStatus,
      setNeedsReferencesStep,
      nextStep,
      goToStep,
    }),
    [
      currentStep,
      mainDocument,
      openaiApiKey,
      projectId,
      preflightStatus,
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
