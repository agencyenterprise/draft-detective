import { Card } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

export function ExtractionProcessing() {
  return (
    <div className="space-y-4">
      <Card className="p-8">
        <div className="text-center space-y-4">
          <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Processing Document</h3>
            <p className="text-sm text-muted-foreground mt-2">Extracting references from your document...</p>
            <p className="text-xs text-muted-foreground mt-1">
              This page can be safely closed - your progress is saved
            </p>
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">References</h2>
          <div className="h-4 w-24 bg-gray-200 rounded animate-pulse"></div>
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="p-3 border border-gray-200 rounded-md">
              <div className="flex items-start gap-3">
                <div className="h-4 w-8 bg-gray-200 rounded animate-pulse mt-0.5"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded animate-pulse w-full"></div>
                  <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
