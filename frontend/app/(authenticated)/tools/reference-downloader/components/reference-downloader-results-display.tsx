'use client';

import { ReferenceFetchConclusion, ReferenceFetchResult } from '@/lib/generated-api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Download, Loader2, AlertTriangle } from 'lucide-react';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import { ReferenceItem } from './reference-item';
import { Callout } from '@/components/ui/callout';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import * as React from 'react';

interface ReferenceDownloaderResultsDisplayProps {
  results: ReferenceFetchResult[];
  projectId: string | null | undefined;
  /** Display a title above the results. Defaults to "Results". Set to null to hide. */
  title?: string | null;
}

type FilterType = 'all' | 'found' | 'not-found' | 'errors';

export function ReferenceDownloaderResultsDisplay({
  results,
  projectId,
  title = 'Results',
}: ReferenceDownloaderResultsDisplayProps) {
  const [filter, setFilter] = React.useState<FilterType>('all');
  const hasDownloadedReferences = results.some((item) => item.result?.file_id != null);
  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId);

  // Calculate statistics
  const stats = React.useMemo(() => {
    const errorCount = results.filter((item) => item.error != null).length;
    const foundCount = results.filter(
      (item) => item.result?.final_conclusion === ReferenceFetchConclusion.SourceFound,
    ).length;
    const notFoundCount = results.filter(
      (item) => item.result?.final_conclusion === ReferenceFetchConclusion.SourceNotFound,
    ).length;
    const notAccessibleCount = results.filter(
      (item) => item.result?.final_conclusion === ReferenceFetchConclusion.SourceFoundButNotAccessible,
    ).length;
    return { foundCount, notFoundCount, notAccessibleCount, errorCount };
  }, [results]);

  // Filter results based on selected filter
  const filteredResults = React.useMemo(() => {
    switch (filter) {
      case 'found':
        return results.filter((item) => item.result?.final_conclusion === ReferenceFetchConclusion.SourceFound);
      case 'not-found':
        return results.filter(
          (item) =>
            item.result?.final_conclusion === ReferenceFetchConclusion.SourceNotFound ||
            item.result?.final_conclusion === ReferenceFetchConclusion.SourceFoundButNotAccessible,
        );
      case 'errors':
        return results.filter((item) => item.error != null);
      case 'all':
      default:
        return results;
    }
  }, [results, filter]);

  // Check if there are any references that couldn't be downloaded
  const failedReferenceCount = stats.notFoundCount + stats.notAccessibleCount + stats.errorCount;
  const hasFailedReferences = failedReferenceCount > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {title && <h3 className="text-lg font-semibold">{title}</h3>}
          <Badge variant="secondary">
            {filteredResults.length} Reference{filteredResults.length !== 1 ? 's' : ''}
            {filter !== 'all' && ` of ${results.length}`}
          </Badge>
          {stats.foundCount > 0 && (
            <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">
              {stats.foundCount} Found
            </Badge>
          )}
          {stats.notAccessibleCount > 0 && (
            <Badge variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-300">
              {stats.notAccessibleCount} Not Accessible
            </Badge>
          )}
          {stats.notFoundCount > 0 && (
            <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
              {stats.notFoundCount} Not Found
            </Badge>
          )}
          {stats.errorCount > 0 && (
            <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
              {stats.errorCount} Error{stats.errorCount !== 1 ? 's' : ''}
            </Badge>
          )}
        </div>
        {projectId && hasDownloadedReferences && (
          <Button onClick={downloadAll} disabled={isDownloading} variant="outline" size="sm">
            {isDownloading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Preparing download...
              </>
            ) : (
              <>
                <Download className="size-4" />
                Download {stats.foundCount} found files (.zip)
              </>
            )}
          </Button>
        )}
      </div>
      <Tabs value={filter} onValueChange={(value) => setFilter(value as FilterType)}>
        <TabsList>
          <TabsTrigger value="all">All ({results.length})</TabsTrigger>
          <TabsTrigger value="found">Found ({stats.foundCount})</TabsTrigger>
          <TabsTrigger value="not-found">Not Found ({stats.notFoundCount + stats.notAccessibleCount})</TabsTrigger>
          {stats.errorCount > 0 && <TabsTrigger value="errors">Errors ({stats.errorCount})</TabsTrigger>}
        </TabsList>
      </Tabs>
      {hasFailedReferences && filter !== 'found' && (
        <Callout variant="warning" icon={AlertTriangle} title="Manual Download Required">
          <strong>
            {failedReferenceCount} {failedReferenceCount === 1 ? 'reference' : 'references'}
          </strong>{' '}
          could not be automatically downloaded. This may be due to paywalls, bot protection, or because the references
          could not be found using web search. We recommend manually downloading these references.
        </Callout>
      )}
      <div className="space-y-3">
        {filteredResults.length > 0 ? (
          filteredResults.map((item) => {
            const originalIndex = results.indexOf(item);
            return <ReferenceItem key={originalIndex} item={item} index={originalIndex} />;
          })
        ) : (
          <div className="text-center py-8 text-muted-foreground text-sm">No references match the selected filter.</div>
        )}
      </div>
    </div>
  );
}
