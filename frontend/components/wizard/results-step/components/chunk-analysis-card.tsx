'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Badge } from '@/components/ui/badge';
import { FileDownloadLink } from '@/components/ui/file-download-link';
import { getChunkId } from '@/lib/chunk-ids';
import { composeReferences } from '@/lib/composed-references';
import { ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { LinkIcon, MessageCirclePlus } from 'lucide-react';
import { useMemo } from 'react';
import { AnalysisResultCard } from './analysis-result-card';
import { ExpandableResultSection } from './expandable-result-section';
import { Markdown } from '@/components/markdown';

export interface ChunkAnalysisCardProps {
  chunkIndex: number;
  projectDetail: ProjectDetailed;
}

export function ChunkAnalysisCard({ chunkIndex, projectDetail }: ChunkAnalysisCardProps) {
  const workflowDetails = useMemo(() => projectDetail.workflow_runs ?? [], [projectDetail.workflow_runs]);
  const files = useMemo(() => projectDetail.files ?? [], [projectDetail.files]);

  const claimExtractionDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ClaimExtraction),
    [workflowDetails],
  );
  const referenceExtractionDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceExtraction),
    [workflowDetails],
  );
  const referenceFileMatchingDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.ReferenceFileMatching),
    [workflowDetails],
  );
  const citationDetectionDetail = useMemo(
    () => getWorkflowRunByType(workflowDetails, WorkflowRunType.CitationDetection),
    [workflowDetails],
  );

  const chunkClaims = claimExtractionDetail?.state?.claims?.find((c) => c.chunk_index === chunkIndex);

  // Compose references from extraction and file matching states
  const references = useMemo(
    () =>
      composeReferences(
        referenceExtractionDetail?.state?.extracted_references,
        referenceFileMatchingDetail?.state?.matches,
        files,
      ),
    [referenceExtractionDetail?.state?.extracted_references, referenceFileMatchingDetail?.state?.matches, files],
  );
  const citations =
    citationDetectionDetail?.state?.citations
      ?.filter((citation) => citation.chunk_index === chunkIndex)
      .flatMap((citation) => citation.citations ?? []) ?? [];
  const citationsWithBibliography = citations.filter((citation) => citation.associated_bibliography);

  return (
    <AnalysisResultCard id={getChunkId(chunkIndex)} title="Chunk Analysis">
      <div className="space-y-2">
        <ExpandableResultSection
          initialIsExpanded={false}
          title={
            <h3 className="font-semibold flex items-center gap-2">
              <MessageCirclePlus className="w-4 h-4" /> Claim extraction rationale
            </h3>
          }
        >
          <p>{chunkClaims?.rationale}</p>
        </ExpandableResultSection>

        <ExpandableResultSection
          title={
            <div className="flex items-center gap-2">
              <h3 className="font-semibold flex items-center gap-2">
                <LinkIcon className="w-4 h-4" /> Citations
              </h3>

              <Badge variant="outline">{citationsWithBibliography?.length || 0} with bibliography</Badge>
            </div>
          }
        >
          {citations.length === 0 && <p className="text-muted-foreground">No citations found</p>}

          {citations.map((citation, index) => {
            const matchedReference = citation.index_of_associated_bibliography
              ? references[citation.index_of_associated_bibliography - 1]
              : null;
            const matchedSupportingFile = files?.find((file) => file.id === matchedReference?.file_id);

            return (
              <div key={index} className="bg-muted p-3 rounded-md space-y-1">
                <LabeledValue label="Associated text">{citation.text}</LabeledValue>
                <LabeledValue label="Format">{citation.format}</LabeledValue>
                <LabeledValue label="Type">{citation.type}</LabeledValue>
                <LabeledValue label="Needs bibliography">{citation.needs_bibliography ? 'Yes' : 'No'}</LabeledValue>
                <LabeledValue label="Associated bibliography index">
                  {citation.index_of_associated_bibliography}
                </LabeledValue>
                <LabeledValue label="Associated bibliography">
                  <Markdown>{citation.associated_bibliography}</Markdown>
                </LabeledValue>
                <LabeledValue label="Rationale">{citation.rationale}</LabeledValue>
                <LabeledValue label="Associated reference file">
                  {matchedSupportingFile ? (
                    <FileDownloadLink fileId={matchedSupportingFile.id} className="text-blue-600 underline">
                      {matchedSupportingFile.file_name}
                    </FileDownloadLink>
                  ) : (
                    'None'
                  )}
                </LabeledValue>
              </div>
            );
          })}
        </ExpandableResultSection>
      </div>
    </AnalysisResultCard>
  );
}
