import { ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';

interface NavigateToExplorerButtonProps {
  /** Callback when button is clicked */
  onClick: () => void;
  /** Optional custom label (defaults to "View in Document Explorer") */
  label?: string;
}

/**
 * Button for navigating to the Document Explorer.
 * Stops event propagation to prevent triggering parent click handlers.
 */
export function NavigateToExplorerButton({
  onClick,
  label = 'View in Document Explorer',
}: NavigateToExplorerButtonProps) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="mt-2 gap-1"
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
