'use client';

import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Link } from 'lucide-react';

interface ShareStatusBadgeProps {
  isEnabled: boolean;
  onClick?: () => void;
}

export function ShareStatusBadge({ isEnabled, onClick }: ShareStatusBadgeProps) {
  if (!isEnabled) return null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          className="cursor-pointer gap-1 bg-green-50 text-green-700 border-green-200 hover:bg-green-100 dark:bg-green-950 dark:text-green-300 dark:border-green-800 dark:hover:bg-green-900"
          onClick={onClick}
        >
          <Link className="h-3 w-3" />
          Sharing enabled
        </Badge>
      </TooltipTrigger>
      <TooltipContent>
        <p>Click to manage share settings</p>
      </TooltipContent>
    </Tooltip>
  );
}
