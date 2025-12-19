'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Markdown } from '@/components/markdown';
import { Callout } from '@/components/ui/callout';
import { Card, CardContent } from '@/components/ui/card';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  LiveReportsState,
  startWorkflowApiWorkflowsStartPost,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { format } from 'date-fns';
import { AlertCircle, FileText } from 'lucide-react';
import { PublicationDateLabel } from '../../components/publication-date-label';
import { TabWithLoadingStates } from '../tab-with-loading-states';

interface LiveReportsTabProps {
  workflowDetail: WorkflowRunDetailTyped<LiveReportsState> | undefined;
  projectId: string;
  readOnly?: boolean;
}

export function LiveReportsTab({ workflowDetail, projectId, readOnly = false }: LiveReportsTabProps) {
  const results = workflowDetail?.state;
  const isProcessing = workflowDetail?.run.status === WorkflowRunStatus.Running;

  const handleStartWorkflow = async (values: WorkflowConfigFormValues) => {
    return await startWorkflowApiWorkflowsStartPost({
      body: {
        type: WorkflowRunType.LiveReports,
        project_id: projectId,
        document_publication_date: new Date(values.publicationDate),
        openai_api_key: values.openaiApiKey || null,
      },
    });
  };

  return (
    <TabWithLoadingStates
      title="Live Reports"
      data={results?.addendum_report}
      isProcessing={isProcessing}
      hasData={(addendum) => !!addendum}
      loadingMessage={{
        title: 'Generating live reports...',
        description: 'Analyzing claims and generating addendum updates',
      }}
      emptyMessage={{
        icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
        title: 'No live reports available',
        description: 'Run the live reports workflow to generate an addendum.',
      }}
      emptyStateChildren={
        <div className="text-sm text-muted-foreground text-left max-w-md">
          <p className="mb-2 font-medium">Why run this?</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Check claims against literature published after the document date</li>
            <li>Generate an addendum with recommended updates</li>
          </ul>
        </div>
      }
      skeletonType="paragraphs"
      skeletonCount={6}
      triggerButton={
        !readOnly && (
          <StartWorkflowButton
            type={WorkflowRunType.LiveReports}
            projectId={projectId}
            workflow={workflowDetail?.run}
            onConfirm={handleStartWorkflow}
          />
        )
      }
    >
      {(addendum) => {
        const metadata = addendum.report_metadata;

        return (
          <div className="space-y-4">
            <div className="space-y-1">
              <LabeledValue label="Title">{metadata.title}</LabeledValue>
              {workflowDetail && (
                <LabeledValue label="Document publication date">
                  <PublicationDateLabel results={[workflowDetail]} />
                </LabeledValue>
              )}
              <LabeledValue label="Live report generation date">
                {format(new Date(metadata.date_generated), 'MMM dd, yyyy')}
              </LabeledValue>
              <LabeledValue label="Update Type">{metadata.update_type}</LabeledValue>
            </div>

            <Callout title="Sentence Summary" variant="info" icon={FileText}>
              <Markdown>{metadata.sentence_summary}</Markdown>
            </Callout>

            <Card>
              <CardContent>
                <div className="space-y-2">
                  <Markdown>{addendum.report_markdown.replace(/\n/g, '\n\n')}</Markdown>
                </div>
              </CardContent>
            </Card>
          </div>
        );
      }}
    </TabWithLoadingStates>
  );
}
