'use client';

import { Badge } from '@/components/ui/badge';
import { AnalyzedChunkOutput } from '@/lib/generated-api';
import { Loader2, CheckCircle2, Clock } from 'lucide-react';
import * as React from 'react';

const COMPLETE_BADGE_FADE_START_MS = 4000;
const COMPLETE_BADGE_REMOVE_MS = 5000;

type ChunkStatus = 'queued' | 'analyzing' | 'complete';

export function getChunkStatus(chunk: AnalyzedChunkOutput): ChunkStatus {
  const hasClaims = !!chunk.claims;
  const hasClaimsData = (chunk.claims?.claims?.length || 0) > 0;

  if (!hasClaims) return 'queued';
  if (!hasClaimsData) return 'analyzing';
  return 'complete';
}

interface ChunkStatusBadgeProps {
  chunk: AnalyzedChunkOutput;
  isWorkflowRunning: boolean;
}

export function useShouldShowStatusBadge(isWorkflowRunning: boolean) {
  const hasEverRun = React.useRef(false);

  React.useEffect(() => {
    if (isWorkflowRunning) {
      hasEverRun.current = true;
    }
  }, [isWorkflowRunning]);

  return hasEverRun.current || isWorkflowRunning;
}

export function ChunkStatusBadge({ chunk, isWorkflowRunning }: ChunkStatusBadgeProps) {
  const status = getChunkStatus(chunk);
  const [completeBadgeState, setCompleteBadgeState] = React.useState<'hidden' | 'visible' | 'fading'>('hidden');
  const prevRunningRef = React.useRef(isWorkflowRunning);
  const shouldShow = useShouldShowStatusBadge(isWorkflowRunning);

  React.useEffect(() => {
    const justCompleted =
      status === 'complete' &&
      (isWorkflowRunning || // Completed while running
        (!isWorkflowRunning && prevRunningRef.current)); // Just finished running

    if (justCompleted) {
      setCompleteBadgeState('visible');

      const fadeTimer = setTimeout(() => {
        setCompleteBadgeState('fading');
      }, COMPLETE_BADGE_FADE_START_MS);

      const removeTimer = setTimeout(() => {
        setCompleteBadgeState('hidden');
      }, COMPLETE_BADGE_REMOVE_MS);

      return () => {
        clearTimeout(fadeTimer);
        clearTimeout(removeTimer);
      };
    }

    prevRunningRef.current = isWorkflowRunning;
  }, [status, isWorkflowRunning]);

  if (!shouldShow) {
    return null;
  }

  if (completeBadgeState !== 'hidden' && status === 'complete') {
    return (
      <Badge
        variant="secondary"
        className={`gap-1 transition-all duration-1000 ease-out ${
          completeBadgeState === 'fading' ? 'opacity-0 scale-95' : 'opacity-100 scale-100'
        }`}
      >
        <CheckCircle2 className="h-3 w-3" />
        Complete
      </Badge>
    );
  }

  if (!isWorkflowRunning) {
    return null;
  }

  switch (status) {
    case 'queued':
      return (
        <Badge variant="outline" className="gap-1">
          <Clock className="h-3 w-3" />
          Queued
        </Badge>
      );
    case 'analyzing':
      return (
        <Badge variant="outline" className="gap-1 border-primary/50 text-primary">
          <Loader2 className="h-3 w-3 animate-spin" />
          Analyzing
        </Badge>
      );
    default:
      return null;
  }
}
