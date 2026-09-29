import {
  getNextAnnotationTaskApiAnnotationsSetsSlugNextGet,
  listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet,
  listAnnotationSetsApiAnnotationsSetsGet,
  listAnnotationSetStatsApiAdminAnnotationsSetsGet,
  submitAnnotationApiAnnotationsItemsItemIdPut,
  type AnnotationSubmission,
} from '@/lib/generated-api';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export const ANNOTATION_SETS_QUERY_KEY = ['annotations', 'sets'] as const;

/** The sets a user can annotate, with their progress in each. */
export function useAnnotationSets() {
  return useQuery({
    queryKey: ANNOTATION_SETS_QUERY_KEY,
    queryFn: () => listAnnotationSetsApiAnnotationsSetsGet(),
  });
}

/**
 * The next item to judge. `round` is part of the key so moving on always asks
 * the server again, even when the skip list has not changed; the fetch time is
 * returned with the task so the screen can report how long the answer took.
 */
export function useNextAnnotationTask(slug: string, skip: string[], round: number) {
  return useQuery({
    queryKey: ['annotations', 'next', slug, skip, round],
    queryFn: async () => {
      const task = await getNextAnnotationTaskApiAnnotationsSetsSlugNextGet({ path: { slug }, query: { skip } });
      return { task, shownAt: Date.now() };
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    // Keeps the set's header on screen while the next item loads.
    placeholderData: keepPreviousData,
  });
}

export function useSubmitAnnotation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, submission }: { itemId: string; submission: AnnotationSubmission }) =>
      submitAnnotationApiAnnotationsItemsItemIdPut({ path: { item_id: itemId }, body: submission }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ANNOTATION_SETS_QUERY_KEY }),
  });
}

export function useAnnotationSetStats() {
  return useQuery({
    queryKey: ['admin', 'annotations', 'sets'],
    queryFn: () => listAnnotationSetStatsApiAdminAnnotationsSetsGet(),
  });
}

export function useAnnotatedItems(slug: string | null, onlyDisagreements: boolean) {
  return useQuery({
    queryKey: ['admin', 'annotations', 'items', slug, onlyDisagreements],
    queryFn: () =>
      listAnnotatedItemsApiAdminAnnotationsSetsSlugItemsGet({
        path: { slug: slug ?? '' },
        query: { only_disagreements: onlyDisagreements },
      }),
    enabled: slug !== null,
  });
}
