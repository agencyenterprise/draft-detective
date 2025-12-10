'use client';

import { ClaimSubstantiationWorkflowDetail } from '@/lib/generated-api';
import * as React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, BookOpen } from 'lucide-react';
import { TabWithLoadingStates } from '../tab-with-loading-states';
import { ReferenceCard } from './reference-card';
import { Badge } from '@/components/ui/badge';
import { ReferenceFilters, FilterState, filterReferences } from './reference-filters';

interface LiteratureReviewTabProps {
  workflowDetail: ClaimSubstantiationWorkflowDetail | undefined;
  isProcessing?: boolean;
}

export function LiteratureReviewTab({ workflowDetail, isProcessing = false }: LiteratureReviewTabProps) {
  const results = workflowDetail?.state;
  const [filters, setFilters] = React.useState<FilterState>({
    quality: 'all',
    direction: 'all',
    action: 'all',
  });

  const shouldShowLoading = isProcessing && results?.config.runLiteratureReview === true;

  if (!results) {
    return null;
  }

  return (
    <TabWithLoadingStates
      title="Literature Review"
      data={results.literatureReview}
      isProcessing={shouldShowLoading}
      hasData={(review) => !!review}
      loadingMessage={{
        title: 'Conducting literature review...',
        description: 'This may take some minutes as we analyze the bibliography and supporting documents',
      }}
      emptyMessage={{
        icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
        title: 'No literature review available',
        description: 'The literature review agent was not enabled for this analysis',
      }}
      emptyStateChildren={
        <div className="text-sm text-muted-foreground text-left max-w-md">
          <p className="mb-2">This may be because:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>The literature review option was not selected during upload</li>
            <li>An error occurred during the literature review process</li>
          </ul>
        </div>
      }
      skeletonType="paragraphs"
      skeletonCount={6}
    >
      {(literatureReview) => {
        if (literatureReview && literatureReview.relevantReferences && literatureReview.relevantReferences.length > 0) {
          const filteredReferences = filterReferences(literatureReview.relevantReferences, filters);

          return (
            <div className="space-y-6">
              <div className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-blue-600" />
                <span className="text-sm font-medium">AI-Generated Literature Review</span>
                <Badge variant="secondary" className="ml-auto">
                  {literatureReview.relevantReferences.length} Reference
                  {literatureReview.relevantReferences.length !== 1 ? 's' : ''}
                </Badge>
              </div>

              {literatureReview.rationale && (
                <Card className="bg-blue-50/50 border-blue-200">
                  <CardContent className="pt-6">
                    <p className="text-sm leading-relaxed">
                      <strong className="text-blue-900">Overall Analysis:</strong>{' '}
                      <span className="text-blue-800">{literatureReview.rationale}</span>
                    </p>
                  </CardContent>
                </Card>
              )}

              <ReferenceFilters
                filters={filters}
                onFiltersChange={setFilters}
                totalCount={literatureReview.relevantReferences.length}
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
                      index={literatureReview.relevantReferences!.indexOf(reference)}
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
  );
}
