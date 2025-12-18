import { WorkflowRunType } from '@/lib/generated-api';

export interface AnalysisConfig {
  domain: string;
  targetAudience: string;
  publicationDate: string;
  openaiApiKey: string;
  workflowTypes: WorkflowRunType[];
}
