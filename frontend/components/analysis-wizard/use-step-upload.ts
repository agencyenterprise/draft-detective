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

// Pure validation function - moved outside hook to avoid recreation on each render
const validateDocument = (file: File | null): PreflightStatus =>
  !file ? 'idle' : file.size <= MAX_FILE_SIZE_BYTES ? 'valid' : 'invalid';

export function useStepUpload(onComplete: () => void) {
  const wizard = useWizard();
  const [storedApiKey, setStoredApiKey] = useSessionStorage<string>('openai-api-key', '');
  const { runPreflight, isValidating } = usePreflight();
  const [showApiKey, setShowApiKey] = useState(false);

  const hideApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';
  const apiKey = wizard.openaiApiKey || storedApiKey;

  const runApiKeyValidation = useCallback(async (): Promise<boolean> => {
    if (hideApiKeyInput) {
      wizard.setPreflightStatus({ apiKey: 'valid' });
      return true;
    }
    if (!apiKey || apiKey.length < 10) {
      wizard.setPreflightStatus({ apiKey: 'idle' });
      return false;
    }
    wizard.setPreflightStatus({ apiKey: 'pending' });
    const isValid = await runPreflight({
      mainDocument: wizard.mainDocument,
      supportingDocuments: [],
      openaiApiKey: apiKey,
    });
    wizard.setPreflightStatus({ apiKey: isValid ? 'valid' : 'invalid' });
    return isValid;
  }, [hideApiKeyInput, apiKey, wizard.mainDocument, wizard.setPreflightStatus, runPreflight]);

  // Auto-validate on changes
  useEffect(() => {
    wizard.setPreflightStatus({ format: validateDocument(wizard.mainDocument) });
  }, [wizard.mainDocument, wizard.setPreflightStatus]);

  useEffect(() => {
    if (wizard.mainDocument && apiKey?.length >= 10 && wizard.preflightStatus.apiKey === 'idle') {
      runApiKeyValidation();
    }
  }, [wizard.mainDocument, apiKey, wizard.preflightStatus.apiKey, runApiKeyValidation]);

  // Project creation and document processing
  const createProjectAndProcess = useMutation({
    mutationFn: async () => {
      if (!wizard.mainDocument) throw new Error('No document selected');

      // 1. Create the project
      const projectResponse = await createProjectEndpointApiProjectsPost({
        body: { title: wizard.mainDocument.name, main_document: wizard.mainDocument },
      });

      // 2. Start document processing immediately
      await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: {
          project_id: projectResponse.project.id,
          workflow_types: [WorkflowRunType.DocumentProcessing],
          openai_api_key: apiKey || undefined,
        },
      });

      return projectResponse;
    },
    onSuccess: (response) => {
      wizard.setProjectId(response.project.id);
      toast.success('Project created - document processing started');
      onComplete();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to create project');
    },
  });

  // Handlers
  const handleDocumentChange = (files: File[]) => {
    wizard.setMainDocument(files[0] || null);
    if (!hideApiKeyInput) wizard.setPreflightStatus({ apiKey: 'idle' });
  };

  const handleApiKeyChange = (value: string) => {
    wizard.setApiKey(value);
    setStoredApiKey(value);
    wizard.setPreflightStatus({ apiKey: 'idle' });
  };

  const handleContinue = async () => {
    if (wizard.preflightStatus.format !== 'valid') {
      toast.error('Please upload a valid document');
      return;
    }
    if (!hideApiKeyInput && wizard.preflightStatus.apiKey !== 'valid') {
      if (!(await runApiKeyValidation())) {
        toast.error('Please enter a valid OpenAI API key');
        return;
      }
    }
    createProjectAndProcess.mutate();
  };

  const isLoading = isValidating || createProjectAndProcess.isPending;
  const canContinue =
    wizard.preflightStatus.format === 'valid' &&
    (hideApiKeyInput || wizard.preflightStatus.apiKey === 'valid') &&
    !isLoading;

  return {
    // State
    mainDocument: wizard.mainDocument,
    apiKey,
    showApiKey,
    preflightStatus: wizard.preflightStatus,
    hideApiKeyInput,
    isLoading,
    isValidating,
    canContinue,
    // Handlers
    setShowApiKey,
    handleDocumentChange,
    handleApiKeyChange,
    handleContinue,
  };
}
