'use client';

import { Button } from '@/components/ui/button';
import { Check, Square } from 'lucide-react';
import {
  BRIEF_APPROVED,
  finishOutputsMessage,
  MESSAGES,
  outputsAction,
  outputNames,
  SEARCH_DISCLOSURE,
  type Outputs,
  type Step,
} from './live-report-state';
import { RefineBox, Working } from './step-parts';
import type { LiveReport } from './use-live-report';

/** What the agent is doing, by step and by the last message the buttons sent. */
function workingLabel(step: Step, lastSent: string | undefined, researchDone: boolean): string {
  if (step === 'upload') return 'Reading the report and writing the intake…';
  if (step === 'intake') {
    if (lastSent === MESSAGES.approveIntake) return 'Writing the research plan…';
    return lastSent === MESSAGES.start ? 'Writing the intake…' : 'Updating the intake…';
  }
  if (step === 'research') {
    return researchDone
      ? 'All items researched. Writing the brief…'
      : 'Researching. The brief follows once every item is done…';
  }
  if (step === 'brief') return lastSent?.startsWith(BRIEF_APPROVED) ? 'Writing the outputs…' : 'Updating the brief…';
  return 'Updating…';
}

interface StepActionsProps {
  report: LiveReport;
  /** Approves the brief with the person's answers and output choice; absent while no output is chosen. */
  onApproveBrief?: () => void;
  /** The outputs chosen on the brief. */
  outputs: Outputs;
}

/** The brief's approve button, naming what it will have written. */
function approveBriefLabel({ addendum, changePlan }: Outputs): string {
  if (addendum && changePlan) return 'Approve the brief and write the addendum and change plan';
  if (addendum) return 'Approve the brief and write the addendum';
  if (changePlan) return 'Approve the brief and write the change plan';
  return 'Choose the addendum, the change plan or both';
}

/** The action bar under the current step: its buttons, the refine box, and what the agent is doing. */
export function StepActions({ report, onApproveBrief, outputs }: StepActionsProps) {
  const { step, working } = report;
  const { lastSent, researchDone } = report;
  const items = report.research.length;
  // Back on the plan after research began: the plan was changed, and consent was given.
  const revised = step === 'plan' && report.files.some((f) => f.name.startsWith('research/'));
  return (
    <footer className="bg-background border-t">
      {/* Aligned with the reading column above. */}
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-2 px-6 py-3">
        {report.error && <p className="text-destructive text-sm">{report.error}</p>}
        {/* The button sends the person's consent to web search, so it says what that means. */}
        {step === 'plan' && !revised && (
          <p className="text-muted-foreground text-xs leading-relaxed">{SEARCH_DISCLOSURE}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {step === 'upload' && !working && (
            <Button onClick={() => report.send(MESSAGES.retryIntake)}>Try again</Button>
          )}
          {step === 'research' && !working && (
            <Button onClick={() => report.send(MESSAGES.resumeResearch)}>Resume the research</Button>
          )}
          {step === 'intake' && (
            <Button disabled={working} onClick={() => report.send(MESSAGES.approveIntake)}>
              Approve and continue
            </Button>
          )}
          {step === 'plan' &&
            (revised ? (
              <Button disabled={working} onClick={() => report.send(MESSAGES.approveRevisedPlan)}>
                Approve the revised plan and continue the research
              </Button>
            ) : (
              <Button disabled={working} onClick={() => report.send(MESSAGES.approvePlan)}>
                Consent and start the research{items ? ` (${items} items)` : ''}
              </Button>
            ))}
          {step === 'brief' && (
            <Button disabled={working || !onApproveBrief} onClick={onApproveBrief}>
              {approveBriefLabel(outputs)}
            </Button>
          )}
          {step === 'outputs' && <OutputsActions report={report} />}
          {step !== 'upload' && (step !== 'research' || !working) && (
            <RefineBox step={step === 'research' ? 'plan' : step} disabled={working} onSend={report.send} />
          )}
          {working && (
            // What the agent is doing, and the way to stop it, together on the right.
            <div className="bg-muted/60 ml-auto flex items-center gap-3 rounded-full py-1 pr-1 pl-3">
              <Working label={workingLabel(step, lastSent, researchDone)} />
              <Button
                variant="outline"
                size="sm"
                className="hover:border-destructive/40 hover:text-destructive h-7 rounded-full"
                onClick={report.stop}
              >
                <Square className="size-2.5 fill-current" /> Stop
              </Button>
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}

/** The Outputs step's action: see ``outputsAction``. */
function OutputsActions({ report }: { report: LiveReport }) {
  const { working, missing } = report;
  const action = outputsAction(report.lastSent, missing, working);
  if (action === 'approved') {
    return (
      <span className="inline-flex items-center gap-2 py-2 text-sm font-medium text-emerald-800">
        <Check className="size-4" /> Approved
      </span>
    );
  }
  if (action === 'finish') {
    return <Button onClick={() => report.send(finishOutputsMessage(missing))}>Write {outputNames(missing)}</Button>;
  }
  return (
    <Button disabled={working} onClick={() => report.send(MESSAGES.approveOutputs)}>
      Approve
    </Button>
  );
}
