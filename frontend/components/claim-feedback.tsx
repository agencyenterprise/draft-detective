'use client';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { FeedbackType } from '@/lib/generated-api';
import { useClaimFeedback } from '@/lib/hooks/use-claim-feedback';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import * as React from 'react';
import { toast } from 'sonner';

interface ClaimFeedbackProps {
  workflowRunId: string;
  chunkIndex: number;
  claimIndex: number;
}

export function ClaimFeedback({ workflowRunId, chunkIndex, claimIndex }: ClaimFeedbackProps) {
  const { feedback, submitFeedback, isSubmitting } = useClaimFeedback(workflowRunId, chunkIndex, claimIndex);

  const [selectedFeedback, setSelectedFeedback] = React.useState<FeedbackType | null>(feedback?.feedback_type || null);
  const [feedbackText, setFeedbackText] = React.useState(feedback?.feedback_text || '');
  const [hasSubmitted, setHasSubmitted] = React.useState(!!feedback);

  React.useEffect(() => {
    if (feedback) {
      setSelectedFeedback(feedback.feedback_type);
      setFeedbackText(feedback.feedback_text || '');
      setHasSubmitted(true);
    } else {
      setSelectedFeedback(null);
      setFeedbackText('');
      setHasSubmitted(false);
    }
  }, [feedback]);

  const handleFeedbackChange = (type: FeedbackType) => {
    setSelectedFeedback(type);
    setHasSubmitted(false);

    if (type === FeedbackType.ThumbsUp) {
      setFeedbackText('');
    }
  };

  const handleSubmit = () => {
    if (!selectedFeedback) return;

    submitFeedback(
      {
        feedback_type: selectedFeedback,
        feedback_text: feedbackText || null,
      },
      {
        onSuccess: () => {
          setHasSubmitted(true);
          toast.success('Thank you for your feedback!');
        },
        onError: () => {
          toast.error('Failed to submit feedback. Please try again.');
        },
      },
    );
  };

  return (
    <div className="border-t pt-3 mt-3 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Was this analysis helpful?</span>
        <div className="flex gap-1">
          <Button
            variant={selectedFeedback === FeedbackType.ThumbsUp ? 'default' : 'ghost'}
            size="sm"
            onClick={() => handleFeedbackChange(FeedbackType.ThumbsUp)}
            className="h-7 w-7 p-0"
            disabled={hasSubmitted && selectedFeedback === FeedbackType.ThumbsUp}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={selectedFeedback === FeedbackType.ThumbsDown ? 'default' : 'ghost'}
            size="sm"
            onClick={() => handleFeedbackChange(FeedbackType.ThumbsDown)}
            className="h-7 w-7 p-0"
            disabled={hasSubmitted && selectedFeedback === FeedbackType.ThumbsDown}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {selectedFeedback === FeedbackType.ThumbsDown && (
        <div className="space-y-2 animate-in fade-in-50 duration-200">
          <Textarea
            placeholder="What could we improve about this claim analysis?"
            value={feedbackText}
            onChange={(e) => {
              setFeedbackText(e.target.value);
              setHasSubmitted(false);
            }}
            rows={2}
            className="resize-none text-sm"
            disabled={hasSubmitted}
          />
          {!hasSubmitted && (
            <div className="flex justify-end">
              <Button onClick={handleSubmit} disabled={isSubmitting} size="sm" variant="secondary">
                {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
              </Button>
            </div>
          )}
        </div>
      )}

      {selectedFeedback === FeedbackType.ThumbsUp && !hasSubmitted && (
        <div className="flex justify-end">
          <Button onClick={handleSubmit} disabled={isSubmitting} size="sm" variant="secondary">
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </Button>
        </div>
      )}

      {hasSubmitted && <p className="text-xs text-muted-foreground text-center">✓ Feedback submitted</p>}
    </div>
  );
}
