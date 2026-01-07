'use client';

import { ReferenceItem } from '@/app/(authenticated)/tools/reference-downloader/components/reference-item';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import {
  ReferenceDownloaderState,
  ReferenceFetchConclusion,
  ReferenceFetchItem,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import { AlertCircle, Download, Loader2 } from 'lucide-react';
import * as React from 'react';

interface ReferenceDownloaderResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function ReferenceDownloaderResults({ workflowDetail }: ReferenceDownloaderResultsProps) {
  const results = workflowDetail.state as ReferenceDownloaderState | undefined;

  const fetchedReferences = React.useMemo(() => results?.fetched_references ?? [], [results?.fetched_references]);

  const projectId = workflowDetail.run.project_id;
  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId);

  // Calculate statistics
  const totalReferences = fetchedReferences.length;
  const foundCount = fetchedReferences.filter(
    (item) => item.final_conclusion === ReferenceFetchConclusion.SourceFound,
  ).length;
  const notFoundCount = fetchedReferences.filter(
    (item) => item.final_conclusion === ReferenceFetchConclusion.SourceNotFound,
  ).length;
  const notAccessibleCount = fetchedReferences.filter(
    (item) => item.final_conclusion === ReferenceFetchConclusion.SourceFoundButNotAccessible,
  ).length;
  const hasDownloadedReferences = fetchedReferences.some((item) => item.file_id !== null);

  if (totalReferences === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground">No reference download results available.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="ml-auto">
            {totalReferences} Reference{totalReferences !== 1 ? 's' : ''}
          </Badge>
          {foundCount > 0 && (
            <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">
              {foundCount} Found
            </Badge>
          )}
          {notAccessibleCount > 0 && (
            <Badge variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-300">
              {notAccessibleCount} Not Accessible
            </Badge>
          )}
          {notFoundCount > 0 && (
            <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
              {notFoundCount} Not Found
            </Badge>
          )}
        </div>

        {projectId && hasDownloadedReferences && (
          <div className="flex justify-end">
            <Button onClick={downloadAll} disabled={isDownloading} variant="outline" size="sm">
              {isDownloading ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Preparing download...
                </>
              ) : (
                <>
                  <Download className="size-4 mr-2" />
                  Download all files (.zip)
                </>
              )}
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {fetchedReferences.map((item: ReferenceFetchItem, index: number) => (
          <ReferenceItem key={index} item={item} index={index} />
        ))}
      </div>
    </div>
  );
}
