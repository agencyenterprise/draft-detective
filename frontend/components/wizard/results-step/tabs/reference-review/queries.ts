import { formatFileSize } from '@/components/analysis-form/utils';
import { composeReferences } from '@/lib/composed-references';
import { BibliographyItemValidation, ReferenceFetchStatus, WorkflowRunType } from '@/lib/generated-api';
import { useProjectDetails } from '@/lib/hooks/use-project-details';
import { useProjectFiles } from '@/lib/hooks/use-project-files';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef } from 'react';
import { ReferenceReviewItem } from './types';

export function useReferenceReviewReferences(projectId: string) {
  const queryClient = useQueryClient();
  const projectDetail = useProjectDetails(projectId);
  const { data: files } = useProjectFiles(projectId);

  const { referenceExtraction, referenceFileMatching, referenceDownloader, referenceValidation } = useMemo(() => {
    const allWorkflowDetails = projectDetail?.workflowDetails ?? [];
    return {
      referenceExtraction: getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceExtraction),
      referenceFileMatching: getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceFileMatching),
      referenceDownloader: getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceDownloader),
      referenceValidation: getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceValidation),
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

  // Compose references from extraction and file matching states
  const composedReferences = useMemo(
    () =>
      composeReferences(referenceExtraction?.state?.extracted_references, referenceFileMatching?.state?.matches, files),
    [referenceExtraction?.state?.extracted_references, referenceFileMatching?.state?.matches, files],
  );

  // Create validation map from reference validation workflow
  const validationMap = useMemo(() => {
    const map = new Map<string, BibliographyItemValidation>();
    referenceValidation?.state?.reference_validations?.forEach((v) => {
      if (v.original_reference) {
        map.set(v.original_reference, v);
      }
    });
    return map;
  }, [referenceValidation?.state?.reference_validations]);

  const references = useMemo(() => {
    if (!referenceExtraction) {
      return [];
    }

    return composedReferences.map((item, index): ReferenceReviewItem => {
      const matchedFile = item.file_id ? files?.find((file) => file.id === item.file_id) : undefined;
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
              name: matchedFile.file_name,
              url: `/api/files/download/${matchedFile.id}`,
              size: formatFileSize(matchedFile.file_size),
            }
          : null,
        fetchResult: shouldShowFetchedResult ? fetchedReference : null,
        validation: validationMap.get(item.text) || null,
      };
    });
  }, [composedReferences, files, referenceExtraction, referenceDownloader, validationMap]);

  return references;
}
