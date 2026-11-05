import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useWorkflowDurationEstimates } from '@/lib/hooks/use-workflow-duration-estimates';
import { WorkflowRunType } from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ estimates: vi.fn() }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getDurationEstimatesApiWorkflowTypesDurationEstimatesGet: mocks.estimates,
}));

beforeEach(() => vi.clearAllMocks());

type Estimates = ReturnType<typeof useWorkflowDurationEstimates>;

async function mount(projectId: string | undefined) {
  let latest!: Estimates;
  function Probe() {
    latest = useWorkflowDurationEstimates(projectId);
    return null;
  }
  const view = await renderInto(withQueryClient(testQueryClient(), <Probe />));
  await flush();
  return { view, latest: () => latest };
}

describe('useWorkflowDurationEstimates', () => {
  it('asks for nothing until there is a project', async () => {
    const { view, latest } = await mount(undefined);

    expect(mocks.estimates).not.toHaveBeenCalled();
    expect(latest().getEstimatedSeconds(WorkflowRunType.AbbreviationScanV2)).toBeNull();
    await view.unmount();
  });

  it("looks up each type's estimate for the project, null when there is none", async () => {
    mocks.estimates.mockResolvedValue({
      estimates: [
        { type: WorkflowRunType.AbbreviationScanV2, estimated_seconds: 90 },
        { type: WorkflowRunType.FiguresTablesCheck, estimated_seconds: null },
      ],
    });

    const { view, latest } = await mount('p');

    expect(mocks.estimates).toHaveBeenCalledWith({ query: { project_id: 'p' } });
    expect(latest().getEstimatedSeconds(WorkflowRunType.AbbreviationScanV2)).toBe(90);
    expect(latest().getEstimatedSeconds(WorkflowRunType.FiguresTablesCheck)).toBeNull();
    expect(latest().getEstimatedSeconds(WorkflowRunType.ReferenceValidationV2)).toBeNull();
    await view.unmount();
  });
});
