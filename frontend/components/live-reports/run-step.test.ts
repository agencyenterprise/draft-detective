import { describe, expect, it } from 'vitest';
import { finishOutputsMessage, MESSAGES, outputsMessage, type RunFile } from './live-report-state';
import { missingOutputs, outputsAction, stepNotes, stepOf } from './run-step';

const file = (name: string, content = ''): RunFile => ({ name, content });

describe('stepOf', () => {
  const approved = 'The brief is approved. Leave the questions for the authors open.\nI want the addendum.';

  it('follows the files the agent has written', () => {
    expect(stepOf([], [])).toBe('upload');
    expect(stepOf([file('intake.md')], [MESSAGES.start])).toBe('intake');
    expect(stepOf([file('intake.md'), file('research-plan.md')], [MESSAGES.approveIntake])).toBe('plan');
    expect(stepOf([file('research-plan.md'), file('research-brief.md')], [MESSAGES.approvePlan])).toBe('brief');
    expect(stepOf([file('research-brief.md'), file('addendum.md')], [approved])).toBe('outputs');
    expect(stepOf([file('research-brief.md'), file('change-plan.md')], [approved])).toBe('outputs');
  });

  it('is researching from a go-ahead, before any note exists', () => {
    expect(stepOf([file('research-plan.md')], [MESSAGES.approvePlan])).toBe('research');
    expect(stepOf([file('research-plan.md'), file('research/F1.md')], [MESSAGES.resumeResearch])).toBe('research');
    expect(stepOf([file('research-plan.md'), file('research/F1.md')], [MESSAGES.approveRevisedPlan])).toBe('research');
  });

  it('is back on the plan when it is changed after research started', () => {
    const files = [file('research-plan.md'), file('research/F1.md')];
    expect(stepOf(files, [MESSAGES.approvePlan, 'Drop F1 and add a fact on remote work.'])).toBe('plan');
  });

  it('stays on the plan while the agent revises it', () => {
    expect(stepOf([file('research-plan.md')], ['Drop F4.'])).toBe('plan');
  });

  it('is on the outputs once the brief is approved, even before one is written', () => {
    expect(stepOf([file('research-brief.md')], [MESSAGES.approvePlan, approved])).toBe('outputs');
    const finish = finishOutputsMessage(['addendum']);
    expect(stepOf([file('research-brief.md')], [approved, finish])).toBe('outputs');
  });

  it('reopens a step whose file was revised after a later one was written', () => {
    const at = (name: string, time: string) => ({ name, content: '', modified_at: `2026-11-20T10:${time}:00+00:00` });
    // The brief changed after the addendum: approve the brief again.
    const briefRevised = [at('research-brief.md', '30'), at('addendum.md', '20')];
    expect(stepOf(briefRevised, [approved, 'Make the brief shorter.'])).toBe('brief');
    // The addendum rewritten from it: back on the outputs.
    expect(stepOf([at('research-brief.md', '30'), at('addendum.md', '40')], [approved])).toBe('outputs');
    // The plan changed after the brief: approve the plan again.
    const planRevised = [at('research-plan.md', '50'), at('research-brief.md', '30')];
    expect(stepOf(planRevised, [MESSAGES.approvePlan, 'Add an angle.'])).toBe('plan');
    expect(stepOf(planRevised, [MESSAGES.approveRevisedPlan])).toBe('research');
    // The plan changed after the outputs too: approve the plan again.
    const underOutputs = [...planRevised, at('addendum.md', '40')];
    expect(stepOf(underOutputs, [approved, 'Add an angle.'])).toBe('plan');
  });

  it('counts each output as current only if written after everything it was built on', () => {
    const at = (name: string, time: string) => ({ name, content: '', modified_at: `2026-11-20T10:${time}:00+00:00` });
    // Both outputs existed; the brief changed; a stopped re-run rewrote only the addendum.
    const partial = [at('research-brief.md', '30'), at('addendum.md', '40'), at('change-plan.md', '20')];
    const both = outputsMessage({ addendum: true, changePlan: true }, [], []);
    expect(stepOf(partial, [both, both])).toBe('outputs');
    expect(missingOutputs(partial, [{ from: 'you', text: both }])).toEqual(['changePlan']);
  });

  it('reopens the intake, or the research, when they change under what was built on them', () => {
    const at = (name: string, time: string) => ({ name, content: '', modified_at: `2026-11-20T10:${time}:00+00:00` });
    const built = [at('research-plan.md', '20'), at('research-brief.md', '30'), at('addendum.md', '40')];
    // The publication date corrected after everything was written: approve the intake again.
    expect(stepOf([at('intake.md', '50'), ...built], [approved, 'The date is wrong.'])).toBe('intake');
    // A research item re-run after the brief, stopped before the brief was rewritten.
    const rerun = [at('intake.md', '10'), ...built, at('research/F1.md', '50')];
    expect(stepOf(rerun, [approved, 'Look for more recent sources on F1.'])).toBe('research');
  });

  it('is back on the brief when it is changed after its approval, before any output', () => {
    expect(stepOf([file('research-brief.md')], [approved, 'Make the brief shorter.'])).toBe('brief');
  });
});

describe('stepNotes', () => {
  const you = (text: string) => ({ from: 'you' as const, text });
  const agent = (text: string) => ({ from: 'agent' as const, text });

  it('gives each step the last reply the agent gave on it', () => {
    const notes = stepNotes([
      you(MESSAGES.start),
      agent('Intake written; the date is provisional.'),
      you('The date is August 6.'),
      agent('Intake updated.'),
      you(MESSAGES.approveIntake),
      agent('Plan drafted: 14 items.'),
      you(MESSAGES.approvePlan),
      agent('The brief is ready.'),
      you(outputsMessage({ addendum: true, changePlan: false }, [], [])),
      agent('The addendum is ready.'),
    ]);
    expect(notes).toEqual({
      intake: 'Intake updated.',
      plan: 'Plan drafted: 14 items.',
      brief: 'The brief is ready.',
      outputs: 'The addendum is ready.',
    });
  });

  it('gives a step no note when its turn ended without a reply', () => {
    expect(stepNotes([you(MESSAGES.start)])).toEqual({});
  });
});

describe('missingOutputs', () => {
  const you = (text: string) => ({ from: 'you' as const, text });
  const both = outputsMessage({ addendum: true, changePlan: true }, [], []);

  it('names an output asked for on the brief and not written', () => {
    expect(missingOutputs([file('addendum.md')], [you(both)])).toEqual(['changePlan']);
  });

  it('is empty once every output asked for is written, or for a single output', () => {
    expect(missingOutputs([file('addendum.md'), file('change-plan.md')], [you(both)])).toEqual([]);
    const addendumOnly = outputsMessage({ addendum: true, changePlan: false }, [], []);
    expect(missingOutputs([file('addendum.md')], [you(addendumOnly)])).toEqual([]);
  });

  it('names every output when the turn stopped before writing any', () => {
    expect(missingOutputs([file('research-brief.md')], [you(both)])).toEqual(['addendum', 'changePlan']);
  });

  it('reads what was asked from the request line, not from the answers', () => {
    const answered = outputsMessage(
      { addendum: true, changePlan: false },
      ['Add it to the change plan.'],
      [{ about: 'C1', text: 'Q?' }],
    );
    expect(missingOutputs([file('addendum.md')], [you(answered)])).toEqual([]);
  });
});

describe('outputsAction', () => {
  it('is approved once the approval is sent and the agent is idle', () => {
    expect(outputsAction(MESSAGES.approveOutputs, [], false)).toBe('approved');
  });

  it('writes what is missing before anything can be approved', () => {
    expect(outputsAction('Make the addendum shorter.', ['changePlan'], false)).toBe('finish');
  });

  it('offers approval otherwise, and while the agent works', () => {
    expect(outputsAction('Make the addendum shorter.', [], false)).toBe('approve');
    expect(outputsAction(MESSAGES.approveOutputs, ['changePlan'], true)).toBe('approve');
  });
});
