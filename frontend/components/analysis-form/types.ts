import { AnalysisConfig } from '../wizard/types';

export interface AnalysisFormData {
  mainDocument: File;
  supportingDocuments: File[];
  config: AnalysisConfig;
}

export interface AnalysisFormValues {
  reviewType: string;
  domain: string;
  targetAudience: string;
  runSuggestCitations: boolean;
  runReferenceValidation: boolean;
  webSearchConsent: boolean;
  openaiApiKey: string;
  mainDocument: File | null;
  supportingDocuments: File[];
}
