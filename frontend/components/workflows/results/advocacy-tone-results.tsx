'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { EmptyState } from '@/components/shared/empty-state';
import { NavigateToChunkButton } from '@/components/shared/navigate-to-chunk-button';
import {
  AdvocacyToneState,
  ChunkAdvocacyToneResult,
  DocumentChunk,
  LlmVerificationResult,
  ProjectDetailed,
  WorkflowRunType,
} from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowCancelled, isWorkflowProcessing } from '@/lib/workflow-state';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
  FileWarning,
  Loader2,
  MessageSquareWarning,
  type LucideIcon,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface AdvocacyToneResultsProps {
  project: ProjectDetailed;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
}

type CheckType = 'trigger_words' | 'advocacy_language' | 'subjective_tone';

const CHECK_CONFIG: Record<
  CheckType,
  {
    label: string;
    singularLabel: string;
    icon: LucideIcon;
    color: string;
    bgColor: string;
    ringColor: string;
  }
> = {
  trigger_words: {
    label: 'Trigger Words',
    singularLabel: 'Trigger Word',
    icon: FileWarning,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    ringColor: 'ring-amber-400',
  },
  advocacy_language: {
    label: 'Advocacy Language',
    singularLabel: 'Advocacy Issue',
    icon: MessageSquareWarning,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    ringColor: 'ring-orange-400',
  },
  subjective_tone: {
    label: 'Subjective Tone',
    singularLabel: 'Subjective Tone',
    icon: AlertTriangle,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    ringColor: 'ring-red-400',
  },
};

function CheckBadge({ type, confirmed }: { type: CheckType; confirmed: boolean }) {
  const config = CHECK_CONFIG[type];
  const Icon = config.icon;

  if (!confirmed) return null;

  return (
    <Badge variant="outline" className={cn('gap-1', config.bgColor, config.color, 'border-current')}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

interface ChunkResultCardProps {
  result: ChunkAdvocacyToneResult;
  chunkContent?: string;
  onNavigateToChunk?: () => void;
}

function ChunkResultCard({ result, chunkContent, onNavigateToChunk }: ChunkResultCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  const confirmedChecks = useMemo(() => {
    const checks: { type: CheckType; llmResult: LlmVerificationResult }[] = [];

    if (result.llm_trigger_words?.confirmed) {
      checks.push({ type: 'trigger_words', llmResult: result.llm_trigger_words });
    }
    if (result.llm_advocacy_language?.confirmed) {
      checks.push({ type: 'advocacy_language', llmResult: result.llm_advocacy_language });
    }
    if (result.llm_subjective_tone?.confirmed) {
      checks.push({ type: 'subjective_tone', llmResult: result.llm_subjective_tone });
    }

    return checks;
  }, [result]);

  // Truncate chunk content for display
  const truncatedContent = useMemo(() => {
    if (!chunkContent) return null;
    const maxLength = 200;
    if (chunkContent.length <= maxLength) return chunkContent;
    return chunkContent.slice(0, maxLength).trim() + '…';
  }, [chunkContent]);

  if (confirmedChecks.length === 0) return null;

  return (
    <Card>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
              <div className="space-y-2 flex-1">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">Chunk {result.chunk_index}</span>
                  <div className="flex gap-1.5 flex-wrap">
                    {confirmedChecks.map(({ type }) => (
                      <CheckBadge key={type} type={type} confirmed={true} />
                    ))}
                  </div>
                </div>
                {truncatedContent && <p className="text-sm text-muted-foreground line-clamp-2">{truncatedContent}</p>}
              </div>
              <ChevronDown className={cn('h-4 w-4 transition-transform flex-shrink-0 ml-2', isOpen && 'rotate-180')} />
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0 space-y-3">
            {chunkContent && (
              <div className="p-3 rounded-md bg-muted/50 border">
                <p className="text-sm text-foreground whitespace-pre-wrap">{chunkContent}</p>
                {onNavigateToChunk && <NavigateToChunkButton onClick={onNavigateToChunk} />}
              </div>
            )}
            {confirmedChecks.map(({ type, llmResult }) => {
              const config = CHECK_CONFIG[type];
              const Icon = config.icon;

              return (
                <div key={type} className={cn('p-3 rounded-md', config.bgColor)}>
                  <div className="flex items-start gap-2">
                    <Icon className={cn('h-4 w-4 mt-0.5 flex-shrink-0', config.color)} />
                    <div>
                      <p className={cn('font-medium text-sm', config.color)}>{config.label}</p>
                      <p className="text-sm text-muted-foreground mt-1">{llmResult.explanation}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

interface FilterButtonProps {
  type: CheckType;
  count: number;
  isActive: boolean;
  isFiltered: boolean;
  onClick: () => void;
}

function FilterButton({ type, count, isActive, isFiltered, onClick }: FilterButtonProps) {
  const config = CHECK_CONFIG[type];
  const Icon = config.icon;

  if (count === 0) return null;

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-md transition-all',
        config.bgColor,
        isActive && `ring-2 ${config.ringColor} shadow-md`,
        isFiltered && !isActive && 'opacity-50',
      )}
    >
      <Icon className={cn('h-4 w-4', config.color)} />
      <span className="text-sm font-medium">
        {count} {count !== 1 ? config.label : config.singularLabel}
      </span>
    </button>
  );
}

export function AdvocacyToneResults({ project, onNavigateToDocumentExplorer }: AdvocacyToneResultsProps) {
  const workflowRuns = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);

  // Use type-safe utility to get the workflow runs
  const advocacyToneRun = getWorkflowRunByType(workflowRuns, WorkflowRunType.AdvocacyTone);
  const chunkSplittingRun = getWorkflowRunByType(workflowRuns, WorkflowRunType.ChunkSplitting);

  // Get chunks for displaying content
  const chunks: DocumentChunk[] = useMemo(
    () => chunkSplittingRun?.state?.chunks ?? [],
    [chunkSplittingRun?.state?.chunks],
  );

  // Build a map of chunk_index -> content for quick lookup
  const chunkContentMap = useMemo(() => {
    const map = new Map<number, string>();
    chunks.forEach((chunk) => {
      map.set(chunk.chunk_index, chunk.content);
    });
    return map;
  }, [chunks]);

  // Not run yet
  if (!advocacyToneRun) {
    return <EmptyState message="Advocacy & Tone analysis has not been run." />;
  }

  // Still processing
  if (isWorkflowProcessing(advocacyToneRun)) {
    return (
      <EmptyState
        icon={<Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />}
        message="Analyzing Advocacy & Tone..."
        description="The Advocacy & Tone analysis is currently running. Results will appear here once complete."
      />
    );
  }

  if (isWorkflowCancelled(advocacyToneRun)) {
    return (
      <EmptyState
        icon={<Ban className="h-8 w-8 text-muted-foreground mx-auto" />}
        message="Analysis Cancelled"
        description="The Advocacy & Tone analysis was cancelled before it could complete."
      />
    );
  }

  return (
    <AdvocacyToneContent
      state={advocacyToneRun.state}
      chunkContentMap={chunkContentMap}
      onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
    />
  );
}

interface AdvocacyToneContentProps {
  state: AdvocacyToneState;
  chunkContentMap: Map<number, string>;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
}

function AdvocacyToneContent({ state, chunkContentMap, onNavigateToDocumentExplorer }: AdvocacyToneContentProps) {
  const [filterType, setFilterType] = useState<CheckType | null>(null);
  const results = useMemo(() => state.results ?? [], [state.results]);

  // Count confirmed issues by type
  const stats = useMemo(() => {
    let triggerWords = 0;
    let advocacyLanguage = 0;
    let subjectiveTone = 0;

    for (const result of results) {
      if (result.llm_trigger_words?.confirmed) triggerWords++;
      if (result.llm_advocacy_language?.confirmed) advocacyLanguage++;
      if (result.llm_subjective_tone?.confirmed) subjectiveTone++;
    }

    return { triggerWords, advocacyLanguage, subjectiveTone, total: triggerWords + advocacyLanguage + subjectiveTone };
  }, [results]);

  // Filter to only chunks with confirmed issues
  const chunksWithIssues = useMemo(
    () =>
      results.filter(
        (r) => r.llm_trigger_words?.confirmed || r.llm_advocacy_language?.confirmed || r.llm_subjective_tone?.confirmed,
      ),
    [results],
  );

  // Apply filter by issue type
  const filteredChunks = useMemo(() => {
    if (!filterType) return chunksWithIssues;
    return chunksWithIssues.filter((r) => {
      if (filterType === 'trigger_words') return r.llm_trigger_words?.confirmed;
      if (filterType === 'advocacy_language') return r.llm_advocacy_language?.confirmed;
      if (filterType === 'subjective_tone') return r.llm_subjective_tone?.confirmed;
      return true;
    });
  }, [chunksWithIssues, filterType]);

  const handleFilterClick = (type: CheckType) => {
    setFilterType((prev) => (prev === type ? null : type));
  };

  // No issues found
  if (chunksWithIssues.length === 0) {
    return (
      <EmptyState
        icon={CheckCircle2}
        message="No advocacy or tone issues detected"
        description={`${results.length} chunk${results.length !== 1 ? 's' : ''} analyzed`}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Advocacy & Tone Analysis</CardTitle>
          <CardDescription>
            Detected language issues that may require attention for objectivity and neutrality.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <FilterButton
              type="trigger_words"
              count={stats.triggerWords}
              isActive={filterType === 'trigger_words'}
              isFiltered={filterType !== null}
              onClick={() => handleFilterClick('trigger_words')}
            />
            <FilterButton
              type="advocacy_language"
              count={stats.advocacyLanguage}
              isActive={filterType === 'advocacy_language'}
              isFiltered={filterType !== null}
              onClick={() => handleFilterClick('advocacy_language')}
            />
            <FilterButton
              type="subjective_tone"
              count={stats.subjectiveTone}
              isActive={filterType === 'subjective_tone'}
              isFiltered={filterType !== null}
              onClick={() => handleFilterClick('subjective_tone')}
            />
            {filterType && (
              <button
                onClick={() => setFilterType(null)}
                className="text-xs text-muted-foreground hover:text-foreground underline"
              >
                Clear filter
              </button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results by chunk */}
      <div className="max-h-[50vh] overflow-y-auto space-y-3 pr-1">
        {filteredChunks.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">No results match the current filter.</p>
        ) : (
          filteredChunks
            .sort((a, b) => a.chunk_index - b.chunk_index)
            .map((result) => (
              <ChunkResultCard
                key={result.chunk_index}
                result={result}
                chunkContent={chunkContentMap.get(result.chunk_index)}
                onNavigateToChunk={
                  onNavigateToDocumentExplorer ? () => onNavigateToDocumentExplorer([result.chunk_index]) : undefined
                }
              />
            ))
        )}
      </div>
    </div>
  );
}
