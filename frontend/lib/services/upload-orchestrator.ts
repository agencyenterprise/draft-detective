import { AnalysisRequest, analysisService } from '../analysis-service';
import { StartWorkflowResponse } from '../generated-api';
import { ProgressCallbacks, ProgressTracker } from './progress-tracker';

export interface ValidationError {
  fileName: string;
  error: string;
}

export interface ValidationResult {
  valid: boolean;
  errors?: ValidationError[];
}

export class UploadOrchestrator {
  formatValidationErrors(errors: ValidationError[]): string {
    const fileList = errors.map((e) => `${e.fileName}: ${e.error}`).join('\n');
    return `File validation failed:\n${fileList}`;
  }

  async startAnalysisWithProgress(
    request: AnalysisRequest,
    callbacks: ProgressCallbacks,
  ): Promise<StartWorkflowResponse> {
    const tracker = new ProgressTracker('Uploading files');

    try {
      callbacks.onStageChange?.('uploading');

      const response = await analysisService.startAnalysis(request, (progress) => {
        const state = tracker.setProgress(progress);
        callbacks.onProgress?.(state.progress);
      });

      tracker.setCompleted();
      callbacks.onProgress?.(100);
      callbacks.onStageChange?.('complete');

      return response;
    } catch (error) {
      tracker.setError(error instanceof Error ? error.message : 'Upload failed');
      throw error;
    }
  }
}

export const uploadOrchestrator = new UploadOrchestrator();
