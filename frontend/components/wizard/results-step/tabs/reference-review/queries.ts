import { ReferenceFetchStatus, WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef } from 'react';
import { ReferenceReviewItem } from './types';
import { useProjectFiles } from '@/lib/hooks/use-project-files';
import { formatFileSize } from '@/components/analysis-form/utils';

export function useReferenceReviewReferences(projectId: string) {
  const queryClient = useQueryClient();
  const projectDetail = useProjectDetails(projectId);
  const { data: files } = useProjectFiles(projectId);

  const { referenceExtraction, referenceDownloader } = useMemo(() => {
    const allWorkflowDetails = projectDetail?.workflowDetails ?? [];
    return {
      referenceExtraction: getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceExtraction),
      referenceDownloader: getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceDownloader),
    };
  }, [projectDetail?.workflowDetails]);

  // Track if we were previously processing to detect completion
  const wasProcessingRef = useRef(false);
  const isProcessing = isWorkflowProcessing(referenceDownloader);

  // Poll files every 3 seconds while reference downloader is running
  // and invalidate once more when it completes
  useEffect(() => {
    if (isProcessing) {
      wasProcessingRef.current = true;
      const interval = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ['files', projectId] });
      }, 3000);
      return () => clearInterval(interval);
    } else if (wasProcessingRef.current) {
      // Workflow just finished - do final invalidation
      wasProcessingRef.current = false;
      queryClient.invalidateQueries({ queryKey: ['files', projectId] });
    }
  }, [isProcessing, projectId, queryClient]);

  const references = useMemo(() => {
    if (!referenceExtraction) {
      return [];
    }

    const bibliographyItems = referenceExtraction.state?.references ?? [];

    return bibliographyItems.map((item, index): ReferenceReviewItem => {
      const matchedFile = files?.find((file) => file.id === item.file_id);
      const fetchedReference = referenceDownloader?.state?.fetched_references?.find(
        (ref) => ref.input_reference === item.text,
      );

      // In case the reference was fetched but the matching file no longer exists, we don't want to show the fetched result
      const shouldShowFetchedResult = fetchedReference && (fetchedReference.result?.file_id ? !!matchedFile : true);

      return {
        index,
        text: item.text,
        status:
          fetchedReference?.status === ReferenceFetchStatus.Pending
            ? 'fetching'
            : matchedFile
              ? 'matched'
              : 'unmatched',
        matchedFile: matchedFile
          ? {
              id: matchedFile.id,
              name: item.name_of_associated_supporting_document,
              url: `/api/files/download/${item.file_id}`,
              size: formatFileSize(matchedFile.file_size),
            }
          : null,
        fetchResult: shouldShowFetchedResult ? fetchedReference : null,
      };
    });
  }, [files, referenceExtraction, referenceDownloader]);

  return references;
}
