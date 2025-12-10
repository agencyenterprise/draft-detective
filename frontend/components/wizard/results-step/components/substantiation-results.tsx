'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import {
  BibliographyItem,
  ClaimSubstantiationResultWithClaimIndex,
  FileDocumentOutput,
  RetrievedPassageInfo,
} from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { BookOpen, ChevronDown, ChevronRight, FileSearch } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { EvidenceAlignmentLevelBadge } from './evidence-alignment-level-badge';

interface SubstantiationResultsProps {
  substantiation: ClaimSubstantiationResultWithClaimIndex;
  references: BibliographyItem[];
  supportingFiles: FileDocumentOutput[];
  retrievedPassages?: RetrievedPassageInfo[];
  className?: string;
}

export function SubstantiationResults({
  substantiation,
  references,
  supportingFiles,
  retrievedPassages,
  className = '',
}: SubstantiationResultsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const hasCitationBasedEvidence = substantiation.evidenceSources.length > 0;
  const hasRagEvidence = retrievedPassages && retrievedPassages.length > 0;

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

        <EvidenceAlignmentLevelBadge evidenceAlignment={substantiation.evidenceAlignment} variant="solid" />
      </div>

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Evidence Alignment">{substantiation.evidenceAlignment}</LabeledValue>
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
                      Citation-Based Evidence ({substantiation.evidenceSources.length})
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 mt-2">
                      {substantiation.evidenceSources.map((source, index) => {
                        const matchedReference = references.find(
                          (reference) => reference.nameOfAssociatedSupportingDocument === source.referenceFileName,
                        );
                        const matchedFile = supportingFiles.find((file) => file.fileName === source.referenceFileName);

                        return (
                          <div key={index} className="bg-muted p-3 rounded-md space-y-1">
                            <p className="font-medium text-sm">
                              Source {index + 1} of {substantiation.evidenceSources.length}
                            </p>
                            <LabeledValue label="Reference">
                              {matchedFile && matchedFile.fileId ? (
                                <>
                                  <Link
                                    href={`/api/files/download/${matchedFile.fileId}`}
                                    target="_blank"
                                    className="text-blue-600 underline text-sm"
                                  >
                                    {source.referenceFileName}
                                  </Link>{' '}
                                  <span className="text-muted-foreground text-sm"> - {matchedReference?.text}</span>
                                </>
                              ) : (
                                <span className="text-muted-foreground text-sm">{source.referenceFileName}</span>
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

          {!hasCitationBasedEvidence && !hasRagEvidence && (
            <p className="text-muted-foreground text-sm">No evidence sources found.</p>
          )}
        </div>
      )}
    </div>
  );
}
