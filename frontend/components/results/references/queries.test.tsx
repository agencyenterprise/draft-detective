import { afterEach, describe, expect, it, vi } from 'vitest';
import { useLayoutEffect } from 'react';
import { composeReferences } from '@/lib/composed-references';
import {
  type FileListItem,
  getProjectReferencesEndpointApiProjectProjectIdReferencesGet,
  MatchSource,
  type ProjectOverview,
  type ProjectReferences,
  type ReferenceFetchResult,
  ReferenceFetchStatus,
} from '@/lib/generated-api';
import { flush, renderInto, testQueryClient, withQueryClient } from '@/lib/test-render';
import { toReferenceReviewItems, useReferenceReviewReferences } from './queries';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  getProjectReferencesEndpointApiProjectProjectIdReferencesGet: vi.fn(),
}));

const fetchReferences = vi.mocked(getProjectReferencesEndpointApiProjectProjectIdReferencesGet);

afterEach(() => vi.clearAllMocks());

const file = (id: string, name: string, size: number) =>
  ({ id, file_name: name, file_size: size }) as unknown as FileListItem;

const fetched = (referenceId: string, status: ReferenceFetchStatus) =>
  ({ reference_id: referenceId, input_reference: '', status }) as ReferenceFetchResult;

/** Rows for references r1..rN, matched as given. */
function rows(
  matches: { reference_id: string; file_id: string; source?: MatchSource }[],
  files: FileListItem[],
  fetchedReferences?: ReferenceFetchResult[],
) {
  const extracted = ['r1', 'r2', 'r3'].map((id) => ({ id, text: `Reference ${id}` }));
  return toReferenceReviewItems(composeReferences(extracted, matches), files, fetchedReferences);
}

describe('toReferenceReviewItems', () => {
  it('keeps extraction order and numbers the rows from zero', () => {
    expect(rows([], []).map((r) => [r.index, r.id, r.text])).toEqual([
      [0, 'r1', 'Reference r1'],
      [1, 'r2', 'Reference r2'],
      [2, 'r3', 'Reference r3'],
    ]);
  });

  it('marks a reference matched only when its file is among the project files', () => {
    const items = rows(
      [
        { reference_id: 'r1', file_id: 'f1', source: MatchSource.AutoMatched },
        // The match outlived its file (deleted, say): the reader still has a source to provide.
        { reference_id: 'r2', file_id: 'gone', source: MatchSource.AutoMatched },
      ],
      [file('f1', 'smith.pdf', 2048)],
    );

    expect(items.map((r) => r.status)).toEqual(['matched', 'unmatched', 'unmatched']);
    expect(items[0].matchedFile).toEqual({ id: 'f1', name: 'smith.pdf', size: '2 KB' });
    expect(items[1].matchedFile).toBeNull();
    expect(items[1].source).toBe(MatchSource.AutoMatched);
  });

  // 'fetching' wins over a match on purpose: the detail pane disables its actions while a
  // row is fetching, since a fetch that finds a source replaces whatever match came before.
  it('shows a reference as fetching while its web fetch is pending, matched or not', () => {
    const items = rows(
      [{ reference_id: 'r1', file_id: 'f1', source: MatchSource.AutoMatched }],
      [file('f1', 'smith.pdf', 10)],
      [fetched('r1', ReferenceFetchStatus.Pending), fetched('r2', ReferenceFetchStatus.Pending)],
    );

    expect(items.map((r) => r.status)).toEqual(['fetching', 'fetching', 'unmatched']);
  });

  it('reads a finished fetch by whether a file is matched', () => {
    const items = rows(
      [{ reference_id: 'r1', file_id: 'f1', source: MatchSource.AutoFetched }],
      [file('f1', 'smith.pdf', 10)],
      [fetched('r1', ReferenceFetchStatus.Completed), fetched('r2', ReferenceFetchStatus.Error)],
    );

    expect(items.map((r) => r.status)).toEqual(['matched', 'unmatched', 'unmatched']);
  });

  it('surfaces each fetch outcome on its own reference, failures included', () => {
    const notFound = fetched('r2', ReferenceFetchStatus.Error);
    const found = fetched('r1', ReferenceFetchStatus.Completed);
    const items = rows([], [], [notFound, found]);

    expect(items.map((r) => r.fetchResult)).toEqual([found, notFound, null]);
  });

  it("hides the fetch outcome once the user uploaded the reference's source", () => {
    const items = rows(
      [
        { reference_id: 'r1', file_id: 'f1', source: MatchSource.ManualUpload },
        { reference_id: 'r2', file_id: 'f2', source: MatchSource.AutoMatched },
      ],
      [file('f1', 'mine.pdf', 10), file('f2', 'theirs.pdf', 10)],
      [fetched('r1', ReferenceFetchStatus.Completed), fetched('r2', ReferenceFetchStatus.Completed)],
    );

    expect(items[0].fetchResult).toBeNull();
    expect(items[1].fetchResult).toEqual(fetched('r2', ReferenceFetchStatus.Completed));
  });
});

describe('useReferenceReviewReferences', () => {
  type Result = ReturnType<typeof useReferenceReviewReferences>;

  function Probe({ of, seenRef }: { of: ProjectOverview; seenRef: { current?: Result } }) {
    const result = useReferenceReviewReferences(of);
    useLayoutEffect(() => {
      seenRef.current = result;
    });
    return null;
  }

  /** A project with no extraction run: nothing to review, and nothing to wait for. */
  const noExtraction = {
    project: { id: 'p1' },
    revision: 1,
    files: [],
    workflow_runs: [],
  } as unknown as ProjectOverview;

  async function mount() {
    const seen: { current?: Result } = {};
    const view = await renderInto(withQueryClient(testQueryClient(), <Probe of={noExtraction} seenRef={seen} />));
    await flush();
    return { seen, view };
  }

  it('lists nothing before references were extracted, whatever the endpoint returns', async () => {
    const leftover = {
      extracted_references: [{ id: 'r1', text: 'Smith 2020' }],
      matches: [],
      fetched_references: [],
    } as unknown as ProjectReferences;
    fetchReferences.mockResolvedValue(leftover as never);
    const { seen, view } = await mount();

    expect(seen.current).toEqual({ references: [], isLoading: false, isStale: false, error: null });
    await view.unmount();
  });

  it('is not loading before references were extracted, while the endpoint hangs', async () => {
    fetchReferences.mockReturnValue(new Promise(() => {}) as never);
    const { seen, view } = await mount();

    expect(seen.current).toMatchObject({ isLoading: false, error: null });
    await view.unmount();
  });

  it('reports no error before references were extracted, when the endpoint fails', async () => {
    fetchReferences.mockRejectedValue(new Error('Server error'));
    const { seen, view } = await mount();

    expect(seen.current).toMatchObject({ isLoading: false, error: null });
    await view.unmount();
  });
});
