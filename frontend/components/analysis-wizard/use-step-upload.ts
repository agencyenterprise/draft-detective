import { useState, useEffect, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useWizard, PreflightStatus } from './wizard-context';
import { usePreflight } from '@/lib/hooks/use-preflight';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { MAX_FILE_SIZE_BYTES } from '@/lib/constants';
import {
  createProjectEndpointApiProjectsPost,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  WorkflowRunType,
} from '@/lib/generated-api';

const validateDocument = (file: File | null): PreflightStatus =>
  !file ? 'idle' : file.size <= MAX_FILE_SIZE_BYTES ? 'valid' : 'invalid';

export function useStepUpload(onComplete: () => void) {
  const wizard = useWizard();
  const { mainDocument, openaiApiKey, preflightStatus, setPreflightStatus, setMainDocument, setApiKey, setProjectId } =
    wizard;
  const [storedApiKey, setStoredApiKey] = useSessionStorage<string>('openai-api-key', '');
  const { runPreflight, isValidating } = usePreflight();
  const [showApiKey, setShowApiKey] = useState(false);

  const hideApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';
  const apiKey = openaiApiKey || storedApiKey;

  const runApiKeyValidation = useCallback(async (): Promise<boolean> => {
    if (hideApiKeyInput) {
      setPreflightStatus({ apiKey: 'valid' });
      return true;
    }
    if (!apiKey || apiKey.length < 10) {
      setPreflightStatus({ apiKey: 'idle' });
      return false;
    }
    setPreflightStatus({ apiKey: 'pending' });
    const isValid = await runPreflight({
      mainDocument: mainDocument,
      supportingDocuments: [],
      openaiApiKey: apiKey,
    });
    setPreflightStatus({ apiKey: isValid ? 'valid' : 'invalid' });
    return isValid;
  }, [hideApiKeyInput, apiKey, mainDocument, setPreflightStatus, runPreflight]);

  useEffect(() => {
    setPreflightStatus({ format: validateDocument(mainDocument) });
  }, [mainDocument, setPreflightStatus]);

  useEffect(() => {
    if (mainDocument && apiKey?.length >= 10 && preflightStatus.apiKey === 'idle') {
      runApiKeyValidation();
    }
  }, [mainDocument, apiKey, preflightStatus.apiKey, runApiKeyValidation]);

  const createProjectAndProcess = useMutation({
    mutationFn: async () => {
      if (!mainDocument) throw new Error('No document selected');

      const projectResponse = await createProjectEndpointApiProjectsPost({
        body: { title: mainDocument.name, main_document: mainDocument },
      });

      await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectResponse.project.id,
          workflow_types: [
            WorkflowRunType.DocumentProcessing,
            WorkflowRunType.ReferenceExtraction,
            WorkflowRunType.DocumentSummarization,
          ],
          openai_api_key: apiKey || undefined,
        },
      });

      return projectResponse;
    },
    onSuccess: (response) => {
      setProjectId(response.project.id);
      toast.success('Project created - document processing started');
      onComplete();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to create project');
    },
  });

  const handleDocumentChange = (files: File[]) => {
    setMainDocument(files[0] || null);
    if (!hideApiKeyInput) setPreflightStatus({ apiKey: 'idle' });
  };

  const handleApiKeyChange = (value: string) => {
    setApiKey(value);
    setStoredApiKey(value);
    setPreflightStatus({ apiKey: 'idle' });
  };

  const handleContinue = async () => {
    if (preflightStatus.format !== 'valid') {
      toast.error('Please upload a valid document');
      return;
    }
    if (!hideApiKeyInput && preflightStatus.apiKey !== 'valid') {
      if (!(await runApiKeyValidation())) {
        toast.error('Please enter a valid OpenAI API key');
        return;
      }
    }
    createProjectAndProcess.mutate();
  };

  const isLoading = isValidating || createProjectAndProcess.isPending;
  const canContinue =
    preflightStatus.format === 'valid' && (hideApiKeyInput || preflightStatus.apiKey === 'valid') && !isLoading;

  return {
    mainDocument,
    apiKey,
    showApiKey,
    preflightStatus,
    hideApiKeyInput,
    isLoading,
    isValidating,
    canContinue,
    setShowApiKey,
    handleDocumentChange,
    handleApiKeyChange,
    handleContinue,
  };
}
