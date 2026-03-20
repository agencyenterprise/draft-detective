'use client';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { RadioGroup } from '@/components/ui/radio-group';
import { RadioGroupItemWithDescription } from '@/components/ui/radio-group-with-description';
import { FeedbackVisibility } from '@/lib/generated-api';
import { InfoIcon } from 'lucide-react';
import { useState } from 'react';

interface FeedbackPrivacyDialogProps {
  isOpen: boolean;
  onConfirm: (visibility: FeedbackVisibility) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

const VISIBILITY_OPTIONS: {
  value: FeedbackVisibility;
  label: string;
  description: string;
}[] = [
  {
    value: FeedbackVisibility.Private,
    label: "Don't share any information",
    description: 'Your feedback is visible only to you.',
  },
  {
    value: FeedbackVisibility.IssueOnly,
    label: 'Share only this issue information',
    description:
      'Includes the issue title, description, and your feedback text. Project files and other analysis results are not shared.',
  },
  {
    value: FeedbackVisibility.FullProject,
    label: 'Share whole project information',
    description: 'Administrators will be able to view the project, all uploaded files, and all analysis results.',
  },
];

export function FeedbackPrivacyDialog({
  isOpen,
  onConfirm,
  onCancel,
  isSubmitting = false,
}: FeedbackPrivacyDialogProps) {
  const [selected, setSelected] = useState<FeedbackVisibility>(FeedbackVisibility.Private);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Who can see your feedback?</DialogTitle>
          <DialogDescription>
            Choose how much information administrators and developers can access for this project.
          </DialogDescription>
        </DialogHeader>

        <RadioGroup value={selected} onValueChange={(v) => setSelected(v as FeedbackVisibility)} className="space-y-2">
          {VISIBILITY_OPTIONS.map((opt) => (
            <RadioGroupItemWithDescription
              key={opt.value}
              id={opt.value}
              value={selected}
              label={opt.label}
              description={opt.description}
            />
          ))}
        </RadioGroup>

        <p className="text-xs text-muted-foreground flex items-start gap-1.5">
          <InfoIcon className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          You can change this preference at any time in the project settings.
        </p>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={() => onConfirm(selected)} disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : 'Save & Submit Feedback'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
