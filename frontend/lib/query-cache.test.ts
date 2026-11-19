import { QueryObserver } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { flush, testQueryClient } from '@/lib/test-render';
import { writeServerAnswerAndRefresh } from './query-cache';

type Doc = { title: string; version: string };

describe('writeServerAnswerAndRefresh', () => {
  it('writes into every matching query at once, refetches the ones in use and marks the rest stale', async () => {
    const client = testQueryClient();
    client.setQueryData(['doc', 'a', 1], { title: 'Old', version: '1' });
    client.setQueryData(['doc', 'a', 2], { title: 'Old', version: '2' });
    client.setQueryData(['doc', 'b', 1], { title: 'Other', version: '1' });
    // The refetch stays in flight, so the test sees what was written before it lands.
    const fetchWatched = vi.fn(() => new Promise<Doc>(() => {}));
    new QueryObserver(client, { queryKey: ['doc', 'a', 1], queryFn: fetchWatched, staleTime: Infinity }).subscribe(
      () => {},
    );

    writeServerAnswerAndRefresh<Doc>(client, { queryKey: ['doc', 'a'] }, (doc) => doc && { ...doc, title: 'New' });
    await flush();

    expect(client.getQueryData(['doc', 'a', 1])).toEqual({ title: 'New', version: '1' });
    expect(client.getQueryData(['doc', 'a', 2])).toEqual({ title: 'New', version: '2' });
    expect(client.getQueryData(['doc', 'b', 1])).toEqual({ title: 'Other', version: '1' });
    expect(fetchWatched).toHaveBeenCalledOnce();
    expect(client.getQueryState(['doc', 'a', 2])?.isInvalidated).toBe(true);
    expect(client.getQueryState(['doc', 'b', 1])?.isInvalidated).toBe(false);
  });

  it('drops a fetch that left before the write and fetches again, so the old data never lands and its awaiter still settles', async () => {
    const client = testQueryClient();
    const key = ['doc', 'a'];
    client.setQueryData(key, { title: 'Old', version: '1' });
    let answerFirst!: (doc: Doc) => void;
    const fetchDoc = vi
      .fn()
      .mockImplementationOnce(() => new Promise<Doc>((resolve) => (answerFirst = resolve)))
      .mockResolvedValue({ title: 'New', version: '2' });
    new QueryObserver(client, { queryKey: key, queryFn: fetchDoc, staleTime: Infinity }).subscribe(() => {});
    // Something, say the refresh after a start, awaits a fetch that left before the change.
    const awaited = client.refetchQueries({ queryKey: key });

    writeServerAnswerAndRefresh<Doc>(client, { queryKey: key }, (doc) => doc && { ...doc, title: 'New' });
    answerFirst({ title: 'Old', version: '1' });
    await awaited;
    await flush();

    expect(fetchDoc).toHaveBeenCalledTimes(2);
    expect(client.getQueryData(key)).toEqual({ title: 'New', version: '2' });
  });
});
