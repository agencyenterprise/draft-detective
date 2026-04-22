import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Textarea } from '@/components/ui/textarea';
import { useIssueFeedbackFromContext } from '@/lib/contexts/project-feedback-context';
import { FeedbackType, Issue, SeverityEnum } from '@/lib/generated-api';
import { useIssueActions } from '@/lib/hooks/use-issue-actions';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CircleAlertIcon,
  ExternalLinkIcon,
  MessageCircleWarningIcon,
  MoreHorizontalIcon,
  ThumbsDown,
  ThumbsUp,
  TriangleAlertIcon,
  UndoIcon,
} from 'lucide-react';
import { memo, useState } from 'react';
import { Markdown } from '@/components/markdown';
import { SeverityBadge } from './severity-badge';
import { isIssueResolved } from '@/lib/stores/document-explorer-store';

interface DocumentIssueCardProps {
  issue: Issue;
  hideJumpButton?: boolean;
  onSelect: (issue: Issue) => void;
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

function IssueFeedbackButtons({ issueId }: { issueId: string }) {
  const { feedback, submitFeedback, isSubmitting } = useIssueFeedbackFromContext(issueId);
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

function IssueActionsMenu({ issue }: { issue: Issue }) {
  const { resolveIssue, unresolveIssue, isResolving, isUnresolving } = useIssueActions();
  const isResolved = isIssueResolved(issue);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="xs" className="h-6 w-6 p-0" disabled={isResolving || isUnresolving}>
          <MoreHorizontalIcon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {isResolved ? (
          <DropdownMenuItem onClick={() => unresolveIssue(issue.id)}>
            <UndoIcon className="h-4 w-4 mr-2" />
            Mark as unresolved
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onClick={() => resolveIssue(issue.id)}>
            <CheckIcon className="h-4 w-4 mr-2" />
            Mark as resolved
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function DocumentIssueCardRaw({ issue, hideJumpButton = false, onSelect, readOnly = false }: DocumentIssueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { className, icon, accentClassName } = severityColorMap[issue.severity];
  const { getWorkflowTypeName } = useWorkflowTypes();
  const isResolved = isIssueResolved(issue);

  const { start_line: startLine, end_line: endLine } = issue as Issue & {
    start_line?: number | null;
    end_line?: number | null;
  };
  const lineRangeLabel =
    typeof startLine === 'number' && typeof endLine === 'number'
      ? startLine === endLine
        ? `Line ${startLine}`
        : `Lines ${startLine}–${endLine}`
      : null;
  const jumpLabel =
    typeof startLine === 'number' && typeof endLine === 'number'
      ? startLine === endLine
        ? `Jump to line ${startLine}`
        : `Jump to lines ${startLine}–${endLine}`
      : null;
  const showJumpButton = !hideJumpButton && jumpLabel !== null;

  return (
    <div
      id={`issue-${issue.id}`}
      className={cn('rounded-lg p-4 space-y-3 border-l-4 shadow-sm break-words transition-opacity text-sm', className, {
        'opacity-60': isResolved,
      })}
    >
      <div className="flex items-center gap-2 justify-between">
        <div className="flex gap-2">
          <div className="mt-1">{icon}</div>
          <hgroup>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-normal">{issue.title}</h3>
              {isResolved && (
                <Badge variant="outline" className="text-xs h-5 bg-white/50">
                  <CheckIcon className="h-3 w-3 mr-1" />
                  Resolved
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground italic">
              {getWorkflowTypeName(issue.workflow_type)}
              {lineRangeLabel && <span className="not-italic"> · {lineRangeLabel}</span>}
            </p>
          </hgroup>
        </div>
        <div className="flex items-center gap-1">
          {!readOnly && issue.id && <IssueFeedbackButtons issueId={issue.id} />}
          {!readOnly && issue.id && <IssueActionsMenu issue={issue} />}
          <SeverityBadge severity={issue.severity} hideIcon={true} />
        </div>
      </div>

      <Markdown>{issue.description}</Markdown>

      <div
        className={cn('flex items-center gap-2', {
          'border-t pt-1': showJumpButton || !!issue.long_description,
        })}
      >
        {showJumpButton && (
          <Button variant="ghost" size="xs" className={accentClassName} onClick={() => onSelect(issue)}>
            <ExternalLinkIcon className="size-3" />
            {jumpLabel}
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
