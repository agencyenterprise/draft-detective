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
import { CheckboxWithDescription } from '../ui/checkbox-with-description';

interface WorkflowConfigDialogProps {
  isOpen: boolean;
  webSearchConsent?: boolean;
  publicationDate?: boolean;
  onConfirm: (values: WorkflowConfigFormValues) => void;
  onCancel: () => void;
}

export interface WorkflowConfigFormValues {
  openaiApiKey: string;
  webSearchConsent: boolean;
  publicationDate: string;
}

export function WorkflowConfigDialog({
  isOpen,
  webSearchConsent = false,
  publicationDate = false,
  onConfirm,
  onCancel,
}: WorkflowConfigDialogProps) {
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  const form = useForm({
    defaultValues: {
      openaiApiKey: openaiApiKey,
      webSearchConsent: false,
      publicationDate: '',
    } as WorkflowConfigFormValues,
    validators: {
      onChange: ({ value }) => {
        const errors: GlobalFormValidationError<WorkflowConfigFormValues> = { fields: {}, form: undefined };
        if (!hideOpenaiApiKeyInput && (!value.openaiApiKey || value.openaiApiKey.trim() === '')) {
          errors.fields.openaiApiKey = 'OpenAI API Key is required';
        }
        if (webSearchConsent && !value.webSearchConsent) {
          errors.fields.webSearchConsent = 'Web search consent is required';
        }
        if (publicationDate && (!value.publicationDate || value.publicationDate.trim() === '')) {
          errors.fields.publicationDate = 'Document publication date is required';
        }
        return errors;
      },
    },
    onSubmit: ({ value }) => {
      onConfirm(value);
    },
  });

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

          {publicationDate && (
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
                  {!field.state.meta.isValid && (
                    <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                  )}
                </div>
              )}
            </form.Field>
          )}

          {webSearchConsent && (
            <form.Field name="webSearchConsent">
              {(field) => (
                <div>
                  <div className="bg-yellow-50 border border-yellow-400 rounded-lg">
                    <CheckboxWithDescription
                      id="web-search-consent"
                      checked={field.state.value}
                      onCheckedChange={(checked) => field.handleChange(checked === true)}
                      label="I consent to perform web search using parts or the whole document for this workflow"
                      description={`Web search is required to perform this workflow. Parts of the document will be used to perform web search, so we don't recommend using confidential information. Don't proceed if you don't consent to perform web search.`}
                    />
                  </div>
                  {!field.state.meta.isValid && (
                    <p className="text-sm text-destructive mt-1 pl-6">{field.state.meta.errors.join(', ')}</p>
                  )}
                </div>
              )}
            </form.Field>
          )}
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
