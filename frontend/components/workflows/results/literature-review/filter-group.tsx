'use client';

import { Button } from '@/components/ui/button';

interface FilterOption<T> {
  value: T;
  label: string;
}

interface FilterGroupProps<T extends string> {
  label: string;
  options: FilterOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

export function FilterGroup<T extends string>({ label, options, value, onChange }: FilterGroupProps<T>) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <Button
            key={option.value}
            variant={value === option.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange(option.value)}
            className="capitalize"
          >
            {option.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
