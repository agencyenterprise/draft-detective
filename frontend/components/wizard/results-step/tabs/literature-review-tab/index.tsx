'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  LiteratureReviewState,
  startWorkflowApiWorkflowsStartPost,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { AlertCircle, BookOpen } from 'lucide-react';
import * as React from 'react';
import { TabWithLoadingStates } from '../tab-with-loading-states';
import { ReferenceCard } from './reference-card';
import { filterReferences, FilterState, ReferenceFilters } from './reference-filters';

interface LiteratureReviewTabProps {
  workflowDetail: WorkflowRunDetailTyped<LiteratureReviewState> | undefined;
  projectId: string;
  readOnly?: boolean;
}

export function LiteratureReviewTab({ workflowDetail, projectId, readOnly = false }: LiteratureReviewTabProps) {
  const results = workflowDetail?.state;
  const runStatus = workflowDetail?.run.status;
  const [filters, setFilters] = React.useState<FilterState>({
    quality: 'all',
    direction: 'all',
    action: 'all',
  });

  const handleStartWorkflow = async (values: WorkflowConfigFormValues) => {
    if (!values.publicationDate) {
      throw new Error('Document publication date is required to run literature review.');
    }

    return await startWorkflowApiWorkflowsStartPost({
      body: {
        type: WorkflowRunType.LiteratureReview,
        project_id: projectId,
        document_publication_date: new Date(values.publicationDate),
        openai_api_key: values.openaiApiKey || null,
      },
    });
  };

  const literatureReview = results?.literature_review;

  return (
    <>
      <TabWithLoadingStates
        title="Literature Review"
        data={literatureReview}
        isProcessing={runStatus === WorkflowRunStatus.Running}
        hasData={(review) => !!review}
        loadingMessage={{
          title: 'Conducting literature review...',
          description: 'This may take some minutes as we analyze the bibliography and supporting documents',
        }}
        emptyMessage={{
          icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
          title: 'No literature review available',
          description: 'Run the literature review to generate recommendations and references.',
        }}
        emptyStateChildren={
          <div className="text-sm text-muted-foreground text-left max-w-md space-y-3">
            <div>
              <p className="mb-2 font-medium">Why run this?</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>Find higher-quality or missing references</li>
                <li>Identify where to cite existing bibliography items</li>
              </ul>
            </div>
          </div>
        }
        skeletonType="paragraphs"
        skeletonCount={6}
        triggerButton={
          !readOnly && (
            <StartWorkflowButton
              type={WorkflowRunType.LiteratureReview}
              projectId={projectId}
              workflow={workflowDetail?.run}
              onConfirm={handleStartWorkflow}
            />
          )
        }
      >
        {(review) => {
          if (review?.relevant_references && review.relevant_references.length > 0) {
            const filteredReferences = filterReferences(review.relevant_references, filters);

            return (
              <div className="space-y-6">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-blue-600" />
                  <span className="text-sm font-medium">AI-Generated Literature Review</span>
                  <Badge variant="secondary" className="ml-auto">
                    {review.relevant_references.length} Reference
                    {review.relevant_references.length !== 1 ? 's' : ''}
                  </Badge>
                </div>

                {review.rationale && (
                  <Card className="bg-blue-50/50 border-blue-200">
                    <CardContent>
                      <p className="text-sm leading-relaxed">
                        <strong className="text-blue-900">Overall Analysis:</strong>{' '}
                        <span className="text-blue-800">{review.rationale}</span>
                      </p>
                    </CardContent>
                  </Card>
                )}

                <ReferenceFilters
                  filters={filters}
                  onFiltersChange={setFilters}
                  totalCount={review.relevant_references.length}
                  filteredCount={filteredReferences.length}
                />

                <div className="space-y-4">
                  {filteredReferences.length === 0 ? (
                    <Card>
                      <CardContent className="flex items-center justify-center py-12">
                        <div className="text-center space-y-2">
                          <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto" />
                          <p className="text-sm text-muted-foreground">No references match the selected filters</p>
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    filteredReferences.map((reference, index) => (
                      <ReferenceCard
                        key={index}
                        reference={reference}
                        index={review.relevant_references!.indexOf(reference)}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          }

          return (
            <>
              <div className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-blue-600" />
                <span className="text-sm font-medium">AI-Generated Report</span>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Literature Review Analysis</CardTitle>
                  <CardDescription>
                    This report analyzes the document&apos;s content and bibliography to identify potential citation
                    improvements and additional references.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">No structured literature review data available.</p>
                </CardContent>
              </Card>
            </>
          );
        }}
      </TabWithLoadingStates>
    </>
  );
}
