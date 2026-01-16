'use client';

import { ReferenceDownloaderResultsDisplay } from '@/app/(authenticated)/tools/reference-downloader/components/reference-downloader-results-display';
import { Card, CardContent } from '@/components/ui/card';
import { ReferenceDownloaderState, WorkflowRunDetail } from '@/lib/generated-api';
import { AlertCircle } from 'lucide-react';
import * as React from 'react';

interface ReferenceDownloaderResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function ReferenceDownloaderResults({ workflowDetail }: ReferenceDownloaderResultsProps) {
  const results = workflowDetail.state as ReferenceDownloaderState | undefined;
  const fetchedReferences = React.useMemo(() => results?.fetched_references ?? [], [results?.fetched_references]);
  const projectId = workflowDetail.run.project_id;

  if (fetchedReferences.length === 0) {
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

  return <ReferenceDownloaderResultsDisplay results={fetchedReferences} projectId={projectId} title={null} />;
}
