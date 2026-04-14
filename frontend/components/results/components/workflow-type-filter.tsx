'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Issue, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { getIssueCount } from '@/lib/stores/document-explorer-store';
import { groupBy } from 'lodash';
import { FilterIcon } from 'lucide-react';
import { useMemo } from 'react';

interface WorkflowTypeFilterProps {
  issues: Issue[];
  value: WorkflowRunType[];
  onChange: (value: WorkflowRunType[]) => void;
  showPassing: boolean;
  onShowPassingChange: (value: boolean) => void;
  showResolved: boolean;
  onShowResolvedChange: (value: boolean) => void;
  resolvedCount: number;
  passingCount: number;
}

export function WorkflowTypeFilter({
  issues,
  value,
  onChange,
  showPassing,
  onShowPassingChange,
  showResolved,
  onShowResolvedChange,
  resolvedCount,
  passingCount,
}: WorkflowTypeFilterProps) {
  const { getWorkflowTypeName } = useWorkflowTypes();

  // Convert selected values to Set for O(1) lookups
  const selectedSet = useMemo(() => new Set(value), [value]);

  // Get unique workflow types from issues, sorted by count (most common first)
  const workflowTypeOptions = useMemo(() => {
    const issuesByType = groupBy(issues, (issue) => issue.workflow_type);

    return Object.entries(issuesByType)
      .map(([type, issues]) => ({
        value: type as WorkflowRunType,
        label: getWorkflowTypeName(type as WorkflowRunType),
        count: getIssueCount(issues),
      }))
      .sort((a, b) => b.count - a.count);
  }, [issues, getWorkflowTypeName]);

  if (workflowTypeOptions.length <= 0) {
    return null;
  }

  const handleToggle = (type: WorkflowRunType) => {
    if (selectedSet.has(type)) {
      onChange(value.filter((t) => t !== type));
    } else {
      onChange([...value, type]);
    }
  };

  const activeCount = value.length + (showPassing ? 1 : 0) + (showResolved ? 1 : 0);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          title="Filter by assessment type"
          className="h-6 px-2 text-xs gap-1 flex items-center"
        >
          <FilterIcon className="size-3.5" />
          <span>Filters</span>
          {activeCount > 0 && (
            <Badge variant="secondary" className="h-4 min-w-4 px-1 text-[10px] rounded-full">
              {activeCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-2" align="end">
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground px-2 pb-1">Assessment type</p>
          {workflowTypeOptions.map((option) => (
            <label
              key={option.value}
              className="flex items-center gap-2 px-2 py-1 rounded-sm hover:bg-muted cursor-pointer"
            >
              <Checkbox checked={selectedSet.has(option.value)} onCheckedChange={() => handleToggle(option.value)} />
              <span className="text-sm flex-1">{option.label}</span>
              <span className="text-xs text-muted-foreground">{option.count}</span>
            </label>
          ))}
        </div>
        <div className="border-t mt-2 pt-2 space-y-1">
          <p className="text-xs font-medium text-muted-foreground px-2 pb-1">Visibility</p>
          {resolvedCount > 0 && (
            <label className="flex items-center gap-2 px-2 py-1 rounded-sm hover:bg-muted cursor-pointer">
              <Checkbox checked={showResolved} onCheckedChange={(checked) => onShowResolvedChange(!!checked)} />
              <span className="text-sm flex-1">Show resolved issues</span>
              <span className="text-xs text-muted-foreground">{resolvedCount}</span>
            </label>
          )}
          <label className="flex items-center gap-2 px-2 py-1 rounded-sm hover:bg-muted cursor-pointer">
            <Checkbox checked={showPassing} onCheckedChange={(checked) => onShowPassingChange(!!checked)} />
            <span className="text-sm flex-1">Show passing checks</span>
            <span className="text-xs text-muted-foreground">{passingCount}</span>
          </label>
        </div>
        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full h-7 text-xs mt-2"
            onClick={() => {
              onChange([]);
              onShowPassingChange(false);
              onShowResolvedChange(false);
            }}
          >
            Clear all
          </Button>
        )}
      </PopoverContent>
    </Popover>
  );
}
