'use client';

import { useState, useEffect } from 'react';
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
import { Label } from '@/components/ui/label';
import { FileUpload } from '@/components/ui/file-upload';
import { FileListItem } from '@/components/analysis-form/file-list-item';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { cn } from '@/lib/utils';
import { Upload, FileText, Link2, Loader2, Check } from 'lucide-react';

export interface FileUploadDialogProps {
  isOpen: boolean;
  isUploading: boolean;
  title: string;
  description: string;
  multiple?: boolean;
  submitLabel?: string;
  onConfirm: (files: File[], openaiApiKey: string) => void;
  onCancel: () => void;
}

const uploadSteps = [
  { id: 'upload', label: 'Uploading files', icon: Upload },
  { id: 'process', label: 'Processing documents', icon: FileText },
  { id: 'match', label: 'Matching references', icon: Link2 },
];

export function FileUploadDialog({
  isOpen,
  isUploading,
  title,
  description,
  multiple = false,
  submitLabel,
  onConfirm,
  onCancel,
}: FileUploadDialogProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  // Hide API key input if env var is set OR if user already has a key saved
  const shouldHideApiKeyInput = hideOpenaiApiKeyInput || openaiApiKey.trim() !== '';

  // Reset files when dialog opens
  useEffect(() => {
    if (isOpen) {
      setFiles([]);
    }
  }, [isOpen]);

  const handleFilesChange = (newFiles: File[]) => {
    // In single file mode, only keep the last selected file
    setFiles(multiple ? newFiles : newFiles.slice(-1));
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleConfirm = () => {
    if (files.length === 0) return;
    if (!shouldHideApiKeyInput && !openaiApiKey.trim()) return;
    onConfirm(files, openaiApiKey);
  };

  const canSubmit = files.length > 0 && (shouldHideApiKeyInput || openaiApiKey.trim() !== '');

  const getSubmitLabel = () => {
    if (submitLabel) return submitLabel;
    if (multiple) {
      return `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`;
    }
    return files.length > 0 ? 'Upload' : 'Upload';
  };

  // Loading state UI
  if (isUploading) {
    return (
      <Dialog open={isOpen} onOpenChange={() => {}}>
        <DialogContent className="max-w-md" showCloseButton={false}>
          <div className="py-8 space-y-6">
            <div className="text-center space-y-2">
              <h3 className="text-lg font-semibold">Processing your files</h3>
              <p className="text-sm text-muted-foreground">
                Uploading {files.length} file{files.length !== 1 ? 's' : ''} and starting workflows...
              </p>
            </div>

            <div className="space-y-3">
              {uploadSteps.map((step, index) => {
                const Icon = step.icon;
                const isActive = index === 0;
                const isCompleted = false;

                return (
                  <div
                    key={step.id}
                    className={cn(
                      'flex items-center gap-3 p-3 rounded-lg border transition-colors',
                      isActive && 'border-primary bg-primary/5',
                      !isActive && !isCompleted && 'border-border bg-muted/30 opacity-50',
                      isCompleted && 'border-green-500/30 bg-green-500/5',
                    )}
                  >
                    <div
                      className={cn(
                        'flex items-center justify-center size-8 rounded-full',
                        isActive && 'bg-primary text-primary-foreground',
                        !isActive && !isCompleted && 'bg-muted text-muted-foreground',
                        isCompleted && 'bg-green-500 text-white',
                      )}
                    >
                      {isCompleted ? (
                        <Check className="size-4" />
                      ) : isActive ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Icon className="size-4" />
                      )}
                    </div>
                    <span
                      className={cn(
                        'text-sm font-medium',
                        isActive && 'text-foreground',
                        !isActive && !isCompleted && 'text-muted-foreground',
                        isCompleted && 'text-green-700 dark:text-green-400',
                      )}
                    >
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>

            <p className="text-xs text-muted-foreground text-center">
              This may take a few minutes depending on file size. Please don&apos;t close this window.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isUploading && onCancel()}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 flex-1 overflow-y-auto min-h-0">
          {/* OpenAI API Key Input */}
          {!shouldHideApiKeyInput && (
            <div className="space-y-2">
              <Label htmlFor="openai-key" required>
                OpenAI API Key
              </Label>
              <Input
                id="openai-key"
                type="text"
                placeholder="sk-..."
                value={openaiApiKey}
                onChange={(e) => setOpenaiApiKey(e.target.value)}
                error={!openaiApiKey.trim()}
                required={true}
                disabled={isUploading}
              />
              <p className="text-sm text-muted-foreground">
                Your API key is used for processing documents and will not be stored.
              </p>
            </div>
          )}

          {/* File Upload Area */}
          <div className="space-y-2">
            <Label>{multiple ? 'Select Files' : 'Select File'}</Label>
            <FileUpload
              files={files}
              onFilesChange={handleFilesChange}
              accept=".pdf,.doc,.docx,.txt,.md"
              multiple={multiple}
              maxSize={80}
              className="h-36"
              disabled={isUploading}
              compact
            />
          </div>

          {/* Selected Files List */}
          {files.length > 0 && (
            <div className="space-y-2">
              <Label>{multiple ? `Selected Files (${files.length})` : 'Selected File'}</Label>
              <div className="space-y-1">
                {files.map((file, index) => (
                  <FileListItem key={index} file={file} type="supporting" onRemove={() => handleRemoveFile(index)} />
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-shrink-0">
          <Button variant="outline" onClick={onCancel} disabled={isUploading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!canSubmit || isUploading}>
            {getSubmitLabel()}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
