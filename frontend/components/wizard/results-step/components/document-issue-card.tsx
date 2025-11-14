import { Markdown } from '@/components/markdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { DocumentIssue, SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleAlertIcon,
  MessageCircleWarningIcon,
  TriangleAlertIcon,
} from 'lucide-react';
import { useState } from 'react';

interface DocumentIssueCardProps {
  issue: DocumentIssue;
  onSelect: (issue: DocumentIssue) => void;
}

const severityColorMap: Record<
  SeverityEnum,
  {
    className: string;
    icon: React.ReactNode;
    badgeTitle: string;
    badgeDescription: string;
    badgeClassName: string;
  }
> = {
  [SeverityEnum.None]: {
    className: 'bg-green-50 border-green-400',
    icon: <CheckCircleIcon className="size-4 text-green-600" />,
    badgeTitle: 'No issue',
    badgeDescription: 'No issue found.',
    badgeClassName: 'bg-green-500 text-white',
  },
  [SeverityEnum.Low]: {
    className: 'bg-blue-50 border-blue-400',
    icon: <MessageCircleWarningIcon className="size-4 text-blue-600" />,
    badgeTitle: 'Low',
    badgeDescription: 'Low severity issue',
    badgeClassName: 'bg-blue-500 text-white',
  },
  [SeverityEnum.Medium]: {
    className: 'bg-yellow-50 border-yellow-400',
    icon: <TriangleAlertIcon className="size-4 text-yellow-600" />,
    badgeTitle: 'Medium',
    badgeDescription: 'Medium severity issue',
    badgeClassName: 'bg-yellow-500 text-white',
  },
  [SeverityEnum.High]: {
    className: 'bg-red-50 border-red-400',
    icon: <CircleAlertIcon className="size-4 text-red-600" />,
    badgeTitle: 'High',
    badgeDescription: 'High severity issue',
    badgeClassName: 'bg-red-500 text-white',
  },
};

export function DocumentIssueCard({ issue, onSelect }: DocumentIssueCardProps) {
  const { className, icon, badgeTitle, badgeDescription, badgeClassName } = severityColorMap[issue.severity];
  const [isExpanded, setIsExpanded] = useState(false);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(issue);
    }
  };

  const handleExpandClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded(!isExpanded);
  };

  return (
    <div
      className={cn('rounded-lg p-4 space-y-3 border-l-4 shadow-sm cursor-pointer break-words', className)}
      role="button"
      tabIndex={0}
      aria-label={`Select issue: ${issue.title}`}
      onClick={() => onSelect(issue)}
      onKeyDown={handleKeyDown}
    >
      <div className="flex items-center gap-2 justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-semibold text-normal">{issue.title}</h3>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="secondary" className={cn(badgeClassName)}>
              {badgeTitle}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>{badgeDescription}</TooltipContent>
        </Tooltip>
      </div>
      <p className="text-sm text-gray-700">{issue.description}</p>
      <div className="flex items-center gap-2 justify-between">
        <p className="text-xs text-muted-foreground italic flex items-center gap-1">
          {issue.claimIndex !== undefined && issue.claimIndex !== null && <span>Claim {issue.claimIndex + 1}</span>}
          {issue.chunkIndex !== undefined && issue.chunkIndex !== null && <span>Chunk {issue.chunkIndex}</span>}
        </p>
        <Button variant="ghost" size="xs" onClick={handleExpandClick}>
          {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
          {isExpanded ? 'Hide details' : 'Show details'}
        </Button>
      </div>
      {isExpanded && (
        <div className="text-sm text-gray-700">
          <Markdown>{issue.additionalContext}</Markdown>
        </div>
      )}
    </div>
  );
}
