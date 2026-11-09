import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'sonner';
import { WorkflowRunType, type WorkflowTypeDescription } from '@/lib/generated-api';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { StepAnalyses } from './step-analyses';
import { useWizard, WizardProvider } from './wizard-context';

function workflowType(type: WorkflowRunType, needsWebSearch = false): WorkflowTypeDescription {
  return {
    type,
    name: type,
    description: '',
    needs_web_search: needsWebSearch,
    is_experimental: false,
    is_internal: false,
    category: 'test',
    gates: [],
  };
}

const TYPES = [workflowType(WorkflowRunType.ActiveVoice), workflowType(WorkflowRunType.ReferenceValidationV2, true)];

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  start: vi.fn(),
  saveProject: vi.fn(),
  recentTypes: [] as WorkflowRunType[],
  selector: { onSelectionChange: null as ((types: WorkflowRunType[]) => void) | null },
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  startMultipleWorkflowsApiWorkflowsStartMultiplePost: mocks.start,
  updateProjectEndpointApiProjectProjectIdPatch: mocks.saveProject,
}));
vi.mock('@/lib/hooks/use-workflow-types', () => ({
  useWorkflowTypes: () => ({ workflowTypes: TYPES, isPending: false, isError: false }),
}));
vi.mock('@/lib/hooks/use-visible-workflow-types', () => ({
  useVisibleWorkflowTypes: () => ({ visibleTypes: TYPES.map((wt) => wt.type) }),
}));
vi.mock('@/lib/hooks/use-recent-workflow-selection', () => ({
  useRecentWorkflowSelection: () => ({ recentTypes: mocks.recentTypes, isPending: false }),
}));
// The picker has its own tests; here it only has to hand a selection to the step.
vi.mock('@/components/workflows/workflow-type-selector', () => ({
  WorkflowTypeSelector: (props: { onSelectionChange: (types: WorkflowRunType[]) => void }) => {
    mocks.selector.onSelectionChange = props.onSelectionChange;
    return null;
  },
}));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

/** A promise the test settles by hand, to look at the step while a request is in flight. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mocks.recentTypes = [WorkflowRunType.ActiveVoice];
  mocks.start.mockResolvedValue([]);
  mocks.saveProject.mockResolvedValue({});
});

let view: Rendered | undefined;
afterEach(async () => {
  await view?.unmount();
  view = undefined;
});

/** Step 2 of the wizard, on project p-1 as the upload step leaves it. */
async function mountStep() {
  let wizard!: ReturnType<typeof useWizard>;
  function Probe() {
    wizard = useWizard();
    return null;
  }
  view = await renderInto(
    withQueryClient(
      testQueryClient(),
      <WizardProvider>
        <Probe />
        <StepAnalyses />
      </WizardProvider>,
    ),
  );
  await act(async () => wizard.setProjectId('p-1'));

  const container = view.container;
  const button = (label: RegExp) =>
    Array.from(container.querySelectorAll('button')).find((b) => label.test(b.textContent ?? ''))!;
  const click = async (element: HTMLElement) => {
    await act(async () => element.click());
    await flush();
  };
  return {
    wizard: () => wizard,
    start: () => button(/^Start/),
    skip: () => button(/^Skip for now$/),
    severity: () => container.querySelector<HTMLButtonElement>('[role="switch"]')!,
    consent: () => container.querySelector<HTMLButtonElement>('#web-search-consent'),
    select: (types: WorkflowRunType[]) => act(async () => mocks.selector.onSelectionChange?.(types)),
    click,
  };
}

describe('StepAnalyses', () => {
  it('starts the selected assessments on the new project and opens it', async () => {
    const step = await mountStep();

    await step.click(step.start());

    expect(mocks.start).toHaveBeenCalledOnce();
    expect(mocks.start).toHaveBeenCalledWith({
      body: { project_id: 'p-1', workflow_types: [WorkflowRunType.ActiveVoice] },
    });
    expect(mocks.push).toHaveBeenCalledWith('/projects/p-1');
    // Nothing more to do here while the project opens.
    expect(step.start().disabled).toBe(true);
    expect(step.skip().disabled).toBe(true);
  });

  it('holds Start and Skip while the assessments are starting, so a second click starts nothing', async () => {
    const pending = deferred<[]>();
    mocks.start.mockReturnValue(pending.promise);
    const step = await mountStep();

    await step.click(step.start());
    expect(step.start().disabled).toBe(true);
    expect(step.skip().disabled).toBe(true);
    await step.click(step.start());

    await act(async () => pending.resolve([]));
    await flush();
    expect(mocks.start).toHaveBeenCalledOnce();
    expect(mocks.push).toHaveBeenCalledOnce();
  });

  it('reports a failed start and lets the user try again', async () => {
    mocks.start.mockRejectedValueOnce(new Error('boom'));
    const step = await mountStep();

    await step.click(step.start());
    expect(toast.error).toHaveBeenCalledOnce();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(step.start().disabled).toBe(false);

    await step.click(step.start());
    expect(mocks.start).toHaveBeenCalledTimes(2);
    expect(mocks.push).toHaveBeenCalledWith('/projects/p-1');
  });

  it('starts nothing until an assessment is selected', async () => {
    const step = await mountStep();
    await step.select([]);

    expect(step.start().disabled).toBe(true);
    await step.click(step.start());
    expect(mocks.start).not.toHaveBeenCalled();
  });

  it('starts a web-searching assessment only once the user consents to web search', async () => {
    const step = await mountStep();
    await step.select([WorkflowRunType.ActiveVoice, WorkflowRunType.ReferenceValidationV2]);

    expect(step.start().disabled).toBe(true);
    await step.click(step.start());
    expect(mocks.start).not.toHaveBeenCalled();

    await step.click(step.consent()!);
    await step.click(step.start());
    expect(mocks.start).toHaveBeenCalledWith({
      body: {
        project_id: 'p-1',
        workflow_types: [WorkflowRunType.ActiveVoice, WorkflowRunType.ReferenceValidationV2],
      },
    });
  });

  it('asks for no consent when nothing selected searches the web', async () => {
    const step = await mountStep();

    expect(step.consent()).toBeNull();
    expect(step.start().disabled).toBe(false);
  });

  it('saves the severity setting on the project, and holds Start and Skip until it lands', async () => {
    const save = deferred<object>();
    mocks.saveProject.mockReturnValue(save.promise);
    const step = await mountStep();
    expect(step.wizard().groupBySeverity).toBe(true);

    await step.click(step.severity());
    expect(mocks.saveProject).toHaveBeenCalledWith({
      path: { project_id: 'p-1' },
      body: { group_by_severity: false },
    });
    expect(step.start().disabled).toBe(true);
    expect(step.skip().disabled).toBe(true);

    await act(async () => save.resolve({}));
    await flush();
    expect(step.wizard().groupBySeverity).toBe(false);
    expect(step.start().disabled).toBe(false);
    expect(step.skip().disabled).toBe(false);
  });

  it('puts the severity setting back when it fails to save', async () => {
    mocks.saveProject.mockRejectedValueOnce(new Error('boom'));
    const step = await mountStep();

    await step.click(step.severity());

    expect(toast.error).toHaveBeenCalledOnce();
    expect(step.wizard().groupBySeverity).toBe(true);
  });

  it('opens the project without starting anything when the step is skipped', async () => {
    const step = await mountStep();

    await step.click(step.skip());

    expect(mocks.push).toHaveBeenCalledWith('/projects/p-1');
    expect(mocks.start).not.toHaveBeenCalled();
  });
});
