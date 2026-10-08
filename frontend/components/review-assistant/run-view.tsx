'use client';

import { HtmlReportFrame, HtmlReportFrameHandle } from '@/components/results/components/html-report-frame';
import { Button } from '@/components/ui/button';
import { ReviewAssistantRun, WorkflowRunStatus } from '@/lib/generated-api';
import { Ban, Loader2, X, XCircle } from 'lucide-react';
import { Ref } from 'react';
import { DashedCta } from './dashed-cta';
import { OUTPUT_ICONS } from './output-icons';
import { OutputDefinition } from './outputs';
import { isRunActive } from './use-review-assistant-runs';

interface RunViewProps {
  output: OutputDefinition;
  run?: ReviewAssistantRun;
  readOnly: boolean;
  frameRef: Ref<HtmlReportFrameHandle>;
  onCancel: (runId: string) => void;
  /** Present where the inputs are a sheet rather than a column, so the empty state can open it. */
  onOpenInputs?: () => void;
}

/** The middle column: the picked run's report, or what stands in for it. */
export function RunView({ output, run, readOnly, frameRef, onCancel, onOpenInputs }: RunViewProps) {
  if (!run) {
    return (
      <DashedCta
        icon={OUTPUT_ICONS[output.type]}
        title={`No ${output.noun} yet`}
        description={
          readOnly
            ? `Nobody has generated a ${output.noun} from this page yet.`
            : `Choose its inputs in the Inputs pane, then generate it. It takes a few minutes, and every run is kept with the inputs it used.`
        }
        action={
          onOpenInputs &&
          !readOnly && (
            <Button variant="outline" onClick={onOpenInputs}>
              Choose inputs
            </Button>
          )
        }
      />
    );
  }

  if (isRunActive(run)) {
    return (
      <DashedCta
        icon={Loader2}
        spin
        title={`Writing the ${output.noun}`}
        description="This takes a few minutes. You can leave the page; the run carries on."
        action={
          !readOnly && (
            <Button variant="outline" onClick={() => onCancel(run.run.id)}>
              <X className="size-4" />
              Cancel
            </Button>
          )
        }
      />
    );
  }

  if (!run.report_html) {
    const cancelled = run.run.status === WorkflowRunStatus.Cancelled;
    return (
      <DashedCta
        icon={cancelled ? Ban : XCircle}
        title={cancelled ? 'This run was cancelled' : 'This run produced no report'}
        description={run.run.failure_message ?? undefined}
      />
    );
  }

  return <HtmlReportFrame ref={frameRef} html={run.report_html} title={output.title} />;
}
