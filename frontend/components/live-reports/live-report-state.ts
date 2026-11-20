/**
 * What the /live-reports page derives from a run: which step it is on, and what
 * the buttons need from the files the agent wrote. The agent writes the
 * `live-reports` skill's files under `/live-report/`; the backend serves them by
 * their path in that folder (`GET /api/live-reports/{id}/files`), research
 * notes as `research/<id>.md`.
 *
 * The conversation behind the page is driven by the buttons: each sends one of
 * the messages below.
 */

export type Step = 'upload' | 'intake' | 'plan' | 'research' | 'brief' | 'outputs';
export const STEPS: Step[] = ['upload', 'intake', 'plan', 'research', 'brief', 'outputs'];

export interface RunFile {
  name: string;
  content: string;
  /** When the agent last wrote it (ISO 8601, all in UTC, so they sort as text). */
  modified_at?: string | null;
}

export const FILE_OF: Partial<Record<Step, string>> = {
  intake: 'intake.md',
  plan: 'research-plan.md',
  brief: 'research-brief.md',
};
export const OUTPUT_FILES = { addendum: 'addendum.md', changePlan: 'change-plan.md' } as const;

/** Where the brief's approval names the outputs wanted ("…\nI want the addendum."). */
export const WANTS = '\nI want ';

/** How a request to write the outputs a stopped turn left out ends. */
export const FINISH_OUTPUTS = ' as well, from the approved brief.';

/** The messages the buttons send. Fixed, so the page can tell from history what was approved. */
export const MESSAGES = {
  start: 'Please bring this report up to date.',
  approveIntake: 'The intake is right. Approved.',
  approvePlan: 'The plan is approved. Yes, I consent to running web search on this document. Start the research.',
  approveOutputs: 'Approved.',
  /** After a stop during research: the items with no note, and again those the plan changed since, then the brief. */
  resumeResearch:
    'Continue the research: research the items that have no notes yet, and again any item the plan changed since its note was written, then write the brief.',
  /** A plan changed after research started: carry on with the changed scope. */
  approveRevisedPlan:
    'The revised plan is approved. Research the items that have no notes yet and again any item the change rewrote, then write the brief.',
  /** After a stop before the intake: start again on the report already attached. */
  retryIntake: 'Please read the attached report again and write the intake.',
};

/** What approving the plan agrees to, shown beside the button: the skill's own consent question. */
export const SEARCH_DISCLOSURE =
  "Starting the research sends parts of your document, and possibly the whole document, to a web search provider as search queries. Don't proceed if the document contains confidential information you aren't comfortable sharing with an external search engine.";

export interface Outputs {
  addendum: boolean;
  changePlan: boolean;
}

/** The start of the message that approves the brief, whatever answers and outputs follow. */
export const BRIEF_APPROVED = 'The brief is approved';

export function fileContent(files: RunFile[], name: string | undefined): string | undefined {
  return name ? files.find((f) => f.name === name)?.content : undefined;
}

/** One message of the conversation behind the buttons. */
export interface Exchange {
  from: 'you' | 'agent';
  text: string;
}

export interface FileLink {
  step: Step;
  file: string;
}

const STEP_OF_FILE: Record<string, Step> = {
  ...Object.fromEntries(Object.entries(FILE_OF).map(([step, file]) => [file, step as Step])),
  ...Object.fromEntries(Object.values(OUTPUT_FILES).map((file) => [file, 'outputs' as Step])),
};

/**
 * The step a link opens, when it points at one of the run's files. The agent
 * links them as `sandbox:/live-report/addendum.md`, `/live-report/…` or by bare
 * name; research notes live under `research/`.
 */
export function fileLinkOf(href: string | null | undefined): FileLink | null {
  if (!href) return null;
  const path = href.replace(/^sandbox:/, '').replace(/[?#].*$/, '');
  const file = path.replace(/^\/?live-report\//, '').replace(/^\//, '');
  if (/^research\/[^/]+\.md$/.test(file)) return { step: 'research', file };
  const step = STEP_OF_FILE[file];
  return step ? { step, file } : null;
}

/** The id a file's place on the page carries, so a link to the file can scroll to it. */
export function fileAnchor(file: string): string {
  return `live-report-${file.replace(/[^a-z0-9]+/gi, '-')}`;
}

export interface ResearchItem {
  id: string;
  text: string;
  /** The note's verdict, once the note exists. */
  verdict?: string;
  /** The researcher's full note, once written. */
  note?: string;
}

/**
 * The items the plan sends to research (facts, data and angles; claims aren't
 * searched), each with its note's verdict once written.
 */
export function researchItems(plan: string | undefined, files: RunFile[]): ResearchItem[] {
  if (!plan) return [];
  // Only the sections that are researched: "Not included" lists candidates with ids too.
  const researched = plan
    .split(/^(?=## )/m)
    .filter((section) => RESEARCHED_SECTIONS.some((heading) => section.startsWith(`## ${heading}`)))
    .join('\n');
  const items: ResearchItem[] = [];
  for (const match of researched.matchAll(/^- \*\*([FDA]\d+)\b[^*]*\*\*\s*(.*)$/gm)) {
    const [, id, text] = match;
    const note = fileContent(files, `research/${id}.md`);
    items.push({
      id,
      text: text.replace(/\s*From:.*$/, '').trim(),
      verdict: note ? verdictOf(note) : undefined,
      note,
    });
  }
  return items;
}

/** The plan's sections whose items are researched, as the skill's template names them. */
const RESEARCHED_SECTIONS = ['Facts to check', 'Data', 'Angles beyond the report'];

/** What a research verdict means for the report, which sets its badge's colour. */
export type VerdictKind = 'holds' | 'update' | 'caution' | 'broken' | 'nothing';

/** Every verdict the skill's research step can give (`steps/research.md`), by what it means. */
export const VERDICT_KINDS: Record<string, VerdictKind> = {
  'still holds': 'holds',
  'agreeing views only': 'holds',
  strengthened: 'update',
  'newer release': 'update',
  'significant developments': 'update',
  'minor developments': 'update',
  weakened: 'caution',
  superseded: 'caution',
  contested: 'caution',
  'contrary views found': 'caution',
  'discontinued or replaced': 'caution',
  overturned: 'broken',
  'nothing new found': 'nothing',
  'no newer release': 'nothing',
};

/** A verdict's kind; one the skill doesn't list (a model's own wording) is neutral. */
export function verdictKind(label: string): VerdictKind {
  return (
    VERDICT_KINDS[
      label
        .toLowerCase()
        .replace(/[.:]+$/, '')
        .trim()
    ] ?? 'nothing'
  );
}

/** A note's verdict, short: the label before any explanation. */
export function verdictOf(note: string): string {
  const raw = note.match(/\*\*Verdict:\*\*\s*([^\n]+)/)?.[1] ?? 'Done';
  const label = raw.split(/[.;(]/)[0].trim();
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export interface AuthorQuestion {
  /** The ids the question is about, as the brief writes them: "C3", "C6–C8 (A1)". */
  about: string;
  text: string;
}

/** The brief's "Questions for the authors", one per numbered item. */
export function authorQuestions(brief: string | undefined): AuthorQuestion[] {
  const section = brief?.match(/^## Questions for the authors\s*\n([\s\S]*?)(?=^## |(?![\s\S]))/m)?.[1];
  if (!section) return [];
  return [...section.matchAll(/^\d+\.\s+(?:\*\*([^*]+?)\.?\*\*\s*)?(.+)$/gm)].map(([, about, text]) => ({
    about: (about ?? '').trim(),
    text: text.trim(),
  }));
}

/** Which question an answer belongs to: its wording, not its place in the list. */
export function questionKey(question: AuthorQuestion): string {
  return `${question.about}|${question.text}`;
}

/** The message that approves the brief, with the person's answers and chosen outputs. */
export function outputsMessage(outputs: Outputs, answers: string[], questions: AuthorQuestion[]): string {
  const picked = [outputs.addendum && 'the addendum', outputs.changePlan && 'the change plan'].filter(Boolean);
  // Each answer keeps its question's number and wording: two questions can be about the same claim.
  const answered = questions
    .map((q, i) => ({ q, n: i + 1, answer: (answers[i] ?? '').trim() }))
    .filter(({ answer }) => answer);
  const answerText = answered.length
    ? `My answers to the questions for the authors:\n${answered.map(({ q, n, answer }) => `${n}. ${q.about ? `${q.about}: ` : ''}${q.text}\n   Answer: ${answer}`).join('\n')}\nLeave any other question open.`
    : 'Leave the questions for the authors open.';
  return `${BRIEF_APPROVED}. ${answerText}${WANTS}${picked.join(' and ')}.`;
}

export const OUTPUT_NAMES: Record<keyof Outputs, string> = { addendum: 'the addendum', changePlan: 'the change plan' };

/** The names of some outputs, for a sentence: "the addendum and the change plan". */
export function outputNames(keys: (keyof Outputs)[]): string {
  return keys.map((key) => OUTPUT_NAMES[key]).join(' and ');
}

/** Asks for the outputs a stopped turn left unwritten. */
export function finishOutputsMessage(missing: (keyof Outputs)[]): string {
  return `Write ${outputNames(missing)}${FINISH_OUTPUTS}`;
}
