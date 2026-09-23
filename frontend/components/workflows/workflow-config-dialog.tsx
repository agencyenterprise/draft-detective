import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { HelpLink } from '@/components/help/help-link';
import { HelpTopicId } from '@/components/help/topics';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { GlobalFormValidationError, useForm } from '@tanstack/react-form';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useUserMe } from '@/lib/hooks/use-user-me';
import { WorkflowRunType } from '@/lib/generated-api';
import { CircleAlert, KeyRound } from 'lucide-react';
import { useEffect } from 'react';
import { WorkflowTypeSelector } from './workflow-type-selector';
import { WebSearchConsentCheckbox } from './web-search-consent-checkbox';
import { hasPublicationDateRequirement, hasWebSearchRequirement, startBlocker, StartBlocker } from './utils';
import { useWebSearchConsent } from '@/lib/hooks/use-web-search-consent';

interface WorkflowConfigDialogProps {
  isOpen: boolean;
  type?: WorkflowRunType;
  projectId: string;
  onConfirm: (values: WorkflowConfigFormValues) => void;
  onCancel: () => void;
  /**
   * Names the action in the caller's own words. Without these the dialog talks
   * about running an assessment, which is wrong for the internal workflows —
   * nobody asked to "run Reference Downloader", they asked to fetch a source.
   */
  title?: string;
  description?: string;
  submitLabel?: string;
  /** The help topic the dialog's link opens. Follows what the dialog is for. */
  helpTopic?: HelpTopicId;
}

/** The footer's message for each reason the form cannot be submitted. */
const BLOCKER_MESSAGES: Record<StartBlocker, string> = {
  'metadata-pending': 'Loading the available assessments…',
  'metadata-failed': 'The available assessments could not be loaded. Close this dialog and try again.',
  'none-selected': 'Select at least one assessment.',
  'consent-missing': 'Consent to web search to run the selected assessments.',
};

/** The run button says how many it will start, so the count is confirmed where it matters. */
function runLabel(selectedCount: number): string {
  if (selectedCount === 0) return 'Run assessments';
  return selectedCount === 1 ? 'Run 1 assessment' : `Run ${selectedCount} assessments`;
}

export interface WorkflowConfigFormValues {
  webSearchConsent: boolean;
  publicationDate: string;
  workflowTypes: WorkflowRunType[];
}

export function WorkflowConfigDialog({
  isOpen,
  type,
  projectId,
  onConfirm,
  onCancel,
  title,
  description,
  submitLabel,
  helpTopic = 'assessments',
}: WorkflowConfigDialogProps) {
  const [storedWebSearchConsent] = useWebSearchConsent(projectId);
  const { showExperimentalFeatures } = useExperimentalFeatures();
  const { data: user } = useUserMe();

  const {
    workflowTypes,
    getWorkflowTypeName,
    isPending: isMetadataPending,
    isError: isMetadataFailed,
  } = useWorkflowTypes();

  // Named when the dialog is opened for one assessment; otherwise it is the
  // picker over all of them.
  const assessmentName = type ? getWorkflowTypeName(type) : null;

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
        // Only require publication date input when the field is shown
        if (showPublicationDateField && (!value.publicationDate || value.publicationDate.trim() === '')) {
          errors.fields.publicationDate = 'Document publication date is required';
        }
        // Form-level rather than on the fields: a field error is held by the
        // field's own meta, and the consent field is not mounted until a
        // web-searching assessment is picked. Reported against the field, the
        // error from a bulk "select all" had nowhere to land and the form
        // counted as valid.
        const blocker = startBlocker({
          selectedTypes: value.workflowTypes,
          workflowTypes,
          metadataPending: isMetadataPending,
          metadataFailed: isMetadataFailed,
          webSearchConsent: value.webSearchConsent,
        });
        if (blocker) errors.form = BLOCKER_MESSAGES[blocker];
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

  // The validator above runs on change, and a dialog opened for one assessment
  // starts with it selected and nothing changed. Until the metadata is in, the
  // button waits on this rather than on a validation that has not run.
  const metadataNotReady = isMetadataPending || isMetadataFailed;

  return (
    <Dialog open={isOpen} onOpenChange={onCancel}>
      {/* The list scrolls inside the dialog while the title and the run button
          stay put, so the action is never below the fold of a dozen rows. */}
      <DialogContent className="flex max-h-[90vh] flex-col gap-0 p-0 sm:max-w-4xl">
        <DialogHeader className="border-b px-6 pt-6 pb-4">
          <DialogTitle>{title ?? (assessmentName ? `Run ${assessmentName}` : 'Run assessments')}</DialogTitle>
          <DialogDescription>
            {description ??
              (assessmentName
                ? 'Confirm how this assessment should run on your document.'
                : 'Choose which assessments to run on your document.')}{' '}
            <HelpLink topic={helpTopic}>
              {helpTopic === 'assessments' ? 'How assessments work' : 'What this is for'}
            </HelpLink>
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4">
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
            {(field) => (
              <WorkflowTypeSelector
                restrictToType={type}
                projectId={projectId}
                selectedTypes={field.state.value}
                onSelectionChange={field.handleChange}
                disabledTypes={type ? [type] : undefined}
              />
            )}
          </form.Field>
        </div>

        {/* The consent sits with the run button rather than at the end of the
            list: it is what the button is waiting on, and a dozen rows above
            it would otherwise hide that it exists at all. */}
        <div className="space-y-4 border-t px-6 py-4">
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
                    <form.Subscribe selector={(state) => state.errors.length > 0}>
                      {(formInvalid) => (
                        <WebSearchConsentCheckbox
                          checked={field.state.value}
                          onCheckedChange={field.handleChange}
                          // With assessments picked, the only form-level error left is this one.
                          invalid={formInvalid && !field.state.value}
                        />
                      )}
                    </form.Subscribe>
                  )}
                </form.Field>
              );
            }}
          </form.Field>

          {/* Every message the form can raise, in one place the reader can
              see without scrolling: the list's own error used to sit under
              its last row, off screen for anyone who had not scrolled. */}
          <form.Subscribe selector={(state) => state.errors}>
            {(errors) => {
              const messages =
                errors.length > 0
                  ? errors.map(String)
                  : metadataNotReady
                    ? [BLOCKER_MESSAGES[isMetadataPending ? 'metadata-pending' : 'metadata-failed']]
                    : [];
              return messages.length > 0 ? (
                <ul className="space-y-1" aria-live="polite">
                  {messages.map((message) => (
                    <li key={message} className="flex items-center gap-1.5 text-xs text-destructive">
                      <CircleAlert aria-hidden className="size-3.5 shrink-0" />
                      {message}
                    </li>
                  ))}
                </ul>
              ) : null;
            }}
          </form.Subscribe>

          <form.Subscribe
            selector={(state) => ({
              canSubmit: state.canSubmit,
              isSubmitting: state.isSubmitting,
              selectedCount: state.values.workflowTypes.length,
            })}
          >
            {({ canSubmit, isSubmitting, selectedCount }) => (
              <DialogFooter className="sm:items-center">
                {user?.has_openai_api_key && (
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground sm:mr-auto">
                    <KeyRound className="size-3.5 shrink-0" />
                    Your saved OpenAI API key will be used for this assessment.
                  </p>
                )}
                <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button onClick={() => form.handleSubmit()} disabled={!canSubmit || isSubmitting || metadataNotReady}>
                  {isSubmitting ? 'Starting...' : (submitLabel ?? runLabel(selectedCount))}
                </Button>
              </DialogFooter>
            )}
          </form.Subscribe>
        </div>
      </DialogContent>
    </Dialog>
  );
}
