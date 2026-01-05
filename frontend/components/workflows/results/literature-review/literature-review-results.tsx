'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { LiteratureReviewState, WorkflowRunDetail } from '@/lib/generated-api';
import { AlertCircle, BookOpen } from 'lucide-react';
import * as React from 'react';
import { ReferenceCard } from './reference-card';
import { filterReferences, FilterState, ReferenceFilters } from './reference-filters';

interface LiteratureReviewResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function LiteratureReviewResults({ workflowDetail }: LiteratureReviewResultsProps) {
  const results = workflowDetail.state as LiteratureReviewState | undefined;
  const [filters, setFilters] = React.useState<FilterState>({
    quality: 'all',
    direction: 'all',
    action: 'all',
  });

  const literatureReview = results?.literature_review;

  if (!literatureReview?.relevant_references || literatureReview.relevant_references.length === 0) {
    return <div className="p-4 text-center text-muted-foreground">No literature review results available</div>;
  }

  const filteredReferences = filterReferences(literatureReview.relevant_references, filters);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <BookOpen className="h-5 w-5 text-blue-600" />
        <span className="text-sm font-medium">AI-Generated Literature Review</span>
        <Badge variant="secondary" className="ml-auto">
          {literatureReview.relevant_references.length} Reference
          {literatureReview.relevant_references.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      {literatureReview.rationale && (
        <Card className="bg-blue-50/50 border-blue-200">
          <CardContent>
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
        totalCount={literatureReview.relevant_references.length}
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
              index={literatureReview.relevant_references!.indexOf(reference)}
            />
          ))
        )}
      </div>
    </div>
  );
}
