import { describe, expect, it } from 'vitest';
import {
  authorQuestions,
  fileLinkOf,
  finishOutputsMessage,
  missingOutputs,
  outputsAction,
  verdictKind,
  stepNotes,
  MESSAGES,
  outputsMessage,
  researchItems,
  stepOf,
  verdictOf,
  type RunFile,
} from './live-report-state';

const file = (name: string, content = '') => ({ name, content });

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

  it('is back on the brief when it is changed after its approval, before any output', () => {
    expect(stepOf([file('research-brief.md')], [approved, 'Make the brief shorter.'])).toBe('brief');
  });
});

const PLAN = `## Claims

- **C1 (Summary).** Vacancy will stabilize. Rests on F1.

## Facts to check

- **F1 (Section 1).** "Vacancy is 17 percent." From: inference over D1.
- **F2 (Section 2).** About 30 percent of days are remote. From: the world.

## Data

- **D1.** Quarterly vacancy series.

## Angles beyond the report

- **A1.** New conversion incentives.`;

describe('researchItems', () => {
  it('lists facts, data and angles but not claims, with verdicts once their notes exist', () => {
    const files: RunFile[] = [file('research/F1.md', '# F1\n\n- **Verdict:** Superseded\n')];
    expect(researchItems(PLAN, files)).toEqual([
      { id: 'F1', text: '"Vacancy is 17 percent."', verdict: 'Superseded', note: files[0].content },
      { id: 'F2', text: 'About 30 percent of days are remote.', verdict: undefined },
      { id: 'D1', text: 'Quarterly vacancy series.', verdict: undefined },
      { id: 'A1', text: 'New conversion incentives.', verdict: undefined },
    ]);
  });

  it('leaves out the candidates the plan did not include', () => {
    const plan = `${PLAN}\n\n## Not included\n\n- **F16 (S4).** A fact left out.`;
    expect(researchItems(plan, []).map((item) => item.id)).toEqual(['F1', 'F2', 'D1', 'A1']);
  });

  it('is empty before there is a plan', () => {
    expect(researchItems(undefined, [])).toEqual([]);
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

describe('fileLinkOf', () => {
  it('finds the step for each way the agent links its files', () => {
    expect(fileLinkOf('sandbox:/live-report/addendum.md')).toEqual({ step: 'outputs', file: 'addendum.md' });
    expect(fileLinkOf('/live-report/research-plan.md')).toEqual({ step: 'plan', file: 'research-plan.md' });
    expect(fileLinkOf('intake.md')).toEqual({ step: 'intake', file: 'intake.md' });
    expect(fileLinkOf('sandbox:/live-report/research/F1.md')).toEqual({ step: 'research', file: 'research/F1.md' });
  });

  it('leaves other links alone', () => {
    expect(fileLinkOf('https://example.org/report.md')).toBeNull();
    expect(fileLinkOf('/live-report/notes.md')).toBeNull();
    expect(fileLinkOf(undefined)).toBeNull();
  });
});

describe('verdictOf', () => {
  it('keeps the label and drops the explanation', () => {
    expect(verdictOf('- **Verdict:** newer release. Many models came out.')).toBe('Newer release');
    expect(verdictOf('- **Verdict:** Contrary views found (on C3); agreeing on C4')).toBe('Contrary views found');
  });
});

const BRIEF = `## Claims that stand

C7.

## Questions for the authors

1. **C3 (F3).** Should the claim stay historical?
2. **C6–C8 (A1).** Should the framework cover agentic tasks?

## Nothing new found

- **D1.** No newer release.`;

describe('authorQuestions', () => {
  it('reads the numbered questions and what each is about', () => {
    expect(authorQuestions(BRIEF)).toEqual([
      { about: 'C3 (F3)', text: 'Should the claim stay historical?' },
      { about: 'C6–C8 (A1)', text: 'Should the framework cover agentic tasks?' },
    ]);
  });

  it('is empty when the brief has none', () => {
    expect(authorQuestions('## What changed\n\nNothing.')).toEqual([]);
  });
});

describe('outputsMessage', () => {
  const questions = authorQuestions(BRIEF);

  it('names the chosen outputs and leaves unanswered questions open', () => {
    const message = outputsMessage({ addendum: true, changePlan: false }, [], questions);
    expect(message).toContain('Leave the questions for the authors open.');
    expect(message).toContain('I want the addendum.');
  });

  it('passes on the answers given, by what they are about', () => {
    const message = outputsMessage({ addendum: true, changePlan: true }, ['', 'Yes, cover them.'], questions);
    expect(message).toContain('2. C6–C8 (A1): Should the framework cover agentic tasks?\n   Answer: Yes, cover them.');
    expect(message).toContain('I want the addendum and the change plan.');
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

describe('verdictKind', () => {
  it('tells apart verdicts that share words', () => {
    expect(verdictKind('Newer release')).toBe('update');
    expect(verdictKind('No newer release')).toBe('nothing');
    expect(verdictKind('Discontinued or replaced')).toBe('caution');
    expect(verdictKind('Still holds')).toBe('holds');
  });

  it("is neutral for a verdict the skill doesn't list", () => {
    expect(verdictKind('Done')).toBe('nothing');
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
