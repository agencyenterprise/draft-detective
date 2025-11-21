'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { BibliographyItem, FileDocument, DocumentChunk } from '@/lib/generated-api';
import { LinkIcon, MessageCirclePlus } from 'lucide-react';
import { ExpandableResultSection } from './expandable-result-section';
import { AiGeneratedLabel } from '@/components/ai-generated-label';
import { apiUrl } from '@/lib/api';
import Link from 'next/link';
import { LabeledValue } from '@/components/labeled-value';

export interface ChunkAnalysisCardProps {
  chunk: DocumentChunk;
  supportingFiles: FileDocument[];
  references: BibliographyItem[];
}

export function ChunkAnalysisCard({ chunk, references, supportingFiles }: ChunkAnalysisCardProps) {
  const citationsWithBibliography = chunk.citations?.citations?.filter((citation) => citation.associatedBibliography);

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="font-medium">Chunk Analysis</p>
          <AiGeneratedLabel />
        </div>

        <div className="space-y-2">
          <ExpandableResultSection
            initialIsExpanded={true}
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
                    {matchedSupportingFile ? (
                      <Link
                        href={`${apiUrl}/api/files/download/${matchedSupportingFile.filePath.split('/').pop()}/${matchedSupportingFile.fileName}`}
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
      </CardContent>
    </Card>
  );
}
