import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { ReferenceFetchConclusion, ReferenceFetchResult, ReferenceFetchStatus } from '@/lib/generated-api';
import { formatReferenceError } from '@/lib/utils';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDownIcon,
  ChevronRightIcon,
  GlobeIcon,
  Loader2,
  XCircle,
} from 'lucide-react';
import * as React from 'react';

function FetchConclusionBadge({ conclusion }: { conclusion: ReferenceFetchConclusion }) {
  switch (conclusion) {
    case ReferenceFetchConclusion.SourceFound:
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-green-50 text-green-700 border-green-200">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Source Found
        </span>
      );
    case ReferenceFetchConclusion.SourceFoundButNotAccessible:
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-yellow-50 text-yellow-700 border-yellow-200">
          <AlertCircle className="w-3.5 h-3.5" />
          Found but not accessible
        </span>
      );
    case ReferenceFetchConclusion.SourceNotFound:
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-red-50 text-red-700 border-red-200">
          <XCircle className="w-3.5 h-3.5" />
          Not Found
        </span>
      );
    default:
      return null;
  }
}

export interface FetchResultsBoxProps {
  fetchResult: ReferenceFetchResult;
}

export function FetchResultsBox({ fetchResult }: FetchResultsBoxProps) {
  const [isReasoningExpanded, setIsReasoningExpanded] = React.useState(false);

  const isFetchPending = fetchResult.status === ReferenceFetchStatus.Pending;
  const isFetchError = fetchResult.status === ReferenceFetchStatus.Error || fetchResult.error != null;
  const fetchConclusion = fetchResult.result?.final_conclusion;
  const sourceUrl = fetchResult.result?.source_url;
  const reasoning = fetchResult.result?.reasoning;
  const inaccessibilityReason = fetchResult.result?.inaccessibility_reason;

  const getBoxColorClass = () => {
    if (isFetchPending) return 'bg-blue-50/80 border-blue-200';
    if (isFetchError) return 'bg-red-50/80 border-red-200';
    switch (fetchConclusion) {
      case ReferenceFetchConclusion.SourceFound:
        return 'bg-green-50/80 border-green-200';
      case ReferenceFetchConclusion.SourceFoundButNotAccessible:
        return 'bg-yellow-50/80 border-yellow-200';
      case ReferenceFetchConclusion.SourceNotFound:
        return 'bg-red-50/80 border-red-200';
      default:
        return 'bg-gray-50/80 border-gray-200';
    }
  };

  return (
    <div className={`rounded border py-1 px-2 ${getBoxColorClass()}`}>
      {/* Header with title and badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GlobeIcon className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-gray-700">Fetch results</span>
          {isFetchPending ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-blue-100 text-blue-700 border-blue-300">
              <Loader2 className="w-3 h-3 animate-spin" />
              Fetching...
            </span>
          ) : isFetchError ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-xs font-medium rounded-full border bg-red-100 text-red-700 border-red-300">
              <AlertTriangle className="w-3 h-3" />
              Error
            </span>
          ) : (
            fetchConclusion && <FetchConclusionBadge conclusion={fetchConclusion} />
          )}
        </div>
        {reasoning && (
          <Button variant="outline" size="xs" onClick={() => setIsReasoningExpanded(!isReasoningExpanded)}>
            {isReasoningExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
            {isReasoningExpanded ? 'Hide fetch agent reasoning' : 'Show fetch agent reasoning'}
          </Button>
        )}
      </div>

      {/* Fetch error message */}
      {isFetchError && <div className="text-sm text-red-700">{formatReferenceError(fetchResult.error)}</div>}

      {/* Inaccessibility reason */}
      {inaccessibilityReason && <div className="text-xs text-yellow-700 my-1">{inaccessibilityReason}</div>}

      {/* Fetching message */}
      {isFetchPending && (
        <div className="text-xs text-muted-foreground italic my-1">Please wait while we fetch this reference...</div>
      )}

      {/* Agent reasoning (expandable) */}
      {isReasoningExpanded && (
        <div className="space-y-2 pt-2 mt-2 border-t border-current/10 text-sm leading-relaxed">
          {sourceUrl && (
            <LabeledValue label="Source URL">
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline break-all"
              >
                {sourceUrl}
              </a>
            </LabeledValue>
          )}
          <LabeledValue label="Reasoning">
            <Markdown>{reasoning}</Markdown>
          </LabeledValue>
        </div>
      )}
    </div>
  );
}
