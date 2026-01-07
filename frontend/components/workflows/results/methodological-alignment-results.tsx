import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import {
  MethodologicalAlignmentState,
  ReferenceMinimal,
  ReproducibilityCategory,
  WorkflowRunDetail,
} from '@/lib/generated-api';
import {
  AlertCircleIcon,
  CheckCircleIcon,
  ChevronDown,
  ChevronRight,
  FileTextIcon,
  SearchIcon,
  UploadIcon,
} from 'lucide-react';
import { useState } from 'react';

interface MethodologicalAlignmentResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function MethodologicalAlignmentResults({ workflowDetail }: MethodologicalAlignmentResultsProps) {
  const state = workflowDetail.state as MethodologicalAlignmentState;

  if (!state) {
    return <div className="p-4 text-center text-muted-foreground">No state available</div>;
  }

  const methodologyComparison = state.methodology_comparison;

  if (!methodologyComparison) {
    return <div className="p-4 text-center text-muted-foreground">No methodology comparison data available</div>;
  }

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
        return <CheckCircleIcon className="h-4 w-4" />;
      case ReproducibilityCategory.ReproducibleWithWebSearch:
        return <SearchIcon className="h-4 w-4" />;
      case ReproducibilityCategory.ReproducibleWithExternalUploads:
        return <UploadIcon className="h-4 w-4" />;
      case ReproducibilityCategory.NotReproducible:
        return <AlertCircleIcon className="h-4 w-4" />;
      default:
        return null;
    }
  };

  const summariesAndOutputs = [
    {
      title: 'Extracted Methodology',
      summary: methodologyComparison.extracted_methodology.summary,
      output: methodologyComparison.extracted_methodology.markdown_output,
    },
    {
      title: 'Field Methods Overview',
      summary: methodologyComparison.field_methods_overview.summary,
      output: methodologyComparison.field_methods_overview.markdown_output,
    },
    {
      title: 'Alignment with Field Practice',
      summary: methodologyComparison.alignment_with_field_practice.summary,
      output: methodologyComparison.alignment_with_field_practice.markdown_output,
    },
    {
      title: 'Methodological Rigor and Risks',
      summary: methodologyComparison.methodological_rigor_and_risks.summary,
      output: methodologyComparison.methodological_rigor_and_risks.markdown_output,
    },
    {
      title: 'Suggestions for Improvements',
      summary: methodologyComparison.suggestions_for_improvements.summary,
      output: methodologyComparison.suggestions_for_improvements.markdown_output,
    },
  ];

  return (
    <div className="space-y-3">
      {methodologyComparison.reproducibility && (
        <div className="flex items-start gap-4">
          <span className="flex items-center gap-2 bg-blue-50 p-2 rounded-md border-blue-200 text-blue-900 text-sm font-medium whitespace-nowrap">
            {getReproducibilityIcon(methodologyComparison.reproducibility.class_value)}
            {getReproducibilityLabel(methodologyComparison.reproducibility.class_value)}
          </span>
          <div className="text-sm">{methodologyComparison.reproducibility.rationale}</div>
        </div>
      )}

      <div className="w-full space-y-3">
        {summariesAndOutputs.map((summaryAndOutput) => (
          <ExpandableSection
            key={summaryAndOutput.title}
            title={summaryAndOutput.title}
            summary={summaryAndOutput.summary}
            output={summaryAndOutput.output}
          />
        ))}
      </div>

      {methodologyComparison.references && methodologyComparison.references.length > 0 && (
        <ReferencesSection references={methodologyComparison.references} />
      )}
    </div>
  );
}

interface ExpandableSectionProps {
  title: string;
  summary: string;
  output: string;
  defaultExpanded?: boolean;
}

function ExpandableSection({ title, summary, output, defaultExpanded = false }: ExpandableSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-md border">
      <div className="bg-gray-50 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h2 className="font-semibold text-base mb-1">{title}</h2>
            <p className="text-sm">{summary}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="shrink-0 text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Hide Details
              </>
            ) : (
              <>
                <ChevronRight className="h-4 w-4 mr-1" />
                View Details
              </>
            )}
          </Button>
        </div>
      </div>
      {isExpanded && (
        <div className="p-4">
          <div className="text-sm">
            <Markdown>{output}</Markdown>
          </div>
        </div>
      )}
    </div>
  );
}

interface ReferencesSectionProps {
  references: ReferenceMinimal[];
}

function ReferencesSection({ references }: ReferencesSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-md border">
      <div className="bg-gray-50 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h2 className="font-semibold text-base mb-1">References ({references.length})</h2>
            <p className="text-sm text-muted-foreground">Sources cited in this analysis</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="shrink-0 text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Hide Details
              </>
            ) : (
              <>
                <ChevronRight className="h-4 w-4 mr-1" />
                View Details
              </>
            )}
          </Button>
        </div>
      </div>
      {isExpanded && (
        <div className="p-4">
          <div className="space-y-4">
            {references.map((reference, index) => (
              <div key={index} className="flex items-start gap-3 border-b pb-2">
                <FileTextIcon className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
                <div className="flex-1 space-y-1">
                  <h3 className="font-medium text-base">
                    <a
                      href={reference.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {reference.title}
                    </a>
                  </h3>
                  <p className="text-sm text-muted-foreground">{reference.bibliography_info}</p>
                  {reference.link && (
                    <p className="text-sm">
                      <a
                        href={reference.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        {reference.link}
                      </a>
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
