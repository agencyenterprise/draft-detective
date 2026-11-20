'use client';

import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';
import { useState } from 'react';
import {
  authorQuestions,
  FILE_OF,
  fileContent,
  outputsMessage,
  questionKey,
  researchItems,
  STEPS,
  type Outputs,
  fileAnchor,
  stepNotes,
  type FileLink,
  type Step,
} from './live-report-state';
import { StepActions } from './step-actions';
import { StepBody } from './step-body';
import { BriefForm, Doc } from './step-parts';
import type { LiveReport } from './use-live-report';

const TITLES: Record<Step, string> = {
  upload: 'Upload',
  intake: 'Intake',
  plan: 'Research plan',
  research: 'Research',
  brief: 'Research brief',
  outputs: 'Addendum and change plan',
};

const HINTS: Record<Step, string> = {
  upload: 'Start from a published report.',
  intake: 'Check the dates and the scope.',
  plan: 'What will be researched, and where.',
  research: 'One helper per item, in parallel.',
  brief: 'What changed, and what it does to each claim.',
  outputs: 'Review what was written.',
};

/** What each step is, what it produces and what that is for: the heading of the step's page. */
const DESCRIPTIONS: Record<Step, string> = {
  upload:
    'Start from a published report, as a PDF or DOCX. The agent reads it and works through the steps with you; nothing goes to the web until you approve the research plan.',
  intake:
    'What the report is and what the update covers: its title, authors, publication date, the date its data ends, and which sections are in scope. The dates set the cutoff for what counts as new.',
  plan: "What will be researched before any searching starts: the report's claims, the facts and data they rest on, new angles to look into, and the sources to use. Each fact, data source and angle gets its own researcher.",
  research:
    'One researcher per item of the plan, searching the web in parallel. Each writes a note with a verdict, how sure it is, and the sources behind it. Open an item to read its note.',
  brief:
    "What has changed since the report came out, and what that does to each of its claims, with sources. It ends with questions only the authors can answer, and it's where you choose what to write.",
  outputs:
    'The addendum, a section to publish with the report that tells its readers what has changed, and the change plan, which tells the authors what to revise, section by section.',
};

/**
 * The live report as guided steps: a stepper, the current step's document and
 * one action bar. The conversation is hidden; every button sends a message.
 */
export function GuidedSteps({ report, onStart }: { report: LiveReport; onStart: (file: File) => void }) {
  const [viewing, setViewing] = useState<Step | null>(null);
  // The brief's draft lives here, not in CurrentStep, so looking back at an
  // earlier step while answering it keeps what was typed and chosen.
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [outputs, setOutputs] = useState<Outputs>({ addendum: true, changePlan: true });
  const draft: BriefDraft = { answers, setAnswers, outputs, setOutputs };
  const current = STEPS.indexOf(report.step);
  const shown = viewing && STEPS.indexOf(viewing) < current ? viewing : report.step;

  // What the agent said as each step ended, shown on the steps already approved.
  const notes = stepNotes(report.conversation);

  /** A link the agent wrote to one of its files: open its step, then scroll to the file. */
  const openFile = (link: FileLink) => {
    const target = STEPS.indexOf(link.step);
    if (target > current) return;
    setViewing(target < current ? link.step : null);
    requestAnimationFrame(() =>
      document.getElementById(fileAnchor(link.file))?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    );
  };

  return (
    <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[264px_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)]">
      {/* The steps: a tinted sidebar, set apart by its tint alone. */}
      <ol className="bg-muted/40 flex flex-col gap-1 p-3 md:overflow-y-auto">
        {STEPS.map((step, i) => {
          const done = i < current;
          return (
            <li key={step}>
              <button
                type="button"
                disabled={!done && i !== current}
                onClick={() => setViewing(done ? step : null)}
                className={cn(
                  'flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left',
                  step === shown && 'bg-background ring-border shadow-xs ring-1',
                  done && step !== shown && 'hover:bg-background/60',
                  i > current && 'opacity-50',
                )}
              >
                <span
                  className={cn(
                    'mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border text-[11px] font-semibold',
                    done && 'border-emerald-700 bg-emerald-700 text-white',
                    i === current && 'border-primary text-primary',
                  )}
                >
                  {done ? <Check className="size-3" /> : i + 1}
                </span>
                <span className="flex flex-col">
                  <span className="text-sm font-medium">{TITLES[step]}</span>
                  <span className="text-muted-foreground text-xs">{HINTS[step]}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      {/* The page: a reading column that scrolls, and an action bar pinned under it. */}
      <section className="flex min-h-0 flex-col">
        {shown === report.step ? (
          <CurrentStep report={report} draft={draft} onStart={onStart} onFileLink={openFile} />
        ) : (
          <ReadingColumn>
            <StepHeading title={TITLES[shown]} hint={DESCRIPTIONS[shown]} />
            {notes[shown] && <AgentNote markdown={notes[shown]} onFileLink={openFile} />}
            <StepBody step={shown} report={report} onStart={onStart} onFileLink={openFile} />
          </ReadingColumn>
        )}
      </section>
    </div>
  );
}

/** The scrolling area, with its content held to a comfortable reading width. */
function ReadingColumn({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-8">{children}</div>
    </div>
  );
}

/** What the agent said on a step: its reply, often a question or a caveat. */
function AgentNote({ markdown, onFileLink }: { markdown: string; onFileLink: (link: FileLink) => void }) {
  return (
    <div className="bg-muted/50 rounded-lg px-4 py-3">
      <p className="text-muted-foreground mb-1 text-xs font-semibold tracking-wide uppercase">From the agent</p>
      <Doc markdown={markdown} onFileLink={onFileLink} />
    </div>
  );
}

function StepHeading({ title, hint }: { title: string; hint: string }) {
  return (
    <header className="flex flex-col gap-1">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="text-muted-foreground text-sm leading-relaxed">{hint}</p>
    </header>
  );
}

/**
 * The step the run is on: the agent's note and the document scroll; the action
 * bar is the card's footer, always in view. The brief's answers and output
 * choice live here so its approve button can sit in that footer.
 */
interface BriefDraft {
  /** By question (`questionKey`), so a revised brief's questions don't inherit another's answer. */
  answers: Record<string, string>;
  setAnswers: (answers: Record<string, string>) => void;
  outputs: Outputs;
  setOutputs: (outputs: Outputs) => void;
}

interface CurrentStepProps {
  report: LiveReport;
  draft: BriefDraft;
  onStart: (file: File) => void;
  onFileLink: (link: FileLink) => void;
}

function CurrentStep({ report, draft, onStart, onFileLink }: CurrentStepProps) {
  const { step, working, lastReply } = report;
  const { outputs, setOutputs } = draft;
  const questions = authorQuestions(fileContent(report.files, FILE_OF.brief));
  const answers = questions.map((q) => draft.answers[questionKey(q)] ?? '');
  const setAnswers = (next: string[]) =>
    draft.setAnswers({ ...draft.answers, ...Object.fromEntries(questions.map((q, k) => [questionKey(q), next[k]])) });
  const researched = researchItems(fileContent(report.files, FILE_OF.plan), report.files);
  const items = researched.length;
  const researchDone = items > 0 && researched.every((item) => item.verdict);
  const noOutput = !outputs.addendum && !outputs.changePlan;

  return (
    <>
      <ReadingColumn>
        <StepHeading title={TITLES[step]} hint={DESCRIPTIONS[step]} />
        {/* The last word is the agent's: on Research that is a question or a reason it
            didn't go on, since the brief's own reply moves the run to the brief. */}
        {lastReply && !working && <AgentNote markdown={lastReply} onFileLink={onFileLink} />}
        <StepBody step={step} report={report} onStart={onStart} onFileLink={onFileLink} />
        {/* Before a thread exists there is no action bar, so a failed upload's error shows here. */}
        {step === 'upload' && !report.conversation.length && report.error && (
          <p className="text-destructive text-sm">{report.error}</p>
        )}
        {step === 'brief' && !working && (
          <BriefForm
            questions={questions}
            answers={answers}
            onAnswers={setAnswers}
            outputs={outputs}
            onOutputs={setOutputs}
          />
        )}
      </ReadingColumn>

      {(step !== 'upload' || report.conversation.length > 0) && (
        <StepActions
          report={report}
          items={items}
          researchDone={researchDone}
          onApproveBrief={noOutput ? undefined : () => report.send(outputsMessage(outputs, answers, questions))}
          outputs={outputs}
        />
      )}
    </>
  );
}
