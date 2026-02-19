import { WorkflowError } from '@/lib/generated-api';
import { AlertTriangleIcon } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

export interface ErrorsCardProps {
  errors: WorkflowError[];
  maxCount?: number;
}

export function ErrorsCard({ errors, maxCount = 3 }: ErrorsCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const displayErrors = isExpanded ? errors : errors.slice(0, maxCount);
  const hasMore = errors.length > maxCount;

  return (
    <div className="bg-red-200/40 p-4 rounded-lg text-sm">
      <h4 className="font-bold mb-2 flex items-center gap-2">
        <AlertTriangleIcon className="w-4 h-4" />
        Unexpected processing errors occurred while processing this chunk / document
      </h4>
      <div className="space-y-2">
        {displayErrors.map((error, ei) => (
          <pre key={ei} className="whitespace-pre-wrap break-words">
            <strong>{error.task_name}:</strong> {error.error}
          </pre>
        ))}
      </div>
      {hasMore && (
        <div className="flex items-center justify-center">
          <Button variant="ghost" size="sm" onClick={() => setIsExpanded(!isExpanded)} className="mt-2 text-xs">
            {isExpanded ? 'Show less' : `Show more (${errors.length - maxCount} more)`}
          </Button>
        </div>
      )}
    </div>
  );
}
