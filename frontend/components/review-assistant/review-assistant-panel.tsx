'use client';

import { HtmlReportFrameHandle } from '@/components/results/components/html-report-frame';
import { Rail, RailToggle, SidePane, useRailState } from '@/components/results/panes';
import { useProjectView } from '@/components/results/project-view-context';
import { Button } from '@/components/ui/button';
import { useExperimentalFeatures } from '@/context/experimental-features-context';
import { WIDE_ENOUGH_FOR_PANE, useMediaQuery } from '@/lib/use-media-query';
import { Download, SlidersHorizontal } from 'lucide-react';
import { useRef, useState } from 'react';
import { InputsPane } from './inputs-pane';
import { OUTPUT_ICONS } from './output-icons';
import { OutputRail } from './output-rail';
import { OUTPUTS, ReviewOutputType, SLOTS, outputDefinition } from './outputs';
import { RunView } from './run-view';
import { EMPTY_SELECTION, InputSelection, defaultSelection, toRequestInputs } from './selection';
import { useReviewAssistantRuns } from './use-review-assistant-runs';

/**
 * Output-first review assistant: pick what you want out, then fill the inputs
 * it needs from any revision or project file, or upload them. A hidden route
 * while the flow is being tried out next to the Peer Review tab.
 */
export function ReviewAssistantPanel() {
  const { showExperimentalFeatures, isLoading } = useExperimentalFeatures();

  if (isLoading) return null;
  if (!showExperimentalFeatures) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="max-w-sm text-center text-sm leading-relaxed text-muted-foreground">
          The review assistant is an alpha feature. Turn on <strong className="font-medium">Alpha features</strong> in
          your profile menu to use it.
        </p>
      </div>
    );
  }
  return <ReviewAssistant />;
}

function ReviewAssistant() {
  const { overview, readOnly, onRevisionCreated } = useProjectView();
  const projectId = overview.project.id;
  const files = overview.files ?? [];
  const currentRevision = overview.project.current_revision ?? 1;

  const rail = useRailState();
  const isWideEnoughForInputs = useMediaQuery(WIDE_ENOUGH_FOR_PANE);
  const [inputsOpen, setInputsOpen] = useState(false);
  const frameRef = useRef<HtmlReportFrameHandle>(null);

  const [outputType, setOutputType] = useState<ReviewOutputType | null>(null);
  const [selection, setSelection] = useState<InputSelection>(EMPTY_SELECTION);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { runs, start, cancel } = useReviewAssistantRuns(projectId, outputType);

  const output = outputType ? outputDefinition(outputType) : null;
  const selectedRun = runs.find((r) => r.run.id === selectedRunId) ?? runs[0];

  const pickOutput = (type: ReviewOutputType) => {
    rail.close();
    if (type === outputType) return;
    setOutputType(type);
    setSelection(defaultSelection(outputDefinition(type), files, currentRevision));
    setSelectedRunId(null);
  };

  const generate = () => {
    if (!output) return;
    start.mutate(toRequestInputs(output, selection, files), {
      onSuccess: (data) => {
        setSelectedRunId(data.workflow_run_id);
        setInputsOpen(false);
      },
    });
  };

  return (
    <div className="flex h-full min-h-0">
      <Rail state={rail} label="Outputs">
        <OutputRail
          outputType={outputType}
          runs={runs}
          files={files}
          selectedRunId={selectedRun?.run.id ?? null}
          onSelectOutput={pickOutput}
          onSelectRun={(runId) => {
            setSelectedRunId(runId);
            rail.close();
          }}
        />
      </Rail>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center gap-2 border-b px-2">
          <RailToggle state={rail} label="Outputs" />
          <span className="min-w-0 truncate text-xs text-muted-foreground">Review assistant</span>

          <span className="ml-auto flex shrink-0 items-center gap-1.5">
            {selectedRun?.report_html && (
              <Button size="xs" variant="outline" onClick={() => frameRef.current?.print()}>
                <Download className="size-3" />
                Download PDF
              </Button>
            )}
            {output && !isWideEnoughForInputs && (
              <Button size="xs" variant="outline" onClick={() => setInputsOpen(true)}>
                <SlidersHorizontal className="size-3" />
                Inputs
              </Button>
            )}
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-4xl px-6 py-5">
            <header className="border-b pb-4">
              <h1 className="text-base font-semibold tracking-tight">{output?.title ?? 'What do you need?'}</h1>
              <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                {output?.summary ??
                  'Pick an output. Each one asks only for the inputs it reads, from any revision or project file, or an upload.'}
              </p>
            </header>

            <div className="pt-4">
              {output ? (
                <RunView
                  key={selectedRun?.run.id}
                  output={output}
                  run={selectedRun}
                  readOnly={readOnly}
                  frameRef={frameRef}
                  onCancel={cancel.mutate}
                  onOpenInputs={isWideEnoughForInputs ? undefined : () => setInputsOpen(true)}
                />
              ) : (
                <OutputChoices onPick={pickOutput} />
              )}
            </div>
          </div>
        </div>
      </main>

      <SidePane
        open={!!output && (isWideEnoughForInputs || inputsOpen)}
        onClose={() => setInputsOpen(false)}
        label="Inputs"
        className="w-[22rem] xl:w-[24rem]"
        empty={
          <p className="px-4 py-5 text-[11.5px] leading-relaxed text-muted-foreground">
            Pick an output to see the inputs it needs.
          </p>
        }
      >
        {output && (
          <InputsPane
            output={output}
            projectId={projectId}
            files={files}
            currentRevision={currentRevision}
            selection={selection}
            readOnly={readOnly}
            isStarting={start.isPending}
            onChange={setSelection}
            onGenerate={generate}
            onRevisionCreated={onRevisionCreated}
          />
        )}
      </SidePane>
    </div>
  );
}

/** The landing state: the three outputs, larger than in the rail, with what each needs. */
function OutputChoices({ onPick }: { onPick: (output: ReviewOutputType) => void }) {
  return (
    <ul className="space-y-2">
      {OUTPUTS.map((output) => {
        const Icon = OUTPUT_ICONS[output.type];
        return (
          <li key={output.type}>
            <button
              onClick={() => onPick(output.type)}
              className="flex w-full cursor-pointer items-start gap-3 rounded-md border px-4 py-3 text-left transition-colors hover:bg-accent/40"
            >
              <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{output.title}</span>
                <span className="mt-0.5 block text-[13px] leading-relaxed text-muted-foreground">{output.summary}</span>
                <span className="mt-1.5 block text-[11px] text-muted-foreground">
                  Needs {output.required.map((slot) => SLOTS[slot].label.toLowerCase()).join(', ')}
                  {output.optional.length > 0 &&
                    `; optionally ${output.optional.map((slot) => SLOTS[slot].label.toLowerCase()).join(', ')}`}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
