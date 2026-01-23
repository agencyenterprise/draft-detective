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
import { Loader2 } from 'lucide-react';

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
    if (!hideOpenaiApiKeyInput && !openaiApiKey.trim()) return;
    onConfirm(files, openaiApiKey);
  };

  const canSubmit = files.length > 0 && (hideOpenaiApiKeyInput || openaiApiKey.trim() !== '');

  const getSubmitLabel = () => {
    if (submitLabel) return submitLabel;
    if (multiple) {
      return `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`;
    }
    return files.length > 0 ? 'Upload' : 'Upload';
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isUploading && onCancel()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* OpenAI API Key Input */}
          {!hideOpenaiApiKeyInput && (
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
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {files.map((file, index) => (
                  <FileListItem key={index} file={file} type="supporting" onRemove={() => handleRemoveFile(index)} />
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isUploading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!canSubmit || isUploading}>
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading...
              </>
            ) : (
              getSubmitLabel()
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
