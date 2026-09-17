import { describe, expect, expectTypeOf, it } from 'vitest';
import { type SimpleDeepAgentState, type WorkflowRunDetail, WorkflowRunType } from './generated-api';
import { getWorkflowRunByType, type WorkflowRunDetailTyped } from './workflow-state';

function detail(type: WorkflowRunType): WorkflowRunDetail {
  return { run: { id: `run-${type}`, type }, state: { status: 'completed' } } as unknown as WorkflowRunDetail;
}

describe('getWorkflowRunByType', () => {
  it('finds a skill-declared workflow and types its state as the shared deep-agent state', () => {
    const runs = [detail(WorkflowRunType.AdvocacyToneV2), detail(WorkflowRunType.ActiveVoice)];

    const found = getWorkflowRunByType(runs, WorkflowRunType.ActiveVoice);

    expect(found?.run.type).toBe(WorkflowRunType.ActiveVoice);
    // Checked by the TypeScript build: a type with no bespoke state falls back to SimpleDeepAgentState.
    expectTypeOf(found).toEqualTypeOf<WorkflowRunDetailTyped<SimpleDeepAgentState> | undefined>();
  });

  it('returns undefined when no run of that type exists', () => {
    expect(getWorkflowRunByType([detail(WorkflowRunType.AdvocacyToneV2)], WorkflowRunType.ActiveVoice)).toBeUndefined();
  });
});
