import { useQuery } from '@tanstack/react-query';
import { getWorkflowTypesApiWorkflowTypesGet } from '../generated-api';

export function useWorkflowTypes() {
  return useQuery({
    queryKey: ['workflow-types'],
    queryFn: async () => {
      return await getWorkflowTypesApiWorkflowTypesGet();
    },
  });
}
