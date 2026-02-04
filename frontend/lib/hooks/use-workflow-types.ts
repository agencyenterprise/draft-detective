import { useQuery } from '@tanstack/react-query';
import { getWorkflowTypesApiWorkflowTypesGet, WorkflowRunType } from '../generated-api';
import { useCallback } from 'react';

export function useWorkflowTypes() {
  const query = useQuery({
    queryKey: ['workflow-types'],
    staleTime: Infinity,
    queryFn: async () => {
      return await getWorkflowTypesApiWorkflowTypesGet();
    },
  });

  const isWorkflowTypeVisible = useCallback(
    (type: WorkflowRunType) => {
      const types = query.data ?? [];
      return types.some((wt) => wt.type === type && !wt.is_internal && wt.can_be_triggered_by_user);
    },
    [query.data],
  );

  const getWorkflowTypeName = useCallback(
    (type: WorkflowRunType) => {
      const types = query.data ?? [];
      return types.find((wt) => wt.type === type)?.name ?? type;
    },
    [query.data],
  );

  return {
    ...query,
    isWorkflowTypeVisible,
    getWorkflowTypeName,
  };
}
