import type { QueryClient, QueryFilters } from '@tanstack/react-query';

/*
 * Two ways to put a server's answer into the cache over a fetch that may still
 * be on its way. Both write at once; they differ in what they do to that fetch.
 *
 * - `writeServerAnswer` cancels it and asks again in the background. Use it for
 *   lists nothing else awaits: cancelling hands the old data to anyone awaiting.
 * - `writeServerAnswerAndRefresh` refreshes every matching query instead. Use it
 *   where other code awaits those fetches (the project overviews: the refresh
 *   after a start), so the fetch it awaits lands with the new answer.
 */

/**
 * Writes what the server answered into the cached queries matching `filters`,
 * so the page shows it without asking again. A fetch still on its way may have
 * been read before the change and would overwrite it when it lands, so those
 * are cancelled before the write and asked again after it, in the background:
 * the caller need not wait on a list that can run to megabytes. Queries at rest
 * keep what was written and are not refetched.
 */
export async function writeServerAnswer<T>(
  queryClient: QueryClient,
  filters: QueryFilters,
  update: (data: T | undefined) => T | undefined,
): Promise<void> {
  const inFlight = queryClient.getQueryCache().findAll({ ...filters, fetchStatus: 'fetching' });
  await queryClient.cancelQueries(filters);
  queryClient.setQueriesData<T>(filters, update);
  for (const query of inFlight) {
    void queryClient.refetchQueries({ queryKey: query.queryKey, exact: true });
  }
}

/**
 * Writes what the server answered into the cached queries matching `filters`,
 * so the page shows it at once, then refreshes them in the background. The
 * refresh drops a fetch that left before the change and would land with the old
 * data, and starts it again, so code awaiting that fetch gets the new answer.
 * Queries in use refetch; the rest are marked stale. A query still on its first
 * load holds nothing to write into, and the refresh can't drop that load: it
 * lands with what it read before the change. So once it lands, it is refreshed
 * again (its awaiters still get the first answer).
 */
export function writeServerAnswerAndRefresh<T>(
  queryClient: QueryClient,
  filters: QueryFilters,
  update: (data: T | undefined) => T | undefined,
): void {
  const firstLoads = queryClient
    .getQueryCache()
    .findAll({ ...filters, fetchStatus: 'fetching' })
    .filter((query) => query.state.data === undefined);
  queryClient.setQueriesData<T>(filters, update);
  void queryClient.invalidateQueries(filters);
  for (const query of firstLoads) {
    // A failed load brought no old data, so only a successful one is refreshed again.
    void query.promise?.then(
      () => queryClient.invalidateQueries({ queryKey: query.queryKey, exact: true }),
      () => {},
    );
  }
}
