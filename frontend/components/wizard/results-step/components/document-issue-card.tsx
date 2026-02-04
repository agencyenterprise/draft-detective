import { useState } from 'react';
import { Markdown } from '@/components/markdown';
import { getIssueId } from '@/lib/chunk-ids';
import { DocumentIssue, SeverityEnum } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CircleAlertIcon,
  ExternalLinkIcon,
  MessageCircleWarningIcon,
  TriangleAlertIcon,
} from 'lucide-react';
import { SeverityBadge } from './severity-badge';
import { Button } from '@/components/ui/button';

interface DocumentIssueCardProps {
  issue: DocumentIssue;
  onSelect: (issue: DocumentIssue) => void;
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

export function DocumentIssueCard({ issue, onSelect }: DocumentIssueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const { className, icon, accentClassName } = severityColorMap[issue.severity];
  const { getWorkflowTypeName } = useWorkflowTypes();

  return (
    <div
      id={getIssueId(issue.chunk_index, issue.claim_index)}
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
        <SeverityBadge severity={issue.severity} hideIcon={true} />
      </div>

      <Markdown>{issue.description}</Markdown>

      <div className="flex items-center gap-2 justify-between border-t pt-1">
        <Button variant="ghost" size="xs" className={accentClassName} onClick={() => onSelect(issue)}>
          <ExternalLinkIcon className="size-3" />
          Jump to chunk {issue.chunk_index !== undefined ? issue.chunk_index : ''}
        </Button>
        {issue.long_description && (
          <Button
            variant="ghost"
            size="xs"
            className={accentClassName}
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
        <div className="leading-relaxed">
          <Markdown>{issue.long_description}</Markdown>
        </div>
      )}
    </div>
  );
}

export interface DocumentIssueCardMinimalProps {
  issue: DocumentIssue;
}

export function DocumentIssueCardMinimal({ issue }: DocumentIssueCardMinimalProps) {
  const { className, icon } = severityColorMap[issue.severity];
  const { getWorkflowTypeName } = useWorkflowTypes();
  return (
    <div className={cn('space-y-2 px-3 py-2 rounded-md', className)}>
      <div className="flex items-center gap-2">
        {icon}
        <h4 className="font-medium">{issue.title}</h4>
      </div>
      <Markdown>{issue.description}</Markdown>
      <div className="flex items-center gap-2 justify-between">
        <p className="text-xs text-muted-foreground italic flex items-center gap-1">
          {getWorkflowTypeName(issue.type)}
        </p>
        <p className="text-xs text-muted-foreground italic flex items-center gap-1">
          {issue.claim_index !== undefined && issue.claim_index !== null && <span>Claim {issue.claim_index + 1}</span>}
          {issue.chunk_index !== undefined && issue.chunk_index !== null && <span>Chunk {issue.chunk_index}</span>}
        </p>
      </div>
    </div>
  );
}
