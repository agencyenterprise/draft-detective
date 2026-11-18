import type { QueryClient, QueryFilters } from '@tanstack/react-query';

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
