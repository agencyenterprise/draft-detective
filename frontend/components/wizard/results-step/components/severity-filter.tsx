'use client';

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';

const severityOptions = [
  { value: SeverityEnum.High, label: 'High', className: 'data-[state=on]:bg-red-600 data-[state=on]:text-white' },
  { value: SeverityEnum.Medium, label: 'Med', className: 'data-[state=on]:bg-yellow-600 data-[state=on]:text-white' },
  { value: SeverityEnum.Low, label: 'Low', className: 'data-[state=on]:bg-blue-600 data-[state=on]:text-white' },
] as const;

interface SeverityFilterProps {
  value: SeverityEnum[];
  onChange: (value: SeverityEnum[]) => void;
}

export function SeverityFilter({ value, onChange }: SeverityFilterProps) {
  return (
    <ToggleGroup
      type="multiple"
      value={value}
      onValueChange={(v) => onChange(v as SeverityEnum[])}
      variant="outline"
      size="sm"
      className="shadow-xs bg-white"
    >
      {severityOptions.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          title={value.includes(option.value) ? `Hide ${option.label} issues` : `Show ${option.label} issues`}
          className={cn('text-xs h-6 px-2 cursor-pointer', option.className)}
        >
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
