'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Issue, WorkflowRunType } from '@/lib/generated-api';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { FilterIcon } from 'lucide-react';
import { useMemo } from 'react';

interface WorkflowTypeFilterProps {
  issues: Issue[];
  value: WorkflowRunType[];
  onChange: (value: WorkflowRunType[]) => void;
}

export function WorkflowTypeFilter({ issues, value, onChange }: WorkflowTypeFilterProps) {
  const { getWorkflowTypeName } = useWorkflowTypes();

  // Convert selected values to Set for O(1) lookups
  const selectedSet = useMemo(() => new Set(value), [value]);

  // Get unique workflow types from issues, sorted by count (most common first)
  const workflowTypeOptions = useMemo(() => {
    const typeCounts = new Map<WorkflowRunType, number>();
    for (const issue of issues) {
      if (issue.workflow_type) {
        typeCounts.set(issue.workflow_type, (typeCounts.get(issue.workflow_type) ?? 0) + 1);
      }
    }

    return Array.from(typeCounts.entries())
      .sort((a, b) => b[1] - a[1]) // Sort by count descending
      .map(([type, count]) => ({
        value: type,
        label: getWorkflowTypeName(type),
        count,
      }));
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

  const activeCount = value.length;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-6 px-2 text-xs gap-1 flex items-center">
          <FilterIcon className="size-3.5" />
          <span>Type</span>
          {activeCount > 0 && (
            <Badge variant="secondary" className="h-4 min-w-4 px-1 text-[10px] rounded-full">
              {activeCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-2" align="end">
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground px-2 pb-1">Filter by analysis type</p>
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
          {activeCount > 0 && (
            <Button variant="ghost" size="sm" className="w-full h-7 text-xs mt-1" onClick={() => onChange([])}>
              Clear filters
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function filterIssuesByWorkflowType(issues: Issue[], workflowTypes: WorkflowRunType[]): Issue[] {
  if (workflowTypes.length === 0) return issues;
  const typeSet = new Set(workflowTypes);
  return issues.filter((issue) => issue.workflow_type && typeSet.has(issue.workflow_type));
}
