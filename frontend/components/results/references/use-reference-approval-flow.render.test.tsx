import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost,
  getProjectReferencesEndpointApiProjectProjectIdReferencesGet,
  type ProjectOverview,
  type ProjectReferences,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { act } from 'react';
import { useReferenceApprovalFlow } from './use-reference-approval-flow';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getProjectReferencesEndpointApiProjectProjectIdReferencesGet: vi.fn(),
  approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost: vi.fn(),
}));
vi.mock('@/lib/hooks/use-workflow-types', () => ({ useWorkflowTypes: () => ({ workflowTypes: [] }) }));

const fetchReferences = vi.mocked(getProjectReferencesEndpointApiProjectProjectIdReferencesGet);
const approve = vi.mocked(approveProjectGateEndpointApiProjectsProjectIdGatesGateApprovePost);

const overview = {
  project: { id: 'project-1', current_revision: 1 },
  revision: 1,
  files: [],
  workflow_runs: [
    {
      run: { id: 'extraction', type: WorkflowRunType.ReferenceExtraction, status: WorkflowRunStatus.Completed },
      errors: [],
    },
  ],
} as unknown as ProjectOverview;

/** One unmatched reference: approving must warn before starting. */
const references = {
  extracted_references: [{ id: 'r1', text: 'Smith 2020' }],
  matches: [],
  fetched_references: [],
} as unknown as ProjectReferences;

type Flow = ReturnType<typeof useReferenceApprovalFlow>;

async function mountFlow() {
  const seen: { current?: Flow } = {};
  function Probe() {
    seen.current = useReferenceApprovalFlow(overview);
    return null;
  }
  const view = await renderInto(withQueryClient(testQueryClient(), <Probe />));
  return { seen, view };
}

afterEach(() => vi.clearAllMocks());

describe('useReferenceApprovalFlow', () => {
  it('keeps approval closed while the references are loading', async () => {
    fetchReferences.mockReturnValue(new Promise(() => {}) as never);
    const { seen, view } = await mountFlow();

    expect(seen.current?.isApproveDisabled).toBe(true);
    expect(seen.current?.approveButtonText).toBe('Loading references...');
    await act(async () => seen.current?.handleApprove());
    expect(approve).not.toHaveBeenCalled();
    await view.unmount();
  });

  it('keeps approval closed when the references failed to load', async () => {
    fetchReferences.mockRejectedValue(new Error('Server error'));
    const { seen, view } = await mountFlow();
    await flush();

    expect(seen.current?.isApproveDisabled).toBe(true);
    await act(async () => seen.current?.handleApprove());
    expect(approve).not.toHaveBeenCalled();
    expect(seen.current?.showUnmatchedWarning).toBe(false);
    await view.unmount();
  });

  it('warns about unmatched references once they have loaded', async () => {
    fetchReferences.mockResolvedValue(references as never);
    const { seen, view } = await mountFlow();
    await flush();

    expect(seen.current?.isApproveDisabled).toBe(false);
    expect(seen.current?.unmatchedCount).toBe(1);
    await act(async () => seen.current?.handleApprove());
    expect(seen.current?.showUnmatchedWarning).toBe(true);
    expect(approve).not.toHaveBeenCalled();
    await view.unmount();
  });
});
