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
import { Download, Link, Loader2, PencilLineIcon } from 'lucide-react';
import { DocxType } from '../results/components/use-download-docx';
import { ActiveFilters, ExportScope } from './active-filters-summary';
import type { ExportCounts } from '@/lib/export-scope';

interface ShareWarningDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isProjectPublic: boolean;
  isEnablingShare: boolean;
  isDownloading: boolean;
  /** The document explorer's filters, which scope the export. */
  filters: ActiveFilters;
  /**
   * What that scope amounts to: issues that become comments, and their proposed
   * edits. Null while the issues are still loading.
   */
  counts: ExportCounts | null;
  /** The issues could not be loaded, so the scope is stated without counts. */
  countsFailed?: boolean;
  /**
   * Whether the export can carry links back to Draft Detective at all. False
   * for a historical revision, where the backend leaves them out, so the option
   * is not offered: see `shareLinksAvailable`.
   */
  linksAvailable: boolean;
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
  countsFailed = false,
  linksAvailable,
  onDownload,
}: ShareWarningDialogProps) {
  const isProcessing = isEnablingShare || isDownloading;
  // Hold the download until the reader can see what it contains; a failed count
  // does not hold it, since the export does not depend on the count.
  const isCounting = counts === null && !countsFailed;
  const [makePublicAndAddLinks, setMakePublicAndAddLinks] = useState(isProjectPublic);
  const [includeEdits, setIncludeEdits] = useState(true);

  const shouldShowLinksCheckbox = !isProjectPublic && linksAvailable;
  // Never ask for links the backend would drop: the file would be the same
  // either way, and asking would make a private project public for nothing.
  const addLinks = linksAvailable && makePublicAndAddLinks;

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setMakePublicAndAddLinks(isProjectPublic);
      setIncludeEdits(true);
    }
    onOpenChange(isOpen);
  };

  const handleDownload = () => {
    const docxType: DocxType = addLinks ? 'comments-with-links' : 'comments';

    onDownload(docxType, { includeEdits });
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
            <ExportScope filters={filters} counts={counts} countsFailed={countsFailed} includeEdits={includeEdits} />
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Options</h3>
            <div className="divide-y rounded-lg border">
              <CheckboxWithDescription
                id="include-edits"
                icon={PencilLineIcon}
                checked={includeEdits}
                disabled={isProcessing}
                onCheckedChange={setIncludeEdits}
                label="Apply proposed edits as tracked changes"
                description="Accept or reject each edit in Word. Every edit is also described in its issue's comment."
              />

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

              {!linksAvailable && (
                <p className="p-4 text-sm text-muted-foreground">
                  Links to Draft Detective are only added when exporting the current revision.
                </p>
              )}
            </div>
          </section>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => handleOpenChange(false)} disabled={isProcessing}>
            Cancel
          </Button>
          <Button onClick={handleDownload} disabled={isProcessing || isCounting} className="gap-2">
            {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {isProcessing ? 'Preparing...' : 'Download'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
