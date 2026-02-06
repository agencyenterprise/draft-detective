import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import debounce from 'lodash/debounce';
import { useWizard, PreflightStatus } from './wizard-context';
import { usePreflight } from '@/lib/hooks/use-preflight';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { MAX_FILE_SIZE_BYTES } from '@/lib/constants';
import { uploadSingleFile, formatBytes, UploadProgress } from '@/lib/hooks/upload';
import { startMultipleWorkflowsApiWorkflowsStartMultiplePost, WorkflowRunType, FileRole } from '@/lib/generated-api';
import { getAuthHeader, baseUrl } from '@/lib/api';

export type UploadStage = 'idle' | 'creating' | 'uploading' | 'processing' | 'complete';

const MIN_API_KEY_LENGTH = 10;
const HIDE_API_KEY_INPUT = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

const INITIAL_WORKFLOWS = [
  WorkflowRunType.DocumentProcessing,
  WorkflowRunType.ReferenceExtraction,
  WorkflowRunType.ChunkSplitting,
  WorkflowRunType.DocumentSummarization,
];

async function createProject(title: string): Promise<{ project: { id: string } }> {
  const authHeader = await getAuthHeader();
  if (!authHeader) {
    throw new Error('Authentication required');
  }

  const response = await fetch(`${baseUrl}/api/projects`, {
    method: 'POST',
    headers: {
      Authorization: authHeader,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create project: ${error}`);
  }

  return response.json();
}

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
  const { mainDocument, openaiApiKey, preflightStatus, setPreflightStatus, setMainDocument, setApiKey, setProjectId } =
    wizard;
  const [storedApiKey, setStoredApiKey] = useSessionStorage<string>('openai-api-key', '');
  const { runPreflight, isValidating } = usePreflight();
  const [showApiKey, setShowApiKey] = useState(false);
  const [uploadStage, setUploadStage] = useState<UploadStage>('idle');
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  const apiKey = openaiApiKey || storedApiKey;
  const fileSizeLabel = mainDocument ? formatBytes(mainDocument.size) : '';

  // Refs to track current values for debounced validation (avoids stale closures)
  const apiKeyRef = useRef(apiKey);
  const mainDocumentRef = useRef(mainDocument);
  apiKeyRef.current = apiKey;
  mainDocumentRef.current = mainDocument;

  const formatStatus = validateDocument(mainDocument);

  const runApiKeyValidation = useCallback(async (): Promise<boolean> => {
    if (HIDE_API_KEY_INPUT) {
      setPreflightStatus({ apiKey: 'valid' });
      return true;
    }
    if (!apiKey || apiKey.length < MIN_API_KEY_LENGTH) {
      setPreflightStatus({ apiKey: 'idle' });
      return false;
    }
    setPreflightStatus({ apiKey: 'pending' });
    const isValid = await runPreflight({
      mainDocument,
      supportingDocuments: [],
      openaiApiKey: apiKey,
    });
    setPreflightStatus({ apiKey: isValid ? 'valid' : 'invalid' });
    return isValid;
  }, [apiKey, mainDocument, setPreflightStatus, runPreflight]);

  const debouncedValidation = useMemo(
    () =>
      debounce(async () => {
        if (HIDE_API_KEY_INPUT) return;
        const currentApiKey = apiKeyRef.current;
        const currentDocument = mainDocumentRef.current;
        if (!currentDocument || !currentApiKey || currentApiKey.length < MIN_API_KEY_LENGTH) {
          return;
        }
        setPreflightStatus({ apiKey: 'pending' });
        const isValid = await runPreflight({
          mainDocument: currentDocument,
          supportingDocuments: [],
          openaiApiKey: currentApiKey,
        });
        setPreflightStatus({ apiKey: isValid ? 'valid' : 'invalid' });
      }, 500),
    [setPreflightStatus, runPreflight],
  );

  useEffect(() => {
    return () => {
      debouncedValidation.cancel();
    };
  }, [debouncedValidation]);

  const createProjectAndProcess = useMutation({
    mutationFn: async () => {
      if (!mainDocument) throw new Error('No document selected');

      setUploadStage('creating');
      const { project } = await createProject(mainDocument.name);

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
          openai_api_key: apiKey || undefined,
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
      toast.error(error instanceof Error ? error.message : 'Failed to create project');
    },
  });

  const handleDocumentChange = useCallback(
    (files: File[]) => {
      setMainDocument(files[0] || null);
      setUploadStage('idle');
      setUploadProgress(null);
      if (!HIDE_API_KEY_INPUT) {
        setPreflightStatus({ apiKey: 'idle' });
        debouncedValidation();
      }
    },
    [setMainDocument, setPreflightStatus, debouncedValidation],
  );

  const handleApiKeyChange = useCallback(
    (value: string) => {
      setApiKey(value);
      setStoredApiKey(value);
      setPreflightStatus({ apiKey: 'idle' });
      debouncedValidation();
    },
    [setApiKey, setStoredApiKey, setPreflightStatus, debouncedValidation],
  );

  const handleContinue = useCallback(async () => {
    setPreflightStatus({ format: formatStatus });

    if (formatStatus !== 'valid') {
      toast.error('Please upload a valid document');
      return;
    }
    if (!HIDE_API_KEY_INPUT && preflightStatus.apiKey !== 'valid') {
      if (!(await runApiKeyValidation())) {
        toast.error('Please enter a valid OpenAI API key');
        return;
      }
    }
    createProjectAndProcess.mutate();
  }, [formatStatus, preflightStatus.apiKey, setPreflightStatus, runApiKeyValidation, createProjectAndProcess]);

  const isLoading = isValidating || createProjectAndProcess.isPending;
  const canContinue =
    formatStatus === 'valid' && (HIDE_API_KEY_INPUT || preflightStatus.apiKey === 'valid') && !isLoading;

  const stageMessage = useMemo(
    () => getStageMessage(uploadStage, uploadProgress, fileSizeLabel),
    [uploadStage, uploadProgress, fileSizeLabel],
  );

  return {
    mainDocument,
    apiKey,
    showApiKey,
    preflightStatus: { ...preflightStatus, format: formatStatus },
    hideApiKeyInput: HIDE_API_KEY_INPUT,
    isLoading,
    isValidating,
    canContinue,
    uploadStage,
    uploadProgress,
    stageMessage,
    fileSizeLabel,
    setShowApiKey,
    handleDocumentChange,
    handleApiKeyChange,
    handleContinue,
  };
}
