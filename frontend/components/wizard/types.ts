import { ClaimSubstantiatorStateSummary } from '@/lib/generated-api';

export interface AnalysisConfig {
  domain: string;
  targetAudience: string;
  documentPublicationDate: string;
  runSuggestCitations: boolean;
  runLiveReports: boolean;
  runReferenceValidation: boolean;
  openaiApiKey: string;
}

export interface AnalysisResults {
  status: 'processing' | 'completed' | 'error';
  error?: string;
  fullResults?: ClaimSubstantiatorStateSummary;
}
