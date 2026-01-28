'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import { FileDownloadLink } from '@/components/ui/file-download-link';
import { ComposedReference } from '@/lib/composed-references';
import { ClaimSubstantiationResultWithClaimIndex, FileDocument } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { BookOpen, ChevronDown, ChevronRight, FileSearch } from 'lucide-react';
import { useState } from 'react';
import { EvidenceAlignmentLevelBadge } from './evidence-alignment-level-badge';

interface SubstantiationResultsProps {
  substantiation: ClaimSubstantiationResultWithClaimIndex;
  references: ComposedReference[];
  supportingFiles: FileDocument[];
  className?: string;
}

export function SubstantiationResults({
  substantiation,
  references,
  supportingFiles,
  className = '',
}: SubstantiationResultsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasCitationBasedEvidence = substantiation.evidence_sources.length > 0;

  return (
    <div className={cn('border-b pb-2 space-y-4', className)}>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-semibold">
            <FileSearch className="h-4 w-4" />
            Claim-Reference Validation
          </h3>

          <Button
            variant="ghost"
            size="xs"
            className="text-gray-600 hover:text-gray-900"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <>
                <ChevronDown />
                Hide Details
              </>
            ) : (
              <>
                <ChevronRight />
                Show Details
              </>
            )}
          </Button>
        </div>

        <EvidenceAlignmentLevelBadge evidenceAlignment={substantiation.evidence_alignment} variant="solid" />
      </div>

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Evidence Alignment">{substantiation.evidence_alignment}</LabeledValue>
          <LabeledValue label="Rationale">{substantiation.rationale}</LabeledValue>
          <LabeledValue label="Feedback to resolve">{substantiation.feedback}</LabeledValue>

          {/* Citation-Based Evidence Section */}
          {hasCitationBasedEvidence && (
            <div className="mt-4">
              <Accordion type="single" collapsible defaultValue="citation-based">
                <AccordionItem value="citation-based" className="border rounded-md px-3">
                  <AccordionTrigger className="text-sm font-medium hover:no-underline">
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4" />
                      Citation-Based Evidence ({substantiation.evidence_sources.length})
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 mt-2">
                      {substantiation.evidence_sources.map((source, index) => {
                        // Find file by file_name since that's what source.reference_file_name contains
                        const matchedFile = supportingFiles.find(
                          (file) => file.file_name === source.reference_file_name,
                        );
                        // Find reference using file_id for accurate matching
                        const matchedReference = matchedFile
                          ? references.find((reference) => reference.file_id === matchedFile.file_id)
                          : undefined;

                        return (
                          <div key={index} className="bg-muted p-3 rounded-md space-y-1">
                            <p className="font-medium text-sm">
                              Source {index + 1} of {substantiation.evidence_sources.length}
                            </p>
                            <LabeledValue label="Reference">
                              {matchedFile && matchedFile.file_id ? (
                                <>
                                  <FileDownloadLink
                                    fileId={matchedFile.file_id}
                                    className="text-blue-600 underline text-sm"
                                  >
                                    {source.reference_file_name}
                                  </FileDownloadLink>{' '}
                                  <span className="text-muted-foreground text-sm"> - {matchedReference?.text}</span>
                                </>
                              ) : (
                                <span className="text-muted-foreground text-sm">{source.reference_file_name}</span>
                              )}
                            </LabeledValue>
                            <LabeledValue label="Location">{source.location}</LabeledValue>
                            <LabeledValue label="Quote">&quot;{source.quote}&quot;</LabeledValue>
                          </div>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          )}

          {!hasCitationBasedEvidence && <p className="text-muted-foreground text-sm">No evidence sources found.</p>}
        </div>
      )}
    </div>
  );
}
