'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { Card, CardContent } from '@/components/ui/card';
import { ClaimSubstantiatorStateSummary } from '@/lib/generated-api';
import { format } from 'date-fns';
import { AlertCircle } from 'lucide-react';
import { TabWithLoadingStates } from '../tab-with-loading-states';

interface LiveReportsTabProps {
  results: ClaimSubstantiatorStateSummary;
  isProcessing?: boolean;
}

export function LiveReportsTab({ results, isProcessing = false }: LiveReportsTabProps) {
  const shouldShowLoading = isProcessing && results.config.runLiveReports === true;

  return (
    <TabWithLoadingStates
      title="Live Reports"
      data={results.addendumReport}
      isProcessing={shouldShowLoading}
      hasData={(addendum) => !!addendum}
      loadingMessage={{
        title: 'Generating live reports...',
        description: 'Analyzing claims and generating addendum updates',
      }}
      emptyMessage={{
        icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
        title: 'No live reports available',
        description: 'The live reports agent was not enabled for this analysis',
      }}
      emptyStateChildren={
        <div className="text-sm text-muted-foreground text-left max-w-md">
          <p className="mb-2">This may be because:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>The live reports option was not selected during upload</li>
            <li>An error occurred during the live reports process</li>
          </ul>
        </div>
      }
      skeletonType="paragraphs"
      skeletonCount={6}
    >
      {(addendum) => {
        if (!addendum) {
          return null;
        }

        const metadata = addendum.reportMetadata;

        return (
          <div className="space-y-6">
            <div>
              <LabeledValue label="Title">{metadata.title}</LabeledValue>
              <LabeledValue label="Date Generated">
                {format(new Date(metadata.dateGenerated), 'MMM dd, yyyy')}
              </LabeledValue>
              <LabeledValue label="Update Type">{metadata.updateType}</LabeledValue>
              <LabeledValue label="Sentence Summary">{metadata.sentenceSummary}</LabeledValue>
            </div>

            <Card>
              <CardContent>
                <div className="space-y-2">
                  <Markdown>{addendum.reportMarkdown.replace(/\n/g, '\n\n')}</Markdown>
                </div>
              </CardContent>
            </Card>
          </div>
        );
      }}
    </TabWithLoadingStates>
  );
}
