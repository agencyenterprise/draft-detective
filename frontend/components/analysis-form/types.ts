import { WorkflowRunType, AnalysisFormConfig } from '@/lib/generated-api';

export interface AnalysisFormData {
  mainDocument: File;
  supportingDocuments: File[];
  config: AnalysisFormConfig;
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
