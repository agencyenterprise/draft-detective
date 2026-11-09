import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkflowRunType } from '@/lib/generated-api';
import { DEFAULT_SELECTED_WORKFLOW_TYPES } from '@/components/workflows/utils';
import { renderInto, type Rendered } from '@/lib/test-render';
import { useWizard, WizardProvider } from './wizard-context';

const lookups = vi.hoisted(() => ({
  visibleTypes: [] as WorkflowRunType[],
  recentTypes: [] as WorkflowRunType[],
  recentPending: false,
}));
vi.mock('@/lib/hooks/use-visible-workflow-types', () => ({
  useVisibleWorkflowTypes: () => ({ visibleTypes: lookups.visibleTypes }),
}));
vi.mock('@/lib/hooks/use-workflow-types', () => ({ useWorkflowTypes: () => ({ workflowTypes: [] }) }));
vi.mock('@/lib/hooks/use-recent-workflow-selection', () => ({
  useRecentWorkflowSelection: () => ({ recentTypes: lookups.recentTypes, isPending: lookups.recentPending }),
}));

const ALL = [
  ...DEFAULT_SELECTED_WORKFLOW_TYPES,
  WorkflowRunType.ActiveVoice,
  WorkflowRunType.FiguresTablesCheck,
  WorkflowRunType.AbbreviationScanV2,
];

beforeEach(() => {
  lookups.visibleTypes = ALL;
  lookups.recentTypes = [];
  lookups.recentPending = false;
});

let view: Rendered | undefined;
afterEach(async () => {
  await view?.unmount();
  view = undefined;
});

let wizard!: ReturnType<typeof useWizard>;

/** Mounts the provider; `refresh` renders it again after the mocked lookups change. */
async function mount() {
  function Probe() {
    wizard = useWizard();
    return null;
  }
  const tree = () => (
    <WizardProvider>
      <Probe />
    </WizardProvider>
  );
  view = await renderInto(tree());
  return { refresh: () => view!.rerender(tree()) };
}

describe('WizardProvider', () => {
  it('opens on the assessments the user ran on their last project', async () => {
    lookups.recentTypes = [WorkflowRunType.ActiveVoice, WorkflowRunType.FiguresTablesCheck];
    await mount();

    expect(wizard.selectedWorkflowTypes).toEqual([WorkflowRunType.ActiveVoice, WorkflowRunType.FiguresTablesCheck]);
  });

  it('falls back to the recommended set when there is no last project to copy', async () => {
    await mount();

    expect(wizard.selectedWorkflowTypes).toEqual(DEFAULT_SELECTED_WORKFLOW_TYPES);
  });

  it('checks nothing while the last selection loads, rather than swapping the fallback out later', async () => {
    lookups.recentPending = true;
    const { refresh } = await mount();
    expect(wizard.selectedWorkflowTypes).toEqual([]);

    lookups.recentPending = false;
    lookups.recentTypes = [WorkflowRunType.ActiveVoice];
    await refresh();

    expect(wizard.selectedWorkflowTypes).toEqual([WorkflowRunType.ActiveVoice]);
  });

  it('never pre-checks an assessment this user cannot see', async () => {
    lookups.recentTypes = [WorkflowRunType.ActiveVoice, WorkflowRunType.FiguresTablesCheck];
    lookups.visibleTypes = ALL.filter((type) => type !== WorkflowRunType.FiguresTablesCheck);
    await mount();

    expect(wizard.selectedWorkflowTypes).toEqual([WorkflowRunType.ActiveVoice]);
  });

  it("keeps the user's own choice, even an empty one, over any default that arrives later", async () => {
    lookups.recentPending = true;
    const { refresh } = await mount();

    await act(async () => wizard.setSelectedWorkflowTypes([]));
    lookups.recentPending = false;
    lookups.recentTypes = [WorkflowRunType.ActiveVoice];
    await refresh();

    expect(wizard.selectedWorkflowTypes).toEqual([]);
  });

  it('moves from the upload to the assessments and no further', async () => {
    await mount();
    expect(wizard.currentStep).toBe(1);

    await act(async () => wizard.nextStep());
    await act(async () => wizard.nextStep());

    expect(wizard.currentStep).toBe(2);
  });
});
