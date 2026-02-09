'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { DocumentIssuesList } from '@/components/wizard/results-step/components/document-issues-list';
import { DocumentIssue, getSharedResourceApiPublicShareTokenGet } from '@/lib/generated-api';
import { loadSettings, getCurrentParagraphIndex, addIssueMarkers } from '@/lib/addin/office-utils';
import { RotateCwIcon } from 'lucide-react';

// Office onReady check to prevent double initialization issues
let isOfficeReady = false;

const debounce = <Args extends unknown[]>(func: (...args: Args) => void, wait: number) => {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  return (...args: Args) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

export default function AddinPage() {
  const [token, setTokenState] = useState<string | null>(null);
  const [currentParagraphIndex, setCurrentParagraphIndex] = useState<number | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [issuesPerParagraph, setIssuesPerParagraph] = useState<Map<number, DocumentIssue[]>>(new Map());

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      try {
        if (typeof Office === 'undefined') {
          let attempts = 0;
          const maxAttempts = 50; // 10 seconds max wait

          while (typeof Office === 'undefined' && attempts < maxAttempts && mounted) {
            await new Promise((resolve) => setTimeout(resolve, 200));
            attempts++;
          }

          if (typeof Office === 'undefined') {
            console.warn('Office.js not available, running in browser mode');
            setIsInitialized(true);
            return;
          }
        }

        await Office.onReady(async (info) => {
          if (!mounted) return;

          if (isOfficeReady) return;
          isOfficeReady = true;

          if (info.host !== Office.HostType.Word) {
            console.warn('Add-in is not running in Word');
            setIsInitialized(true);
            return;
          }

          const { authToken: savedToken } = await loadSettings();

          try {
            if (Office.addin && Office.addin.setStartupBehavior) {
              await Office.addin.setStartupBehavior(Office.StartupBehavior.load);
            }
          } catch (e) {
            console.error('Error setting startup behavior:', e);
          }

          // If we are running, show the taskpane
          try {
            if (Office.addin && Office.addin.showAsTaskpane) {
              await Office.addin.showAsTaskpane();
            }
          } catch (e) {
            console.error('Error showing taskpane:', e);
          }

          if (mounted) {
            setTokenState(savedToken);
          }

          // Register selection handler
          if (Office.context && Office.context.document) {
            Office.context.document.addHandlerAsync(
              Office.EventType.DocumentSelectionChanged,
              debouncedUpdate,
              (result) => {
                if (result.status === Office.AsyncResultStatus.Failed) {
                  console.error('Failed to add handler', result.error);
                }
              },
            );
            updateCurrentParagraph();
          }

          if (mounted) {
            setIsInitialized(true);
          }
        });
      } catch (e) {
        console.error('Failed to initialize Office', e);
        if (mounted) {
          setIsInitialized(true);
        }
      }
    };

    const updateCurrentParagraph = async () => {
      if (typeof Word === 'undefined') return;
      try {
        const index = await getCurrentParagraphIndex();
        setCurrentParagraphIndex(index);
      } catch (e) {
        console.error('Error getting paragraph index:', e);
      }
    };

    const debouncedUpdate = debounce(updateCurrentParagraph, 300);

    init();

    return () => {
      mounted = false;
    };
  }, []);

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
  }, [project, currentParagraphIndex]);

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
    <div className="flex flex-col h-screen bg-white">
      <div className="border-b p-3 flex justify-between items-center bg-gray-50">
        <h1 className="font-semibold text-sm">Review Issues</h1>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => refetch()} disabled={isLoading} title="Refresh">
            <RotateCwIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {error ? <div className="text-red-500 text-sm">Failed to load issues. Please check your settings.</div> : null}

        {isLoading ? (
          <div className="text-sm text-gray-500">Loading...</div>
        ) : filteredIssues.length > 0 ? (
          <>
            <div className="text-xs text-gray-500 border-b pb-2 mb-2">Paragraph issues</div>
            <DocumentIssuesList issues={filteredIssues} onSelect={() => {}} hideJumpToChunk />
          </>
        ) : (
          <>
            <div className="text-xs text-gray-500 border-b pb-2 mb-2">All issues</div>
            <DocumentIssuesList issues={project?.issues ?? []} onSelect={() => {}} hideJumpToChunk />
          </>
        )}
      </div>
    </div>
  );
}
