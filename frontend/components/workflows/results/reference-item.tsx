'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FileDownloadLink } from '@/components/ui/file-download-link';
import { ReferenceFetchConclusion, ReferenceFetchResult, ReferenceFetchStatus } from '@/lib/generated-api';
import { formatReferenceError } from '@/lib/utils';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDownIcon,
  ChevronRightIcon,
  Download,
  Loader2,
  XCircle,
} from 'lucide-react';
import * as React from 'react';

interface ReferenceItemProps {
  item: ReferenceFetchResult;
  /** Display index for UI numbering (optional, uses array position) */
  displayIndex?: number;
}

function getConclusionBadge(conclusion: ReferenceFetchConclusion) {
  switch (conclusion) {
    case ReferenceFetchConclusion.SourceFound:
      return (
        <Badge
          variant="outline"
          className="bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300 border-green-300 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800"
        >
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Source Found
        </Badge>
      );
    case ReferenceFetchConclusion.SourceFoundButNotAccessible:
      return (
        <Badge
          variant="outline"
          className="bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300 border-yellow-300 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800"
        >
          <AlertCircle className="h-3 w-3 mr-1" />
          Found but not accessible
        </Badge>
      );
    case ReferenceFetchConclusion.SourceNotFound:
      return (
        <Badge
          variant="outline"
          className="bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 border-red-300 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800"
        >
          <XCircle className="h-3 w-3 mr-1" />
          Not Found
        </Badge>
      );
    default:
      return null;
  }
}

function getErrorBadge() {
  return (
    <Badge
      variant="outline"
      className="bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 border-red-300 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800"
    >
      <AlertTriangle className="h-3 w-3 mr-1" />
      Error
    </Badge>
  );
}

function getPendingBadge() {
  return (
    <Badge
      variant="outline"
      className="bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-300 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800"
    >
      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
      Fetching...
    </Badge>
  );
}

export function ReferenceItem({ item, displayIndex }: ReferenceItemProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const isPending = item.status === ReferenceFetchStatus.Pending;
  const isError = item.status === ReferenceFetchStatus.Error || item.error != null;
  const result = item.result;

  return (
    <div className="border rounded-lg p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            {displayIndex !== undefined && (
              <span className="text-sm font-medium text-muted-foreground">#{displayIndex + 1}</span>
            )}
            {isPending
              ? getPendingBadge()
              : isError
                ? getErrorBadge()
                : result && getConclusionBadge(result.final_conclusion)}
            {!isPending &&
              (result?.file_id ? (
                <Badge
                  variant="outline"
                  className="bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-300 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800"
                >
                  <Download className="h-3 w-3 mr-1" />
                  Download Available
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-muted text-muted-foreground border-border">
                  Download not available
                </Badge>
              ))}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {result?.file_id && (
            <Button variant="outline" size="xs" asChild className="text-muted-foreground hover:text-foreground">
              <FileDownloadLink fileId={result.file_id}>
                <Download className="size-4 mr-1" />
                Download
              </FileDownloadLink>
            </Button>
          )}
        </div>
      </div>

      <div className="text-sm">
        <Markdown>{result?.reference_details || item.input_reference}</Markdown>
      </div>

      {isPending && <div className="text-sm text-muted-foreground">Searching for this reference...</div>}

      {result?.source_url && (
        <div>
          <p>
            <span className="text-sm font-medium text-muted-foreground">Source URL: </span>
            <a
              href={result.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline break-all"
            >
              {result.source_url}
            </a>
          </p>
        </div>
      )}

      {result?.inaccessibility_reason && (
        <div className="text-sm text-yellow-700 dark:text-yellow-400">{result.inaccessibility_reason}</div>
      )}

      {isError && (
        <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/10 p-2 rounded">
          {formatReferenceError(item.error)}
        </div>
      )}

      {result && (
        <>
          <div className="flex items-center justify-end">
            <Button
              variant="ghost"
              size="xs"
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-muted-foreground hover:text-foreground"
            >
              {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
              {isExpanded ? 'Hide agent reasoning' : 'Show agent reasoning'}
            </Button>
          </div>

          {isExpanded && (
            <div className="space-y-2 pt-2 border-t text-sm">
              <LabeledValue label="Reasoning">
                <Markdown>{result.reasoning || ''}</Markdown>
              </LabeledValue>
            </div>
          )}
        </>
      )}
    </div>
  );
}
