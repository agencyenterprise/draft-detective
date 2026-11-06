'use client';

import { useState, useCallback, useEffect } from 'react';
import { getErrorMessage } from '@/lib/api-error';
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
import { projectQueryKeys } from '@/lib/hooks/use-project-data';

export interface FileUploadDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  multiple?: boolean;
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
  projectId,
  referenceId,
  onCancel,
  onComplete,
}: FileUploadDialogProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false);
  const queryClient = useQueryClient();

  const handleAllComplete = useCallback(async () => {
    if (referenceId) {
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all(projectId) });
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
      queryClient.invalidateQueries({ queryKey: projectQueryKeys.all(projectId) });
      toast.success('Files uploaded. Matching them to your references.');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to match the files to your references'));
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

  // Start fresh each time the dialog opens, during render rather than in an
  // effect so the first open frame never shows the previous selection.
  const [wasOpen, setWasOpen] = useState(isOpen);
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen);
    if (isOpen) {
      setSelectedFiles([]);
      setIsStartingWorkflow(false);
    }
  }

  // The upload hook owns an Uppy instance, so clearing it is a side effect.
  const resetUploads = uploadHook.reset;
  useEffect(() => {
    if (isOpen) resetUploads();
  }, [isOpen, resetUploads]);

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
    if (multiple) {
      return `Upload ${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''}`;
    }
    return 'Upload';
  };

  const isUploading = uploadHook.isUploading || isStartingWorkflow;
  // Once files have been handed to the uploader we switch from the file-picker
  // view to the progress view. Both share the same dialog shell.
  const showProgress = uploadHook.files.length > 0;
  // Nothing is uploading or paused any more: every file finished or failed, so
  // the progress view must offer a way out even when none succeeded.
  const settled = showProgress && !isUploading && !uploadHook.files.some((f) => f.status === 'paused');

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        // While files are in flight the progress view can't be dismissed by
        // clicking outside or pressing Escape; use Cancel all instead.
        if (!open && (!showProgress || settled) && !isUploading) handleClose();
      }}
    >
      <DialogContent
        className="sm:max-w-3xl max-h-[90vh] flex flex-col overflow-hidden"
        showCloseButton={!showProgress || settled}
      >
        {showProgress ? (
          <>
            <DialogHeader className="flex-shrink-0">
              <DialogTitle>{isStartingWorkflow ? 'Starting file matching...' : 'Uploading files'}</DialogTitle>
              <DialogDescription>
                {isStartingWorkflow
                  ? 'Matching the uploaded files to your references.'
                  : 'Your files are being uploaded. You can cancel at any time.'}
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

            {settled && (
              <DialogFooter className="flex-shrink-0">
                <Button onClick={handleClose}>Done</Button>
              </DialogFooter>
            )}
          </>
        ) : (
          <>
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
                  <Label>{multiple ? `Selected Files (${selectedFiles.length})` : 'Selected File'}</Label>
                  <div className="space-y-1">
                    {selectedFiles.map((file, index) => (
                      <FileListItem
                        key={index}
                        file={file}
                        type={FileRole.Support}
                        onRemove={() => handleRemoveFile(index)}
                      />
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
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
