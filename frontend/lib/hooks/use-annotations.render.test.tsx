import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getNextAnnotationTaskApiAnnotationsSetsSlugNextGet, type AnnotationTask } from '@/lib/generated-api';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { useNextAnnotationTask } from './use-annotations';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getNextAnnotationTaskApiAnnotationsSetsSlugNextGet: vi.fn(),
}));

const fetchNext = vi.mocked(getNextAnnotationTaskApiAnnotationsSetsSlugNextGet);

function task(itemId: string): AnnotationTask {
  return {
    set: { slug: 'active_voice', title: 'Active Voice', guidance: '', questions: [] },
    item_id: itemId,
    passage: { document: 'Doc.', anchor: 'Doc', line: 1 },
    item_count: 2,
    answered_by_me: 0,
  };
}

function ShownItem() {
  const { data } = useNextAnnotationTask('active_voice', [], 0);
  return <span>{data?.task.item_id ?? 'loading'}</span>;
}

beforeEach(() => fetchNext.mockReset());
afterEach(() => vi.clearAllMocks());

describe('useNextAnnotationTask', () => {
  it('asks the server again when a check is opened a second time', async () => {
    fetchNext.mockResolvedValueOnce(task('first')).mockResolvedValueOnce(task('second'));
    const client = testQueryClient();

    const visit = await renderInto(withQueryClient(client, <ShownItem />));
    await flush();
    expect(visit.container.textContent).toBe('first');
    await visit.unmount();
    await flush();

    // Leaving the check and coming back starts at round 0 again. The answered
    // item must not be replayed from the cache.
    const again = await renderInto(withQueryClient(client, <ShownItem />));
    await flush();
    expect(fetchNext).toHaveBeenCalledTimes(2);
    expect(again.container.textContent).toBe('second');
    await again.unmount();
  });
});
