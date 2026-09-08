import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useIssueFeedbackFromContext } from '@/lib/contexts/project-feedback-context';
import { FeedbackType } from '@/lib/generated-api';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { ReactNode, useState } from 'react';

/** How a piece of feedback reads back. Shared so the control and the margin-note indicator never
 *  describe the same feedback differently. `byAuthor` is for a reader who did not leave
 *  it — an admin on someone else's project — where "you" would be plainly wrong. */
export function feedbackLabel(feedbackType: FeedbackType, feedbackText?: string | null, byAuthor = false): string {
  const who = byAuthor ? 'The author marked this issue as' : 'You marked this issue as';
  const verdict = feedbackType === FeedbackType.ThumbsUp ? 'helpful' : 'not helpful';
  return feedbackText ? `${who} ${verdict}: "${feedbackText}"` : `${who} ${verdict}`;
}

/**
 * A tooltip for one of the thumbs.
 *
 * It hangs off a wrapper rather than the button itself because the button is disabled
 * once that thumb is the one chosen — and a disabled button emits no pointer events, so
 * the tooltip would go missing in exactly the case worth explaining: the rating already
 * given, and whatever note came with it.
 */
function ThumbTooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{children}</span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{label}</TooltipContent>
    </Tooltip>
  );
}

/** Thumbs up/down with the "what could be improved" popover. Shared with the margin note. */
export function IssueFeedbackButtons({ issueId }: { issueId: string }) {
  const { feedback, submitFeedback, isSubmitting, isReadOnly } = useIssueFeedbackFromContext(issueId);
  const [feedbackText, setFeedbackText] = useState('');
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);

  const selectedFeedback = feedback?.feedback_type ?? null;
  const hasSubmitted = selectedFeedback !== null;

  const handleThumbsUp = () => {
    if (hasSubmitted && selectedFeedback === FeedbackType.ThumbsUp) return;
    submitFeedback({ feedback_type: FeedbackType.ThumbsUp, feedback_text: null });
  };

  const handleThumbsDownSubmit = () => {
    submitFeedback({ feedback_type: FeedbackType.ThumbsDown, feedback_text: feedbackText || null });
    setIsPopoverOpen(false);
    setFeedbackText('');
  };

  const isThumbsUp = selectedFeedback === FeedbackType.ThumbsUp;
  const isThumbsDown = selectedFeedback === FeedbackType.ThumbsDown;

  // Someone else's rating: show what it was, with nothing to press. Nothing at all when
  // they never rated it, rather than a control this reader could not use anyway.
  if (isReadOnly) {
    if (selectedFeedback === null) return null;
    const label = feedbackLabel(selectedFeedback, feedback?.feedback_text, true);
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            aria-label={label}
            className="bg-primary text-primary-foreground flex h-6 w-6 items-center justify-center rounded-md"
          >
            {isThumbsUp ? <ThumbsUp className="h-3 w-3" /> : <ThumbsDown className="h-3 w-3" />}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{label}</TooltipContent>
      </Tooltip>
    );
  }
  // Both thumbs are icon-only, and the tooltip cannot name them: it describes the wrapper
  // the trigger hangs off, and only while it is open. So each carries its own label.
  const thumbsUpLabel = isThumbsUp ? feedbackLabel(FeedbackType.ThumbsUp) : 'Helpful';
  const thumbsDownLabel = isThumbsDown
    ? feedbackLabel(FeedbackType.ThumbsDown, feedback?.feedback_text)
    : 'Not helpful';

  return (
    <div className="flex items-center gap-0.5">
      <ThumbTooltip label={thumbsUpLabel}>
        <Button
          variant={isThumbsUp ? 'default' : 'ghost'}
          size="xs"
          onClick={handleThumbsUp}
          className="h-6 w-6 p-0"
          disabled={isSubmitting || isThumbsUp}
          aria-label={thumbsUpLabel}
        >
          <ThumbsUp className="h-3 w-3" />
        </Button>
      </ThumbTooltip>
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <ThumbTooltip label={thumbsDownLabel}>
          <PopoverTrigger asChild>
            <Button
              variant={isThumbsDown ? 'default' : 'ghost'}
              size="xs"
              className="h-6 w-6 p-0"
              disabled={isThumbsDown}
              aria-label={thumbsDownLabel}
            >
              <ThumbsDown className="h-3 w-3" />
            </Button>
          </PopoverTrigger>
        </ThumbTooltip>
        <PopoverContent className="w-72" align="end">
          <div className="space-y-3">
            <p className="text-sm font-medium">What could be improved?</p>
            <Textarea
              placeholder="Tell us what's wrong with this issue..."
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              rows={3}
              className="resize-none text-sm"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setIsPopoverOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleThumbsDownSubmit} disabled={isSubmitting}>
                {isSubmitting ? 'Submitting...' : 'Submit'}
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
