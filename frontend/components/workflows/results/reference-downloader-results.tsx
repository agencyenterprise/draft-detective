'use client';

import { ReferenceDownloaderResultsDisplay } from './reference-downloader-results-display';
import { EmptyState } from '@/components/shared/empty-state';
import { ReferenceDownloaderState, WorkflowRunDetail } from '@/lib/generated-api';
import * as React from 'react';

interface ReferenceDownloaderResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function ReferenceDownloaderResults({ workflowDetail }: ReferenceDownloaderResultsProps) {
  const results = workflowDetail.state as ReferenceDownloaderState | undefined;
  const fetchedReferences = React.useMemo(() => results?.fetched_references ?? [], [results?.fetched_references]);
  const projectId = workflowDetail.run.project_id;

  if (fetchedReferences.length === 0) {
    return <EmptyState message="No reference download results available." />;
  }

  return <ReferenceDownloaderResultsDisplay results={fetchedReferences} projectId={projectId} title={null} />;
}
