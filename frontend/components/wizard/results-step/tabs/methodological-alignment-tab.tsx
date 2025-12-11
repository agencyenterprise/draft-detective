import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  MethodologicalAlignmentState,
  ReferenceMinimal,
  ReproducibilityCategory,
  startWorkflowApiWorkflowsStartPost,
  WorkflowRunStatus,
  WorkflowRunType,
} from '@/lib/generated-api';
import { WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { useMutation } from '@tanstack/react-query';
import {
  AlertCircle,
  AlertCircleIcon,
  CheckCircleIcon,
  ChevronDown,
  ChevronRight,
  FileTextIcon,
  Loader2,
  PlayIcon,
  SearchIcon,
  UploadIcon,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { TabWithLoadingStates } from './tab-with-loading-states';

interface MethodologicalAlignmentTabProps {
  results: WorkflowRunDetailTyped<MethodologicalAlignmentState> | undefined;
  isProcessing?: boolean;
  projectId: string;
}

export function MethodologicalAlignmentTab({ results, projectId }: MethodologicalAlignmentTabProps) {
  const [isConfigDialogOpen, setIsConfigDialogOpen] = useState(false);

  const startWorkflowMutation = useMutation({
    mutationFn: async (values: WorkflowConfigFormValues) => {
      return await startWorkflowApiWorkflowsStartPost({
        body: {
          type: WorkflowRunType.MethodologicalAlignment,
          project_id: projectId,
          openai_api_key: values.openaiApiKey || null,
        },
      });
    },
    onSuccess: (_data, variables, context, { client }) => {
      setIsConfigDialogOpen(false);
      toast.success('Methodological alignment workflow started');
      // Invalidate queries to refresh the project data
      client.invalidateQueries({
        queryKey: ['project', projectId],
      });
      client.invalidateQueries({
        queryKey: ['workflowRun', results?.run.id],
      });
    },
    onError: (error) => {
      console.error('Failed to start methodological alignment workflow:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to start methodological alignment workflow');
    },
  });

  const handleTriggerWorkflowConfirm = (values: WorkflowConfigFormValues) => {
    startWorkflowMutation.mutate(values);
  };

  return (
    <div>
      <WorkflowConfigDialog
        isOpen={isConfigDialogOpen}
        webSearchConsent={true}
        onConfirm={handleTriggerWorkflowConfirm}
        onCancel={() => setIsConfigDialogOpen(false)}
      />

      <TabWithLoadingStates
        title="Methodological Alignment"
        data={results?.state.methodology_comparison}
        isProcessing={results?.run.status === WorkflowRunStatus.Running}
        hasData={(comparison) => !!comparison}
        loadingMessage={{
          title: 'Analyzing methodological alignment...',
          description: 'Comparing the document methodology with typical methods in the field',
        }}
        emptyMessage={{
          icon: <AlertCircle className="h-12 w-12 text-muted-foreground" />,
          title: 'No methodological alignment analysis available',
          description: 'The methodological alignment agent was not enabled for this analysis',
        }}
        emptyStateChildren={
          <div className="text-sm text-muted-foreground text-left max-w-md">
            <p className="mb-2">This may be because:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>The methodological alignment option was not selected during upload</li>
              <li>An error occurred during the methodological alignment process</li>
            </ul>
          </div>
        }
        skeletonType="paragraphs"
        skeletonCount={6}
        triggerButton={
          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsConfigDialogOpen(true)}
            disabled={startWorkflowMutation.isPending || results?.run.status === WorkflowRunStatus.Running}
          >
            <PlayIcon />
            {startWorkflowMutation.isPending ? 'Starting...' : 'Start Methodological Alignment'}
            {results?.run.status === WorkflowRunStatus.Running && <Loader2 className="animate-spin" />}
          </Button>
        }
      >
        {(methodologyComparison) => {
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
            <div className="border-t pt-4 space-y-3">
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
        }}
      </TabWithLoadingStates>
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
          <div className="space-y-2 text-sm">
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
