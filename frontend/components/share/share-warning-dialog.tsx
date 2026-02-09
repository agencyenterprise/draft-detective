'use client';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { AlertTriangle, Download, Globe, Loader2 } from 'lucide-react';

interface ShareWarningDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isEnablingShare: boolean;
  isDownloading: boolean;
  onMakePublicAndDownload: () => void;
  onDownloadWithoutLinks: () => void;
}

export function ShareWarningDialog({
  open,
  onOpenChange,
  isEnablingShare,
  isDownloading,
  onMakePublicAndDownload,
  onDownloadWithoutLinks,
}: ShareWarningDialogProps) {
  const isProcessing = isEnablingShare || isDownloading;

  return (
    <Dialog open={open} onOpenChange={isProcessing ? undefined : onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Choose DOCX Export Format
          </DialogTitle>
          <DialogDescription asChild>
            <div className="text-sm text-muted-foreground space-y-3 pt-2">
              <p>You can export this reviewed document in one of two ways:</p>
              <p>
                <strong>AI Reviewer add-in:</strong> reviewers can see the issues directly in the add-in as they see in
                the app. Requires Add-In to be installed.
              </p>
              <p>
                <strong>Regular comments:</strong> adds standard Word comments without links, for use outside the
                add-in.
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="flex-col sm:flex-col gap-2 pt-4">
          <Button onClick={onMakePublicAndDownload} disabled={isProcessing} className="w-full justify-center gap-2">
            {isEnablingShare || isDownloading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {isEnablingShare ? 'Preparing add-in export...' : 'Downloading...'}
              </>
            ) : (
              <>
                <Globe className="h-4 w-4" />
                Export for AI Reviewer Add-In
              </>
            )}
          </Button>

          <Button
            variant="outline"
            onClick={onDownloadWithoutLinks}
            disabled={isProcessing}
            className="w-full justify-center gap-2"
          >
            <Download className="h-4 w-4" />
            Export with Regular Comments
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
