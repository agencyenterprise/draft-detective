'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { Callout } from '@/components/ui/callout';
import { Card, CardContent } from '@/components/ui/card';
import { ClaimSubstantiationWorkflowDetail } from '@/lib/generated-api';
import { format } from 'date-fns';
import { AlertCircle, FileText } from 'lucide-react';
import { TabWithLoadingStates } from '../tab-with-loading-states';
import { PublicationDateLabel } from '../../components/publication-date-label';

interface LiveReportsTabProps {
  workflowDetail: ClaimSubstantiationWorkflowDetail | undefined;
  isProcessing?: boolean;
}

export function LiveReportsTab({ workflowDetail, isProcessing = false }: LiveReportsTabProps) {
  const results = workflowDetail?.state;
  const shouldShowLoading = isProcessing && results?.config.runLiveReports === true;

  if (!results) {
    return null;
  }

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
        const metadata = addendum.reportMetadata;

        return (
          <div className="space-y-4">
            <div className="space-y-1">
              <LabeledValue label="Title">{metadata.title}</LabeledValue>
              <LabeledValue label="Document publication date">
                <PublicationDateLabel results={results} />
              </LabeledValue>
              <LabeledValue label="Live report generation date">
                {format(new Date(metadata.dateGenerated), 'MMM dd, yyyy')}
              </LabeledValue>
              <LabeledValue label="Update Type">{metadata.updateType}</LabeledValue>
            </div>

            <Callout title="Sentence Summary" variant="info" icon={FileText}>
              <Markdown>{metadata.sentenceSummary}</Markdown>
            </Callout>

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
