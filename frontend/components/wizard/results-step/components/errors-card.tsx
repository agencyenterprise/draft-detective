import { WorkflowError } from '@/lib/generated-api';
import { AlertTriangleIcon } from 'lucide-react';

export interface ErrorsCardProps {
  errors: WorkflowError[];
}

export function ErrorsCard({ errors }: ErrorsCardProps) {
  return (
    <div className="bg-red-200/40 p-4 rounded-lg text-sm">
      <h4 className="font-bold mb-2 flex items-center gap-2">
        <AlertTriangleIcon className="w-4 h-4" />
        Unexpected processing errors occurred while processing this chunk / document
      </h4>
      <div className="space-y-2">
        {errors.map((error, ei) => (
          <pre key={ei} className="whitespace-pre-wrap">
            <strong>{error.task_name}:</strong> {error.error}
          </pre>
        ))}
      </div>
    </div>
  );
}
