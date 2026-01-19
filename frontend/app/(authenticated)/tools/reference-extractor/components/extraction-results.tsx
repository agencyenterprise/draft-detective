'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { NoReferencesCallout } from '@/components/references/no-reference-section-callout';
import { Copy, CopyCheck, FileText } from 'lucide-react';
import { toast } from 'sonner';
import type { ReferenceExtractionState } from '@/lib/generated-api';

interface ExtractionResultsProps {
  results: Pick<ReferenceExtractionState, 'detected_sections' | 'references'>;
  onReset: () => void;
}

export function ExtractionResults({ results, onReset }: ExtractionResultsProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const referencesText = React.useMemo(() => {
    return results.references?.map((ref) => ref.text).join('\n') || '';
  }, [results.references]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(referencesText);
      setCopied(true);
      toast.success('References copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
      toast.error('Failed to copy to clipboard');
    }
  };

  const hasReferences = (results.references?.length || 0) > 0;
  const hasSections = (results.detected_sections?.length || 0) > 0;

  const renderEmptyState = () => {
    return <NoReferencesCallout sectionsDetected={hasSections} />;
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Extracted References ({results.references?.length || 0})
        </h2>
        <div className="flex items-center gap-2">
          {hasReferences && (
            <Dialog open={isOpen} onOpenChange={setIsOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <FileText className="h-4 w-4 mr-2" />
                  Copy All References
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Copy References</DialogTitle>
                  <DialogDescription>
                    References formatted for the Reference Downloader tool (one per line)
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <Textarea value={referencesText} readOnly rows={12} className="font-mono text-sm resize-none" />
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                      {results.references?.length || 0} reference{results.references?.length !== 1 ? 's' : ''}
                    </p>
                    <Button onClick={handleCopy} disabled={copied} size="sm">
                      {copied ? (
                        <>
                          <CopyCheck className="h-4 w-4 mr-2" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <Copy className="h-4 w-4 mr-2" />
                          Copy to Clipboard
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          )}
          <Button variant="outline" size="sm" onClick={onReset}>
            Extract Another
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        {hasReferences ? (
          <div className="space-y-2">
            {results.references!.map((ref, idx) => (
              <div key={idx} className="p-3 border border-gray-200 rounded-md hover:border-gray-300 transition">
                <div className="flex items-start gap-3">
                  <span className="text-xs font-medium text-gray-500 mt-0.5">#{idx + 1}</span>
                  <div className="flex-1">
                    <p className="text-sm text-gray-900">{ref.text}</p>
                    {ref.has_associated_supporting_document && (
                      <p className="text-xs text-green-600 mt-1">
                        ✓ Matched with:{' '}
                        {ref.file_id ? (
                          <a
                            href={`/api/files/download/${ref.file_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {ref.name_of_associated_supporting_document}
                          </a>
                        ) : (
                          ref.name_of_associated_supporting_document
                        )}
                      </p>
                    )}
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
