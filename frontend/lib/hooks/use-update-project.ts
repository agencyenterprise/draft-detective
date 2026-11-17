'use client';

import { getErrorMessage } from '@/lib/api-error';
import {
  type Project,
  type ProjectOverview,
  type UpdateProjectRequest,
  updateProjectEndpointApiProjectProjectIdPatch,
} from '@/lib/generated-api';
import { PROJECT_LIST_QUERY_KEY, projectQueryKeys } from '@/lib/hooks/use-project-data';
import { useMutation, useQueryClient, type UseMutationOptions } from '@tanstack/react-query';
import { toast } from 'sonner';

export interface UpdateProjectOptions extends Pick<
  UseMutationOptions<Project, Error, UpdateProjectRequest>,
  'onMutate' | 'onSuccess' | 'onError'
> {
  /** Toasted on success. Leave it out when the caller says it some other way. */
  successMessage?: string;
  /** Toasted on failure when the server gives no reason. */
  errorMessage: string;
}

/**
 * Saves changes to a project's own fields (title, date, settings). The server
 * answers with the whole project, which goes straight into every cached
 * overview of it, so the page shows the change at once. The overviews are then
 * refreshed too: that cancels a poll that left before the save and would land
 * with the old project, and restarts it, so a fetch something else is waiting
 * on (the refresh after a start, a first load) still lands. Nothing else under
 * `['project', id]` changed. The project list shows these fields, so it is
 * refreshed as well.
 *
 * On failure it toasts the server's reason, or `errorMessage`.
 */
export function useUpdateProject(
  projectId: string | null | undefined,
  { successMessage, errorMessage, onSuccess, onError, ...options }: UpdateProjectOptions,
) {
  const queryClient = useQueryClient();
  return useMutation<Project, Error, UpdateProjectRequest>({
    ...options,
    mutationFn: (changes) => {
      if (!projectId) throw new Error('No project ID');
      return updateProjectEndpointApiProjectProjectIdPatch({ path: { project_id: projectId }, body: changes });
    },
    onSuccess: (project, ...rest) => {
      if (projectId) {
        // The overview is keyed per revision, so every cached revision of it gets the project.
        const overviews = { queryKey: projectQueryKeys.overviews(projectId) };
        queryClient.setQueriesData(overviews, (overview: ProjectOverview | undefined) =>
          overview ? { ...overview, project } : overview,
        );
        void queryClient.invalidateQueries(overviews);
      }
      void queryClient.invalidateQueries({ queryKey: PROJECT_LIST_QUERY_KEY });
      if (successMessage) toast.success(successMessage);
      return onSuccess?.(project, ...rest);
    },
    onError: (...args) => {
      toast.error(getErrorMessage(args[0], errorMessage));
      return onError?.(...args);
    },
  });
}
