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
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { GlobalFormValidationError, useForm } from '@tanstack/react-form';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { WorkflowRunType } from '@/lib/generated-api';
import { useEffect } from 'react';
import { WorkflowTypeSelector } from './workflow-type-selector';
import { WebSearchConsentCheckbox } from './web-search-consent-checkbox';
import { hasWebSearchRequirement } from './utils';

interface WorkflowConfigDialogProps {
  isOpen: boolean;
  type?: WorkflowRunType;
  onConfirm: (values: WorkflowConfigFormValues) => void;
  onCancel: () => void;
}

export interface WorkflowConfigFormValues {
  openaiApiKey: string;
  webSearchConsent: boolean;
  workflowTypes: WorkflowRunType[];
}

export function WorkflowConfigDialog({ isOpen, type, onConfirm, onCancel }: WorkflowConfigDialogProps) {
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  const { data: workflowTypes, isPending: isWorkflowTypesPending } = useWorkflowTypes();

  const form = useForm({
    defaultValues: {
      openaiApiKey: openaiApiKey,
      webSearchConsent: false,
      workflowTypes: type ? [type] : [],
    } as WorkflowConfigFormValues,
    validators: {
      onChange: ({ value }) => {
        const errors: GlobalFormValidationError<WorkflowConfigFormValues> = { fields: {}, form: undefined };
        if (!hideOpenaiApiKeyInput && (!value.openaiApiKey || value.openaiApiKey.trim() === '')) {
          errors.fields.openaiApiKey = 'OpenAI API Key is required';
        }
        if (hasWebSearchRequirement(value.workflowTypes, workflowTypes) && !value.webSearchConsent) {
          errors.fields.webSearchConsent = 'Web search consent is required';
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

  const filteredWorkflowTypes =
    workflowTypes?.filter(
      (workflowType) => workflowType.can_be_triggered_by_user && (type ? workflowType.type === type : true),
    ) ?? [];

  const preselectedIsExperimental = type
    ? (workflowTypes?.find((wt) => wt.type === type)?.is_experimental ?? false)
    : false;

  return (
    <Dialog open={isOpen} onOpenChange={onCancel}>
      <DialogContent className="min-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Start Workflow</DialogTitle>
          <DialogDescription>Please select the workflow configuration to start.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!hideOpenaiApiKeyInput && (
            <form.Field
              name="openaiApiKey"
              listeners={{
                onChange: ({ value }) => setOpenaiApiKey(value),
              }}
            >
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="openai-key" required>
                    OpenAI API Key
                  </Label>
                  <Input
                    id="openai-key"
                    type="text"
                    placeholder="sk-..."
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    error={!field.state.meta.isValid}
                    required={true}
                  />
                  <p className="text-sm text-muted-foreground">
                    Your OpenAI API key will be used only for this workflow and will not be stored in our database.
                  </p>
                  {!field.state.meta.isValid && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                  )}
                </div>
              )}
            </form.Field>
          )}

          <form.Field name="workflowTypes">
            {(field) => (
              <WorkflowTypeSelector
                isPending={isWorkflowTypesPending}
                workflowTypes={filteredWorkflowTypes}
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
            )}
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
