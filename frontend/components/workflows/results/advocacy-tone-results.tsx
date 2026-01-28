'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { DocumentChunk, ProjectDetailed, WorkflowRunType } from '@/lib/generated-api';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { AlertCircle, AlertTriangle, ChevronDown, ExternalLink, FileWarning, MessageSquareWarning } from 'lucide-react';
import * as React from 'react';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface AdvocacyToneResultsProps {
  project: ProjectDetailed;
  onNavigateToDocumentExplorer?: (chunkIndex?: number) => void;
}

type CheckType = 'trigger_words' | 'advocacy_language' | 'subjective_tone';

interface LLMVerificationResult {
  confirmed: boolean;
  explanation: string;
  word_positions: number[];
}

interface ProceduralFlags {
  trigger_words: boolean;
  advocacy_language: boolean;
  subjective_tone: boolean;
}

interface ChunkAdvocacyToneResult {
  chunk_index: number;
  procedural_flags: ProceduralFlags;
  llm_trigger_words?: LLMVerificationResult | null;
  llm_advocacy_language?: LLMVerificationResult | null;
  llm_subjective_tone?: LLMVerificationResult | null;
}

interface AdvocacyToneState {
  type: string;
  results: ChunkAdvocacyToneResult[];
  errors?: unknown[];
}

const CHECK_CONFIG: Record<
  CheckType,
  {
    label: string;
    icon: typeof AlertTriangle;
    color: string;
    bgColor: string;
  }
> = {
  trigger_words: {
    label: 'Trigger Words',
    icon: FileWarning,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
  },
  advocacy_language: {
    label: 'Advocacy Language',
    icon: MessageSquareWarning,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
  subjective_tone: {
    label: 'Subjective Tone',
    icon: AlertTriangle,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
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
    const checks: { type: CheckType; llmResult: LLMVerificationResult }[] = [];

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
      <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => setIsOpen(!isOpen)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-sm font-medium">Chunk {result.chunk_index}</CardTitle>
            <div className="flex gap-1.5 flex-wrap">
              {confirmedChecks.map(({ type }) => (
                <CheckBadge key={type} type={type} confirmed={true} />
              ))}
            </div>
          </div>
          <ChevronDown className={cn('h-4 w-4 transition-transform flex-shrink-0', isOpen && 'rotate-180')} />
        </div>
        {truncatedContent && <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{truncatedContent}</p>}
      </CardHeader>
      {isOpen && (
        <CardContent className="pt-0 space-y-3">
          {chunkContent && (
            <div className="p-3 rounded-md bg-muted/50 border">
              <p className="text-sm text-foreground whitespace-pre-wrap">{chunkContent}</p>
              {onNavigateToChunk && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 gap-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    onNavigateToChunk();
                  }}
                >
                  <ExternalLink className="h-3 w-3" />
                  View in Document Explorer
                </Button>
              )}
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
      )}
    </Card>
  );
}

export function AdvocacyToneResults({ project, onNavigateToDocumentExplorer }: AdvocacyToneResultsProps) {
  const workflowDetails = useMemo(() => project.workflow_runs ?? [], [project.workflow_runs]);
  const [filterType, setFilterType] = useState<CheckType | null>(null);

  // Get the advocacy tone workflow - use type assertion since types may not be generated yet
  const advocacyToneRun = workflowDetails.find((w) => w.run.type === ('advocacy_tone' as WorkflowRunType));

  // Get chunks from chunk splitting workflow for displaying content
  const chunkSplittingRun = getWorkflowRunByType(workflowDetails, WorkflowRunType.ChunkSplitting);
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

  const results = useMemo(() => {
    const state = advocacyToneRun?.state as AdvocacyToneState | undefined;
    return state?.results ?? [];
  }, [advocacyToneRun?.state]);

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

  if (!advocacyToneRun) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground">Advocacy & Tone analysis has not been run.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (chunksWithIssues.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center space-y-2">
            <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mx-auto">
              <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-sm font-medium text-green-600">No advocacy or tone issues detected</p>
            <p className="text-xs text-muted-foreground">
              {results.length} chunk{results.length !== 1 ? 's' : ''} analyzed
            </p>
          </div>
        </CardContent>
      </Card>
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
            {stats.triggerWords > 0 && (
              <button
                onClick={() => handleFilterClick('trigger_words')}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-md transition-all',
                  CHECK_CONFIG.trigger_words.bgColor,
                  filterType === 'trigger_words' && 'ring-2 ring-amber-400 shadow-md',
                  filterType && filterType !== 'trigger_words' && 'opacity-50',
                )}
              >
                <FileWarning className={cn('h-4 w-4', CHECK_CONFIG.trigger_words.color)} />
                <span className="text-sm font-medium">
                  {stats.triggerWords} Trigger Word{stats.triggerWords !== 1 ? 's' : ''}
                </span>
              </button>
            )}
            {stats.advocacyLanguage > 0 && (
              <button
                onClick={() => handleFilterClick('advocacy_language')}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-md transition-all',
                  CHECK_CONFIG.advocacy_language.bgColor,
                  filterType === 'advocacy_language' && 'ring-2 ring-orange-400 shadow-md',
                  filterType && filterType !== 'advocacy_language' && 'opacity-50',
                )}
              >
                <MessageSquareWarning className={cn('h-4 w-4', CHECK_CONFIG.advocacy_language.color)} />
                <span className="text-sm font-medium">
                  {stats.advocacyLanguage} Advocacy Issue{stats.advocacyLanguage !== 1 ? 's' : ''}
                </span>
              </button>
            )}
            {stats.subjectiveTone > 0 && (
              <button
                onClick={() => handleFilterClick('subjective_tone')}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-md transition-all',
                  CHECK_CONFIG.subjective_tone.bgColor,
                  filterType === 'subjective_tone' && 'ring-2 ring-red-400 shadow-md',
                  filterType && filterType !== 'subjective_tone' && 'opacity-50',
                )}
              >
                <AlertTriangle className={cn('h-4 w-4', CHECK_CONFIG.subjective_tone.color)} />
                <span className="text-sm font-medium">
                  {stats.subjectiveTone} Subjective Tone{stats.subjectiveTone !== 1 ? 's' : ''}
                </span>
              </button>
            )}
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
                  onNavigateToDocumentExplorer ? () => onNavigateToDocumentExplorer(result.chunk_index) : undefined
                }
              />
            ))
        )}
      </div>
    </div>
  );
}
