import { useState, useCallback, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/api-error';
import { useWizard, PreflightStatus } from './wizard-context';
import { MAX_FILE_SIZE_BYTES } from '@/lib/constants';
import { uploadSingleFile, formatBytes, UploadProgress } from '@/lib/hooks/upload';
import {
  createProjectEndpointApiProjectsPost,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  WorkflowRunType,
  FileRole,
} from '@/lib/generated-api';

export type UploadStage = 'idle' | 'creating' | 'uploading' | 'processing' | 'complete';

const INITIAL_WORKFLOWS = [
  WorkflowRunType.DocumentProcessing,
  WorkflowRunType.ReferenceExtraction,
  WorkflowRunType.ChunkSplitting,
  WorkflowRunType.DocumentSummarization,
];

function validateDocument(file: File | null): PreflightStatus {
  if (!file) return 'idle';
  return file.size <= MAX_FILE_SIZE_BYTES ? 'valid' : 'invalid';
}

function getStageMessage(stage: UploadStage, progress: UploadProgress | null, fileSizeLabel: string): string {
  switch (stage) {
    case 'creating':
      return 'Creating project...';
    case 'uploading':
      if (progress) {
        return `Uploading document... ${progress.progress_percent}% (${formatBytes(progress.uploaded_size)} / ${fileSizeLabel})`;
      }
      return 'Uploading document...';
    case 'processing':
      return 'Starting document processing...';
    case 'complete':
      return 'Upload complete!';
    default:
      return '';
  }
}

export function useStepUpload(onComplete: () => void) {
  const wizard = useWizard();
  const { mainDocument, preflightStatus, setPreflightStatus, setMainDocument, setProjectId } = wizard;
  const [uploadStage, setUploadStage] = useState<UploadStage>('idle');
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  const fileSizeLabel = mainDocument ? formatBytes(mainDocument.size) : '';
  const formatStatus = validateDocument(mainDocument);

  const createProjectAndProcess = useMutation({
    mutationFn: async () => {
      if (!mainDocument) throw new Error('No document selected');

      setUploadStage('creating');
      const { project } = await createProjectEndpointApiProjectsPost({
        body: { title: mainDocument.name },
      });

      setUploadStage('uploading');
      setUploadProgress({ uploaded_size: 0, total_size: mainDocument.size, progress_percent: 0 });

      await uploadSingleFile(mainDocument, {
        projectId: project.id,
        fileRole: FileRole.Main,
        onProgress: setUploadProgress,
      });

      setUploadStage('processing');

      await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: project.id,
          workflow_types: INITIAL_WORKFLOWS,
        },
      });

      setUploadStage('complete');
      return project.id;
    },
    onSuccess: (projectId) => {
      setProjectId(projectId);
      toast.success('Project created - document processing started');
      onComplete();
    },
    onError: (error) => {
      setUploadStage('idle');
      setUploadProgress(null);
      toast.error(getErrorMessage(error, 'Failed to create project'));
    },
  });

  const handleDocumentChange = useCallback(
    (files: File[]) => {
      setMainDocument(files[0] || null);
      setUploadStage('idle');
      setUploadProgress(null);
    },
    [setMainDocument],
  );

  const handleContinue = useCallback(async () => {
    setPreflightStatus({ format: formatStatus });

    if (formatStatus !== 'valid') {
      toast.error('Please upload a valid document');
      return;
    }
    createProjectAndProcess.mutate();
  }, [formatStatus, setPreflightStatus, createProjectAndProcess]);

  const isLoading = createProjectAndProcess.isPending;
  const canContinue = formatStatus === 'valid' && !isLoading;

  const stageMessage = useMemo(
    () => getStageMessage(uploadStage, uploadProgress, fileSizeLabel),
    [uploadStage, uploadProgress, fileSizeLabel],
  );

  return {
    mainDocument,
    preflightStatus: { ...preflightStatus, format: formatStatus },
    isLoading,
    canContinue,
    uploadStage,
    uploadProgress,
    stageMessage,
    fileSizeLabel,
    handleDocumentChange,
    handleContinue,
  };
}
