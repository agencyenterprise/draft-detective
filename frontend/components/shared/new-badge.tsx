import { Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { isNewFeature } from '@/lib/new-features';

interface NewBadgeProps {
  /** The feature's id in the NEW_FEATURES registry, e.g. `workflow:citation_consistency`. */
  feature: string;
  tooltip?: string;
}

/**
 * Marks a recently released feature, and renders nothing once its window in
 * the registry has passed. A faint violet gradient sets it apart from the
 * neutral badges around it without shouting over them.
 */
export function NewBadge({ feature, tooltip = 'Released recently.' }: NewBadgeProps) {
  if (!isNewFeature(feature)) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge className="h-5 gap-1 border-violet-500/20 bg-gradient-to-r from-violet-500/15 to-fuchsia-500/15 px-1.5 text-[11px] font-medium text-violet-700 dark:text-violet-300">
          <Sparkles aria-hidden className="size-3" />
          New
        </Badge>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}
