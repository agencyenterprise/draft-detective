'use client';

import {
  type Project,
  type ProjectOverview,
  type UpdateProjectRequest,
  updateProjectEndpointApiProjectProjectIdPatch,
} from '@/lib/generated-api';
import { PROJECT_LIST_QUERY_KEY, projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useToastMutation, type ToastMutationOptions } from '@/lib/hooks/use-toast-mutation';
import { writeServerAnswerAndRefresh } from '@/lib/query-cache';
import { useQueryClient } from '@tanstack/react-query';

export type UpdateProjectOptions = Pick<
  ToastMutationOptions<Project, UpdateProjectRequest>,
  'onMutate' | 'onSuccess' | 'onError' | 'successMessage' | 'errorMessage'
>;

/**
 * Saves changes to a project's own fields (title, date, settings). The server
 * answers with the whole project, which goes into every cached overview of it
 * through `writeServerAnswerAndRefresh`, so the page shows the change at once
 * and a poll that left before the save can't bring the old project back.
 * Nothing else under `['project', id]` changed. The project list shows these
 * fields, so it is refreshed as well.
 *
 * It toasts like `useToastMutation`.
 */
export function useUpdateProject(
  projectId: string | null | undefined,
  { onSuccess, ...options }: UpdateProjectOptions,
) {
  const queryClient = useQueryClient();
  return useToastMutation<Project, UpdateProjectRequest>({
    ...options,
    mutationFn: (changes) => {
      if (!projectId) throw new Error('No project ID');
      return updateProjectEndpointApiProjectProjectIdPatch({ path: { project_id: projectId }, body: changes });
    },
    onSuccess: (project, ...rest) => {
      if (projectId) {
        // The overview is keyed per revision, so every cached revision of it gets the project.
        writeServerAnswerAndRefresh<ProjectOverview>(
          queryClient,
          { queryKey: projectQueryKeys.overviews(projectId) },
          (overview) => overview && { ...overview, project },
        );
      }
      void queryClient.invalidateQueries({ queryKey: PROJECT_LIST_QUERY_KEY });
      return onSuccess?.(project, ...rest);
    },
  });
}
