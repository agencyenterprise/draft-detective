import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useVisibleWorkflowTypes } from '@/lib/hooks/use-visible-workflow-types';
import { type WorkflowTypeDescription, WorkflowRunType } from '@/lib/generated-api';

const mocks = vi.hoisted(() => ({ types: vi.fn(), experimental: { value: false } }));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getWorkflowTypesApiWorkflowTypesGet: mocks.types,
}));
vi.mock('@/context/experimental-features-context', () => ({
  useExperimentalFeatures: () => ({ showExperimentalFeatures: mocks.experimental.value }),
}));

const { FiguresTablesCheck, AbbreviationScanV2, Reviewer2, ReviewAssistant, DocumentProcessing } = WorkflowRunType;

function type(value: WorkflowRunType, flags: { internal?: boolean; experimental?: boolean } = {}) {
  return {
    type: value,
    name: value,
    is_internal: flags.internal ?? false,
    is_experimental: flags.experimental ?? false,
  } as WorkflowTypeDescription;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.experimental.value = false;
  mocks.types.mockResolvedValue({
    workflow_types: [
      type(FiguresTablesCheck),
      type(AbbreviationScanV2),
      type(Reviewer2, { experimental: true }),
      type(ReviewAssistant),
      type(DocumentProcessing, { internal: true }),
    ],
    categories: [
      { slug: 'style', label: 'Style', workflows: [AbbreviationScanV2, FiguresTablesCheck] },
      { slug: 'review', label: 'Review', workflows: [Reviewer2, DocumentProcessing] },
    ],
    presets: [
      { slug: 'all', label: 'All', workflows: [FiguresTablesCheck, Reviewer2] },
      { slug: 'deep', label: 'Deep', workflows: [Reviewer2] },
    ],
  });
});

async function mount() {
  let latest!: ReturnType<typeof useVisibleWorkflowTypes>;
  function Probe() {
    latest = useVisibleWorkflowTypes();
    return null;
  }
  const view = await renderInto(withQueryClient(testQueryClient(), <Probe />));
  await flush();
  await view.unmount();
  return latest;
}

describe('useVisibleWorkflowTypes', () => {
  it('offers only the categorised, non-internal, non-experimental assessments, in category order', async () => {
    const visible = await mount();

    // The Review Assistant is in no category; the Review category empties out and is dropped.
    expect(visible.visibleTypes).toEqual([AbbreviationScanV2, FiguresTablesCheck]);
    expect(visible.visibleGroups.map((group) => group.category.slug)).toEqual(['style']);
    expect(visible.presets).toEqual([]);
  });

  it('adds experimental assessments and the presets for users who opted in, narrowed to what they can see', async () => {
    mocks.experimental.value = true;

    const visible = await mount();

    expect(visible.visibleTypes).toEqual([AbbreviationScanV2, FiguresTablesCheck, Reviewer2]);
    expect(visible.visibleGroups.map((group) => group.category.slug)).toEqual(['style', 'review']);
    expect(visible.presets.map((preset) => [preset.slug, preset.workflows])).toEqual([
      ['all', [FiguresTablesCheck, Reviewer2]],
      ['deep', [Reviewer2]],
    ]);
  });

  it('drops a preset whose every assessment is hidden', async () => {
    mocks.experimental.value = true;
    mocks.types.mockResolvedValue({
      workflow_types: [type(FiguresTablesCheck), type(DocumentProcessing, { internal: true })],
      categories: [{ slug: 'style', label: 'Style', workflows: [FiguresTablesCheck, DocumentProcessing] }],
      presets: [
        { slug: 'internal', label: 'Internal', workflows: [DocumentProcessing] },
        { slug: 'mixed', label: 'Mixed', workflows: [DocumentProcessing, FiguresTablesCheck] },
      ],
    });

    const visible = await mount();

    expect(visible.presets.map((preset) => [preset.slug, preset.workflows])).toEqual([['mixed', [FiguresTablesCheck]]]);
  });
});
