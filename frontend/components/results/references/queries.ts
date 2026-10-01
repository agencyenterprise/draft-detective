import { formatFileSize } from '@/components/analysis-form/utils';
import { composeReferences } from '@/lib/composed-references';
import { MatchSource, ProjectOverview, ReferenceFetchStatus, WorkflowRunType } from '@/lib/generated-api';
import { useProjectReferences } from '@/lib/hooks/use-project-data';
import { findRunByType } from '@/lib/workflow-state';
import { useMemo } from 'react';
import { ReferenceReviewItem } from './types';

export function useReferenceReviewReferences(overview: ProjectOverview) {
  const files = useMemo(() => overview.files ?? [], [overview.files]);
  const hasExtraction = !!findRunByType(overview.workflow_runs ?? [], WorkflowRunType.ReferenceExtraction);
  const { data: referenceData, isLoading, isPlaceholderData, error } = useProjectReferences(overview);

  // Compose references from extraction and file matching states
  const composedReferences = useMemo(
    () => composeReferences(referenceData?.extracted_references, referenceData?.matches, files),
    [referenceData?.extracted_references, referenceData?.matches, files],
  );

  const references = useMemo(() => {
    if (!hasExtraction) {
      return [];
    }

    return composedReferences.map((item, index): ReferenceReviewItem => {
      const matchedFile = item.file_id ? files?.find((file) => file.id === item.file_id) : undefined;
      const fetchedReference = referenceData?.fetched_references?.find((ref) => ref.reference_id === item.id);

      // Hide fetch results when the file was manually uploaded by the user — the fetch outcome is
      // irrelevant once a user-uploaded source is in place. Otherwise always surface the fetch
      // result (including "Not Found" / errored outcomes) so users can see why no source is attached.
      const shouldShowFetchedResult = !!fetchedReference && item.source !== MatchSource.ManualUpload;

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
              size: formatFileSize(matchedFile.file_size),
            }
          : null,
        source: item.source,
        fetchResult: shouldShowFetchedResult ? fetchedReference : null,
      };
    });
  }, [composedReferences, files, hasExtraction, referenceData?.fetched_references]);

  return {
    references,
    isLoading: hasExtraction && isLoading,
    // The previous version's references, shown while a newer one loads; fine
    // to display, but not to decide on.
    isStale: hasExtraction && isPlaceholderData,
    error: hasExtraction ? error : null,
  };
}
