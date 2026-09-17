'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { CheckboxWithDescription } from '@/components/ui/checkbox-with-description';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItemWithDescription } from '@/components/ui/radio-group-with-description';
import { AlertTriangle, Download, Link, Loader2, PencilLineIcon } from 'lucide-react';
import { DocxType } from '../results/components/use-download-docx';
import { ActiveFilters, ExportScope } from './active-filters-summary';
import type { ExportCounts } from '@/lib/export-scope';

// Temporarily hidden: the Draft Detective add-in export is not offered right now.
// Flip back to `true` to restore the export type picker.
const SHOW_ADD_IN_OPTION = false;

interface ShareWarningDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isProjectPublic: boolean;
  isEnablingShare: boolean;
  isDownloading: boolean;
  /** The document explorer's filters, which scope the export. */
  filters: ActiveFilters;
  /** What that scope amounts to: issues that become comments, edits that become tracked changes. */
  counts: ExportCounts;
  onDownload: (type: DocxType, options: DownloadOptions) => void;
}

export interface DownloadOptions {
  /** Apply each issue's proposed edits to the document as tracked changes. */
  includeEdits: boolean;
}

export function ShareWarningDialog({
  open,
  onOpenChange,
  isProjectPublic,
  isEnablingShare,
  isDownloading,
  filters,
  counts,
  onDownload,
}: ShareWarningDialogProps) {
  const isProcessing = isEnablingShare || isDownloading;
  const [selectedExportType, setSelectedExportType] = useState<'comments' | 'add-in'>('comments');
  const [makePublicAndAddLinks, setMakePublicAndAddLinks] = useState(isProjectPublic);
  const [includeEdits, setIncludeEdits] = useState(true);

  const shouldShowEditsCheckbox = selectedExportType === 'comments';
  const shouldShowLinksCheckbox = selectedExportType === 'comments' && !isProjectPublic;
  const shouldShowAddInDisclaimer = selectedExportType === 'add-in';

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setSelectedExportType('comments');
      setMakePublicAndAddLinks(isProjectPublic);
      setIncludeEdits(true);
    }
    onOpenChange(isOpen);
  };

  const handleDownload = () => {
    const docxType: DocxType =
      selectedExportType === 'add-in' ? 'add-in' : makePublicAndAddLinks ? 'comments-with-links' : 'comments';

    onDownload(docxType, { includeEdits: selectedExportType === 'comments' && includeEdits });
    setSelectedExportType('comments');
    setMakePublicAndAddLinks(isProjectPublic);
    setIncludeEdits(true);
  };

  return (
    <Dialog open={open} onOpenChange={isProcessing ? undefined : handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Download DOCX</DialogTitle>
          <DialogDescription>
            Your Word document with each finding added as a comment on the passage it concerns.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <section className="space-y-2">
            <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Included</h3>
            <ExportScope filters={filters} counts={counts} />
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Options</h3>
            <div className="divide-y rounded-lg border">
              {SHOW_ADD_IN_OPTION && (
                <RadioGroup
                  value={selectedExportType}
                  onValueChange={(value) => setSelectedExportType(value as 'comments' | 'add-in')}
                  className="gap-0 p-1"
                >
                  <RadioGroupItemWithDescription
                    id="comments"
                    value={selectedExportType}
                    label="Regular comments"
                    description="Adds standard Word comments for use outside the add-in."
                    disabled={isProcessing}
                  />
                  <RadioGroupItemWithDescription
                    id="add-in"
                    value={selectedExportType}
                    label="Draft Detective add-in"
                    description="Reviewers can see issues directly in the add-in as they do in the app."
                    disabled={isProcessing}
                  />
                </RadioGroup>
              )}

              {shouldShowEditsCheckbox && (
                <CheckboxWithDescription
                  id="include-edits"
                  icon={PencilLineIcon}
                  checked={includeEdits}
                  disabled={isProcessing}
                  onCheckedChange={setIncludeEdits}
                  label="Apply proposed edits as tracked changes"
                  description="Accept or reject each edit in Word. Every edit is also described in its issue's comment."
                />
              )}

              {shouldShowLinksCheckbox && (
                <CheckboxWithDescription
                  id="add-links"
                  icon={Link}
                  checked={makePublicAndAddLinks}
                  disabled={isProcessing}
                  onCheckedChange={setMakePublicAndAddLinks}
                  label="Link comments to Draft Detective"
                  description="Makes this project public and links each comment to its issue online."
                />
              )}

              {shouldShowAddInDisclaimer && (
                <p className="flex items-start gap-2 p-4 text-sm text-muted-foreground">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                  <span>
                    Requires the Draft Detective Word add-in.
                    {!isProjectPublic && ' This will make this project public.'}
                  </span>
                </p>
              )}
            </div>
          </section>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => handleOpenChange(false)} disabled={isProcessing}>
            Cancel
          </Button>
          <Button onClick={handleDownload} disabled={isProcessing} className="gap-2">
            {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {isProcessing ? 'Preparing...' : 'Download'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
