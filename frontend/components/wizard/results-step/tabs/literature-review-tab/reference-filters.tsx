'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { Filter, X } from 'lucide-react';
import { QualityLevel, ReferenceDirection, DocumentReferenceFactors, RecommendedAction } from '@/lib/generated-api';
import { FilterGroup } from './filter-group';
import { createFilterOptions } from './utils';

export interface FilterState {
  quality: QualityLevel | 'all';
  direction: ReferenceDirection | 'all';
  action: string | 'all';
}

interface ReferenceFiltersProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  totalCount: number;
  filteredCount: number;
}

const FILTER_CONFIGS = [
  { key: 'quality' as const, label: 'Quality', options: createFilterOptions(QualityLevel) },
  { key: 'direction' as const, label: 'Direction', options: createFilterOptions(ReferenceDirection) },
  { key: 'action' as const, label: 'Recommended Action', options: createFilterOptions(RecommendedAction) },
];

export function ReferenceFilters({ filters, onFiltersChange, totalCount, filteredCount }: ReferenceFiltersProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const hasActiveFilters = filters.quality !== 'all' || filters.direction !== 'all' || filters.action !== 'all';

  const handleClearAll = () => {
    onFiltersChange({
      quality: 'all',
      direction: 'all',
      action: 'all',
    });
  };

  const getActiveFilterBadges = () => {
    return FILTER_CONFIGS.filter(({ key }) => filters[key] !== 'all').map(({ key, options }) => {
      const option = options.find((o) => o.value === filters[key]);
      return {
        label: option?.label || '',
        onRemove: () => onFiltersChange({ ...filters, [key]: 'all' }),
      };
    });
  };

  const activeBadges = getActiveFilterBadges();

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <Filter className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <Badge variant="secondary" className="ml-0.5 px-1.5 h-5 text-xs">
                {activeBadges.length}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80" align="start">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-sm">Filter References</h4>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={handleClearAll} className="h-8 gap-1 text-xs">
                  <X className="h-3 w-3" />
                  Clear All
                </Button>
              )}
            </div>

            <Separator />

            <div className="space-y-4">
              {FILTER_CONFIGS.map(({ key, label, options }) => (
                <FilterGroup
                  key={key}
                  label={label}
                  options={options}
                  value={filters[key]}
                  onChange={(value) => onFiltersChange({ ...filters, [key]: value })}
                />
              ))}
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {activeBadges.map((badge, index) => (
        <Badge key={index} variant="secondary" className="gap-1 pl-2.5 pr-1">
          {badge.label}
          <button onClick={badge.onRemove} className="ml-0.5 rounded-sm hover:bg-muted-foreground/20 p-0.5">
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}

      {filteredCount !== totalCount && (
        <span className="text-xs text-muted-foreground ml-auto">
          Showing {filteredCount} of {totalCount}
        </span>
      )}
    </div>
  );
}

export function filterReferences(
  references: DocumentReferenceFactors[],
  filters: FilterState,
): DocumentReferenceFactors[] {
  return references.filter((ref) => {
    if (filters.quality !== 'all' && ref.quality !== filters.quality) return false;
    if (filters.direction !== 'all' && ref.reference_direction !== filters.direction) return false;
    if (filters.action !== 'all' && ref.recommended_action !== filters.action) return false;
    return true;
  });
}
