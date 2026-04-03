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
import { Callout } from '@/components/ui/callout';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { GlobalFormValidationError, useForm } from '@tanstack/react-form';
import { FeedbackVisibility, Project } from '@/lib/generated-api';
import { InfoIcon } from 'lucide-react';

interface EditProjectDialogProps {
  isOpen: boolean;
  project: Project;
  onConfirm: (values: EditProjectFormValues) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export interface EditProjectFormValues {
  title: string;
  publication_date: string;
  domain: string;
  target_audience: string;
  feedback_visibility: FeedbackVisibility | null;
}

function formatDateForInput(date: Date | string | null | undefined): string {
  if (!date) return '';
  // If date is already a string in YYYY-MM-DD format, return as is
  if (typeof date === 'string' && date.match(/^\d{4}-\d{2}-\d{2}$/)) return date;
  // If it's a Date object, format it
  if (date instanceof Date) {
    return date.toISOString().split('T')[0];
  }
  // Otherwise, try to parse and format
  try {
    const d = new Date(date);
    if (isNaN(d.getTime())) return '';
    return d.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

export function EditProjectDialog({
  isOpen,
  project,
  onConfirm,
  onCancel,
  isSubmitting = false,
}: EditProjectDialogProps) {
  const { showExperimentalFeatures } = useExperimentalFeatures();
  const form = useForm({
    defaultValues: {
      title: project.title || '',
      publication_date: formatDateForInput(project.publication_date),
      domain: project.domain || '',
      target_audience: project.target_audience || '',
      feedback_visibility: project.feedback_visibility ?? null,
    } as EditProjectFormValues,
    validators: {
      onChange: ({ value }) => {
        const errors: GlobalFormValidationError<EditProjectFormValues> = { fields: {}, form: undefined };
        if (!value.title || value.title.trim() === '') {
          errors.fields.title = 'Title is required';
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
          <DialogTitle>Edit Project Details</DialogTitle>
          <DialogDescription>Update the project information below.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <form.Field name="title">
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="project-title" required>
                  Project Title
                </Label>
                <Input
                  id="project-title"
                  type="text"
                  placeholder="Enter project title"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  error={!field.state.meta.isValid}
                  required={true}
                  disabled={isSubmitting}
                />
                {!field.state.meta.isValid && (
                  <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                )}
              </div>
            )}
          </form.Field>

          {showExperimentalFeatures && (
            <form.Field name="publication_date">
              {(field) => (
                <div className="space-y-2">
                  <Label htmlFor="publication-date">Document Publication Date</Label>
                  <Input
                    id="publication-date"
                    type="date"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    disabled={isSubmitting}
                  />
                  <p className="text-sm text-muted-foreground">
                    The publication date of the document. For unpublished documents, use the date of the last update or
                    the current date.
                  </p>
                </div>
              )}
            </form.Field>
          )}

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
                  disabled={isSubmitting}
                />
                <p className="text-sm text-muted-foreground">
                  The subject area or field of expertise to contextualize the analysis. This helps tailor the evaluation
                  to domain-specific standards and terminology.
                </p>
              </div>
            )}
          </form.Field>

          <form.Field name="target_audience">
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
                  disabled={isSubmitting}
                />
                <p className="text-sm text-muted-foreground">
                  The intended readers of the document. Specifying the audience helps adjust the analysis to match
                  appropriate complexity level and expectations.
                </p>
              </div>
            )}
          </form.Field>
        </div>

        <form.Field name="feedback_visibility">
          {(field) => (
            <div className="space-y-2">
              <Label htmlFor="feedback-visibility">
                Feedback Visibility <span className="text-muted-foreground text-xs font-normal">(Optional)</span>
              </Label>
              <Select
                value={field.state.value ?? ''}
                onValueChange={(v) => field.handleChange(v ? (v as FeedbackVisibility) : null)}
                disabled={isSubmitting}
              >
                <SelectTrigger id="feedback-visibility">
                  <SelectValue placeholder="Not set" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={FeedbackVisibility.Private}>Only me — don&apos;t share any information</SelectItem>
                  <SelectItem value={FeedbackVisibility.IssueOnly}>Share issue information only</SelectItem>
                  <SelectItem value={FeedbackVisibility.FullProject}>
                    Share whole project with administrators (read-only mode)
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Controls what administrators can see when you submit feedback on issues.
              </p>
            </div>
          )}
        </form.Field>

        <Callout variant="info" icon={InfoIcon} title="Note">
          Only subsequent analyses (new or re-triggered) will use the updated project details. Existing or running
          analyses will keep their original configuration and results.
        </Callout>

        <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
          {([canSubmit, isFormSubmitting]) => (
            <DialogFooter>
              <Button variant="outline" onClick={onCancel} disabled={isFormSubmitting || isSubmitting}>
                Cancel
              </Button>
              <Button onClick={() => form.handleSubmit()} disabled={!canSubmit || isFormSubmitting || isSubmitting}>
                {isFormSubmitting || isSubmitting ? 'Saving...' : 'Save Changes'}
              </Button>
            </DialogFooter>
          )}
        </form.Subscribe>
      </DialogContent>
    </Dialog>
  );
}
