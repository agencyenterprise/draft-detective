import { MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB } from '@/lib/constants';
import { FormValidationError, GlobalFormValidationError } from '@tanstack/react-form';
import { AnalysisFormValues } from './types';

export function validateAnalysisForm(
  value: AnalysisFormValues,
  hideOpenaiApiKeyInput: boolean,
): FormValidationError<AnalysisFormValues> {
  const errors: GlobalFormValidationError<AnalysisFormValues> = { fields: {}, form: undefined };

  if (!value.reviewType) {
    errors.fields.reviewType = 'Review type is required';
  }

  if (!value.mainDocument) {
    errors.fields.mainDocument = 'Main document is required';
  } else {
    // Validate main document file size
    if (value.mainDocument.size > MAX_FILE_SIZE_BYTES) {
      errors.fields.mainDocument = `File exceeds ${MAX_FILE_SIZE_MB}MB limit (${(value.mainDocument.size / 1024 / 1024).toFixed(1)}MB)`;
    }
  }

  // Validate supporting documents file sizes
  const oversizedSupporting = value.supportingDocuments.filter((f) => f.size > MAX_FILE_SIZE_BYTES);
  if (oversizedSupporting.length > 0) {
    const errorMessages = oversizedSupporting.map(
      (f) => `${f.name}: File exceeds ${MAX_FILE_SIZE_MB}MB limit (${(f.size / 1024 / 1024).toFixed(1)}MB)`,
    );
    errors.fields.supportingDocuments = errorMessages.join(', ');
  }

  if (!hideOpenaiApiKeyInput && (!value.openaiApiKey || value.openaiApiKey.trim() === '')) {
    errors.fields.openaiApiKey = 'OpenAI API Key is required';
  }

  if (value.runReferenceValidation) {
    if (!value.webSearchConsent) {
      errors.fields.webSearchConsent = 'Web search consent is required when using reference validation';
    }
  }

  return errors;
}
