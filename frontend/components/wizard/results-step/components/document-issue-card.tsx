import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Textarea } from '@/components/ui/textarea';
import { DocumentIssue, FeedbackType, SeverityEnum, WorkflowRunDetail } from '@/lib/generated-api';
import { useIssueFeedback } from '@/lib/hooks/use-issue-feedback';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CircleAlertIcon,
  ExternalLinkIcon,
  MessageCircleWarningIcon,
  ThumbsDown,
  ThumbsUp,
  TriangleAlertIcon,
} from 'lucide-react';
import { memo, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { SeverityBadge } from './severity-badge';

interface DocumentIssueCardProps {
  issue: DocumentIssue;
  hideJumpToChunk?: boolean;
  jumpToAlias?: string;
  onSelect: (issue: DocumentIssue) => void;
  workflowRuns?: WorkflowRunDetail[];
  readOnly?: boolean;
}

export const severityColorMap: Record<
  SeverityEnum,
  {
    className: string;
    accentClassName: string;
    icon: React.ReactNode;
  }
> = {
  [SeverityEnum.None]: {
    className: 'bg-green-50 border-green-400',
    accentClassName: 'text-green-700',
    icon: <CheckCircleIcon className="size-4 text-white" />,
  },
  [SeverityEnum.Low]: {
    className: 'bg-blue-50 border-blue-400',
    accentClassName: 'text-blue-700',
    icon: <MessageCircleWarningIcon className="size-4 text-blue-600" />,
  },
  [SeverityEnum.Medium]: {
    className: 'bg-yellow-50 border-yellow-400',
    accentClassName: 'text-yellow-700',
    icon: <TriangleAlertIcon className="size-4 text-yellow-600" />,
  },
  [SeverityEnum.High]: {
    className: 'bg-red-50 border-red-400',
    accentClassName: 'text-red-700',
    icon: <CircleAlertIcon className="size-4 text-red-600" />,
  },
};

function IssueFeedbackButtons({ workflowRunId, issueId }: { workflowRunId: string; issueId: string }) {
  const { feedback, submitFeedback, isSubmitting } = useIssueFeedback(workflowRunId, issueId);
  const [feedbackText, setFeedbackText] = useState('');
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);

  const selectedFeedback = feedback?.feedback_type ?? null;
  const hasSubmitted = selectedFeedback !== null;

  const handleThumbsUp = () => {
    if (hasSubmitted && selectedFeedback === FeedbackType.ThumbsUp) return;

    submitFeedback(
      { feedback_type: FeedbackType.ThumbsUp, feedback_text: null },
      {
        onSuccess: () => toast.success('Thanks for your feedback!'),
        onError: () => toast.error('Failed to submit feedback'),
      },
    );
  };

  const handleThumbsDownSubmit = () => {
    submitFeedback(
      { feedback_type: FeedbackType.ThumbsDown, feedback_text: feedbackText || null },
      {
        onSuccess: () => {
          toast.success('Thanks for your feedback!');
          setIsPopoverOpen(false);
          setFeedbackText('');
        },
        onError: () => toast.error('Failed to submit feedback'),
      },
    );
  };

  return (
    <div className="flex items-center gap-0.5">
      <Button
        variant={selectedFeedback === FeedbackType.ThumbsUp ? 'default' : 'ghost'}
        size="xs"
        onClick={handleThumbsUp}
        className="h-6 w-6 p-0"
        disabled={isSubmitting || (hasSubmitted && selectedFeedback === FeedbackType.ThumbsUp)}
        title="Helpful"
      >
        <ThumbsUp className="h-3 w-3" />
      </Button>
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            variant={selectedFeedback === FeedbackType.ThumbsDown ? 'default' : 'ghost'}
            size="xs"
            className="h-6 w-6 p-0"
            disabled={hasSubmitted && selectedFeedback === FeedbackType.ThumbsDown}
            title="Not helpful"
          >
            <ThumbsDown className="h-3 w-3" />
          </Button>
        </PopoverTrigger>
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

function DocumentIssueCardRaw({
  issue,
  hideJumpToChunk = false,
  jumpToAlias = 'chunk',
  onSelect,
  workflowRuns = [],
  readOnly = false,
}: DocumentIssueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { className, icon, accentClassName } = severityColorMap[issue.severity];
  const { getWorkflowTypeName } = useWorkflowTypes();

  const workflowRunId = useMemo(() => {
    const workflowRun = workflowRuns.find((wr) => wr.run.type === issue.type);
    return workflowRun?.run.id;
  }, [workflowRuns, issue.type]);

  const showJumpToChunkButton =
    !hideJumpToChunk &&
    ((issue.chunk_index !== undefined && issue.chunk_index !== null) || (issue.chunk_indices?.length ?? 0) > 0);

  return (
    <div
      id={`issue-${issue.id}`}
      className={cn('rounded-lg p-4 space-y-3 border-l-4 shadow-sm break-words', className)}
    >
      <div className="flex items-center gap-2 justify-between">
        <div className="flex gap-2">
          <div className="mt-1">{icon}</div>
          <hgroup>
            <h3 className="font-semibold text-normal">{issue.title}</h3>
            <p className="text-xs text-muted-foreground italic">{getWorkflowTypeName(issue.type)}</p>
          </hgroup>
        </div>
        <div className="flex items-center gap-2">
          {!readOnly && workflowRunId && issue.id && (
            <IssueFeedbackButtons workflowRunId={workflowRunId} issueId={issue.id} />
          )}
          <SeverityBadge severity={issue.severity} hideIcon={true} />
        </div>
      </div>

      <Markdown>{issue.description}</Markdown>

      <div
        className={cn('flex items-center gap-2', {
          'border-t pt-1': showJumpToChunkButton || !!issue.long_description,
        })}
      >
        {showJumpToChunkButton && (
          <Button variant="ghost" size="xs" className={accentClassName} onClick={() => onSelect(issue)}>
            <ExternalLinkIcon className="size-3" />
            Jump to {jumpToAlias} {issue.chunk_index ?? issue.chunk_indices?.[0] ?? ''}
          </Button>
        )}
        {issue.long_description && (
          <Button
            variant="ghost"
            size="xs"
            className={cn(accentClassName, 'ml-auto')}
            onClick={() => setIsExpanded(!isExpanded)}
            aria-expanded={isExpanded}
          >
            {isExpanded ? (
              <>
                <ChevronUpIcon className="size-3" />
                Hide details
              </>
            ) : (
              <>
                <ChevronDownIcon className="size-3" />
                Show details
              </>
            )}
          </Button>
        )}
      </div>
      {issue.long_description && isExpanded && (
        <div>
          <Markdown>{issue.long_description}</Markdown>
        </div>
      )}
    </div>
  );
}

export const DocumentIssueCard = memo(DocumentIssueCardRaw);
