'use client';

import { useProjectView } from '@/components/results/project-view-context';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { WorkflowConfigDialog } from '@/components/workflows/workflow-config-dialog';
import { cn } from '@/lib/utils';
import { isAnyWorkflowActive } from '@/lib/workflow-state';
import { ChevronDownIcon, Loader2, PlayIcon } from 'lucide-react';
import { useState } from 'react';
import { RunActivityDetails } from './run-activity/run-activity-details';
import { runActivityLabel, runActivityStatus } from './run-activity/run-activity-summary';
import { RunActivity, useRunActivity } from './run-activity/use-run-activity';
import { useStartAssessments } from './run-activity/use-start-assessments';

/**
 * Starts assessments from the project header, so it is reachable from every
 * tab. Running one is the thing people come back to do, and burying it in the
 * Assessments tab made it a two-step trip from wherever they were reading.
 *
 * "Run", not "New": nothing is created here. The dialog is a multi-select over
 * the assessments that already exist, and every other control in this view
 * speaks the same way — "Ready to run", "Run more", "Re-run X".
 *
 * While anything runs the button says so itself, spinner and count, instead of
 * staying a solid "Run assessments" that reads as if nothing had happened. It
 * still opens the dialog, to queue more; the half beside it lists what runs.
 */
export function NewAssessmentButton({
  projectId,
  /** Off where the button is the only thing in its space and the label always fits. */
  collapseLabel = true,
}: {
  projectId: string;
  collapseLabel?: boolean;
}) {
  const { overview, readOnly } = useProjectView();
  const runs = overview.workflow_runs ?? [];
  const runsActive = isAnyWorkflowActive(runs);
  const activity = useRunActivity(projectId, runs, runsActive);
  const [open, setOpen] = useState(false);
  const { startAssessments, startingTypes, busyTypes } = useStartAssessments(projectId, runs);
  const isStarting = startingTypes.length > 0;

  const active = runsActive || isStarting;
  const label = <span className={collapseLabel ? 'hidden sm:inline' : undefined}>{runActivityLabel(activity)}</span>;

  if (readOnly) {
    // Nothing to start in a read-only view, but what runs is still worth knowing.
    return active ? (
      <RunActivityPopover activity={activity}>
        <Button variant="ghost" size="xs" aria-label={`${runActivityStatus(activity)}. Show details`}>
          <Loader2 className="text-primary size-3.5 animate-spin" />
          {label}
        </Button>
      </RunActivityPopover>
    ) : null;
  }

  return (
    <>
      <WorkflowConfigDialog
        isOpen={open}
        projectId={projectId}
        runningTypes={busyTypes}
        onConfirm={(values) => {
          setOpen(false);
          startAssessments(values);
        }}
        onCancel={() => setOpen(false)}
      />

      <div className="flex shrink-0">
        <Tooltip>
          <TooltipTrigger asChild>
            {/* Outlined while running: the solid fill is the call to act, and
                that call has already been answered. The spinner keeps the
                primary colour so the header still has one live thing in it. */}
            <Button
              size="xs"
              variant={active ? 'outline' : 'default'}
              className={cn(active && 'rounded-r-none')}
              onClick={() => setOpen(true)}
              aria-label={active ? `${runActivityStatus(activity)}. Run more assessments` : 'Run assessments'}
            >
              {active ? <Loader2 className="text-primary size-3.5 animate-spin" /> : <PlayIcon />}
              {/* A phone header cannot carry five labelled controls; here the
                  icon and its tooltip say it instead. */}
              {active ? label : <span className={collapseLabel ? 'hidden sm:inline' : undefined}>Run assessments</span>}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {active ? 'Assessments are running. Click to run more' : 'Choose assessments to run on this document'}
          </TooltipContent>
        </Tooltip>

        {active && (
          <RunActivityPopover activity={activity}>
            <Button
              size="xs"
              variant="outline"
              className="rounded-l-none border-l-0 px-1.5 has-[>svg]:px-1.5"
              aria-label={`${runActivityStatus(activity)}. Show details`}
            >
              <ChevronDownIcon />
            </Button>
          </RunActivityPopover>
        )}
      </div>
    </>
  );
}

function RunActivityPopover({ activity, children }: { activity: RunActivity; children: React.ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <RunActivityDetails {...activity} />
      </PopoverContent>
    </Popover>
  );
}
