'use client';

import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useForm } from '@tanstack/react-form';
import { AlertCircle, ExternalLink, Loader2, Play } from 'lucide-react';
import Link from 'next/link';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { WorkflowTypeSelector } from '../workflows/workflow-type-selector';
import { WebSearchConsentCheckbox } from '../workflows/web-search-consent-checkbox';
import {
  hasWebSearchRequirement,
  hasPublicationDateRequirement,
  hasSupportingDocumentsRequirement,
} from '../workflows/utils';
import { AnalysisFormData, AnalysisFormValues } from './types';
import { UploadSection } from './upload-section';
import { validateAnalysisForm } from './validation';

export interface AnalysisFormProps {
  onSubmit: (data: AnalysisFormData) => void;
  isPending?: boolean;
  error?: string;
}

export function AnalysisForm({ onSubmit, isPending = false, error }: AnalysisFormProps) {
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';
  const { showExperimentalFeatures } = useExperimentalFeatures();
  const { data: workflowTypes } = useWorkflowTypes();

  // Get today's date in YYYY-MM-DD format for the date input
  const today = new Date().toISOString().split('T')[0];

  const form = useForm({
    defaultValues: {
      domain: '',
      targetAudience: '',
      webSearchConsent: false,
      publicationDate: today,
      openaiApiKey: openaiApiKey,
      mainDocument: null,
      supportingDocuments: [],
      workflowTypes: [],
    } as AnalysisFormValues,
    validators: {
      onChange: ({ value }) =>
        validateAnalysisForm(value, hideOpenaiApiKeyInput, workflowTypes, showExperimentalFeatures),
    },
    onSubmit: ({ value }) => {
      onSubmit({
        mainDocument: value.mainDocument!,
        supportingDocuments: value.supportingDocuments,
        config: {
          domain: value.domain,
          target_audience: value.targetAudience,
          publication_date: value.publicationDate,
          openai_api_key: value.openaiApiKey,
          workflow_types: value.workflowTypes,
        },
      });
    },
  });

  const removeFile = (type: 'main' | 'supporting', index?: number) => {
    if (type === 'main') {
      form.setFieldValue('mainDocument', null);
    } else if (typeof index === 'number') {
      const currentFiles = form.getFieldValue('supportingDocuments');
      const newFiles = currentFiles.filter((_: File, i: number) => i !== index);
      form.setFieldValue('supportingDocuments', newFiles);
    }
  };

  return (
    <form
      className="space-y-8"
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-medium text-destructive">Failed to start analysis</p>
            <p className="text-sm text-destructive/90 whitespace-pre-line">{error}</p>
          </div>
        </div>
      )}

      {/* Main Document Upload */}
      <form.Field name="mainDocument">
        {(field) => (
          <div className="space-y-2">
            <UploadSection
              title="Main Document"
              description="Primary document for analysis. Word documents are preferred (less LLM conversion errors) but PDFs are also supported."
              required={true}
              onFilesChange={(files) => field.handleChange(files[0] || null)}
              multiple={false}
              files={field.state.value ? [field.state.value] : []}
              fileType="main"
              onRemoveFile={() => removeFile('main')}
            />
            {!field.state.meta.isValid && field.state.meta.errors.length > 0 && (
              <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
            )}
          </div>
        )}
      </form.Field>

      {/* Workflow Selection Section */}
      <form.Field
        name="workflowTypes"
        listeners={{
          onChange: ({ value }) => {
            // Clear supporting documents when no workflow requires them
            if (!hasSupportingDocumentsRequirement(value)) {
              form.setFieldValue('supportingDocuments', []);
            }
          },
        }}
      >
        {(field) => (
          <WorkflowTypeSelector
            workflowTypes={workflowTypes?.filter((wt) => wt.can_be_triggered_by_user && !wt.is_internal)}
            selectedTypes={field.state.value}
            onSelectionChange={field.handleChange}
            disabled={isPending}
            headerDescription="Select which types of analyses to perform"
            error={
              !field.state.meta.isValid && field.state.meta.errors.length > 0
                ? field.state.meta.errors.join(', ')
                : undefined
            }
          />
        )}
      </form.Field>

      {/* Web Search Consent - only shown when relevant workflows are selected */}
      <form.Field name="workflowTypes">
        {(workflowTypesField) => {
          const selectedTypes = workflowTypesField.state.value;
          const needsWebSearch = hasWebSearchRequirement(selectedTypes, workflowTypes);

          if (!needsWebSearch) {
            return null;
          }

          return (
            <form.Field name="webSearchConsent">
              {(field) => (
                <WebSearchConsentCheckbox
                  checked={field.state.value}
                  onCheckedChange={field.handleChange}
                  disabled={isPending}
                  error={!field.state.meta.isValid ? field.state.meta.errors.join(', ') : undefined}
                />
              )}
            </form.Field>
          );
        }}
      </form.Field>

      {/* Supporting Documents Section - only shown when relevant workflows are selected */}
      <form.Field name="workflowTypes">
        {(workflowTypesField) => {
          const selectedTypes = workflowTypesField.state.value;
          const needsSupportingDocuments = hasSupportingDocumentsRequirement(selectedTypes);

          if (!needsSupportingDocuments) {
            return null;
          }

          return (
            <form.Field name="supportingDocuments">
              {(field) => (
                <div className="space-y-2">
                  <UploadSection
                    title="Supporting Documents"
                    description="Reference documents cited in your main document's reference section (e.g., PDFs of cited papers or news websites). These enable validation of claims against their cited sources."
                    required={true}
                    onFilesChange={(files) => field.handleChange(files)}
                    multiple={true}
                    files={field.state.value}
                    fileType="supporting"
                    onRemoveFile={(index) => removeFile('supporting', index)}
                  />
                  <p className="text-sm text-muted-foreground">
                    You can automatically download references using the{' '}
                    <Link
                      href="/tools/reference-downloader"
                      target="_blank"
                      className="text-primary hover:underline inline-flex items-center gap-1"
                    >
                      Reference Downloader tool
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  </p>
                  {!field.state.meta.isValid && field.state.meta.errors.length > 0 && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                  )}
                </div>
              )}
            </form.Field>
          );
        }}
      </form.Field>

      {/* API Configuration Section */}
      {!hideOpenaiApiKeyInput && (
        <div className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">API Configuration</h2>
            <p className="text-sm text-muted-foreground">Configure API settings for analysis execution</p>
          </div>
          <form.Field
            name="openaiApiKey"
            listeners={{
              onChange: ({ value }) => setOpenaiApiKey(value),
            }}
          >
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="openai-api-key">
                  OpenAI API Key <span className="text-destructive ml-1">*</span>
                </Label>
                <Input
                  id="openai-api-key"
                  type="text"
                  placeholder="sk-..."
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  className={field.state.meta.errors.length > 0 ? 'border-destructive' : ''}
                  disabled={isPending}
                  required={true}
                />
                <p className="text-sm text-muted-foreground">
                  Your OpenAI API key will be used only for this analysis session and will not be stored in our
                  database.
                </p>
                {!field.state.meta.isValid && (
                  <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                )}
              </div>
            )}
          </form.Field>
        </div>
      )}

      {/* Additional Context Section */}
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold">Additional Context</h2>
          <p className="text-sm text-muted-foreground">Provide context for more accurate analysis</p>
        </div>
        <div className="space-y-4">
          {/*
           * WHY: Publication date is only relevant for experimental workflows (Literature Review, Live Reports)
           * that need to filter references by date. When experimental features are disabled, we hide this field
           * to simplify the UI, and the form defaults to today's date internally. This allows the backend to
           * still receive a valid date without requiring user input for non-experimental workflows.
           */}
          <form.Field name="workflowTypes">
            {(workflowTypesField) => {
              const selectedTypes = workflowTypesField.state.value;
              const needsPublicationDate = hasPublicationDateRequirement(selectedTypes);

              // Only show publication date field when the user has opted into experimental features and it's required
              if (!showExperimentalFeatures || !needsPublicationDate) {
                return null;
              }

              return (
                <form.Field name="publicationDate">
                  {(field) => (
                    <div className="space-y-2">
                      <Label htmlFor="publication-date">
                        Document Publication Date <span className="text-destructive ml-1">*</span>
                      </Label>
                      <Input
                        id="publication-date"
                        type="date"
                        value={field.state.value}
                        onChange={(e) => field.handleChange(e.target.value)}
                        className={field.state.meta.errors.length > 0 ? 'border-destructive' : ''}
                        disabled={isPending}
                        required={true}
                      />
                      <p className="text-sm text-muted-foreground">
                        The publication date of the document. For unpublished documents, use the date of the last update
                        or the current date.
                      </p>
                      {!field.state.meta.isValid && (
                        <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                      )}
                    </div>
                  )}
                </form.Field>
              );
            }}
          </form.Field>
          <form.Field name="domain">
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="domain">
                  Domain <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
                </Label>
                <Input
                  id="domain"
                  placeholder="e.g., Policy research, Healthcare, Technology, Finance..."
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  disabled={isPending}
                />
                <p className="text-sm text-muted-foreground">
                  The subject area or field of expertise to contextualize the analysis. This helps tailor the evaluation
                  to domain-specific standards and terminology.
                </p>
              </div>
            )}
          </form.Field>
          <form.Field name="targetAudience">
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="target-audience">
                  Target Audience <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
                </Label>
                <Input
                  id="target-audience"
                  placeholder="e.g., Policy makers, General public, Experts, Students..."
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  disabled={isPending}
                />
                <p className="text-sm text-muted-foreground">
                  The intended readers of the document. Specifying the audience helps adjust the analysis to match
                  appropriate complexity level and expectations.
                </p>
              </div>
            )}
          </form.Field>
        </div>
      </div>

      <div className="flex justify-center">
        <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
          {([canSubmit]) => (
            <Button type="submit" disabled={!canSubmit || isPending} size="lg" className="min-w-48 gap-2 font-semibold">
              {isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  {error ? 'Retry Analysis' : 'Start Analysis'}
                </>
              )}
            </Button>
          )}
        </form.Subscribe>
      </div>
    </form>
  );
}
