'use client';

import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useForm } from '@tanstack/react-form';
import { Loader2, Play } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { AnalysisFormData, AnalysisFormValues } from './types';
import { UploadSection } from './upload-section';
import { validateAnalysisForm } from './validation';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';
import { WorkflowRunType } from '@/lib/generated-api';
import { CheckboxWithDescription } from '../ui/checkbox-with-description';

export interface AnalysisFormProps {
  onSubmit: (data: AnalysisFormData) => void;
  isPending?: boolean;
}

export function AnalysisForm({ onSubmit, isPending = false }: AnalysisFormProps) {
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';
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
      workflowTypes: [WorkflowRunType.ClaimSubstantiation],
    } as AnalysisFormValues,
    validators: {
      onChange: ({ value }) => validateAnalysisForm(value, hideOpenaiApiKeyInput, workflowTypes),
    },
    onSubmit: ({ value }) => {
      onSubmit({
        mainDocument: value.mainDocument!,
        supportingDocuments: value.supportingDocuments,
        config: {
          domain: value.domain,
          targetAudience: value.targetAudience,
          publicationDate: value.publicationDate,
          openaiApiKey: value.openaiApiKey,
          workflowTypes: value.workflowTypes,
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
      <div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <form.Field name="mainDocument">
            {(field) => (
              <div className="space-y-2">
                <UploadSection
                  title="Main Document"
                  description="Primary document for analysis"
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

          <form.Field name="supportingDocuments">
            {(field) => (
              <div className="space-y-2">
                <UploadSection
                  title="Supporting Documents"
                  description="Documents used as references for the main document"
                  required={false}
                  onFilesChange={(files) => field.handleChange(files)}
                  multiple={true}
                  files={field.state.value}
                  fileType="supporting"
                  onRemoveFile={(index) => removeFile('supporting', index)}
                />
                {!field.state.meta.isValid && field.state.meta.errors.length > 0 && (
                  <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                )}
              </div>
            )}
          </form.Field>
        </div>
      </div>

      {/* Workflow Selection Section */}
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold">
            Analyses Type Selection <span className="text-destructive ml-1">*</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            Select which types of analyses to perform. Analyses can also be triggered later on, after the project is
            created
          </p>
          <p className="text-sm text-muted-foreground font-medium"> (Note: Claim Substantiation is always performed)</p>
        </div>
        <form.Field name="workflowTypes">
          {(field) => (
            <div className="space-y-2">
              {workflowTypes?.map((workflowType) => (
                <WorkflowTypeCheckbox
                  key={workflowType.type}
                  workflowType={workflowType}
                  checked={field.state.value.includes(workflowType.type)}
                  onCheckedChange={(checked) =>
                    field.handleChange(
                      checked
                        ? [...field.state.value, workflowType.type]
                        : field.state.value.filter((id) => id !== workflowType.type),
                    )
                  }
                  disabled={isPending || workflowType.type === WorkflowRunType.ClaimSubstantiation}
                />
              ))}
              {!workflowTypes && <p className="text-sm text-muted-foreground">Loading available workflows...</p>}
              {!field.state.meta.isValid && field.state.meta.errors.length > 0 && (
                <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
              )}
            </div>
          )}
        </form.Field>
      </div>

      <form.Field name="workflowTypes">
        {(workflowTypesField) => {
          const selectedWorkflowTypes = workflowTypesField.state.value;
          const needsWebSearch = selectedWorkflowTypes.some(
            (selectedType) => workflowTypes?.find((wt) => wt.type === selectedType)?.needs_web_search,
          );

          if (!needsWebSearch) {
            return null;
          }

          return (
            <div className="space-y-4">
              <form.Field name="webSearchConsent">
                {(field) => (
                  <div className="space-y-4">
                    <div className="bg-yellow-50 border border-yellow-400 rounded-lg">
                      <CheckboxWithDescription
                        id="web-search-consent"
                        checked={field.state.value}
                        onCheckedChange={(checked) => field.handleChange(checked === true)}
                        label="I consent to perform web search using parts or the whole document for this analysis"
                        description={`Web search is required to perform this analysis. Parts of the document will be used to perform web search, so we don't recommend using confidential information. Don't proceed if you don't consent to perform web search.`}
                        disabled={isPending}
                      />
                    </div>
                    {!field.state.meta.isValid && (
                      <p className="text-sm text-destructive pl-6">{field.state.meta.errors.join(', ')}</p>
                    )}
                  </div>
                )}
              </form.Field>
            </div>
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
                  The publication date of the document. This is used for some analyses (literature review, live reports)
                  to focus on sources published after or before this date. For unpublished documents, use the date of
                  the last update or the current date.
                </p>
                {!field.state.meta.isValid && (
                  <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                )}
              </div>
            )}
          </form.Field>
          <form.Field name="domain">
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="domain">
                  Domain <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
                </Label>
                <Input
                  id="domain"
                  placeholder="e.g., Healthcare, Technology, Finance..."
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
                  placeholder="e.g., General public, Experts, Students..."
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
                  Start Analysis
                </>
              )}
            </Button>
          )}
        </form.Subscribe>
      </div>
    </form>
  );
}
