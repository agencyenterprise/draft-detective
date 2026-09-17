import { describe, expect, it } from 'vitest';
import React from 'react';
import { GenericWorkflowResults } from '@/components/results/components/generic-workflow-results';
import { SimpleDeepAgentResults } from '@/components/workflows/results/simple-deep-agent-results';
import { type ProjectDetailed, type WorkflowRunDetail, WorkflowRunType } from '@/lib/generated-api';
import { renderWorkflowResults } from './workflow-results-renderer';

const project = { id: 'project-1' } as unknown as ProjectDetailed;
const names: Partial<Record<WorkflowRunType, string>> = {
  [WorkflowRunType.ActiveVoice]: 'Active Voice & Clear Actors',
};
const nameOf = (type: WorkflowRunType) => names[type] ?? type;

/** A completed run on the shared deep-agent state; only the fields the switch reads. */
function run(type: WorkflowRunType): WorkflowRunDetail {
  return {
    run: { id: 'run-1', type },
    state: { status: 'completed', issues: [], report: 'Done.' },
  } as unknown as WorkflowRunDetail;
}

type ResultsProps = React.ComponentProps<typeof SimpleDeepAgentResults>;

function render(detail: WorkflowRunDetail): React.ReactElement<ResultsProps> {
  return renderWorkflowResults(project, detail, () => undefined, nameOf) as React.ReactElement<ResultsProps>;
}

describe('renderWorkflowResults', () => {
  it('shows a skill-declared workflow, which has no case of its own, with the deep-agent results view', () => {
    const element = render(run(WorkflowRunType.ActiveVoice));

    expect(element.type).toBe(SimpleDeepAgentResults);
    expect(element.props).toMatchObject({ project, workflowName: 'Active Voice & Clear Actors' });
    expect(element.props.workflowDetail.run.type).toBe(WorkflowRunType.ActiveVoice);
  });

  it('leaves the workflows with a bespoke view on that view', () => {
    const element = render(run(WorkflowRunType.ClaimReferenceValidationV2));

    expect(element.type).toBe(GenericWorkflowResults);
  });
});
