import { describe, expect, it } from 'vitest';
import {
  authorQuestions,
  fileLinkOf,
  verdictKind,
  outputsMessage,
  researchItems,
  verdictOf,
  type RunFile,
} from './live-report-state';

const file = (name: string, content = '') => ({ name, content });

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
