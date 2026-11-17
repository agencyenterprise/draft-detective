import { act, type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { ProjectOverview, WorkflowRunStatus, WorkflowRunType } from '@/lib/generated-api';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { AssessmentsTab } from './assessments-tab';

interface DialogProps {
  runningTypes?: WorkflowRunType[];
  onConfirm: (values: WorkflowConfigFormValues) => void;
}

const mocks = vi.hoisted(() => ({ startMultiple: vi.fn(), dialog: { props: undefined as DialogProps | undefined } }));

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  startMultipleWorkflowsApiWorkflowsStartMultiplePost: mocks.startMultiple,
}));
vi.mock('@/components/workflows/workflow-config-dialog', () => ({
  WorkflowConfigDialog: (props: DialogProps) => {
    mocks.dialog.props = props;
    return null;
  },
}));
vi.mock('@/lib/hooks/use-project-data', async (original) => ({
  ...(await original<typeof import('@/lib/hooks/use-project-data')>()),
  useProjectIssues: () => ({ data: [], error: null }),
  useWorkflowRunDetail: () => ({ data: undefined, error: null }),
}));
vi.mock('@/lib/hooks/use-workflow-types', () => ({
  useWorkflowTypes: () => ({
    getWorkflowTypeName: (type: string) => type,
    getWorkflowTypeDescription: () => null,
    isWorkflowTypeVisible: () => true,
  }),
}));
vi.mock('./use-workflow-selection', () => ({
  useWorkflowSelection: () => ({
    selectedWorkflowType: null,
    selectedWorkflowRun: null,
    isResolvingRun: false,
    historyError: null,
    historyData: undefined,
    handleSelectWorkflowType: () => {},
    handleSelectRun: () => {},
  }),
}));
vi.mock('./assessment-rail', () => ({ AssessmentRail: () => null }));
vi.mock('../panes', () => ({
  Rail: ({ children }: { children: ReactNode }) => children,
  RailToggle: () => null,
  useRailState: () => ({ close: () => {} }),
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const PROJECT = 'project-1';

function overviewWithRunning(type: WorkflowRunType): ProjectOverview {
  return {
    project: { id: PROJECT },
    access_level: 'write',
    workflow_runs: [{ run: { id: 'run-1', type, status: WorkflowRunStatus.Running } }],
  } as unknown as ProjectOverview;
}

let rendered: Rendered | undefined;
beforeEach(() => vi.clearAllMocks());
afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
  mocks.dialog.props = undefined;
});

async function mountTab(overview: ProjectOverview) {
  rendered = await renderInto(
    withQueryClient(
      testQueryClient(),
      <AssessmentsTab
        overview={overview}
        readOnly={false}
        onNavigateToDocumentExplorer={() => {}}
        onNavigateToReferences={() => {}}
      />,
    ),
  );
}

describe('AssessmentsTab run dialog', () => {
  it('keeps an assessment that is already running out of the selection', async () => {
    await mountTab(overviewWithRunning(WorkflowRunType.AbbreviationScanV2));

    expect(mocks.dialog.props?.runningTypes).toContain(WorkflowRunType.AbbreviationScanV2);
  });

  it('counts a start still in flight as running, so a second Run cannot start it twice', async () => {
    mocks.startMultiple.mockReturnValue(new Promise(() => {}));
    await mountTab(overviewWithRunning(WorkflowRunType.AbbreviationScanV2));

    await act(async () =>
      mocks.dialog.props!.onConfirm({ workflowTypes: [WorkflowRunType.Reviewer2] } as WorkflowConfigFormValues),
    );
    await flush();

    expect(mocks.startMultiple).toHaveBeenCalledOnce();
    expect(mocks.dialog.props?.runningTypes).toContain(WorkflowRunType.Reviewer2);
  });
});
