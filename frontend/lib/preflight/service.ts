import { MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB } from '@/lib/constants';
import { checkPreflightApiPreflightPost, type PreflightResult, type ValidationIssue } from '@/lib/generated-api';

export interface PreflightContext {
  mainDocument: File | null;
  supportingDocuments: File[];
  openaiApiKey?: string;
}

export async function validatePreflight(context: PreflightContext): Promise<PreflightResult> {
  const issues: ValidationIssue[] = [];

  const allFiles = [context.mainDocument, ...context.supportingDocuments].filter(Boolean) as File[];
  for (const file of allFiles) {
    if (file.size > MAX_FILE_SIZE_BYTES) {
      issues.push({
        code: 'FILE_TOO_LARGE',
        message: `${file.name} exceeds ${MAX_FILE_SIZE_MB}MB limit`,
        severity: 'error',
      });
    }
  }

  if (issues.length > 0) {
    return { valid: false, issues };
  }

  try {
    return await checkPreflightApiPreflightPost({
      body: { openai_api_key: context.openaiApiKey },
    });
  } catch {
    return {
      valid: true,
      issues: [{ code: 'PREFLIGHT_SERVER_ERROR', message: 'Could not validate API key', severity: 'warning' }],
    };
  }
}
