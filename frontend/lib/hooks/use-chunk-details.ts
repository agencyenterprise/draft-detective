import { useQuery } from '@tanstack/react-query';
import { workflowsApi } from '@/lib/api';

export function useChunkDetails(
  workflowRunId: string,
  chunkIndex: number | null,
  enabled: boolean = true,
  isWorkflowRunning: boolean = false,
) {
  return useQuery({
    queryKey: ['chunkDetails', workflowRunId, chunkIndex],
    refetchInterval: isWorkflowRunning ? 3000 : false,
    queryFn: async () => {
      if (chunkIndex === null) {
        return null;
      }

      return await workflowsApi.getChunkDetailsEndpointApiWorkflowRunWorkflowRunIdChunkChunkIndexGet({
        workflowRunId,
        chunkIndex,
      });
    },
    enabled: enabled && chunkIndex !== null,
  });
}
