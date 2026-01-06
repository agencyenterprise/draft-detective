'use client';

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';

const projectTypeOptions = [
  { value: 'projects', label: 'Projects' },
  { value: 'tool-runs', label: 'Tool Runs' },
] as const;

export type ProjectTypeValue = 'projects' | 'tool-runs';

interface ProjectTypeFilterProps {
  value: ProjectTypeValue[];
  onChange: (value: ProjectTypeValue[]) => void;
}

/**
 * Multi-select filter for project types (Projects vs Tool Runs).
 * Follows the same pattern as the severity filter in issues.
 */
export function ProjectTypeFilter({ value, onChange }: ProjectTypeFilterProps) {
  return (
    <ToggleGroup
      type="multiple"
      value={value}
      onValueChange={(v) => onChange(v as ProjectTypeValue[])}
      variant="outline"
      size="sm"
    >
      {projectTypeOptions.map((option) => (
        <ToggleGroupItem key={option.value} value={option.value} className={cn('text-xs h-7 px-3')}>
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
