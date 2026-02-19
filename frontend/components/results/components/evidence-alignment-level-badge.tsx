import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { EvidenceAlignmentLevel } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { cva } from 'class-variance-authority';
import { AlertTriangle, CheckCircle } from 'lucide-react';

const evidenceAlignmentLevelConfig: Record<
  EvidenceAlignmentLevel,
  {
    title: string;
    description: string;
    icon: React.ReactNode;
    tone: 'green' | 'yellow' | 'gray' | 'red';
  }
> = {
  [EvidenceAlignmentLevel.Supported]: {
    title: 'Supported',
    description: 'The supporting document(s) directly provide evidence for the claim.',
    icon: <CheckCircle />,
    tone: 'green',
  },
  [EvidenceAlignmentLevel.PartiallySupported]: {
    title: 'Partially supported',
    description: 'The supporting document(s) provide related evidence but do not fully substantiate the claim.',
    icon: <AlertTriangle />,
    tone: 'yellow',
  },
  [EvidenceAlignmentLevel.Unverifiable]: {
    title: 'Unverifiable',
    description: 'The supporting document(s) were not provided, or are inaccessible to confirm or deny the claim.',
    icon: <AlertTriangle />,
    tone: 'gray',
  },
  [EvidenceAlignmentLevel.Unsupported]: {
    title: 'Unsupported',
    description: 'The supporting document(s) do not provide evidence for the claim or contradict the claim.',
    icon: <AlertTriangle />,
    tone: 'red',
  },
};

const badgeStyles = cva('', {
  variants: {
    tone: {
      green: 'bg-green-100 text-green-800',
      yellow: 'bg-yellow-100 text-yellow-800',
      gray: 'bg-gray-100 text-gray-800',
      red: 'bg-red-100 text-red-800',
    },
    variant: {
      solid: '',
      text: 'bg-transparent p-0',
    },
  },
  compoundVariants: [
    { variant: 'text', tone: 'green', class: 'text-green-600' },
    { variant: 'text', tone: 'yellow', class: 'text-yellow-600' },
    { variant: 'text', tone: 'gray', class: 'text-gray-600' },
    { variant: 'text', tone: 'red', class: 'text-red-600' },
  ],
  defaultVariants: {
    tone: 'green',
    variant: 'solid',
  },
});

export interface EvidenceAlignmentLevelBadgeProps {
  evidenceAlignment: EvidenceAlignmentLevel;
  variant: 'solid' | 'text';
  className?: string;
  count?: number;
}

export function EvidenceAlignmentLevelBadge({
  evidenceAlignment,
  className,
  variant = 'solid',
  count,
}: EvidenceAlignmentLevelBadgeProps) {
  const { title, description, icon, tone } = evidenceAlignmentLevelConfig[evidenceAlignment];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge className={cn(badgeStyles({ tone, variant }), className)}>
          {count && (
            <>
              {icon} {count} {title} claim{count > 1 ? 's' : ''}
            </>
          )}
          {!count && (
            <>
              {icon} {title}
            </>
          )}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{description}</TooltipContent>
    </Tooltip>
  );
}
