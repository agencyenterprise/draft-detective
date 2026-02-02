'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { WorkflowRunType, WorkflowTypeDescription } from '@/lib/generated-api';
import { WorkflowTypeCheckbox } from './workflow-type-checkbox';
import { Button } from '../ui/button';
import { useExperimentalFeatures } from '@/context/experimental-features-context';

interface WorkflowTypeSelectorProps {
  workflowTypes?: WorkflowTypeDescription[];
  selectedTypes: WorkflowRunType[];
  onSelectionChange: (types: WorkflowRunType[]) => void;
  disabled?: boolean;
  disabledTypes?: WorkflowRunType[];
  showHeader?: boolean;
  headerDescription?: string;
  error?: string;
  defaultShowExperimental?: boolean;
}

export function WorkflowTypeSelector({
  workflowTypes,
  selectedTypes,
  onSelectionChange,
  disabled = false,
  disabledTypes = [],
  showHeader = true,
  headerDescription,
  error,
  defaultShowExperimental = false,
}: WorkflowTypeSelectorProps) {
  const [showExperimental, setShowExperimental] = useState(defaultShowExperimental);
  const { showExperimentalFeatures } = useExperimentalFeatures();

  const regularWorkflows = workflowTypes?.filter((wt) => !wt.is_experimental);
  const experimentalWorkflows = workflowTypes?.filter((wt) => wt.is_experimental);

  // Only show experimental workflows if the user has opted in
  const shouldShowExperimentalSection = showExperimentalFeatures;
  const hasExperimentalWorkflows =
    shouldShowExperimentalSection && experimentalWorkflows && experimentalWorkflows.length > 0;

  const handleCheckedChange = (type: WorkflowRunType, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedTypes, type]);
    } else {
      onSelectionChange(selectedTypes.filter((t) => t !== type));
    }
  };

  return (
    <div className="space-y-4">
      {showHeader && (
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">
            Analyses Type Selection <span className="text-destructive ml-1">*</span>
          </h2>
          {headerDescription && <p className="text-sm text-muted-foreground">{headerDescription}</p>}
        </div>
      )}
      <div className="space-y-2">
        {regularWorkflows?.map((workflowType) => (
          <WorkflowTypeCheckbox
            key={workflowType.type}
            workflowType={workflowType}
            checked={selectedTypes.includes(workflowType.type)}
            onCheckedChange={(checked) => handleCheckedChange(workflowType.type, checked === true)}
            disabled={disabled || disabledTypes.includes(workflowType.type)}
          />
        ))}

        {hasExperimentalWorkflows && (
          <>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full text-muted-foreground"
              onClick={() => setShowExperimental(!showExperimental)}
            >
              {showExperimental ? (
                <>
                  <ChevronUp className="size-4 mr-1" />
                  Hide experimental analyses
                </>
              ) : (
                <>
                  <ChevronDown className="size-4 mr-1" />
                  Show experimental analyses ({experimentalWorkflows.length})
                </>
              )}
            </Button>

            {showExperimental &&
              experimentalWorkflows.map((workflowType) => (
                <WorkflowTypeCheckbox
                  key={workflowType.type}
                  workflowType={workflowType}
                  checked={selectedTypes.includes(workflowType.type)}
                  onCheckedChange={(checked) => handleCheckedChange(workflowType.type, checked === true)}
                  disabled={disabled || disabledTypes.includes(workflowType.type)}
                />
              ))}
          </>
        )}

        {!workflowTypes && <p className="text-sm text-muted-foreground">Loading available workflows...</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </div>
  );
}
