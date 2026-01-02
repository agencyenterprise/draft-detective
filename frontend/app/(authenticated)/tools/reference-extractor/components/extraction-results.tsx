import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import type { ReferenceExtractionState } from '@/lib/generated-api';

interface ExtractionResultsProps {
  results: Pick<ReferenceExtractionState, 'detected_sections' | 'references'>;
  onReset: () => void;
}

export function ExtractionResults({ results, onReset }: ExtractionResultsProps) {
  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Extracted References ({results.references?.length || 0})
        </h2>
        <Button variant="outline" size="sm" onClick={onReset}>
          Extract Another
        </Button>
      </div>

      <div className="space-y-4">
        {results.detected_sections && results.detected_sections.length > 0 && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
            <h3 className="text-sm font-medium text-blue-900 mb-2">Detected Sections</h3>
            <ul className="text-xs text-blue-700 space-y-1">
              {results.detected_sections.map((section, idx) => (
                <li key={idx}>
                  Section {idx + 1}: characters {section.start_offset}-{section.end_offset}
                </li>
              ))}
            </ul>
          </div>
        )}

        {results.references && results.references.length > 0 ? (
          <div className="space-y-2">
            {results.references.map((ref, idx) => (
              <div key={idx} className="p-3 border border-gray-200 rounded-md hover:border-gray-300 transition">
                <div className="flex items-start gap-3">
                  <span className="text-xs font-medium text-gray-500 mt-0.5">#{idx + 1}</span>
                  <div className="flex-1">
                    <p className="text-sm text-gray-900">{ref.text}</p>
                    {ref.has_associated_supporting_document && (
                      <p className="text-xs text-green-600 mt-1">
                        ✓ Matched with: {ref.name_of_associated_supporting_document}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 space-y-2">
            <p className="text-sm text-muted-foreground">No references found in this document</p>
            <p className="text-xs text-muted-foreground">
              The document may not contain a bibliography section, or the format may not be recognized
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
