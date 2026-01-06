'use client';

import { ReferenceFetchItem } from '@/lib/generated-api';
import { Button } from '@/components/ui/button';
import { Download, Loader2 } from 'lucide-react';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import { ReferenceItem } from './reference-item';

interface ReferenceDownloaderResultsDisplayProps {
  results: ReferenceFetchItem[];
  projectId: string | null | undefined;
}

export function ReferenceDownloaderResultsDisplay({ results, projectId }: ReferenceDownloaderResultsDisplayProps) {
  const hasDownloadedReferences = results.some((item) => item.file_id !== null);
  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Results</h3>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            {results.length} reference{results.length !== 1 ? 's' : ''} checked
          </span>
          {projectId && hasDownloadedReferences && (
            <Button onClick={downloadAll} disabled={isDownloading} variant="outline" size="sm">
              {isDownloading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Preparing download...
                </>
              ) : (
                <>
                  <Download className="size-4" />
                  Download all files (.zip)
                </>
              )}
            </Button>
          )}
        </div>
      </div>
      <div className="space-y-3">
        {results.map((item: ReferenceFetchItem, index: number) => (
          <ReferenceItem key={index} item={item} index={index} />
        ))}
      </div>
    </div>
  );
}
