'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

export type PreflightStatus = 'idle' | 'pending' | 'valid' | 'invalid';

interface WizardState {
  currentStep: 1 | 2;
  mainDocument: File | null;
  openaiApiKey: string;
  projectId: string | null;
  preflightStatus: { apiKey: PreflightStatus; format: PreflightStatus };
}

interface WizardContextValue extends WizardState {
  setMainDocument: (file: File | null) => void;
  setApiKey: (key: string) => void;
  setProjectId: (id: string) => void;
  setPreflightStatus: (status: Partial<WizardState['preflightStatus']>) => void;
  nextStep: () => void;
}

const WizardContext = createContext<WizardContextValue | null>(null);

interface WizardProviderProps {
  children: ReactNode;
  initialApiKey?: string;
  initialProjectId?: string | null;
}

export function WizardProvider({ children, initialApiKey = '', initialProjectId = null }: WizardProviderProps) {
  // Start at step 2 if we have an initial project (resuming wizard)
  const [currentStep, setCurrentStep] = useState<1 | 2>(initialProjectId ? 2 : 1);
  const [mainDocument, setMainDocument] = useState<File | null>(null);
  const [openaiApiKey, setApiKey] = useState(initialApiKey);
  const [projectId, setProjectId] = useState<string | null>(initialProjectId);
  const [preflightStatus, setPreflightStatusState] = useState<WizardState['preflightStatus']>({
    apiKey: initialProjectId ? 'valid' : 'idle', // Skip validation if resuming
    format: initialProjectId ? 'valid' : 'idle',
  });

  const setPreflightStatus = (status: Partial<WizardState['preflightStatus']>) => {
    setPreflightStatusState((prev) => ({ ...prev, ...status }));
  };

  return (
    <WizardContext.Provider
      value={{
        currentStep,
        mainDocument,
        openaiApiKey,
        projectId,
        preflightStatus,
        setMainDocument,
        setApiKey,
        setProjectId,
        setPreflightStatus,
        nextStep: () => setCurrentStep(2),
      }}
    >
      {children}
    </WizardContext.Provider>
  );
}

export function useWizard() {
  const context = useContext(WizardContext);
  if (!context) throw new Error('useWizard must be used within WizardProvider');
  return context;
}
