'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { NoReferencesCallout } from '@/components/references/no-reference-section-callout';
import { CopyReferencesDialog } from '@/components/references/copy-references-dialog';
import { FileText } from 'lucide-react';
import type { ReferenceExtractionState } from '@/lib/generated-api';

interface ExtractionResultsProps {
  results: Pick<ReferenceExtractionState, 'detected_sections' | 'extracted_references'>;
  onReset: () => void;
}

export function ExtractionResults({ results, onReset }: ExtractionResultsProps) {
  const [copyDialogOpen, setCopyDialogOpen] = React.useState(false);

  const referenceTexts = React.useMemo(() => {
    return results.extracted_references?.map((ref) => ref.text) || [];
  }, [results.extracted_references]);

  const hasReferences = referenceTexts.length > 0;
  const hasSections = (results.detected_sections?.length || 0) > 0;

  const renderEmptyState = () => {
    return <NoReferencesCallout sectionsDetected={hasSections} />;
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Extracted References ({results.extracted_references?.length || 0})
        </h2>
        <div className="flex items-center gap-2">
          {hasReferences && (
            <>
              <Button variant="outline" size="sm" onClick={() => setCopyDialogOpen(true)}>
                <FileText className="h-4 w-4 mr-2" />
                Copy All References
              </Button>
              <CopyReferencesDialog
                references={referenceTexts}
                open={copyDialogOpen}
                onOpenChange={setCopyDialogOpen}
              />
            </>
          )}
          <Button variant="outline" size="sm" onClick={onReset}>
            Extract Another
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        {hasReferences ? (
          <div className="space-y-2">
            {results.extracted_references!.map((ref, idx) => (
              <div
                key={ref.id || idx}
                className="p-3 border border-gray-200 rounded-md hover:border-gray-300 transition"
              >
                <div className="flex items-start gap-3">
                  <span className="text-xs font-medium text-gray-500 mt-0.5">#{idx + 1}</span>
                  <div className="flex-1">
                    <p className="text-sm text-gray-900">{ref.text}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          renderEmptyState()
        )}
      </div>
    </Card>
  );
}
