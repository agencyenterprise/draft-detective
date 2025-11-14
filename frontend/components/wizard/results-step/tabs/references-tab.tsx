'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  BibliographyItem,
  BibliographyItemValidationOutput,
  ClaimSubstantiatorStateSummary,
  FileDocument,
} from '@/lib/generated-api';
import { ChevronDownIcon, ChevronRightIcon, FileText } from 'lucide-react';
import * as React from 'react';
import { TabWithLoadingStates } from './tab-with-loading-states';
import { LabeledValue } from '@/components/labeled-value';
import { humanizeLabel } from './literature-review-tab/utils';

interface ReferencesTabProps {
  results: ClaimSubstantiatorStateSummary;
  isProcessing?: boolean;
}

interface ReferenceItemProps {
  reference: BibliographyItem;
  validation?: BibliographyItemValidationOutput;
  supportingFiles?: FileDocument[] | null;
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
                reference.hasAssociatedSupportingDocument
                  ? 'bg-green-100 text-green-800'
                  : 'bg-orange-100 text-orange-800'
              }`}
            >
              {reference.hasAssociatedSupportingDocument ? 'Document provided' : 'Document not provided'}
            </div>
            {reference.hasAssociatedSupportingDocument && supportingFiles && (
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                <strong>Related document:</strong>{' '}
                {supportingFiles[reference.indexOfAssociatedSupportingDocument - 1]?.fileName}
              </span>
            )}
            {validation &&
              validation.bibliographyFieldValidations &&
              validation.bibliographyFieldValidations.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  {validation.bibliographyFieldValidations
                    .filter((field) => field.problemType !== 'correct')
                    .map((field, idx) => (
                      <Badge
                        key={idx}
                        variant="outline"
                        className={`text-xs whitespace-nowrap ${'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800'}`}
                      >
                        {humanizeLabel(field.category)}: {humanizeLabel(field.problemType)}
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

          <LabeledValue label="Suggested Action">{validation.suggestedAction}</LabeledValue>
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
          {validation.bibliographyFieldValidations && validation.bibliographyFieldValidations.length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Field Validations</h4>
              <div className="space-y-2">
                {validation.bibliographyFieldValidations.map((field, idx) => {
                  const isCorrect = field.problemType === 'correct';
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
                          {isCorrect ? 'Valid' : humanizeLabel(field.problemType)}
                        </Badge>
                      </div>
                      <div className="text-xs text-gray-600 space-y-1">
                        {field.currentValue && (
                          <div>
                            <span className="font-medium">Current:</span> {field.currentValue}
                          </div>
                        )}
                        {field.suggestedValue && field.problemType !== 'correct' && (
                          <div>
                            <span className="font-medium">Suggested:</span> {field.suggestedValue}
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

export function ReferencesTab({ results, isProcessing = false }: ReferencesTabProps) {
  // Create a map of validations by reference text for quick lookup
  const validationMap = React.useMemo(() => {
    if (!results.referencesValidated) {
      return new Map<string, BibliographyItemValidationOutput>();
    }

    const map = new Map<string, BibliographyItemValidationOutput>();
    results.referencesValidated.forEach((validation) => {
      if (validation.originalReference?.text) {
        map.set(validation.originalReference.text, validation);
      }
    });
    return map;
  }, [results.referencesValidated]);

  return (
    <TabWithLoadingStates
      title="References"
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
    >
      {(references) => (
        <div className="space-y-3">
          {references.map((reference, index) => (
            <ReferenceItem
              key={index}
              reference={reference}
              validation={validationMap.get(reference.text)}
              supportingFiles={results.supportingFiles}
            />
          ))}
        </div>
      )}
    </TabWithLoadingStates>
  );
}
