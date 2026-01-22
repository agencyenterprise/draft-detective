'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Copy, CopyCheck } from 'lucide-react';
import { toast } from 'sonner';

interface CopyReferencesDialogProps {
  references: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CopyReferencesDialog({ references, open, onOpenChange }: CopyReferencesDialogProps) {
  const [copied, setCopied] = React.useState(false);

  const referencesText = React.useMemo(() => {
    return references.join('\n');
  }, [references]);

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Copy References</DialogTitle>
          <DialogDescription>1 reference per line</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Textarea value={referencesText} readOnly rows={12} className="font-mono text-sm resize-none" />
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {references.length} reference{references.length !== 1 ? 's' : ''}
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
  );
}
