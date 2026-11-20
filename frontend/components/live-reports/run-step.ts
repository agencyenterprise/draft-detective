/**
 * Where a live report stands: the step the page shows, from the files the agent
 * wrote and the messages the buttons sent, and what the Outputs step still lacks.
 * Pure, so the rules are tested without rendering.
 */

import {
  BRIEF_APPROVED,
  FILE_OF,
  FINISH_OUTPUTS,
  MESSAGES,
  OUTPUT_FILES,
  OUTPUT_NAMES,
  WANTS,
  type Exchange,
  type Outputs,
  type RunFile,
  type Step,
} from './live-report-state';

/** The messages that send the run into research. */
const RESEARCH_GO: string[] = [MESSAGES.approvePlan, MESSAGES.resumeResearch, MESSAGES.approveRevisedPlan];

/**
 * The step the run is on, from the files the agent wrote and the messages the
 * person sent, in order. The messages decide two moments the files can't:
 * - Research runs from a go-ahead until the brief is written. Any other message
 *   after notes exist changes the plan, which then needs approving again.
 * - A step whose file was revised after a later step's file reopens (see
 *   ``stages``): the files built on the earlier version no longer count.
 * - An approved brief is on Outputs even before an output is written (a turn
 *   stopped early), so the page offers to write them rather than a fresh form;
 *   until another message asks to change the brief, which then needs approving again.
 */
/** Whether the brief's last approval still stands: only requests to write the outputs followed it. */
function briefStillApproved(sent: string[]): boolean {
  const at = sent.findLastIndex((m) => m.startsWith(BRIEF_APPROVED));
  return at >= 0 && sent.slice(at + 1).every((m) => m.endsWith(FINISH_OUTPUTS));
}

/**
 * When each stage of the run was last written, and which are current: a stage is
 * current only if written after everything it was built on (intake, then plan,
 * then the research notes, then brief, then each output). Times are ISO 8601 in
 * UTC, so they compare as text; a file without one never reads as stale.
 */
function stages(files: RunFile[]) {
  const at = (name: string) => files.find((f) => f.name === name)?.modified_at ?? '';
  const has = (name: string) => files.some((f) => f.name === name);
  const latest = (...times: string[]) => times.sort().at(-1) ?? '';
  const notes = latest(...files.filter((f) => f.name.startsWith('research/')).map((f) => f.modified_at ?? ''));
  const [intake, plan, brief] = [at(FILE_OF.intake!), at(FILE_OF.plan!), at(FILE_OF.brief!)];
  // Stale means written before something it was built on; a missing file is neither.
  const planStale = has(FILE_OF.plan!) && intake > plan;
  const planCurrent = has(FILE_OF.plan!) && !planStale;
  const briefStale = planStale || latest(intake, plan, notes) > brief;
  const briefCurrent = has(FILE_OF.brief!) && !briefStale;
  const inputs = latest(intake, plan, notes, brief);
  const outputs = (Object.keys(OUTPUT_FILES) as (keyof Outputs)[]).filter(
    (key) => has(OUTPUT_FILES[key]) && !briefStale && !(inputs > at(OUTPUT_FILES[key])),
  );
  return { has, planCurrent, briefCurrent, notesAfterBrief: has(FILE_OF.brief!) && notes > brief, outputs };
}

/** The outputs written from the current brief, plan and notes. */
export function currentOutputs(files: RunFile[]): (keyof Outputs)[] {
  return stages(files).outputs;
}

export function stepOf(files: RunFile[], sent: string[]): Step {
  const { has, planCurrent, briefCurrent, notesAfterBrief, outputs } = stages(files);
  if (outputs.length) return 'outputs';
  if (briefCurrent) return briefStillApproved(sent) ? 'outputs' : 'brief';
  if (planCurrent) {
    // A note rewritten after the brief (a stopped re-run) leaves the research to finish.
    if (RESEARCH_GO.includes(sent.at(-1) ?? '') || notesAfterBrief) return 'research';
    return 'plan';
  }
  if (has(FILE_OF.intake!)) return 'intake';
  return 'upload';
}

/** The step a message the person sent moves the run to, if it is one of the buttons'. */
function stepAfter(sent: string, step: Step): Step {
  if (sent === MESSAGES.start || sent === MESSAGES.retryIntake) return 'intake';
  if (sent === MESSAGES.approveIntake) return 'plan';
  // Research and the brief are one turn: its reply is the brief's.
  if (RESEARCH_GO.includes(sent)) return 'brief';
  if (sent.startsWith(BRIEF_APPROVED)) return 'outputs';
  return step;
}

/**
 * The agent's note for each step: the last reply it gave while the run was on
 * that step. The buttons send fixed messages, so the conversation says where
 * each step ends.
 */
export function stepNotes(conversation: Exchange[]): Partial<Record<Step, string>> {
  const notes: Partial<Record<Step, string>> = {};
  let step: Step = 'intake';
  for (const entry of conversation) {
    if (entry.from === 'you') step = stepAfter(entry.text, step);
    else notes[step] = entry.text;
  }
  return notes;
}

/** A link the agent wrote to one of its files: the step that shows it, and the file. */
/**
 * The outputs asked for on the brief and not written yet: a turn stopped after
 * the first of two. Read from the last approval of the brief, as the button sent it.
 */
export function missingOutputs(files: RunFile[], conversation: Exchange[]): (keyof Outputs)[] {
  const asked = conversation.findLast((m) => m.from === 'you' && m.text.startsWith(BRIEF_APPROVED))?.text;
  if (!asked) return [];
  const wanted = asked.slice(asked.lastIndexOf(WANTS));
  // Written before the brief or plan last changed counts as not written yet.
  const current = currentOutputs(files);
  return (Object.keys(OUTPUT_NAMES) as (keyof Outputs)[]).filter(
    (key) => wanted.includes(OUTPUT_NAMES[key]) && !current.includes(key),
  );
}

/** What the Outputs step's action bar offers. */
export type OutputsAction = 'approved' | 'finish' | 'approve';

/**
 * Approving the outputs, once every one asked for is written: a turn stopped
 * between the two leaves one missing, which is written first.
 */
export function outputsAction(lastSent: string | undefined, missing: unknown[], working: boolean): OutputsAction {
  if (lastSent === MESSAGES.approveOutputs && !working) return 'approved';
  if (missing.length && !working) return 'finish';
  return 'approve';
}
