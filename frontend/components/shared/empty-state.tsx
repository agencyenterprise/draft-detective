import { AlertCircle, type LucideIcon } from 'lucide-react';
import { Card, CardContent } from '../ui/card';

interface EmptyStateProps {
  /** Icon to display - can be a LucideIcon component or a ReactNode */
  icon?: LucideIcon | React.ReactNode;
  /** Main message text (alias for title for backward compatibility) */
  message?: string;
  /** Title text (alias for message) */
  title?: string;
  /** Optional secondary description */
  description?: string;
  /** Optional custom content to render below the message */
  children?: React.ReactNode;
}

/**
 * Reusable empty state component for displaying "no data" messages.
 * Used across workflow results when no data is available.
 *
 * Supports two patterns:
 * - Simple: <EmptyState message="No data" />
 * - Rich: <EmptyState icon={<CustomIcon />} title="Title" description="Description" />
 */
export function EmptyState({ icon, message, title, description, children }: EmptyStateProps) {
  // Support both message and title for backward compatibility
  const displayMessage = message ?? title;

  // Render icon - support both LucideIcon components and ReactNode
  const renderIcon = () => {
    if (!icon) {
      return <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto" />;
    }

    // Check if icon is a React element (ReactNode) or a LucideIcon component
    if (typeof icon === 'object' && 'type' in (icon as React.ReactElement)) {
      // It's a ReactNode, render directly
      return <div className="mx-auto">{icon}</div>;
    }

    // It's a LucideIcon component, render it with default styles
    const IconComponent = icon as LucideIcon;
    return <IconComponent className="h-8 w-8 text-muted-foreground mx-auto" />;
  };

  return (
    <Card>
      <CardContent className="flex items-center justify-center py-12">
        <div className="text-center space-y-2">
          {renderIcon()}
          {displayMessage && <p className="text-sm text-muted-foreground">{displayMessage}</p>}
          {description && <p className="text-xs text-muted-foreground max-w-sm mx-auto">{description}</p>}
          {children}
        </div>
      </CardContent>
    </Card>
  );
}
