'use client';

import { WorkflowRun, WorkflowRunStatus } from '@/lib/generated-api';
import { ClockIcon } from 'lucide-react';
import { useEffect, useState } from 'react';

function formatSeconds(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function useElapsedSeconds(startDate: Date | null, active: boolean): number | null {
  const [elapsed, setElapsed] = useState<number | null>(
    startDate ? Math.floor((Date.now() - startDate.getTime()) / 1000) : null,
  );

  useEffect(() => {
    if (!startDate || !active) return;
    const tick = () => setElapsed(Math.floor((Date.now() - startDate.getTime()) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startDate, active]);

  return elapsed;
}

interface WorkflowDurationProps {
  run: WorkflowRun;
}

export function WorkflowDuration({ run }: WorkflowDurationProps) {
  const isRunning = run.status === WorkflowRunStatus.Running;
  const startDate = run.started_at ? new Date(run.started_at) : null;
  const endDate = run.completed_at ? new Date(run.completed_at) : null;

  const liveElapsed = useElapsedSeconds(startDate, isRunning);

  if (!startDate) return null;

  let durationSeconds: number | null = null;

  if (isRunning && liveElapsed !== null) {
    durationSeconds = liveElapsed;
  } else if (endDate) {
    durationSeconds = Math.floor((endDate.getTime() - startDate.getTime()) / 1000);
  }

  if (durationSeconds === null) return null;

  return (
    <div className="flex items-center gap-1.5">
      <ClockIcon className="w-3.5 h-3.5 shrink-0" />
      <span>{formatSeconds(durationSeconds)}</span>
    </div>
  );
}
