import { WorkflowRun, WorkflowRunStatus } from '@/lib/generated-api';
import { useSyncExternalStore } from 'react';

// Shared ticker for synchronizing all duration updates across hook instances
const subscribers = new Set<() => void>();
let currentTime = Date.now();
let tickInterval: ReturnType<typeof setInterval> | null = null;

function startTicker() {
  if (tickInterval) return;
  currentTime = Date.now();
  tickInterval = setInterval(() => {
    currentTime = Date.now();
    subscribers.forEach((callback) => callback());
  }, 1000);
}

function stopTicker() {
  if (tickInterval) {
    clearInterval(tickInterval);
    tickInterval = null;
  }
}

function subscribe(callback: () => void) {
  subscribers.add(callback);
  if (subscribers.size === 1) {
    startTicker();
  }
  return () => {
    subscribers.delete(callback);
    if (subscribers.size === 0) {
      stopTicker();
    }
  };
}

function getSnapshot() {
  return currentTime;
}

// No-op subscribe for non-running workflows
const noopSubscribe = () => () => {};

/**
 * Hook to compute workflow duration with live updates for running workflows.
 * All instances share a single synchronized ticker.
 * @param run - The workflow run
 * @returns Duration in milliseconds, or null if not applicable
 */
export function useWorkflowDuration(run: WorkflowRun): number | null {
  const isRunning = run.status === WorkflowRunStatus.Running;
  const startedAt = run.started_at ? new Date(run.started_at).getTime() : null;
  const completedAt = run.completed_at ? new Date(run.completed_at).getTime() : null;

  // Subscribe to shared ticker only when running
  const now = useSyncExternalStore(isRunning ? subscribe : noopSubscribe, getSnapshot, getSnapshot);

  // No duration if workflow hasn't started
  if (!startedAt) {
    return null;
  }

  // For completed workflows, return total duration
  if (run.status === WorkflowRunStatus.Completed && completedAt) {
    return completedAt - startedAt;
  }

  // For running workflows, return elapsed time
  if (isRunning) {
    return now - startedAt;
  }

  return null;
}
