'use client';

import { useState, useEffect, useCallback } from 'react';
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
import { UploadProgressList } from '@/components/ui/upload-progress-list';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { useUpload } from '@/lib/hooks/use-upload';
import { FileRole, startMultipleWorkflowsApiWorkflowsStartMultiplePost, WorkflowRunType } from '@/lib/generated-api';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';

export interface FileUploadDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  multiple?: boolean;
  submitLabel?: string;
  projectId: string;
  onCancel: () => void;
  onComplete?: () => void;
}

export function FileUploadDialog({
  isOpen,
  title,
  description,
  multiple = false,
  submitLabel,
  projectId,
  onCancel,
  onComplete,
}: FileUploadDialogProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false);
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';
  const queryClient = useQueryClient();

  // Start ReferenceFileMatching workflow after all files are uploaded
  const handleAllComplete = useCallback(async () => {
    try {
      setIsStartingWorkflow(true);
      await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectId,
          workflow_types: [WorkflowRunType.ReferenceFileMatching],
          openai_api_key: openaiApiKey || undefined,
        },
      });
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Files uploaded. Matching workflow started.');
    } catch (error) {
      toast.error('Failed to start file matching workflow');
    } finally {
      setIsStartingWorkflow(false);
      onComplete?.();
    }
  }, [projectId, openaiApiKey, queryClient, onComplete]);

  // Always use chunked upload
  const uploadHook = useUpload({
    projectId,
    fileRole: FileRole.Support,
    onAllComplete: handleAllComplete,
  });

  // Hide API key input if env var is set OR if user already has a key saved
  const shouldHideApiKeyInput = hideOpenaiApiKeyInput || openaiApiKey.trim() !== '';

  // Reset state when dialog opens
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reset is stable, only run when isOpen changes
  useEffect(() => {
    if (isOpen) {
      setSelectedFiles([]);
      setIsStartingWorkflow(false);
      uploadHook.reset();
    }
  }, [isOpen]);

  const handleFilesChange = (newFiles: File[]) => {
    // In single file mode, only keep the last selected file
    setSelectedFiles(multiple ? newFiles : newFiles.slice(-1));
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleClose = useCallback(() => {
    setSelectedFiles([]);
    uploadHook.reset();
    onCancel();
  }, [onCancel, uploadHook]);

  const handleConfirm = async () => {
    if (selectedFiles.length === 0) return;
    if (!shouldHideApiKeyInput && !openaiApiKey.trim()) return;

    // Start upload with the selected files directly
    uploadHook.startUpload(selectedFiles);
  };

  const canSubmit = selectedFiles.length > 0 && (shouldHideApiKeyInput || openaiApiKey.trim() !== '');

  const getSubmitLabel = () => {
    if (submitLabel) return submitLabel;
    if (multiple) {
      return `Upload ${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''}`;
    }
    return selectedFiles.length > 0 ? 'Upload' : 'Upload';
  };

  const isUploading = uploadHook.isUploading || isStartingWorkflow;
  const allCompleted = uploadHook.completedCount > 0 && uploadHook.completedCount === uploadHook.totalCount;

  // Show progress view when upload is active
  if (uploadHook.files.length > 0 && isOpen) {
    return (
      <Dialog open={isOpen} onOpenChange={() => {}}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col overflow-hidden" showCloseButton={false}>
          <DialogHeader className="flex-shrink-0">
            <DialogTitle>{isStartingWorkflow ? 'Starting file matching...' : 'Uploading files'}</DialogTitle>
            <DialogDescription>
              {isStartingWorkflow
                ? 'Starting the file matching workflow to match uploaded files to references.'
                : 'Your files are being uploaded. You can cancel at any time.'}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 min-h-0 overflow-hidden">
            <UploadProgressList
              files={uploadHook.files}
              overallProgress={uploadHook.overallProgress}
              completedCount={uploadHook.completedCount}
              totalCount={uploadHook.totalCount}
              onCancelFile={uploadHook.removeFile}
              onCancelAll={() => {
                uploadHook.cancelAll();
                handleClose();
              }}
              className="h-full"
            />
          </div>

          {allCompleted && !isStartingWorkflow && (
            <DialogFooter className="flex-shrink-0">
              <Button onClick={handleClose}>Done</Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isUploading && handleClose()}>
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
              files={selectedFiles}
              onFilesChange={handleFilesChange}
              accept=".pdf,.doc,.docx,.txt,.md"
              multiple={multiple}
              maxSize={500}
              className="h-36"
              disabled={isUploading}
              compact
            />
          </div>

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <Label>{multiple ? `Selected Files (${selectedFiles.length})` : 'Selected File'}</Label>
              <div className="space-y-1">
                {selectedFiles.map((file, index) => (
                  <FileListItem key={index} file={file} type="supporting" onRemove={() => handleRemoveFile(index)} />
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-shrink-0">
          <Button variant="outline" onClick={handleClose} disabled={isUploading}>
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
