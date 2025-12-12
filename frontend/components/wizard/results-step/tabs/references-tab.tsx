'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  BibliographyItem,
  BibliographyItemValidation,
  ClaimSubstantiatorStateSummary,
  FileDocumentOutput,
  ReferenceValidationState,
  startWorkflowApiWorkflowsStartPost,
  WorkflowRunType,
} from '@/lib/generated-api';
import { WorkflowRunDetailTyped } from '@/lib/workflow-state';
import { ChevronDownIcon, ChevronRightIcon, FileText } from 'lucide-react';
import * as React from 'react';
import { humanizeLabel } from './literature-review-tab/utils';
import { TabWithLoadingStates } from './tab-with-loading-states';

interface ReferencesTabProps {
  workflowDetail: WorkflowRunDetailTyped<ClaimSubstantiatorStateSummary> | undefined;
  referenceValidationDetail: WorkflowRunDetailTyped<ReferenceValidationState> | undefined;
  projectId: string;
  isProcessing?: boolean;
  readOnly?: boolean;
}

interface ReferenceItemProps {
  reference: BibliographyItem;
  validation?: BibliographyItemValidation;
  supportingFiles?: FileDocumentOutput[] | null;
}

function ReferenceItem({ reference, validation, supportingFiles }: ReferenceItemProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <div className="border rounded-lg p-4">
      <div className="space-y-2">
        <p className="text-sm flex-1">{reference.text}</p>
        <div className="flex justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`px-2 py-1 rounded text-xs ${
                reference.has_associated_supporting_document
                  ? 'bg-green-100 text-green-800'
                  : 'bg-orange-100 text-orange-800'
              }`}
            >
              {reference.has_associated_supporting_document ? 'Document provided' : 'Document not provided'}
            </div>
            {reference.has_associated_supporting_document && supportingFiles && (
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                <strong>Related document:</strong>{' '}
                {supportingFiles[reference.index_of_associated_supporting_document - 1]?.file_name}
              </span>
            )}
            {validation &&
              validation.bibliography_field_validations &&
              validation.bibliography_field_validations.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  {validation.bibliography_field_validations
                    .filter((field) => field.problem_type !== 'correct')
                    .map((field, idx) => (
                      <Badge
                        key={idx}
                        variant="outline"
                        className={`text-xs whitespace-nowrap ${'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800'}`}
                      >
                        {humanizeLabel(field.category)}: {humanizeLabel(field.problem_type)}
                      </Badge>
                    ))}
                </div>
              )}
          </div>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
            {isExpanded ? 'Hide details' : 'Show more details'}
          </Button>
        </div>
      </div>
      {isExpanded && validation && (
        <div className="mt-3 text-sm text-gray-700 space-y-2">
          <div>
            <h3 className="text-base font-medium">Reference validation details</h3>
          </div>

          <LabeledValue label="Suggested Action">{validation.suggested_action}</LabeledValue>
          <LabeledValue label="URL">
            <a
              href={validation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline break-all"
            >
              {validation.url}
            </a>
          </LabeledValue>
          {validation.bibliography_field_validations && validation.bibliography_field_validations.length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Field Validations</h4>
              <div className="space-y-2">
                {validation.bibliography_field_validations.map((field, idx) => {
                  const isCorrect = field.problem_type === 'correct';
                  return (
                    <div key={idx} className="pl-4 border-l-2 border-gray-200">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-xs uppercase">{field.category}</span>
                        <Badge
                          variant={isCorrect ? 'success' : 'outline'}
                          className={`text-xs ${
                            isCorrect
                              ? ''
                              : 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800'
                          }`}
                        >
                          {isCorrect ? 'Valid' : humanizeLabel(field.problem_type)}
                        </Badge>
                      </div>
                      <div className="text-xs text-gray-600 space-y-1">
                        {field.current_value && (
                          <div>
                            <span className="font-medium">Current:</span> {field.current_value}
                          </div>
                        )}
                        {field.suggested_value && field.problem_type !== 'correct' && (
                          <div>
                            <span className="font-medium">Suggested:</span> {field.suggested_value}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ReferencesTab({
  workflowDetail,
  referenceValidationDetail,
  projectId,
  isProcessing = false,
  readOnly = false,
}: ReferencesTabProps) {
  const results = workflowDetail?.state;
  const referenceValidationResults = referenceValidationDetail?.state;

  const handleStartWorkflow = async (values: WorkflowConfigFormValues) => {
    return await startWorkflowApiWorkflowsStartPost({
      body: {
        type: WorkflowRunType.ReferenceValidation,
        project_id: projectId,
        openai_api_key: values.openaiApiKey || null,
      },
    });
  };

  // Create a map of validations by reference text for quick lookup
  const validationMap = React.useMemo(() => {
    if (!referenceValidationResults?.reference_validations) {
      return new Map<string, BibliographyItemValidation>();
    }

    const map = new Map<string, BibliographyItemValidation>();
    referenceValidationResults.reference_validations.forEach((validation) => {
      if (validation.original_reference?.text) {
        map.set(validation.original_reference.text, validation);
      }
    });
    return map;
  }, [referenceValidationResults?.reference_validations]);

  if (!results) {
    return null;
  }

  return (
    <TabWithLoadingStates
      title={`References (${results.references?.length || 0})`}
      data={results.references}
      isProcessing={isProcessing}
      hasData={(references) => (references?.length || 0) > 0}
      loadingMessage={{
        title: 'Extracting bibliography...',
        description: 'Identifying references in the document',
      }}
      emptyMessage={{
        icon: <FileText className="h-12 w-12 text-muted-foreground" />,
        title: 'No references found',
        description: "This document doesn't contain a bibliography or reference section",
      }}
      skeletonType="list"
      skeletonCount={5}
      triggerButton={
        !readOnly && (
          <StartWorkflowButton
            type={WorkflowRunType.ReferenceValidation}
            projectId={projectId}
            workflow={referenceValidationDetail?.run}
            onConfirm={handleStartWorkflow}
          />
        )
      }
    >
      {(references) => (
        <div className="space-y-3">
          {references.map((reference, index) => (
            <ReferenceItem
              key={index}
              reference={reference}
              validation={validationMap.get(reference.text)}
              supportingFiles={results.supporting_files}
            />
          ))}
        </div>
      )}
    </TabWithLoadingStates>
  );
}
