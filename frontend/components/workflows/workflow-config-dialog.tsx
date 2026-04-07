import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { GlobalFormValidationError, useForm } from '@tanstack/react-form';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { WorkflowRunType } from '@/lib/generated-api';
import { KeyRound } from 'lucide-react';
import { useEffect } from 'react';
import { WorkflowTypeSelector } from './workflow-type-selector';
import { WebSearchConsentCheckbox } from './web-search-consent-checkbox';
import { hasWebSearchRequirement, hasPublicationDateRequirement } from './utils';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';

interface WorkflowConfigDialogProps {
  isOpen: boolean;
  type?: WorkflowRunType;
  projectId: string;
  onConfirm: (values: WorkflowConfigFormValues) => void;
  onCancel: () => void;
}

export interface WorkflowConfigFormValues {
  webSearchConsent: boolean;
  publicationDate: string;
  workflowTypes: WorkflowRunType[];
}

export function WorkflowConfigDialog({ isOpen, type, projectId, onConfirm, onCancel }: WorkflowConfigDialogProps) {
  const [storedWebSearchConsent] = useWebSearchConsent(projectId);
  const { showExperimentalFeatures } = useExperimentalFeatures();
  const { data: user } = useUserMe();

  const { workflowTypes, categories } = useWorkflowTypes();

  const needsPublicationDate = type ? hasPublicationDateRequirement([type]) : false;

  // WHY: Default to today's date so when experimental features are disabled,
  // the form still submits a valid date without showing the field to the user.
  const today = new Date().toISOString().split('T')[0];

  // WHY: Only show publication date field when the user has opted into experimental features.
  // When disabled, we simplify the UI by hiding this field and using today's date.
  const showPublicationDateField = showExperimentalFeatures && needsPublicationDate;

  const form = useForm({
    defaultValues: {
      webSearchConsent: storedWebSearchConsent,
      publicationDate: today,
      workflowTypes: type ? [type] : [],
    } as WorkflowConfigFormValues,
    validators: {
      onChange: ({ value }) => {
        const errors: GlobalFormValidationError<WorkflowConfigFormValues> = { fields: {}, form: undefined };
        if (hasWebSearchRequirement(value.workflowTypes, workflowTypes) && !value.webSearchConsent) {
          errors.fields.webSearchConsent = 'Web search consent is required';
        }
        // Only require publication date input when the field is shown
        if (showPublicationDateField && (!value.publicationDate || value.publicationDate.trim() === '')) {
          errors.fields.publicationDate = 'Document publication date is required';
        }
        if (value.workflowTypes.length === 0) {
          errors.fields.workflowTypes = 'At least one workflow type must be selected';
        }
        return errors;
      },
    },
    onSubmit: ({ value }) => {
      onConfirm(value);
    },
  });

  useEffect(() => {
    if (isOpen) {
      // Reset the form every time the dialog is opened
      form.reset();
    }
  }, [form, isOpen]);

  return (
    <Dialog open={isOpen} onOpenChange={onCancel}>
      <DialogContent className="min-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Start Workflow</DialogTitle>
          <DialogDescription>Please select the workflow configuration to start.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {showPublicationDateField && (
            <form.Field name="publicationDate">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="publication-date" required>
                    Document Publication Date
                  </Label>
                  <Input
                    id="publication-date"
                    type="date"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    error={!field.state.meta.isValid}
                    required={true}
                  />
                  <p className="text-sm text-muted-foreground">
                    The publication date of the document. For unpublished documents, use the date of the last update or
                    the current date.
                  </p>
                  {!field.state.meta.isValid && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                  )}
                </div>
              )}
            </form.Field>
          )}

          <form.Field name="workflowTypes">
            {(field) => {
              const preselectedIsExperimental = type
                ? workflowTypes.find((wt) => wt.type === type)?.is_experimental
                : false;

              return (
                <WorkflowTypeSelector
                  workflowTypes={workflowTypes.filter((wt) => (type ? wt.type === type : !wt.is_internal))}
                  categories={categories}
                  selectedTypes={field.state.value}
                  onSelectionChange={field.handleChange}
                  disabledTypes={type ? [type] : undefined}
                  defaultShowExperimental={preselectedIsExperimental}
                  error={
                    !field.state.meta.isValid && field.state.meta.errors.length > 0
                      ? field.state.meta.errors.join(', ')
                      : undefined
                  }
                />
              );
            }}
          </form.Field>

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
                      error={!field.state.meta.isValid ? field.state.meta.errors.join(', ') : undefined}
                    />
                  )}
                </form.Field>
              );
            }}
          </form.Field>
        </div>

        {user?.has_openai_api_key && (
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <KeyRound className="h-3.5 w-3.5 shrink-0" />
            Your saved OpenAI API key will be used for this analysis.
          </p>
        )}

        <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
          {([canSubmit, isSubmitting]) => (
            <DialogFooter>
              <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button onClick={() => form.handleSubmit()} disabled={!canSubmit || isSubmitting}>
                {isSubmitting ? 'Starting...' : 'Start Workflow'}
              </Button>
            </DialogFooter>
          )}
        </form.Subscribe>
      </DialogContent>
    </Dialog>
  );
}
