import { Markdown } from '@/components/markdown';
import { getIssueId } from '@/lib/chunk-ids';
import { DocumentIssue, SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { CheckCircleIcon, CircleAlertIcon, MessageCircleWarningIcon, TriangleAlertIcon } from 'lucide-react';
import { SeverityBadge } from './severity-badge';

interface DocumentIssueCardProps {
  issue: DocumentIssue;
  onSelect: (issue: DocumentIssue) => void;
}

export const severityColorMap: Record<
  SeverityEnum,
  {
    className: string;
    icon: React.ReactNode;
  }
> = {
  [SeverityEnum.None]: {
    className: 'bg-green-50 border-green-400',
    icon: <CheckCircleIcon className="size-4 text-white" />,
  },
  [SeverityEnum.Low]: {
    className: 'bg-blue-50 border-blue-400',
    icon: <MessageCircleWarningIcon className="size-4 text-blue-600" />,
  },
  [SeverityEnum.Medium]: {
    className: 'bg-yellow-50 border-yellow-400',
    icon: <TriangleAlertIcon className="size-4 text-yellow-600" />,
  },
  [SeverityEnum.High]: {
    className: 'bg-red-50 border-red-400',
    icon: <CircleAlertIcon className="size-4 text-red-600" />,
  },
};

export function DocumentIssueCard({ issue, onSelect }: DocumentIssueCardProps) {
  const { className, icon } = severityColorMap[issue.severity];

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(issue);
    }
  };

  return (
    <div
      id={getIssueId(issue.chunkIndex, issue.claimIndex)}
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
        <SeverityBadge severity={issue.severity} hideIcon={true} />
      </div>
      <p className="text-sm text-gray-700">{issue.description}</p>
      <div className="flex items-center gap-2 justify-between">
        <p className="text-xs text-muted-foreground italic flex items-center gap-1">
          {issue.claimIndex !== undefined && issue.claimIndex !== null && <span>Claim {issue.claimIndex + 1}</span>}
          {issue.chunkIndex !== undefined && issue.chunkIndex !== null && <span>Chunk {issue.chunkIndex}</span>}
        </p>
      </div>
    </div>
  );
}

export interface DocumentIssueCardMinimalProps {
  issue: DocumentIssue;
}

export function DocumentIssueCardMinimal({ issue }: DocumentIssueCardMinimalProps) {
  const { className, icon } = severityColorMap[issue.severity];

  return (
    <div className={cn('space-y-2 px-3 py-2 rounded-md', className)}>
      <div className="flex items-center gap-2">
        {icon}
        <h4 className="font-medium">{issue.title}</h4>
      </div>
      <Markdown>{issue.description}</Markdown>
    </div>
  );
}
