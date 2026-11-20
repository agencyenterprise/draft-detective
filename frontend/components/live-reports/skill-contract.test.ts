import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { authorQuestions, researchItems, VERDICT_KINDS, verdictOf } from './live-report-state';

/**
 * The page parses what the skill's steps write, so it is checked against the
 * skill's own templates: a skill edit that changes a format fails here, not in
 * front of a user.
 */
function step(name: string): string {
  // Tests run from frontend/; the skill lives at the repo's root.
  return readFileSync(join(process.cwd(), '..', 'skills', 'live-reports', 'steps', `${name}.md`), 'utf8');
}

/** The step's markdown template, between its ```markdown fence and the closing one. */
function template(name: string): string {
  const found = step(name).match(/```markdown\n([\s\S]*?)\n```/)?.[1];
  if (!found) throw new Error(`steps/${name}.md has no markdown template`);
  return found;
}

describe("the skill's templates", () => {
  it('give the research items the page lists', () => {
    expect(researchItems(template('research-plan'), []).map((item) => item.id)).toEqual(['F1', 'D1', 'A1']);
  });

  it("give a note's verdict", () => {
    expect(verdictOf(template('research'))).toBe('<verdict>');
  });

  it('give the questions for the authors', () => {
    expect(authorQuestions(template('research-brief')).map((q) => q.about)).toEqual(['C2']);
  });

  it('give only verdicts the page knows how to show', () => {
    const section = step('research').match(/^## The verdict\n([\s\S]*?)^Then rate your confidence/m)?.[1] ?? '';
    const labels = [...section.matchAll(/\*\*([^*]+?)[:.]?\*\*/g)].map(([, label]) => label.toLowerCase());
    expect(labels.length).toBeGreaterThan(10);
    expect(labels.filter((label) => !(label in VERDICT_KINDS))).toEqual([]);
  });
});
