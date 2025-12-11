import { useQuery } from '@tanstack/react-query';
import { getChunkDetailsEndpointApiWorkflowRunWorkflowRunIdChunkChunkIndexGet } from '@/lib/generated-api';

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

      return await getChunkDetailsEndpointApiWorkflowRunWorkflowRunIdChunkChunkIndexGet({
        path: {
          workflow_run_id: workflowRunId,
          chunk_index: chunkIndex,
        },
      });
    },
    enabled: enabled && chunkIndex !== null,
  });
}
