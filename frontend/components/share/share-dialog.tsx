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
import { Input } from '@/components/ui/input';
import { ShareStatusResponse } from '@/lib/generated-api';
import { Check, Copy, ExternalLink, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface ShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  shareStatus: ShareStatusResponse | null;
  isEnabling: boolean;
  isDisabling: boolean;
  onEnable: () => void;
  onDisable: () => void;
}

type DialogView = 'share' | 'confirm-disable';

export function ShareDialog({
  open,
  onOpenChange,
  shareStatus,
  isEnabling,
  isDisabling,
  onEnable,
  onDisable,
}: ShareDialogProps) {
  const [hasCopied, setHasCopied] = useState(false);
  const [view, setView] = useState<DialogView>('share');
  const inputRef = useRef<HTMLInputElement>(null);

  const shareUrl = shareStatus?.share_link?.url;
  const isEnabled = shareStatus?.enabled && shareUrl;

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (!open) {
      setHasCopied(false);
      setView('share');
    } else if (isEnabled && inputRef.current) {
      setTimeout(() => inputRef.current?.select(), 100);
    }
  }, [open, isEnabled]);

  const handleCopy = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setHasCopied(true);
      setTimeout(() => setHasCopied(false), 2000);
    } catch {
      inputRef.current?.select();
      document.execCommand('copy');
      setHasCopied(true);
      setTimeout(() => setHasCopied(false), 2000);
    }
  };

  const handlePreview = () => {
    if (shareUrl) window.open(shareUrl, '_blank', 'noopener,noreferrer');
  };

  if (view === 'confirm-disable') {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Disable Sharing?</DialogTitle>
            <DialogDescription asChild>
              <div className="text-sm text-muted-foreground space-y-2">
                <p>
                  This will <strong>immediately break all existing links</strong> to this assessment.
                </p>
                <p>You can re-enable sharing later.</p>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setView('share')} disabled={isDisabling}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={onDisable} disabled={isDisabling}>
              {isDisabling ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Disabling...
                </>
              ) : (
                'Disable Sharing'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEnabled ? '🔗 Share Link Ready' : 'Share This Assessment'}</DialogTitle>
          <DialogDescription>
            {isEnabled
              ? 'Anyone with this link can view a read-only version of your assessment.'
              : 'Create a public link that anyone can use to view this assessment.'}
          </DialogDescription>
        </DialogHeader>

        {isEnabled ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Input
                ref={inputRef}
                value={shareUrl}
                readOnly
                className="font-mono text-sm"
                onClick={(e) => e.currentTarget.select()}
              />
              <Button
                type="button"
                size="icon"
                variant={hasCopied ? 'default' : 'outline'}
                onClick={handleCopy}
                className="shrink-0 transition-all"
              >
                {hasCopied ? <Check className="h-4 w-4 animate-in zoom-in-50" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            {hasCopied && (
              <p className="text-sm text-green-600 dark:text-green-400 animate-in fade-in slide-in-from-top-1">
                ✓ Link copied to clipboard!
              </p>
            )}
            <p className="text-xs text-muted-foreground">This link will remain active until you disable sharing.</p>
          </div>
        ) : (
          <div className="py-4 text-center">
            <p className="text-sm text-muted-foreground mb-4">
              Enabling sharing will generate a unique link. You can disable it at any time.
            </p>
          </div>
        )}

        <DialogFooter className="sm:justify-between">
          {isEnabled ? (
            <>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={handlePreview}>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Preview
                </Button>
                <Button type="button" variant="ghost" onClick={() => setView('confirm-disable')}>
                  Disable
                </Button>
              </div>
              <Button type="button" onClick={() => onOpenChange(false)}>
                Done
              </Button>
            </>
          ) : (
            <>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={onEnable} disabled={isEnabling}>
                {isEnabling ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Creating link...
                  </>
                ) : (
                  'Enable Sharing'
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
