'use client';

import { LabeledValue } from '@/components/labeled-value';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { humanizeLabel } from '@/components/workflows/results/literature-review/utils';
import { StartWorkflowButton } from '@/components/workflows/start-workflow-button';
import { WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import {
  BibliographyItem,
  BibliographyItemValidation,
  startMultipleWorkflowsApiWorkflowsStartMultiplePost,
  WorkflowRunDetail,
  WorkflowRunType,
} from '@/lib/generated-api';
import { getWorkflowRunByType, isWorkflowProcessing } from '@/lib/workflow-state';
import { ChevronDownIcon, ChevronRightIcon, FileText, HelpCircle, Search } from 'lucide-react';
import * as React from 'react';
import { TabWithLoadingStates } from './tab-with-loading-states';

interface ReferencesTabProps {
  allWorkflowDetails: WorkflowRunDetail[];
  projectId: string;
  readOnly?: boolean;
}

interface ReferenceTableRowProps {
  reference: BibliographyItem;
  validation?: BibliographyItemValidation;
}

function ReferenceTableRow({ reference, validation }: ReferenceTableRowProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <>
      <TableRow>
        {/* Reference text column */}
        <TableCell className="whitespace-normal break-all w-2xl">
          <p className="text-sm">{reference.text}</p>
        </TableCell>

        {/* Related document column */}
        <TableCell className="text-xs whitespace-normal max-w-sm">
          {reference.has_associated_supporting_document ? (
            reference.file_id ? (
              <a
                href={`/api/files/download/${reference.file_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {reference.name_of_associated_supporting_document || 'Unknown'}
              </a>
            ) : (
              <span>{reference.name_of_associated_supporting_document || 'Unknown'}</span>
            )
          ) : (
            <span className="text-orange-600 font-medium">Document not provided</span>
          )}
        </TableCell>

        {/* Validation column */}
        <TableCell className="text-xs max-w-xs">
          {(() => {
            // Validation not performed
            if (!validation) {
              return <span className="text-muted-foreground/60">-</span>;
            }

            const issues =
              validation.bibliography_field_validations?.filter((field) => field.problem_type !== 'correct') || [];

            // Validation performed with issues
            if (issues.length > 0) {
              return (
                <div className="flex items-center gap-2 flex-wrap">
                  {issues.map((field, idx) => (
                    <Badge
                      key={idx}
                      variant="outline"
                      className="text-xs whitespace-nowrap bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800"
                    >
                      {humanizeLabel(field.category)}: {humanizeLabel(field.problem_type)}
                    </Badge>
                  ))}
                </div>
              );
            }

            // Validation performed with no issues
            return (
              <Badge
                variant="outline"
                className="text-xs whitespace-nowrap bg-green-100 text-green-800 border-green-300 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800"
              >
                No issues
              </Badge>
            );
          })()}
        </TableCell>

        {/* Actions column */}
        <TableCell className="text-center">
          <Button
            variant="ghost"
            size="xs"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? <ChevronDownIcon className="size-4" /> : <ChevronRightIcon className="size-4" />}
          </Button>
        </TableCell>
      </TableRow>

      {/* Expanded row with validation details */}
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={4} className="whitespace-normal bg-muted/30">
            {validation ? (
              <div className="py-3 text-sm text-gray-700 space-y-2">
                <div>
                  <h3 className="text-base font-medium">Reference validation details</h3>
                </div>

                <LabeledValue label="Updated Reference">
                  <p className="break-words">
                    {validation.updated_reference || <span className="text-muted-foreground">No proposed changes</span>}
                  </p>
                </LabeledValue>
                <LabeledValue label="Suggested Action">
                  <span className="break-words">{validation.suggested_action}</span>
                </LabeledValue>
                <LabeledValue label="URL">
                  <a
                    href={validation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline break-all inline-block max-w-full"
                  >
                    {validation.url}
                  </a>
                </LabeledValue>
                <LabeledValue label="Reasoning">
                  <span className="break-words">{validation.reasoning}</span>
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
                                <div className="break-words">
                                  <span className="font-medium">Current:</span> {field.current_value}
                                </div>
                              )}
                              {field.suggested_value && field.problem_type !== 'correct' && (
                                <div className="break-words">
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
            ) : (
              <div className="py-6 text-center text-muted-foreground">
                <p className="text-sm">Validation has not been performed yet for this reference.</p>
                <p className="text-xs mt-1">Run the validation workflow to see detailed information.</p>
              </div>
            )}
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

export function ReferencesTab({ allWorkflowDetails, projectId, readOnly = false }: ReferencesTabProps) {
  const [searchQuery, setSearchQuery] = React.useState('');

  const referenceValidation = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceValidation);
  const referenceExtraction = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceExtraction);

  const referencesResults = referenceExtraction?.state;
  const referenceValidationResults = referenceValidation?.state;

  const handleStartWorkflow = async (values: WorkflowConfigFormValues) => {
    return await startMultipleWorkflowsApiWorkflowsStartMultiplePost({
      body: {
        workflow_types: [WorkflowRunType.ReferenceValidation],
        project_id: projectId,
        openai_api_key: values.openaiApiKey,
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
      if (validation.original_reference) {
        map.set(validation.original_reference, validation);
      }
    });
    return map;
  }, [referenceValidationResults?.reference_validations]);

  // Filter references based on search query
  const filteredReferences = React.useMemo(() => {
    const references = referencesResults?.references;
    if (!references) return [];
    if (!searchQuery.trim()) return references;

    const query = searchQuery.toLowerCase();
    return references.filter((reference) => {
      // Search in reference text
      if (reference.text?.toLowerCase().includes(query)) return true;

      // Search in related document file name
      if (reference.has_associated_supporting_document) {
        if (reference.name_of_associated_supporting_document?.toLowerCase().includes(query)) return true;
      }

      return false;
    });
  }, [referencesResults?.references, searchQuery]);

  return (
    <TabWithLoadingStates
      title={`References (${filteredReferences.length}${searchQuery ? ` of ${referencesResults?.references?.length || 0}` : ''})`}
      data={referencesResults?.references}
      isProcessing={isWorkflowProcessing(referenceExtraction)}
      hasData={(references) => (references?.length || 0) > 0}
      loadingMessage={{
        title: 'Extracting references...',
        description: 'Identifying references in the document',
      }}
      emptyMessage={{
        icon: <FileText className="h-12 w-12 text-muted-foreground" />,
        title: 'No references extracted',
        description:
          "This document doesn't contain a bibliography or reference section or reference extraction was not run yet",
      }}
      skeletonType="list"
      skeletonCount={5}
      triggerButton={
        !readOnly && (
          <StartWorkflowButton
            type={WorkflowRunType.ReferenceValidation}
            projectId={projectId}
            workflow={referenceValidation?.run}
            onConfirm={handleStartWorkflow}
          />
        )
      }
    >
      {(references) => (
        <div className="space-y-4">
          {/* Search input */}
          {references.length > 0 && (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <Input
                placeholder="Search by reference text or file name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          )}

          {/* Table */}
          <div className="w-full overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reference</TableHead>
                  <TableHead>
                    <div className="flex items-center gap-1">
                      Matched file
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <HelpCircle className="size-3.5 text-muted-foreground cursor-help" />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          The supporting file that was matched to this reference item from the main document.
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </TableHead>
                  <TableHead>Validation</TableHead>
                  <TableHead className="w-8"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredReferences.map((reference, index) => (
                  <ReferenceTableRow key={index} reference={reference} validation={validationMap.get(reference.text)} />
                ))}
              </TableBody>
            </Table>
            {filteredReferences.length === 0 && searchQuery && (
              <div className="text-center py-8 text-muted-foreground">
                No references found matching &quot;{searchQuery}&quot;
              </div>
            )}
          </div>
        </div>
      )}
    </TabWithLoadingStates>
  );
}
