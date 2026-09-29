import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import {
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
}));

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

function setButton(title: string): HTMLButtonElement {
  const button = [...rendered.container.querySelectorAll<HTMLButtonElement>('button[aria-pressed]')].find(
    (b) => b.textContent === title,
  );
  if (!button) throw new Error(`no button for ${title}`);
  return button;
}

describe('AnnotationResults', () => {
  it('lets each set be picked with a focusable button', async () => {
    expect(setButton('Active Voice').getAttribute('aria-pressed')).toBe('true');
    const other = setButton('Advocacy & Tone');
    expect(other.getAttribute('aria-pressed')).toBe('false');

    other.focus();
    expect(document.activeElement).toBe(other);
    await act(async () => other.click());
    await flush();

    expect(other.getAttribute('aria-pressed')).toBe('true');
    expect(setButton('Active Voice').getAttribute('aria-pressed')).toBe('false');
    expect(vi.mocked(listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet)).toHaveBeenLastCalledWith(
      expect.objectContaining({ path: { slug: 'advocacy_tone_v2' } }),
    );
  });
});
