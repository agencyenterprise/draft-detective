'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  BibliographyItem,
  CitationSuggestionResultWithClaimIndexOutput,
  FileDocumentOutput,
} from '@/lib/generated-api';
import { scoreReference } from '@/lib/reference-scoring';
import { ChevronDown, ChevronRight, Link2Icon } from 'lucide-react';
import { useState } from 'react';
import { CitationReferenceItem } from '../tabs/citation-reference-item';
import { LabeledValue } from '@/components/labeled-value';

interface ClaimCitationSuggestionsProps {
  citationSuggestion: CitationSuggestionResultWithClaimIndexOutput;
  references: BibliographyItem[];
  supportingFiles: FileDocumentOutput[];
}

export function ClaimCitationSuggestions({
  citationSuggestion,
  references,
  supportingFiles,
}: ClaimCitationSuggestionsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const sortedReferences = [...(citationSuggestion.relevantReferences || [])].sort(
    (a, b) => scoreReference(b) - scoreReference(a),
  );

  return (
    <div className="border-b pb-2 space-y-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-semibold">
            <Link2Icon className="h-4 w-4" />
            Citation Suggestions
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

        <Badge variant="outline">{citationSuggestion.relevantReferences.length} reference suggestions</Badge>
      </div>

      {isExpanded && (
        <div className="space-y-2">
          <LabeledValue label="Rationale">{citationSuggestion.rationale}</LabeledValue>
          <h4 className="font-medium">References to add:</h4>
          <div className="space-y-2">
            {sortedReferences.length === 0 && <p className="text-muted-foreground">No suggested references to add.</p>}
            {sortedReferences.map((reference, index) => (
              <div key={index} className="bg-muted p-3 rounded-md">
                <CitationReferenceItem
                  reference={reference}
                  references={references}
                  supportingFiles={supportingFiles}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
