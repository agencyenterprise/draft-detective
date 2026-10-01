import { describe, expect, it, vi } from 'vitest';
import { TooltipProvider } from '@/components/ui/tooltip';
import {
  type Issue,
  type WorkflowRunDetail,
  type WorkflowRunSummary,
  WorkflowRunStatus,
  WorkflowRunType,
  WorkflowStateStatus,
} from '@/lib/generated-api';
import { renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { WorkflowResultsContent } from './workflow-results-renderer';

vi.mock('@/lib/hooks/use-workflow-types', () => ({
  useWorkflowTypes: () => ({
    getWorkflowTypeName: (type: string) => type,
    isWorkflowTypeVisible: () => true,
  }),
}));

const TYPE = WorkflowRunType.ClaimReferenceValidationV2;
const run = { id: 'run-1', type: TYPE, status: WorkflowRunStatus.Completed };
const summary = { run, errors: [] } as unknown as WorkflowRunSummary;
const detail = {
  run,
  state: { type: TYPE, errors: [] },
  state_status: WorkflowStateStatus.Ok,
} as unknown as WorkflowRunDetail;

async function show(props: { workflowRun?: WorkflowRunDetail; issues?: Issue[]; loadError?: unknown }) {
  const view = await renderInto(
    withQueryClient(
      testQueryClient(),
      <TooltipProvider>
        <WorkflowResultsContent
          summary={summary}
          workflowRun={props.workflowRun}
          issues={props.issues}
          loadError={props.loadError}
          canEditIssues
          onNavigateToDocumentExplorer={() => undefined}
        />
      </TooltipProvider>,
    ),
  );
  const text = view.container.textContent ?? '';
  await view.unmount();
  return text;
}

describe('WorkflowResultsContent', () => {
  it('waits for the issues rather than calling the run clean', async () => {
    const text = await show({ workflowRun: detail, issues: undefined });

    expect(text).toContain('Loading results');
    expect(text).not.toContain('All checks passed');
  });

  it('says so when the issues failed to load, instead of an all-clear', async () => {
    const text = await show({ workflowRun: detail, issues: undefined, loadError: new Error('Access denied') });

    expect(text).toContain('Could not load these results: Access denied');
    expect(text).not.toContain('All checks passed');
  });

  it('reports a failed run detail instead of loading forever', async () => {
    const text = await show({ workflowRun: undefined, issues: [], loadError: new Error('Server error') });

    expect(text).toContain('Could not load these results: Server error');
    expect(text).not.toContain('Loading results');
  });

  it('calls the run clean only once its issues have loaded empty', async () => {
    const text = await show({ workflowRun: detail, issues: [] });

    expect(text).toContain('All checks passed');
  });
});
