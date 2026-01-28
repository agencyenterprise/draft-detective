'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/shared';
import {
  ResultsExtractionState,
  ResultSection,
  ResultType,
  ReproducibilityCategory,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import {
  AlertCircleIcon,
  CheckCircleIcon,
  FileTextIcon,
  SearchIcon,
  UploadIcon,
  BarChart3,
  Table,
  Sigma,
  Code,
  FileQuestion,
} from 'lucide-react';
import * as React from 'react';

interface ResultsExtractorResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function ResultsExtractorResults({ workflowDetail }: ResultsExtractorResultsProps) {
  const results = workflowDetail.state as ResultsExtractionState | undefined;

  const resultSections = React.useMemo(
    () => results?.results?.result_sections ?? [],
    [results?.results?.result_sections],
  );

  // Calculate statistics
  const reproducibilityCounts = React.useMemo(() => {
    const counts = {
      [ReproducibilityCategory.FullyReproducible]: 0,
      [ReproducibilityCategory.ReproducibleWithWebSearch]: 0,
      [ReproducibilityCategory.ReproducibleWithExternalUploads]: 0,
      [ReproducibilityCategory.NotReproducible]: 0,
    };
    resultSections.forEach((section) => {
      counts[section.reproducibility] = (counts[section.reproducibility] || 0) + 1;
    });
    return counts;
  }, [resultSections]);

  if (resultSections.length === 0) {
    return <EmptyState message="No results extracted yet." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 flex-wrap">
        <BarChart3 className="h-5 w-5 text-blue-600" />
        <span className="text-sm font-medium">Extracted Results</span>
        <Badge variant="secondary" className="ml-auto">
          {resultSections.length} Result{resultSections.length !== 1 ? 's' : ''}
        </Badge>
        {reproducibilityCounts[ReproducibilityCategory.FullyReproducible] > 0 && (
          <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">
            {reproducibilityCounts[ReproducibilityCategory.FullyReproducible]} Fully Reproducible
          </Badge>
        )}
        {reproducibilityCounts[ReproducibilityCategory.ReproducibleWithWebSearch] > 0 && (
          <Badge variant="outline" className="bg-blue-100 text-blue-800 border-blue-300">
            {reproducibilityCounts[ReproducibilityCategory.ReproducibleWithWebSearch]} With Web Search
          </Badge>
        )}
        {reproducibilityCounts[ReproducibilityCategory.ReproducibleWithExternalUploads] > 0 && (
          <Badge variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-300">
            {reproducibilityCounts[ReproducibilityCategory.ReproducibleWithExternalUploads]} With External Uploads
          </Badge>
        )}
        {reproducibilityCounts[ReproducibilityCategory.NotReproducible] > 0 && (
          <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
            {reproducibilityCounts[ReproducibilityCategory.NotReproducible]} Not Reproducible
          </Badge>
        )}
      </div>

      <div className="space-y-4">
        {resultSections.map((section: ResultSection, index: number) => (
          <ResultSectionCard key={index} section={section} />
        ))}
      </div>
    </div>
  );
}

interface ResultSectionCardProps {
  section: ResultSection;
}

function ResultSectionCard({ section }: ResultSectionCardProps) {
  const getReproducibilityLabel = (category: ReproducibilityCategory) => {
    switch (category) {
      case ReproducibilityCategory.FullyReproducible:
        return 'Fully Reproducible';
      case ReproducibilityCategory.ReproducibleWithWebSearch:
        return 'Reproducible with Web Search';
      case ReproducibilityCategory.ReproducibleWithExternalUploads:
        return 'Reproducible with External Uploads';
      case ReproducibilityCategory.NotReproducible:
        return 'Not Reproducible';
      default:
        return 'Unknown';
    }
  };

  const getReproducibilityIcon = (category: ReproducibilityCategory) => {
    switch (category) {
      case ReproducibilityCategory.FullyReproducible:
        return <CheckCircleIcon className="h-4 w-4 text-green-600" />;
      case ReproducibilityCategory.ReproducibleWithWebSearch:
        return <SearchIcon className="h-4 w-4 text-blue-600" />;
      case ReproducibilityCategory.ReproducibleWithExternalUploads:
        return <UploadIcon className="h-4 w-4 text-yellow-600" />;
      case ReproducibilityCategory.NotReproducible:
        return <AlertCircleIcon className="h-4 w-4 text-red-600" />;
      default:
        return null;
    }
  };

  const getResultTypeIcon = (type: ResultType) => {
    switch (type) {
      case ResultType.Figure:
        return <BarChart3 className="h-4 w-4" />;
      case ResultType.Table:
        return <Table className="h-4 w-4" />;
      case ResultType.Equation:
        return <Sigma className="h-4 w-4" />;
      case ResultType.Algorithm:
        return <Code className="h-4 w-4" />;
      case ResultType.Text:
        return <FileTextIcon className="h-4 w-4" />;
      case ResultType.Other:
        return <FileQuestion className="h-4 w-4" />;
      default:
        return <FileTextIcon className="h-4 w-4" />;
    }
  };

  const getResultTypeLabel = (type: ResultType) => {
    switch (type) {
      case ResultType.Figure:
        return 'Figure';
      case ResultType.Table:
        return 'Table';
      case ResultType.Equation:
        return 'Equation';
      case ResultType.Algorithm:
        return 'Algorithm';
      case ResultType.Text:
        return 'Text';
      case ResultType.Other:
        return 'Other';
      default:
        return 'Unknown';
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {getResultTypeIcon(section.result_type)}
              <CardTitle className="text-base">{section.title}</CardTitle>
              <Badge variant="outline" className="ml-2">
                {getResultTypeLabel(section.result_type)}
              </Badge>
            </div>
            <CardDescription className="text-xs text-muted-foreground">Location: {section.location}</CardDescription>
          </div>
          <div className="flex items-center gap-2 bg-muted/50 px-3 py-1.5 rounded-md border">
            {getReproducibilityIcon(section.reproducibility)}
            <span className="text-sm font-medium">{getReproducibilityLabel(section.reproducibility)}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <h4 className="text-sm font-semibold mb-2">Description</h4>
          <p className="text-sm text-muted-foreground leading-relaxed">{section.description}</p>
        </div>
        <div>
          <h4 className="text-sm font-semibold mb-2">Reproducibility Assessment</h4>
          <p className="text-sm text-muted-foreground leading-relaxed">{section.reproducibility_rationale}</p>
        </div>
      </CardContent>
    </Card>
  );
}
