import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import {
  CheckCircleIcon,
  CircleAlertIcon,
  LucideProps,
  MessageCircleWarningIcon,
  TriangleAlertIcon,
} from 'lucide-react';

const severityConfigMap: Record<
  SeverityEnum,
  {
    icon: React.ComponentType<LucideProps>;
    title: string;
    description: string;
    className: string;
  }
> = {
  [SeverityEnum.None]: {
    icon: CheckCircleIcon,
    // fgColorClassName: 'text-green-600',
    title: 'No issues',
    description: 'No issues found',
    className: 'bg-green-700 text-white',
  },
  [SeverityEnum.Low]: {
    icon: MessageCircleWarningIcon,
    title: 'Low',
    description: 'Low severity issue found',
    className: 'bg-blue-600 text-white',
  },
  [SeverityEnum.Medium]: {
    icon: TriangleAlertIcon,
    title: 'Medium',
    description: 'Medium severity issue found',
    className: 'bg-yellow-600 text-white',
  },
  [SeverityEnum.High]: {
    icon: CircleAlertIcon,
    title: 'High',
    description: 'High severity issue found',
    className: 'bg-red-600 text-white',
  },
};

export interface SeverityBadgeProps {
  severity: SeverityEnum;
  hideIcon?: boolean;
}

export function SeverityBadge({ severity, hideIcon = false }: SeverityBadgeProps) {
  const { icon: Icon, title, description, className } = severityConfigMap[severity];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn('inline-flex items-center gap-1 px-2 py-0.75 rounded-md text-xs font-medium', className)}>
          {hideIcon ? null : <Icon className="size-3" />}
          {title}
        </span>
      </TooltipTrigger>
      <TooltipContent>{description}</TooltipContent>
    </Tooltip>
  );
}
