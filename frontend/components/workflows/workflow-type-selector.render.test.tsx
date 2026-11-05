import { act, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkflowRunType, type WorkflowTypeDescription } from '@/lib/generated-api';
import { renderInto, type Rendered } from '@/lib/test-render';
import { WorkflowTypeSelector } from './workflow-type-selector';

function workflowType(type: WorkflowRunType, name: string): WorkflowTypeDescription {
  return {
    type,
    name,
    description: `${name} description`,
    needs_web_search: false,
    is_experimental: false,
    is_internal: false,
    category: 'language',
    gates: [],
  };
}

const TYPES = [
  workflowType(WorkflowRunType.AbbreviationScanV2, 'Abbreviations'),
  workflowType(WorkflowRunType.AdvocacyToneV2, 'Advocacy Tone'),
  workflowType(WorkflowRunType.FiguresTablesCheck, 'Figures and Tables'),
];

vi.mock('@/lib/hooks/use-workflow-types', () => ({
  useWorkflowTypes: () => ({ workflowTypes: TYPES, getWorkflowTypeName: (t: string) => t, isPending: false }),
}));
vi.mock('@/lib/hooks/use-workflow-duration-estimates', () => ({
  useWorkflowDurationEstimates: () => ({ getEstimatedSeconds: () => null }),
}));
vi.mock('@/lib/hooks/use-visible-workflow-types', () => ({
  useVisibleWorkflowTypes: () => ({
    visibleGroups: [{ category: { slug: 'language', label: 'Language' }, workflows: TYPES }],
    presets: [],
  }),
}));

let rendered: Rendered | undefined;
afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
});

async function mount(selectedTypes: WorkflowRunType[], runningTypes: WorkflowRunType[]) {
  const onSelectionChange = vi.fn();
  rendered = await renderInto(
    <WorkflowTypeSelector
      selectedTypes={selectedTypes}
      onSelectionChange={onSelectionChange}
      runningTypes={runningTypes}
    />,
  );
  const checkbox = (type: WorkflowRunType) => rendered!.container.querySelector<HTMLButtonElement>(`[id="${type}"]`)!;
  const button = (label: string) =>
    Array.from(rendered!.container.querySelectorAll('button')).find((b) => b.textContent === label)!;
  return { onSelectionChange, checkbox, button };
}

describe('WorkflowTypeSelector with running assessments', () => {
  it('locks running assessments out of the selection', async () => {
    const { checkbox } = await mount([WorkflowRunType.AbbreviationScanV2], [WorkflowRunType.AbbreviationScanV2]);

    expect(checkbox(WorkflowRunType.AbbreviationScanV2).disabled).toBe(true);
    // Ticked before it started elsewhere, it no longer reads as selected.
    expect(checkbox(WorkflowRunType.AbbreviationScanV2).getAttribute('data-state')).toBe('unchecked');
    expect(checkbox(WorkflowRunType.AdvocacyToneV2).disabled).toBe(false);
  });

  it('leaves running assessments out of Select all', async () => {
    const { onSelectionChange, button } = await mount([], [WorkflowRunType.AdvocacyToneV2]);

    await act(async () => button('Select all').click());

    expect(onSelectionChange).toHaveBeenCalledWith([
      WorkflowRunType.AbbreviationScanV2,
      WorkflowRunType.FiguresTablesCheck,
    ]);
  });

  it('does not bring back a row that started running, then finished, after Deselect all', async () => {
    const A = WorkflowRunType.AbbreviationScanV2;
    const B = WorkflowRunType.AdvocacyToneV2;
    let setRunning: (types: WorkflowRunType[]) => void = () => {};

    // The dialog's form owns the selection; this stands in for it.
    function Stateful() {
      const [selected, setSelected] = useState<WorkflowRunType[]>([A, B]);
      const [running, setRunningState] = useState<WorkflowRunType[]>([]);
      setRunning = setRunningState;
      return <WorkflowTypeSelector selectedTypes={selected} onSelectionChange={setSelected} runningTypes={running} />;
    }

    rendered = await renderInto(<Stateful />);
    const checkbox = (type: WorkflowRunType) => rendered!.container.querySelector<HTMLButtonElement>(`[id="${type}"]`)!;
    const deselectAll = () =>
      Array.from(rendered!.container.querySelectorAll('button')).find((b) => b.textContent === 'Deselect all')!;

    // A starts elsewhere while the dialog is open, then the user clears the list.
    await act(async () => setRunning([A]));
    await act(async () => deselectAll().click());
    // A's run finishes.
    await act(async () => setRunning([]));

    expect(checkbox(A).getAttribute('data-state')).toBe('unchecked');
    expect(checkbox(B).getAttribute('data-state')).toBe('unchecked');
  });
});

describe('WorkflowTypeSelector search', () => {
  async function type(input: HTMLInputElement, value: string) {
    // React tracks the input's value; set it through the native setter so the change event registers.
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    await act(async () => {
      setValue.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

  it('narrows the list and selects only the matches, keeping hidden selections', async () => {
    const { onSelectionChange, checkbox, button } = await mount([WorkflowRunType.FiguresTablesCheck], []);
    const search = rendered!.container.querySelector<HTMLInputElement>('input[type="search"]')!;

    await type(search, 'a TONE');
    expect(checkbox(WorkflowRunType.AdvocacyToneV2)).not.toBeNull();
    expect(checkbox(WorkflowRunType.AbbreviationScanV2)).toBeNull();

    await act(async () => button('Select matches').click());
    expect(onSelectionChange).toHaveBeenLastCalledWith([
      WorkflowRunType.FiguresTablesCheck,
      WorkflowRunType.AdvocacyToneV2,
    ]);
  });
});
