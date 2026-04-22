import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { EvidenceWeighterRecommendedAction } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { cva } from 'class-variance-authority';
import { CheckCircleIcon, PencilIcon } from 'lucide-react';

const config: Record<
  EvidenceWeighterRecommendedAction,
  {
    title: string;
    description: string;
    icon: React.ReactNode;
    tone: 'green' | 'yellow';
  }
> = {
  [EvidenceWeighterRecommendedAction.NoUpdateNeeded]: {
    title: 'No Update Needed',
    description: 'The claim does not need to be updated.',
    icon: <CheckCircleIcon />,
    tone: 'green',
  },
  [EvidenceWeighterRecommendedAction.AddCitation]: {
    title: 'Add Citation',
    description: 'The claim can remain as is, but additional citations prove more influential.',
    icon: <PencilIcon />,
    tone: 'yellow',
  },
  [EvidenceWeighterRecommendedAction.UpdateClaim]: {
    title: 'Update Claim',
    description:
      'The claim is either no longer true and needs to be updated or it should be qualified given the newer sources.',
    icon: <PencilIcon />,
    tone: 'yellow',
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
  },
  defaultVariants: {
    tone: 'green',
  },
});

export interface EvidenceWeighterRecommendedActionBadgeProps {
  recommendedAction: EvidenceWeighterRecommendedAction;
  className?: string;
}

export function EvidenceWeighterRecommendedActionBadge({
  recommendedAction,
  className,
}: EvidenceWeighterRecommendedActionBadgeProps) {
  const { title, description, icon, tone } = config[recommendedAction];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge className={cn(badgeStyles({ tone }), className)}>
          {icon} {title}
        </Badge>
      </TooltipTrigger>
      <TooltipContent>{description}</TooltipContent>
    </Tooltip>
  );
}
