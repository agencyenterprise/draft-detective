import { formatFileSize } from '@/components/analysis-form/utils';
import { composeReferences } from '@/lib/composed-references';
import {
  BibliographyItemValidation,
  ProjectDetailed,
  ReferenceFetchStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { useMemo } from 'react';
import { ReferenceReviewItem } from './types';

export function useReferenceReviewReferences(projectDetail: ProjectDetailed | undefined) {
  const files = useMemo(() => projectDetail?.files ?? [], [projectDetail?.files]);
  const workflowDetails = useMemo(() => projectDetail?.workflow_runs ?? [], [projectDetail?.workflow_runs]);

  const { referenceExtraction, referenceFileMatching, referenceDownloader, referenceValidation } = useMemo(() => {
    return {
      referenceExtraction: getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction),
      referenceFileMatching: getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching),
      referenceDownloader: getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceDownloader),
      referenceValidation: getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceValidation),
    };
  }, [workflowDetails]);

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
        (ref) => ref.reference_id === item.id,
      );

      // In case the reference was fetched but the matching file no longer exists, we don't want to show the fetched result
      const shouldShowFetchedResult = fetchedReference && (fetchedReference.result?.file_id ? !!matchedFile : true);

      return {
        id: item.id,
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
