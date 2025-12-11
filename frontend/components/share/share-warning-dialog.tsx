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
            Share Links in Document
          </DialogTitle>
          <DialogDescription asChild>
            <div className="text-sm text-muted-foreground space-y-3 pt-2">
              <p>
                The downloaded DOCX can include links to view each issue in the AI Reviewer. However, these links{' '}
                <strong>only work when sharing is enabled</strong>.
              </p>
              <p>Would you like to make this analysis public so the links work for anyone with the document?</p>
            </div>
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="flex-col sm:flex-col gap-2 pt-4">
          <Button onClick={onMakePublicAndDownload} disabled={isProcessing} className="w-full justify-center gap-2">
            {isEnablingShare || isDownloading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {isEnablingShare ? 'Enabling sharing...' : 'Downloading...'}
              </>
            ) : (
              <>
                <Globe className="h-4 w-4" />
                Make Public & Download with Links
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
            Download Without Links
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
