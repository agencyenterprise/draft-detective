'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/api-error';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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
import { uploadSingleFile, formatBytes, type UploadProgress } from '@/lib/hooks/upload';
import {
  createRevisionEndpointApiProjectProjectIdRevisionsPost,
  FileRole,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  WorkflowRunType,
} from '@/lib/generated-api';
import { MAX_FILE_SIZE_BYTES } from '@/lib/constants';
import { Loader2 } from 'lucide-react';

const INITIAL_WORKFLOWS = [
  WorkflowRunType.DocumentProcessing,
  WorkflowRunType.ReferenceExtraction,
  WorkflowRunType.DocumentSummarization,
];

type Stage = 'select' | 'creating-revision' | 'uploading' | 'starting-workflows' | 'complete';

export interface ReplaceMainDocumentDialogProps {
  isOpen: boolean;
  projectId: string;
  onClose: () => void;
}

export function ReplaceMainDocumentDialog({ isOpen, projectId, onClose }: ReplaceMainDocumentDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [rerunAnalyses, setRerunAnalyses] = useState(true);
  const [stage, setStage] = useState<Stage>('select');
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const queryClient = useQueryClient();
  const abortRef = useRef(false);

  useEffect(() => {
    if (isOpen) {
      setSelectedFile(null);
      setRerunAnalyses(true);
      setStage('select');
      setUploadProgress(null);
      abortRef.current = false;
    }
  }, [isOpen]);

  const replaceMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('No file selected');

      // Step 1: Create new revision
      setStage('creating-revision');
      const { previous_workflow_types } = await createRevisionEndpointApiProjectProjectIdRevisionsPost({
        path: { project_id: projectId },
      });

      if (abortRef.current) return;

      // Step 2: Upload new main document
      setStage('uploading');
      await uploadSingleFile(selectedFile, {
        projectId,
        fileRole: FileRole.Main,
        onProgress: setUploadProgress,
      });

      if (abortRef.current) return;

      // Step 3: Start workflows if requested
      if (rerunAnalyses && previous_workflow_types.length > 0) {
        setStage('starting-workflows');
        const initialSet = new Set<string>(INITIAL_WORKFLOWS);
        const workflowTypes = [
          ...INITIAL_WORKFLOWS,
          ...previous_workflow_types.filter((t: WorkflowRunType) => !initialSet.has(t)),
        ];
        await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
          body: { project_id: projectId, workflow_types: workflowTypes },
        });
      } else {
        // Always run initial processing workflows
        setStage('starting-workflows');
        await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
          body: { project_id: projectId, workflow_types: INITIAL_WORKFLOWS },
        });
      }

      setStage('complete');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast.success('Main document replaced. Assessment started.');
      onClose();
    },
    onError: (error) => {
      setStage('select');
      toast.error(getErrorMessage(error, 'Failed to replace document'));
    },
  });

  const handleFilesChange = useCallback((files: File[]) => {
    setSelectedFile(files[0] || null);
  }, []);

  const handleClose = useCallback(() => {
    if (stage !== 'select' && stage !== 'complete') {
      abortRef.current = true;
    }
    onClose();
  }, [stage, onClose]);

  const isProcessing = stage !== 'select' && stage !== 'complete';
  const isValid = selectedFile && selectedFile.size <= MAX_FILE_SIZE_BYTES;

  const stageMessage = (() => {
    switch (stage) {
      case 'creating-revision':
        return 'Creating new revision...';
      case 'uploading':
        if (uploadProgress && selectedFile) {
          return `Uploading... ${uploadProgress.progress_percent}% (${formatBytes(uploadProgress.uploaded_size)} / ${formatBytes(selectedFile.size)})`;
        }
        return 'Uploading document...';
      case 'starting-workflows':
        return 'Starting assessment workflows...';
      default:
        return '';
    }
  })();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isProcessing && handleClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Replace main document</DialogTitle>
          <DialogDescription>
            Upload a new version of the main document. Previous assessment results will be archived (not deleted).
            Supporting documents will be preserved.
          </DialogDescription>
        </DialogHeader>

        {isProcessing ? (
          <div className="flex items-center gap-3 py-4">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <span className="text-sm text-muted-foreground">{stageMessage}</span>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>New document</Label>
              <FileUpload
                files={selectedFile ? [selectedFile] : []}
                onFilesChange={handleFilesChange}
                accept=".pdf,.doc,.docx,.txt,.md"
                multiple={false}
                maxSize={MAX_FILE_SIZE_BYTES / (1024 * 1024)}
                className="h-36"
                compact
              />
            </div>

            {selectedFile && (
              <div className="space-y-2">
                <FileListItem file={selectedFile} type="main" onRemove={() => setSelectedFile(null)} />
              </div>
            )}

            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="rerun-analyses"
                  checked={rerunAnalyses}
                  onCheckedChange={(checked) => setRerunAnalyses(checked === true)}
                />
                <Label htmlFor="rerun-analyses" className="text-sm font-normal cursor-pointer">
                  Re-run previous assessments
                </Label>
              </div>
              <p className="text-xs text-muted-foreground pl-6">
                Automatically run the same assessment workflows that were previously executed on the old document. If
                unchecked, only document processing will run and you can manually start assessments later.
              </p>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button onClick={() => replaceMutation.mutate()} disabled={!isValid || isProcessing}>
            Replace &amp; analyze
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
