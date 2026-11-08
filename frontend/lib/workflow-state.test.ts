import { describe, expect, it } from 'vitest';
import { WorkflowRunPublic, WorkflowRunStatus, WorkflowRunType } from './generated-api';
import { getDocumentProcessingFailure } from './workflow-state';

function run(
  type: WorkflowRunType,
  status: WorkflowRunStatus,
  failure_message: string | null = null,
): { run: WorkflowRunPublic } {
  return { run: { id: crypto.randomUUID(), type, status, failure_message } as WorkflowRunPublic };
}

describe('getDocumentProcessingFailure', () => {
  it("returns the failed document processing run's own message", () => {
    const runs = [
      run(WorkflowRunType.ReferenceExtraction, WorkflowRunStatus.Cancelled),
      run(
        WorkflowRunType.DocumentProcessing,
        WorkflowRunStatus.Failed,
        'Could not convert the main document broken.docx: File is not a zip file',
      ),
    ];

    expect(getDocumentProcessingFailure(runs)).toBe(
      'Could not convert the main document broken.docx: File is not a zip file',
    );
  });

  it('still reports a failure that carries no message', () => {
    expect(getDocumentProcessingFailure([run(WorkflowRunType.DocumentProcessing, WorkflowRunStatus.Failed)])).not.toBe(
      null,
    );
  });

  it('is null unless document processing itself failed', () => {
    expect(getDocumentProcessingFailure([])).toBe(null);
    expect(getDocumentProcessingFailure([run(WorkflowRunType.DocumentProcessing, WorkflowRunStatus.Completed)])).toBe(
      null,
    );
    expect(
      getDocumentProcessingFailure([
        run(WorkflowRunType.ReferenceExtraction, WorkflowRunStatus.Failed, 'Rate limited'),
      ]),
    ).toBe(null);
  });
});
