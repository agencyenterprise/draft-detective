import { ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface NavigateToExplorerButtonProps {
  /** Callback when button is clicked */
  onClick: () => void;
  /** Optional custom label (defaults to "View in Document Explorer") */
  label?: string;
  /** Extra classes, e.g. to drop the default top margin inside a flex row */
  className?: string;
}

/**
 * Button for navigating to the Document Explorer.
 * Stops event propagation to prevent triggering parent click handlers.
 */
export function NavigateToExplorerButton({
  onClick,
  label = 'View in Document Explorer',
  className,
}: NavigateToExplorerButtonProps) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn('mt-2 gap-1', className)}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <ExternalLink className="h-3 w-3" />
      {label}
    </Button>
  );
}
