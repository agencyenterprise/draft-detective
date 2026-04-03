'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { FileUpload } from '@/components/ui/file-upload';
import { FileListItem } from '@/components/analysis-form/file-list-item';
import { UploadProgressList } from '@/components/ui/upload-progress-list';
import { useUpload } from '@/lib/hooks/upload';
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
  /** When set, force-matches the uploaded file to this reference instead of triggering the matching workflow. */
  referenceId?: string;
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
  referenceId,
  onCancel,
  onComplete,
}: FileUploadDialogProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false);
  const queryClient = useQueryClient();
  const resetRef = useRef<(() => void) | null>(null);

  const handleAllComplete = useCallback(async () => {
    if (referenceId) {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('File uploaded and matched to reference.');
      onComplete?.();
      return;
    }

    try {
      setIsStartingWorkflow(true);
      await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectId,
          workflow_types: [WorkflowRunType.ReferenceFileMatching],
        },
      });
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Sources uploaded. Matching workflow started.');
    } catch {
      toast.error('Failed to start file matching workflow');
    } finally {
      setIsStartingWorkflow(false);
      onComplete?.();
    }
  }, [referenceId, projectId, queryClient, onComplete]);

  const uploadHook = useUpload({
    projectId,
    fileRole: FileRole.Support,
    referenceId,
    onAllComplete: handleAllComplete,
  });

  // Store reset in ref to avoid effect dependency on uploadHook
  resetRef.current = uploadHook.reset;

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setSelectedFiles([]);
      setIsStartingWorkflow(false);
      resetRef.current?.();
    }
  }, [isOpen]);

  const handleFilesChange = (newFiles: File[]) => {
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
    uploadHook.startUpload(selectedFiles);
  };

  const canSubmit = selectedFiles.length > 0;

  const getSubmitLabel = () => {
    if (submitLabel) return submitLabel;
    if (multiple) {
      return `Upload ${selectedFiles.length} source${selectedFiles.length !== 1 ? 's' : ''}`;
    }
    return 'Upload';
  };

  const isUploading = uploadHook.isUploading || isStartingWorkflow;
  const allCompleted = uploadHook.completedCount > 0 && uploadHook.completedCount === uploadHook.totalCount;

  if (uploadHook.files.length > 0 && isOpen) {
    return (
      <Dialog open={isOpen} onOpenChange={() => {}}>
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col overflow-hidden" showCloseButton={false}>
          <DialogHeader className="flex-shrink-0">
            <DialogTitle>{isStartingWorkflow ? 'Starting file matching...' : 'Uploading sources'}</DialogTitle>
            <DialogDescription>
              {isStartingWorkflow
                ? 'Starting the file matching workflow to match uploaded sources to references.'
                : 'Your sources are being uploaded. You can cancel at any time.'}
            </DialogDescription>
          </DialogHeader>

          <UploadProgressList
            files={uploadHook.files}
            overallProgress={uploadHook.overallProgress}
            completedCount={uploadHook.completedCount}
            totalCount={uploadHook.totalCount}
            onCancelFile={uploadHook.removeFile}
            onPauseFile={uploadHook.pauseFile}
            onResumeFile={uploadHook.resumeFile}
            onCancelAll={() => {
              uploadHook.cancelAll();
              handleClose();
            }}
            onPauseAll={uploadHook.pauseAll}
            onResumeAll={uploadHook.resumeAll}
            className="flex-1 min-h-0"
          />

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
          <div className="space-y-2">
            <Label>{multiple ? 'Select Source Files' : 'Select Source File'}</Label>
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

          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <Label>{multiple ? `Selected Source Files (${selectedFiles.length})` : 'Selected Source File'}</Label>
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
