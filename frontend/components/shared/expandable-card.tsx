'use client';

import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader } from '../ui/card';

interface ExpandableCardProps {
  /** Content to render in the card header (clickable area) */
  header: React.ReactNode;
  /** Content to render when expanded */
  children: React.ReactNode;
  /** Optional className for the Card component */
  className?: string;
  /** Whether the card should be expanded by default */
  defaultOpen?: boolean;
  /** Optional className for the CardContent */
  contentClassName?: string;
}

/**
 * Reusable expandable card component with chevron toggle.
 * Used for collapsible result cards across workflow results.
 */
export function ExpandableCard({
  header,
  children,
  className,
  defaultOpen = false,
  contentClassName,
}: ExpandableCardProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <Card className={className}>
      <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setIsOpen(!isOpen)}>
        <div className="flex items-center justify-between">
          <div className="flex-1">{header}</div>
          <ChevronDown className={cn('h-4 w-4 transition-transform flex-shrink-0 ml-2', isOpen && 'rotate-180')} />
        </div>
      </CardHeader>
      {isOpen && <CardContent className={cn('pt-0', contentClassName)}>{children}</CardContent>}
    </Card>
  );
}
