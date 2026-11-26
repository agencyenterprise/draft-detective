'use client';

import type { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { startMultipleWorkflowsApiWorkflowsStartMultiplePost, WorkflowRunPublic } from '@/lib/generated-api';
import { useProjectMutation } from '@/lib/hooks/use-project-mutation';
import { busyWorkflowTypes } from './run-activity-summary';
import { startAssessmentsKey, useStartingWorkflowTypes } from './use-starting-workflow-types';

/**
 * What every "Run assessments" dialog on the project page needs: the start
 * itself, keyed so the other controls see it in flight, and the assessments
 * that cannot be picked again because they run or are starting.
 */
export function useStartAssessments(projectId: string, runs: { run: WorkflowRunPublic }[]) {
  const { mutate } = useProjectMutation(projectId, {
    mutationKey: startAssessmentsKey(projectId),
    mutationFn: (values: WorkflowConfigFormValues) =>
      startMultipleWorkflowsApiWorkflowsStartMultiplePost({
        body: { project_id: projectId, workflow_types: values.workflowTypes },
      }),
    successMessage: 'Assessments started',
    errorMessage: 'Failed to start assessments',
    // The header button goes from "Starting…" to "Running" with no idle state between.
    waitForRefresh: true,
  });
  const startingTypes = useStartingWorkflowTypes(projectId);

  return { startAssessments: mutate, startingTypes, busyTypes: busyWorkflowTypes(runs, startingTypes) };
}
