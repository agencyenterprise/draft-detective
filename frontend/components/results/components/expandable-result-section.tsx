import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';

export interface ExpandableResultSectionProps {
  title: React.ReactNode;
  children: React.ReactNode;
  initialIsExpanded?: boolean;
}

export function ExpandableResultSection({ title, children, initialIsExpanded = false }: ExpandableResultSectionProps) {
  const [isExpanded, setIsExpanded] = useState(initialIsExpanded);

  return (
    <div className="border-b pb-2 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">{title}</div>

        <Button
          variant="ghost"
          size="xs"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-gray-600 hover:text-gray-900"
        >
          {isExpanded ? (
            <>
              <ChevronDown />
              Hide Details
            </>
          ) : (
            <>
              <ChevronRight />
              Show Details
            </>
          )}
        </Button>
      </div>

      {isExpanded && <div className="space-y-2">{children}</div>}
    </div>
  );
}
