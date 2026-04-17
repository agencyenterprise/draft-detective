'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItemWithDescription } from '@/components/ui/radio-group-with-description';
import { AlertTriangle, Download, Loader2 } from 'lucide-react';
import { DocxType } from '../results/components/use-download-docx';

interface ShareWarningDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isProjectPublic: boolean;
  isEnablingShare: boolean;
  isDownloading: boolean;
  onDownload: (type: DocxType) => void;
}

export function ShareWarningDialog({
  open,
  onOpenChange,
  isProjectPublic,
  isEnablingShare,
  isDownloading,
  onDownload,
}: ShareWarningDialogProps) {
  const isProcessing = isEnablingShare || isDownloading;
  const [selectedExportType, setSelectedExportType] = useState<'comments' | 'add-in'>('add-in');
  const [makePublicAndAddLinks, setMakePublicAndAddLinks] = useState(isProjectPublic);

  const shouldShowLinksCheckbox = selectedExportType === 'comments' && !isProjectPublic;
  const shouldShowAddInDisclaimer = selectedExportType === 'add-in';

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setSelectedExportType('add-in');
      setMakePublicAndAddLinks(isProjectPublic);
    }
    onOpenChange(isOpen);
  };

  const handleDownload = () => {
    const docxType: DocxType =
      selectedExportType === 'add-in' ? 'add-in' : makePublicAndAddLinks ? 'comments-with-links' : 'comments';

    onDownload(docxType);
    setSelectedExportType('add-in');
    setMakePublicAndAddLinks(isProjectPublic);
  };

  return (
    <Dialog open={open} onOpenChange={isProcessing ? undefined : handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Choose How Issues Are Shown
          </DialogTitle>
          <DialogDescription asChild>
            <div className="text-sm text-muted-foreground pt-2">
              Choose how reviewers should see this assessment in the downloaded DOCX.
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 pt-2">
          <RadioGroup
            value={selectedExportType}
            onValueChange={(value) => setSelectedExportType(value as 'comments' | 'add-in')}
            className="gap-2"
          >
            <RadioGroupItemWithDescription
              id="add-in"
              value={selectedExportType}
              label="Draft Detective add-in"
              description="Reviewers can see issues directly in the add-in as they do in the app."
              disabled={isProcessing}
            />
            <RadioGroupItemWithDescription
              id="comments"
              value={selectedExportType}
              label="Regular comments"
              description="Adds standard Word comments for use outside the add-in."
              disabled={isProcessing}
            />
          </RadioGroup>

          {shouldShowLinksCheckbox && (
            <label className="flex items-start gap-2 rounded-md border p-3 cursor-pointer">
              <Checkbox
                checked={makePublicAndAddLinks}
                disabled={isProcessing}
                onCheckedChange={(checked) => setMakePublicAndAddLinks(checked === true)}
                className="mt-0.5"
              />
              <span className="text-sm text-muted-foreground">
                Make this assessment public and add links to comments redirecting to the full assessment page.
              </span>
            </label>
          )}

          {shouldShowAddInDisclaimer && (
            <div className="flex items-start gap-2 rounded-md border p-3">
              <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
              <span className="text-sm text-muted-foreground">
                Requires the Draft Detective Word add-in.
                {!isProjectPublic && ' This will make this assessment public.'}
              </span>
            </div>
          )}
        </div>

        <DialogFooter className="pt-4">
          <Button onClick={handleDownload} disabled={isProcessing} className="w-full justify-center gap-2">
            {isProcessing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Download
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
