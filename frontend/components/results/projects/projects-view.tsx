'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { listProjectsEndpointApiProjectsGet, ProjectListPage } from '@/lib/generated-api';
import { InfiniteData, keepPreviousData, useInfiniteQuery } from '@tanstack/react-query';
import { FolderOpen, Loader2, Plus, Search } from 'lucide-react';
import Link from 'next/link';
import { ReactNode, useCallback, useState } from 'react';
import { useDebounce } from 'use-debounce';
import { AnnotateCallout } from '@/components/annotate/annotate-callout';
import { ProjectRow } from './project-row';
import { readProjectState } from './project-state';

const PAGE_SIZE = 50;
const ACTIVE_POLL_MS = 3000;
const IDLE_POLL_MS = 30_000;

function hasActiveRuns(pages: ProjectListPage[] | undefined): boolean {
  return (pages ?? []).some((page) =>
    page.items.some((item) => {
      const state = readProjectState(item);
      return state === 'running' || state === 'waiting';
    }),
  );
}

/**
 * Every project you have. No rail: a project is either the one you came for or
 * it is not, and the row already says what each is doing — a column of filters
 * beside a searchable list would be furniture rather than help.
 *
 * The server does the searching and the ordering (latest activity first); the
 * list pages itself in as you scroll, so no cap on the number of projects.
 */
export function ProjectsView() {
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search.trim(), 300);

  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage, isPlaceholderData } =
    // Explicit generics: a function-valued refetchInterval stops TypeScript
    // inferring the page type from queryFn.
    useInfiniteQuery<ProjectListPage, Error, InfiniteData<ProjectListPage>, [string, string], number>({
      queryKey: ['projects', debouncedSearch],
      // Every loaded page is refetched on each tick, so the interval scales with
      // what is on screen: quick while something is still running, otherwise a
      // slow heartbeat that still picks up projects created elsewhere.
      refetchInterval: (query) => (hasActiveRuns(query.state.data?.pages) ? ACTIVE_POLL_MS : IDLE_POLL_MS),
      // Keep the current rows on screen while a new search term loads.
      placeholderData: keepPreviousData,
      queryFn: ({ pageParam }) =>
        listProjectsEndpointApiProjectsGet({
          query: { search: debouncedSearch || undefined, limit: PAGE_SIZE, offset: pageParam },
        }),
      initialPageParam: 0,
      getNextPageParam: (lastPage) => {
        const next = lastPage.offset + lastPage.items.length;
        return next < lastPage.total ? next : undefined;
      },
    });

  const items = data?.pages.flatMap((page) => page.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;
  const filtered = debouncedSearch !== '';

  // Loads the next page when the tail of the list scrolls into view. React 19
  // ref callbacks may return a cleanup, which keeps this out of useEffect.
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (!node) return;
      const observer = new IntersectionObserver(
        (entries) => {
          // cancelRefetch: false so a second intersection while a page is
          // already loading does not abort and restart that request.
          if (entries.some((entry) => entry.isIntersecting)) fetchNextPage({ cancelRefetch: false });
        },
        { rootMargin: '240px' },
      );
      observer.observe(node);
      return () => observer.disconnect();
    },
    [fetchNextPage],
  );

  return (
    <main className="flex min-h-0 min-w-0 flex-1 flex-col">
      <AnnotateCallout />
      {/* The bar spans the window so its rule does; its contents line up with
          the list on the same centred column. */}
      <div className="flex h-10 shrink-0 items-center border-b px-4">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-2">
          <span className="shrink-0 truncate text-xs text-muted-foreground">
            {isLoading ? 'Loading…' : <ProjectCount total={total} filtered={filtered} />}
          </span>

          <div className="relative ml-2 hidden max-w-64 min-w-0 flex-1 sm:block">
            <Search className="absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search projects"
              className="h-7 pl-7 text-xs"
            />
            {isPlaceholderData && (
              <Loader2 className="absolute top-1/2 right-2 size-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
            )}
          </div>

          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button size="xs" asChild aria-label="New project">
                  <Link href="/new">
                    <Plus className="size-3" />
                    <span className="hidden sm:inline">New project</span>
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Upload a draft and start a project</TooltipContent>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Keyed on the term so a new result set starts at the top rather than
          wherever the previous list had been scrolled to. */}
      <div key={debouncedSearch} className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <Centred>
            <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />
            <p className="mt-2 text-xs text-muted-foreground">Loading your projects…</p>
          </Centred>
        ) : error ? (
          <Centred>
            <p className="text-sm text-destructive">{error.message}</p>
          </Centred>
        ) : items.length === 0 && !filtered ? (
          <Centred>
            <FolderOpen className="mx-auto size-7 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">No projects yet</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              A project is one draft and everything found in it. Upload a document to start the first.
            </p>
            <Button size="sm" className="mt-3" asChild>
              <Link href="/new">
                <Plus className="size-3.5" />
                New project
              </Link>
            </Button>
          </Centred>
        ) : items.length === 0 ? (
          <div className="space-y-1 py-12 text-center text-sm text-muted-foreground">
            <p>No projects match that search.</p>
            <Button variant="link" size="sm" className="text-xs" onClick={() => setSearch('')}>
              Clear search
            </Button>
          </div>
        ) : (
          <div className="mx-auto max-w-5xl">
            {items.map((item) => (
              <ProjectRow key={item.project.id} item={item} />
            ))}

            {hasNextPage && (
              <div ref={sentinelRef} className="flex justify-center py-4">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-muted-foreground"
                  onClick={() => fetchNextPage({ cancelRefetch: false })}
                  disabled={isFetchingNextPage}
                >
                  {isFetchingNextPage ? <Loader2 className="size-3.5 animate-spin" /> : 'Load more'}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

function ProjectCount({ total, filtered }: { total: number; filtered: boolean }) {
  const noun = filtered ? (total === 1 ? 'match' : 'matches') : total === 1 ? 'project' : 'projects';
  return (
    <>
      {total} {noun}
    </>
  );
}

function Centred({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-xs text-center">{children}</div>
    </div>
  );
}
