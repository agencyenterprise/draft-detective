'use client';

import { Markdown } from '@/components/markdown';
import { NavigateToChunkButton } from '@/components/shared/navigate-to-chunk-button';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import { SeverityBadge } from '@/components/wizard/results-step/components/severity-badge';
import {
  ExtractedInferenceResult,
  InferenceValidationV2State,
  SeverityEnum,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { CheckCircleIcon, ChevronDown, ChevronRight, Scale, XCircleIcon } from 'lucide-react';
import { useState } from 'react';

interface InferenceValidationV2ResultsProps {
  workflowDetail: WorkflowRunDetail;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
}

export function InferenceValidationV2Results({
  workflowDetail,
  onNavigateToDocumentExplorer,
}: InferenceValidationV2ResultsProps) {
  const state = workflowDetail.state as InferenceValidationV2State;

  if (!state) {
    return <div className="p-4 text-center text-muted-foreground">No state available</div>;
  }

  const inferenceResults = state.inference_results;

  if (!inferenceResults || !inferenceResults.results) {
    return (
      <Callout title="No Inference Results" variant="info" icon={Scale}>
        <p className="text-sm">No inference analysis results are available yet.</p>
      </Callout>
    );
  }

  const results = inferenceResults.results;
  const invalidInferences = results.filter((r) => !r.inference_validity);

  if (results.length === 0) {
    return (
      <Callout title="No Issues Found" variant="success" icon={CheckCircleIcon}>
        <p className="text-sm">
          The inference validation analysis found no logical fallacies or unsupported conclusions in the document.
        </p>
      </Callout>
    );
  }

  // Count issues by severity
  const severityCounts = results.reduce(
    (acc, r) => {
      const severity = r.severity as SeverityEnum;
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    },
    {} as Record<SeverityEnum, number>,
  );

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <div className="flex flex-wrap items-center gap-3 p-3 bg-muted/50 rounded-lg">
        <span className="text-sm font-medium">
          Found {invalidInferences.length} inference {invalidInferences.length === 1 ? 'issue' : 'issues'}
        </span>
        <div className="flex gap-2">
          {(severityCounts[SeverityEnum.High] ?? 0) > 0 && (
            <Badge variant="destructive" className="bg-red-600">
              {severityCounts[SeverityEnum.High]} High
            </Badge>
          )}
          {(severityCounts[SeverityEnum.Medium] ?? 0) > 0 && (
            <Badge className="bg-yellow-600 text-white">{severityCounts[SeverityEnum.Medium]} Medium</Badge>
          )}
          {(severityCounts[SeverityEnum.Low] ?? 0) > 0 && (
            <Badge className="bg-blue-600 text-white">{severityCounts[SeverityEnum.Low]} Low</Badge>
          )}
        </div>
      </div>

      {/* Results list */}
      <div className="space-y-3">
        {results.map((analysis, index) => (
          <InferenceAnalysisCard
            key={`${analysis.chunk_indices?.join(',') ?? 'none'}-${index}`}
            analysis={analysis}
            index={index}
            onNavigateToDocumentExplorer={onNavigateToDocumentExplorer}
          />
        ))}
      </div>
    </div>
  );
}

interface InferenceAnalysisCardProps {
  analysis: ExtractedInferenceResult;
  index: number;
  onNavigateToDocumentExplorer?: (chunkIndices?: number[]) => void;
}

function InferenceAnalysisCard({ analysis, index, onNavigateToDocumentExplorer }: InferenceAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-lg border bg-card">
      <div className="p-4 bg-gray-50 rounded-t-lg space-y-2">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-muted-foreground">#{index + 1}</span>
            <SeverityBadge severity={analysis.severity} />
            <Badge
              variant="outline"
              className={cn(
                'text-xs',
                analysis.inference_validity
                  ? 'border-green-300 bg-green-50 text-green-700'
                  : 'border-red-300 bg-red-50 text-red-700',
              )}
            >
              {analysis.inference_validity ? (
                <CheckCircleIcon className="mr-1 h-3 w-3" />
              ) : (
                <XCircleIcon className="mr-1 h-3 w-3" />
              )}
              {analysis.inference_validity ? 'Valid' : 'Invalid'}
            </Badge>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="shrink-0 text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Hide Details
              </>
            ) : (
              <>
                <ChevronRight className="h-4 w-4 mr-1" />
                View Details
              </>
            )}
          </Button>
        </div>

        <blockquote className="border-l-2 border-muted-foreground/30 pl-3 text-sm italic text-muted-foreground">
          &ldquo;{analysis.key_sentence}&rdquo;
        </blockquote>

        {onNavigateToDocumentExplorer && analysis.chunk_indices?.length && (
          <NavigateToChunkButton
            onClick={() =>
              onNavigateToDocumentExplorer(analysis.chunk_indices?.length ? [analysis.chunk_indices[0]] : [])
            }
          />
        )}

        <p className="text-sm">{analysis.short_form_argument_analysis}</p>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-4 border-t">
          <div>
            <h4 className="text-sm font-semibold mb-2">Detailed Analysis</h4>
            <div className="text-sm prose prose-sm max-w-none">
              <Markdown>{analysis.long_form_argument_analysis}</Markdown>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold mb-2">Suggested Action</h4>
            <p className="text-sm text-muted-foreground">{analysis.suggested_action}</p>
          </div>
        </div>
      )}
    </div>
  );
}
