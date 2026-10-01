'use client';

import { StatusIndicator } from '@/components/ui/status-indicator';
import { FileListItem, ReviewAssistantRun } from '@/lib/generated-api';
import { RAIL_ITEM_ACTIVE, RAIL_ITEM_IDLE } from '@/lib/rail-style';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { OUTPUT_ICONS } from './output-icons';
import { OUTPUTS, ReviewOutputType } from './outputs';
import { describeInputs } from './run-inputs';

interface OutputRailProps {
  outputType: ReviewOutputType | null;
  runs: ReviewAssistantRun[];
  files: FileListItem[];
  selectedRunId: string | null;
  onSelectOutput: (output: ReviewOutputType) => void;
  onSelectRun: (runId: string) => void;
}

/**
 * The outputs to choose from, then the chosen one's runs. Output first: the
 * rail starts from what the user wants out, and only the runs of that output
 * are listed under it.
 */
export function OutputRail({ outputType, runs, files, selectedRunId, onSelectOutput, onSelectRun }: OutputRailProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <h2 className="px-2 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">Outputs</h2>
        <ul className="mt-2 space-y-px">
          {OUTPUTS.map((output) => {
            const Icon = OUTPUT_ICONS[output.type];
            const active = output.type === outputType;
            return (
              <li key={output.type}>
                <button
                  onClick={() => onSelectOutput(output.type)}
                  aria-current={active ? 'true' : undefined}
                  className={cn(
                    'flex w-full cursor-pointer gap-2.5 rounded-md px-2 py-2 text-left transition-colors',
                    active ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE,
                  )}
                >
                  <Icon className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 text-[13px] leading-tight font-medium">{output.title}</span>
                </button>
              </li>
            );
          })}
        </ul>

        {outputType && (
          <>
            <h2 className="mt-5 flex items-center gap-2 px-2 font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
              Runs
              <span className="text-[11px] tabular-nums">{runs.length}</span>
            </h2>
            {runs.length === 0 ? (
              <p className="mt-2 px-2 text-[11px] leading-relaxed text-muted-foreground">
                None yet. Each run is kept here with the inputs it used.
              </p>
            ) : (
              <ol className="mt-2 space-y-px">
                {runs.map((run) => {
                  const active = run.run.id === selectedRunId;
                  return (
                    <li key={run.run.id}>
                      <button
                        onClick={() => onSelectRun(run.run.id)}
                        aria-current={active ? 'true' : undefined}
                        className={cn(
                          'w-full cursor-pointer rounded-md px-2 py-2 text-left transition-colors',
                          active ? RAIL_ITEM_ACTIVE : RAIL_ITEM_IDLE,
                        )}
                      >
                        <span className="flex items-center justify-between gap-2">
                          <StatusIndicator status={run.run.status} />
                          <span className="shrink-0 text-[11px] text-muted-foreground">
                            {formatDistanceToNow(new Date(run.run.created_at), { addSuffix: true })}
                          </span>
                        </span>
                        <span className="mt-1 block text-[11px] leading-snug text-muted-foreground">
                          {describeInputs(run, files).join(' · ')}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            )}
          </>
        )}
      </div>

      <p className="shrink-0 border-t px-5 py-4 text-xs leading-relaxed text-muted-foreground">
        Pick the output you need. The inputs pane asks only for what it reads, from any revision or project file, or an
        upload.
      </p>
    </div>
  );
}
