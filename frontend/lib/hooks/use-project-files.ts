import { useQuery } from '@tanstack/react-query';
import { listProjectFilesEndpointApiProjectProjectIdFilesGet } from '../generated-api';
import { useShare } from '@/context/share-context';

export function useProjectFiles(projectId: string) {
  const { shareToken } = useShare();

  return useQuery({
    queryKey: ['files', projectId],
    queryFn: () =>
      listProjectFilesEndpointApiProjectProjectIdFilesGet({
        path: { project_id: projectId },
        query: { share_token: shareToken },
      }),
  });
}
