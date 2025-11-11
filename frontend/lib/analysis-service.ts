import {
  AnalysisApi,
  ChunkEvalPackageRequest,
  ChunkReevaluationRequest,
  ChunkReevaluationResponse,
  ClaimSubstantiatorStateOutput,
  EvaluationApi,
  EvalPackageRequest,
  HealthApi,
  SubstantiationWorkflowConfig,
  StartAnalysisResponse,
  StartAnalysisResponseFromJSON,
} from '@/lib/generated-api';
import { downloadBlobResponse, generateDefaultTestName } from '@/lib/utils';
import { analysisApi, evaluationApi, healthApi, apiUrl, getAuthHeader } from './api';
import { getSession } from 'next-auth/react';

interface AnalysisRequest {
  mainDocument: File;
  supportingDocuments?: File[];
  config?: SubstantiationWorkflowConfig;
}

export interface SupportedAgentsResponse {
  supported_agents: string[];
  agent_descriptions: Record<string, string>;
}
class AnalysisService {
  private readonly analysisApi: AnalysisApi;
  private readonly evaluationApi: EvaluationApi;
  private readonly healthApi: HealthApi;

  constructor() {
    this.analysisApi = analysisApi;
    this.evaluationApi = evaluationApi;
    this.healthApi = healthApi;
  }

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
  ): Promise<StartAnalysisResponse> {
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
        if (config.useToulmin !== undefined) formData.append('use_toulmin', String(config.useToulmin));
        if (config.runLiteratureReview !== undefined)
          formData.append('run_literature_review', String(config.runLiteratureReview));
        if (config.runSuggestCitations !== undefined)
          formData.append('run_suggest_citations', String(config.runSuggestCitations));
        if (config.runLiveReports !== undefined) formData.append('run_live_reports', String(config.runLiveReports));
        if (config.runReferenceValidation !== undefined)
          formData.append('run_reference_validation', String(config.runReferenceValidation));
        if (config.domain) formData.append('domain', config.domain);
        if (config.targetAudience) formData.append('target_audience', config.targetAudience);
        if (config.documentPublicationDate)
          formData.append('document_publication_date', config.documentPublicationDate.toISOString().split('T')[0]);
        if (config.sessionId) formData.append('session_id', config.sessionId);

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
              const response = StartAnalysisResponseFromJSON(rawResponse);
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

        xhr.open('POST', `${apiUrl}/api/start-analysis`);

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

  async getSupportedAgents(): Promise<SupportedAgentsResponse> {
    try {
      return await this.healthApi.getSupportedAgentsApiSupportedAgentsGet();
    } catch (error) {
      console.error('Error fetching supported agents:', error);
      throw error;
    }
  }

  async reevaluateChunk(
    request: ChunkReevaluationRequest & { sessionId?: string | null },
  ): Promise<ChunkReevaluationResponse> {
    try {
      const requestWithSession: ChunkReevaluationRequest = {
        ...request,
        sessionId: request.sessionId,
      };

      return await this.analysisApi.reevaluateChunkApiReevaluateChunkPost({
        chunkReevaluationRequest: requestWithSession,
      });
    } catch (error) {
      console.error('Error re-evaluating chunk:', error);
      throw error;
    }
  }

  async generateEvalPackage(
    results: ClaimSubstantiatorStateOutput,
    testName?: string,
    description?: string,
  ): Promise<Blob> {
    try {
      const evalRequest: EvalPackageRequest = {
        results,
        testName: testName || generateDefaultTestName('eval'),
        description: description || 'Generated from frontend analysis',
      };

      return downloadBlobResponse(() =>
        this.evaluationApi.generateEvalPackageApiGenerateEvalPackagePostRaw({
          evalPackageRequest: evalRequest,
        }),
      );
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
        chunkIndex,
        selectedAgents,
        testName: testName || generateDefaultTestName('chunk_eval', chunkIndex.toString()),
        description: description || `Generated from chunk ${chunkIndex} analysis`,
      };

      return downloadBlobResponse(() =>
        this.evaluationApi.generateChunkEvalPackageApiGenerateChunkEvalPackagePostRaw({
          chunkEvalPackageRequest: evalRequest,
        }),
      );
    } catch (error) {
      console.error('Error generating chunk eval package:', error);
      throw error;
    }
  }
}

export const analysisService = new AnalysisService();

export { AnalysisService };
export type { AnalysisRequest };
