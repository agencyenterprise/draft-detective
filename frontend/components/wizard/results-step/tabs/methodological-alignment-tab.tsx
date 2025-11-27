import { Markdown } from '@/components/markdown';
import { ClaimSubstantiatorStateSummary, MethodologyComparisonResponse } from '@/lib/generated-api';
import { AlertCircle } from 'lucide-react';
import { TabWithLoadingStates } from './tab-with-loading-states';

interface MethodologicalAlignmentTabProps {
  results: ClaimSubstantiatorStateSummary;
  isProcessing?: boolean;
}

export function MethodologicalAlignmentTab({ results, isProcessing = false }: MethodologicalAlignmentTabProps) {
  const shouldShowLoading = isProcessing && results.config.runAlignMethods === true;

  return (
    <TabWithLoadingStates<MethodologyComparisonResponse>
      title="Methodological Alignment"
      data={results.methodologyComparison}
      isProcessing={shouldShowLoading}
      hasData={(comparison) => !!comparison?.comparison}
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
    >
      {(methodologyComparison) => {
        return (
          <div className="border-t pt-4">
            <div className="space-y-2 text-sm">
              <Markdown>{methodologyComparison.comparison}</Markdown>
            </div>
          </div>
        );
      }}
    </TabWithLoadingStates>
  );
}
