import {
  ChunkEvalPackageRequest,
  ClaimSubstantiatorStateOutput,
  EvalPackageRequest,
  generateChunkEvalPackageApiGenerateChunkEvalPackagePost,
  generateEvalPackageApiGenerateEvalPackagePost,
  StartWorkflowResponse,
  SubstantiationWorkflowConfig,
} from '@/lib/generated-api';
import { generateDefaultTestName } from '@/lib/utils';
import { baseUrl, getAuthHeader } from './api';

interface AnalysisRequest {
  mainDocument: File;
  supportingDocuments?: File[];
  config?: SubstantiationWorkflowConfig;
}

class AnalysisService {
  constructor() {}

  /**
   * Start analysis with upload progress tracking.
   *
   * Note: This method bypasses the OpenAPI client to support
   * XMLHttpRequest progress events. All other endpoints use
   * the generated client for type safety.
   */
  async startAnalysis(
    request: AnalysisRequest,
    onProgress?: (progress: number) => void,
  ): Promise<StartWorkflowResponse> {
    return new Promise(async (resolve, reject) => {
      try {
        const config = request.config || {};

        const formData = new FormData();
        formData.append('main_document', request.mainDocument);

        if (request.supportingDocuments) {
          request.supportingDocuments.forEach((file) => {
            formData.append('supporting_documents', file);
          });
        }

        // Add config parameters
        if (config.use_toulmin !== undefined) formData.append('use_toulmin', String(config.use_toulmin));
        if (config.domain) formData.append('domain', config.domain);
        if (config.target_audience) formData.append('target_audience', config.target_audience);
        if (config.openai_api_key) formData.append('openai_api_key', config.openai_api_key);
        if (config.publication_date) formData.append('publication_date', config.publication_date);
        if (config.workflow_types) formData.append('workflow_types', config.workflow_types.join(','));

        // Use XMLHttpRequest for upload progress tracking
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable && onProgress) {
            const percentComplete = (event.loaded / event.total) * 100;
            onProgress(percentComplete);
          }
        });

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const rawResponse = JSON.parse(xhr.responseText);
              const response = rawResponse as StartWorkflowResponse;
              resolve(response);
            } catch {
              reject(new Error('Failed to parse response'));
            }
          } else {
            reject(new Error(`HTTP error! status: ${xhr.status}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Network error occurred'));
        });

        xhr.addEventListener('abort', () => {
          reject(new Error('Upload aborted'));
        });

        xhr.open('POST', `${baseUrl}/api/start-analysis`);

        // Set authorization header if available
        const authHeader = await getAuthHeader();
        if (authHeader) {
          xhr.setRequestHeader('Authorization', authHeader);
        }

        xhr.send(formData);
      } catch (error) {
        console.error('Error starting analysis:', error);
        reject(error);
      }
    });
  }

  async generateEvalPackage(
    results: ClaimSubstantiatorStateOutput,
    testName?: string,
    description?: string,
  ): Promise<Blob> {
    try {
      const evalRequest: EvalPackageRequest = {
        results,
        test_name: testName || generateDefaultTestName('eval'),
        description: description || 'Generated from frontend analysis',
      };

      const response = await generateEvalPackageApiGenerateEvalPackagePost({
        body: evalRequest,
      });

      // The response should be a Blob for file downloads
      if (response instanceof Blob) {
        return response;
      }

      // If it's not a Blob, try to convert it
      throw new Error('Unexpected response type from eval package generation');
    } catch (error) {
      console.error('Error generating eval package:', error);
      throw error;
    }
  }

  async generateChunkEvalPackage(
    results: ClaimSubstantiatorStateOutput,
    chunkIndex: number,
    selectedAgents: string[],
    testName?: string,
    description?: string,
  ): Promise<Blob> {
    try {
      const evalRequest: ChunkEvalPackageRequest = {
        results,
        chunk_index: chunkIndex,
        selected_agents: selectedAgents,
        test_name: testName || generateDefaultTestName('chunk_eval', chunkIndex.toString()),
        description: description || `Generated from chunk ${chunkIndex} analysis`,
      };

      const response = await generateChunkEvalPackageApiGenerateChunkEvalPackagePost({
        body: evalRequest,
      });

      // The response should be a Blob for file downloads
      if (response instanceof Blob) {
        return response;
      }

      // If it's not a Blob, try to convert it
      throw new Error('Unexpected response type from chunk eval package generation');
    } catch (error) {
      console.error('Error generating chunk eval package:', error);
      throw error;
    }
  }
}

export const analysisService = new AnalysisService();

export { AnalysisService };
export type { AnalysisRequest };
