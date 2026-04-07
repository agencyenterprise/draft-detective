import { useQuery } from '@tanstack/react-query';
import {
  getWorkflowTypesApiWorkflowTypesGet,
  WorkflowCategoryOrder,
  WorkflowRunType,
  WorkflowTypeDescription,
} from '../generated-api';
import { useCallback, useMemo } from 'react';

export function useWorkflowTypes() {
  const query = useQuery({
    queryKey: ['workflow-types'],
    staleTime: Infinity,
    queryFn: async () => {
      return await getWorkflowTypesApiWorkflowTypesGet();
    },
  });

  const workflowTypes: WorkflowTypeDescription[] = useMemo(() => query.data?.workflow_types ?? [], [query.data]);
  const categories: WorkflowCategoryOrder[] = useMemo(() => query.data?.categories ?? [], [query.data]);

  const isWorkflowTypeVisible = useCallback(
    (type: WorkflowRunType) => {
      return workflowTypes.some((wt) => wt.type === type && !wt.is_internal);
    },
    [workflowTypes],
  );

  const getWorkflowTypeName = useCallback(
    (type: WorkflowRunType) => {
      return workflowTypes.find((wt) => wt.type === type)?.name ?? type;
    },
    [workflowTypes],
  );

  const getWorkflowTypeDescription = useCallback(
    (type: WorkflowRunType) => {
      return workflowTypes.find((wt) => wt.type === type)?.description ?? null;
    },
    [workflowTypes],
  );

  return {
    ...query,
    workflowTypes,
    categories,
    isWorkflowTypeVisible,
    getWorkflowTypeName,
    getWorkflowTypeDescription,
  };
}
