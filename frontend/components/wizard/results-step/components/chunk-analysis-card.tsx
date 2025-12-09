'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClaimSubstantiatorStateSummary, DocumentChunkOutput } from '@/lib/generated-api';
import { getChunkIssues, getMaxSeverity } from '@/lib/severity';
import { ChevronDownIcon, ChevronRightIcon, LinkIcon, MessageCirclePlus } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { AnalysisResultCard } from './analysis-result-card';
import { DocumentIssueCardMinimal } from './document-issue-card';
import { ExpandableResultSection } from './expandable-result-section';

export interface ChunkAnalysisCardProps {
  results: ClaimSubstantiatorStateSummary;
  chunk: DocumentChunkOutput;
}

export function ChunkAnalysisCard({ results, chunk }: ChunkAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const references = results?.references || [];
  const supportingFiles = results?.supportingFiles || [];
  const citationsWithBibliography = chunk.citations?.citations?.filter((citation) => citation.associatedBibliography);
  const chunkIssues = getChunkIssues(results, chunk.chunkIndex);
  const maxSeverity = getMaxSeverity(chunkIssues);

  return (
    <AnalysisResultCard title="Chunk Analysis" severity={maxSeverity}>
      {!chunkIssues.length && <p className="text-muted-foreground">No issues found for this chunk.</p>}

      {chunkIssues.map((issue, issueIndex) => (
        <DocumentIssueCardMinimal key={issueIndex} issue={issue} />
      ))}

      <div className="flex items-center justify-end">
        <Button variant="ghost" size="xs" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
          {isExpanded ? 'Hide details' : 'Show details'}
        </Button>
      </div>

      {isExpanded && (
        <>
          <div className="space-y-2">
            <ExpandableResultSection
              initialIsExpanded={false}
              title={
                <h3 className="font-semibold flex items-center gap-2">
                  <MessageCirclePlus className="w-4 h-4" /> Claim extraction rationale
                </h3>
              }
            >
              <p>{chunk.claims?.rationale}</p>
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
              {chunk.citations?.citations?.length === 0 && <p className="text-muted-foreground">No citations found</p>}

              {chunk.citations?.citations?.map((citation, index) => {
                const matchedReference = citation.indexOfAssociatedBibliography
                  ? references[citation.indexOfAssociatedBibliography - 1]
                  : null;
                const matchedSupportingFile = supportingFiles.find(
                  (file) => file.fileName === matchedReference?.nameOfAssociatedSupportingDocument,
                );

                return (
                  <div key={index} className="bg-muted p-3 rounded-md space-y-1">
                    <LabeledValue label="Associated text">{citation.text}</LabeledValue>
                    <LabeledValue label="Format">{citation.format}</LabeledValue>
                    <LabeledValue label="Type">{citation.type}</LabeledValue>
                    <LabeledValue label="Needs bibliography">{citation.needsBibliography ? 'Yes' : 'No'}</LabeledValue>
                    <LabeledValue label="Associated reference file">
                      {matchedSupportingFile && matchedSupportingFile.fileId ? (
                        <Link
                          href={`/api/files/download/${matchedSupportingFile.fileId}`}
                          target="_blank"
                          className="text-blue-600 underline"
                        >
                          {matchedSupportingFile.fileName}
                        </Link>
                      ) : (
                        'None'
                      )}
                    </LabeledValue>
                    <LabeledValue label="Associated bibliography">{citation.associatedBibliography}</LabeledValue>
                    <LabeledValue label="Rationale">{citation.rationale}</LabeledValue>
                  </div>
                );
              })}
            </ExpandableResultSection>
          </div>
        </>
      )}
    </AnalysisResultCard>
  );
}
