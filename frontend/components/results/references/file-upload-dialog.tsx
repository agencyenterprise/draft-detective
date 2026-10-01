'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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
  /** Role assigned to the uploaded files. Defaults to supporting documents. */
  fileRole?: FileRole;
  /**
   * Revision reviewer memos are attached to. Defaults to the current revision.
   * Only meaningful for the reviewer-memo role.
   */
  targetRevision?: number;
  /**
   * Show which draft the memos are attached to, and let the user change it.
   * Requires `currentRevision`. The control renders for every reviewer-memo
   * upload — memos are always bound to a draft, and seeing that up front is
   * what stops a later batch going to the wrong one — but it is disabled while
   * the project has only one revision, since there is nothing to choose.
   */
  allowRevisionSelection?: boolean;
  /** The project's current revision, used to build the revision options. */
  currentRevision?: number;
  /** When set, force-matches the uploaded file to this reference instead of triggering the matching workflow. */
  referenceId?: string;
  onCancel: () => void;
  onComplete?: () => void;
}

/** Roles that skip reference matching say so, rather than promise it. */
const SUCCESS_MESSAGES: Partial<Record<FileRole, string>> = {
  [FileRole.ReviewerMemo]: 'Reviewer memos uploaded.',
  [FileRole.ResponseMemo]: 'Response memos uploaded.',
};

export function FileUploadDialog({
  isOpen,
  title,
  description,
  multiple = false,
  submitLabel,
  projectId,
  fileRole = FileRole.Support,
  targetRevision,
  allowRevisionSelection = false,
  currentRevision,
  referenceId,
  onCancel,
  onComplete,
}: FileUploadDialogProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedRevision, setSelectedRevision] = useState<number | undefined>(targetRevision);
  const [isStartingWorkflow, setIsStartingWorkflow] = useState(false);
  const queryClient = useQueryClient();
  const resetRef = useRef<(() => void) | null>(null);

  const isMemoUpload = fileRole === FileRole.ReviewerMemo;
  // Reference matching only applies to supporting documents (that aren't
  // already tied to a specific reference); other roles skip it.
  const skipMatching = fileRole !== FileRole.Support;
  const successMessage = SUCCESS_MESSAGES[fileRole] ?? 'Files uploaded. Matching them to your references.';
  // Only memos carry a revision; sending one for any other role is a 400.
  const uploadRevision = isMemoUpload ? selectedRevision : undefined;
  // Shown even when there is only one revision: memos are always bound to a
  // specific draft, and seeing that up front is what stops people from
  // attaching a later batch to the wrong one.
  const showRevisionPicker = isMemoUpload && allowRevisionSelection;
  const revisionCount = currentRevision ?? 1;
  const revisionOptions = Array.from({ length: revisionCount }, (_, i) => revisionCount - i);

  const handleAllComplete = useCallback(async () => {
    if (referenceId) {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('File uploaded and matched to reference.');
      onComplete?.();
      return;
    }

    if (skipMatching) {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success(successMessage);
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
      toast.success(successMessage);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to match the files to your references'));
    } finally {
      setIsStartingWorkflow(false);
      onComplete?.();
    }
  }, [referenceId, skipMatching, successMessage, projectId, queryClient, onComplete]);

  const uploadHook = useUpload({
    projectId,
    fileRole,
    referenceId,
    targetRevision: uploadRevision,
    onAllComplete: handleAllComplete,
  });

  // Store reset in ref to avoid effect dependency on uploadHook
  resetRef.current = uploadHook.reset;

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen) {
      setSelectedFiles([]);
      setSelectedRevision(targetRevision);
      setIsStartingWorkflow(false);
      resetRef.current?.();
    }
  }, [isOpen, targetRevision]);

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
      return `Upload ${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''}`;
    }
    return 'Upload';
  };

  const isUploading = uploadHook.isUploading || isStartingWorkflow;
  const allCompleted = uploadHook.completedCount > 0 && uploadHook.completedCount === uploadHook.totalCount;
  // Once files have been handed to the uploader we switch from the file-picker
  // view to the progress view. Both share the same dialog shell.
  const showProgress = uploadHook.files.length > 0;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        // The progress view can't be dismissed by clicking outside or pressing
        // Escape; use its own controls (Cancel all / Done) instead.
        if (!open && !showProgress && !isUploading) handleClose();
      }}
    >
      <DialogContent
        className="sm:max-w-3xl max-h-[90vh] flex flex-col overflow-hidden"
        showCloseButton={!showProgress}
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

            {allCompleted && !isStartingWorkflow && (
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
              {showRevisionPicker && (
                <div className="space-y-2">
                  <Label htmlFor="memo-revision">Which draft did these reviewers read?</Label>
                  <Select
                    value={String(selectedRevision ?? revisionCount)}
                    onValueChange={(v) => setSelectedRevision(Number(v))}
                    disabled={isUploading || revisionCount === 1}
                  >
                    <SelectTrigger id="memo-revision" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {revisionOptions.map((rev) => (
                        <SelectItem key={rev} value={String(rev)}>
                          Revision {rev}
                          {rev === revisionCount ? ' (current)' : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {revisionCount === 1
                      ? 'Memos are attached to the draft they reviewed. This project has one revision, so they attach to revision 1 — once you upload a revised draft, the assessments compare the two.'
                      : 'The assessments compare that draft against the current one. Pick the draft the reviewers actually saw, which is not always the latest.'}
                  </p>
                </div>
              )}
              <div className="space-y-2">
                <Label>
                  {fileRole === FileRole.Support ? 'Select Source ' : 'Select '}
                  {multiple ? 'Files' : 'File'}
                </Label>
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
                      <FileListItem key={index} file={file} type={fileRole} onRemove={() => handleRemoveFile(index)} />
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
