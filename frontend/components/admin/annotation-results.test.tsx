import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { ApiError } from '@/lib/api-error';
import { downloadFile } from '@/lib/file-download';
import {
  exportAnnotationsApiAdminAnnotationsExportGet,
  listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet,
  listAnnotationSetStatsApiAdminAnnotationsSetsGet,
  type AnnotationSetStats,
} from '@/lib/generated-api';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { AnnotationResults } from './annotation-results';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  listAnnotationSetStatsApiAdminAnnotationsSetsGet: vi.fn(),
  listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet: vi.fn(),
  exportAnnotationsApiAdminAnnotationsExportGet: vi.fn(),
}));
vi.mock('@/lib/file-download', () => ({ downloadFile: vi.fn() }));

function stats(slug: string, title: string): AnnotationSetStats {
  return {
    slug,
    title,
    item_count: 10,
    annotated_items: 0,
    annotation_count: 0,
    annotator_count: 0,
    agreements: 0,
    disagreements: 0,
    abstentions: 0,
  };
}

let rendered: Rendered;

beforeEach(async () => {
  vi.mocked(listAnnotationSetStatsApiAdminAnnotationsSetsGet).mockResolvedValue([
    stats('active_voice', 'Active Voice'),
    stats('advocacy_tone_v2', 'Advocacy & Tone'),
  ]);
  vi.mocked(listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet).mockResolvedValue([]);
  rendered = await renderInto(withQueryClient(testQueryClient(), <AnnotationResults />));
  await flush();
});
afterEach(async () => {
  await rendered.unmount();
  vi.clearAllMocks();
});

function button(label: string): HTMLButtonElement {
  const found = [...rendered.container.querySelectorAll<HTMLButtonElement>('button')].find((b) =>
    b.textContent?.includes(label),
  );
  if (!found) throw new Error(`no "${label}" button`);
  return found;
}

describe('AnnotationResults', () => {
  it('loads the items of the set that is picked', async () => {
    const items = vi.mocked(listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet);
    expect(items).toHaveBeenLastCalledWith(expect.objectContaining({ path: { slug: 'active_voice' } }));

    await act(async () => button('Advocacy & Tone').click());
    await flush();

    expect(items).toHaveBeenLastCalledWith(expect.objectContaining({ path: { slug: 'advocacy_tone_v2' } }));
  });

  it('exports every set in one file, not just the one on screen', async () => {
    const everySet = [
      {
        slug: 'active_voice',
        title: 'Active Voice',
        workflow_type: 'active_voice',
        is_active: true,
        questions: [],
        items: [],
      },
      {
        slug: 'advocacy_tone_v2',
        title: 'Advocacy & Tone',
        workflow_type: 'advocacy_tone_v2',
        is_active: true,
        questions: [],
        items: [],
      },
    ];
    vi.mocked(exportAnnotationsApiAdminAnnotationsExportGet).mockResolvedValue(everySet);

    await act(async () => button('Export all').click());
    await flush();

    expect(vi.mocked(listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet)).not.toHaveBeenCalledWith(
      expect.objectContaining({ path: { slug: 'advocacy_tone_v2' } }),
    );
    const [{ filename, blob }] = vi.mocked(downloadFile).mock.calls[0];
    expect(filename).toMatch(/^annotations-\d{4}-\d{2}-\d{2}\.json$/);
    expect(JSON.parse(await blob.text()).map((set: { slug: string }) => set.slug)).toEqual([
      'active_voice',
      'advocacy_tone_v2',
    ]);
  });
  it('says the sets could not load, not the bare status, when the server gives no reason', async () => {
    await rendered.unmount();
    vi.mocked(listAnnotationSetStatsApiAdminAnnotationsSetsGet).mockRejectedValue(new ApiError(502));
    rendered = await renderInto(withQueryClient(testQueryClient(), <AnnotationResults />));
    await flush();

    expect(rendered.container.textContent).toContain('Could not load the annotation sets');
    expect(rendered.container.textContent).not.toContain('HTTP 502');
  });
});
