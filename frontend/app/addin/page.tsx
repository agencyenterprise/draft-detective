'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { DocumentIssuesList } from '@/components/wizard/results-step/components/document-issues-list';
import { ProjectFeedbackProvider } from '@/lib/contexts/project-feedback-context';
import { Issue, getSharedResourceApiPublicShareTokenGet } from '@/lib/generated-api';
import { addIssueMarkers } from '@/lib/addin/office-utils';
import { useOfficeInit } from '@/lib/addin/use-office-init';
import { RotateCwIcon } from 'lucide-react';

export default function AddinPage() {
  const { token, currentParagraphIndex, isInitialized } = useOfficeInit();
  const [issuesPerParagraph, setIssuesPerParagraph] = useState<Map<number, Issue[]>>(new Map());

  const {
    data: project,
    isLoading,
    error,
    refetch,
  } = useQuery({
    enabled: !!token,
    queryKey: ['share', token],
    // Cache for 10 minutes
    staleTime: 60 * 1000 * 10,
    queryFn: () =>
      getSharedResourceApiPublicShareTokenGet({
        path: { token: token! },
      }),
  });

  useEffect(() => {
    if (project?.issues?.length) {
      addIssueMarkers(project.issues)
        .then(setIssuesPerParagraph)
        .catch((e) => console.error('Error adding markers', e));
    }
  }, [project]);

  const filteredIssues = useMemo(() => {
    if (!project?.issues || currentParagraphIndex === null) return [];
    return issuesPerParagraph.get(currentParagraphIndex) ?? [];
  }, [project, currentParagraphIndex, issuesPerParagraph]);

  if (!isInitialized) return <div className="p-4 text-center">Loading Add-in...</div>;

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 p-4 flex flex-col">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-sm text-gray-600 max-w-md">No project associated with this document.</div>
        </div>
      </div>
    );
  }

  return (
    <ProjectFeedbackProvider projectId={undefined}>
      <div className="flex flex-col h-screen bg-white">
        <div className="border-b p-3 flex justify-between items-center bg-gray-50">
          <h1 className="font-semibold text-sm">Review Issues</h1>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={() => refetch()} disabled={isLoading} title="Refresh">
              <RotateCwIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
          {error ? (
            <div className="text-red-500 text-sm">Failed to load issues. Please check your settings.</div>
          ) : null}

          {isLoading ? (
            <div className="text-sm text-gray-500">Loading...</div>
          ) : filteredIssues.length > 0 ? (
            <>
              <div className="text-xs text-gray-500 border-b pb-2 mb-2">Paragraph issues</div>
              <DocumentIssuesList issues={filteredIssues} onSelect={() => {}} hideJumpToChunk readOnly />
            </>
          ) : (
            <>
              <div className="text-xs text-gray-500 border-b pb-2 mb-2">All issues</div>
              <DocumentIssuesList issues={project?.issues ?? []} onSelect={() => {}} hideJumpToChunk readOnly />
            </>
          )}
        </div>
      </div>
    </ProjectFeedbackProvider>
  );
}
