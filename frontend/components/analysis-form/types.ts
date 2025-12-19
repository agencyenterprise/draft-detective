import { WorkflowRunType } from '@/lib/generated-api';
import { AnalysisConfig } from '../wizard/types';

export interface AnalysisFormData {
  mainDocument: File;
  supportingDocuments: File[];
  config: AnalysisConfig;
}

export interface AnalysisFormValues {
  domain: string;
  targetAudience: string;
  webSearchConsent: boolean;
  publicationDate: string;
  openaiApiKey: string;
  mainDocument: File | null;
  supportingDocuments: File[];
  workflowTypes: WorkflowRunType[];
}
