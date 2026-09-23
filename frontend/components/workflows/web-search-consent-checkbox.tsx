'use client';

import { Globe } from 'lucide-react';
import { Checkbox } from '../ui/checkbox';
import { cn } from '@/lib/utils';

interface WebSearchConsentCheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Marks the row as the thing a validation message is about; the message itself is the caller's. */
  invalid?: boolean;
  error?: string;
}

/**
 * The consent a web-searching assessment needs before it runs. Shaped like an
 * assessment row in the picker (checkbox, icon square, name, one-line detail),
 * in the amber the picker already uses for "this one needs something from you".
 */
export function WebSearchConsentCheckbox({
  checked,
  onCheckedChange,
  disabled = false,
  invalid = false,
  error,
}: WebSearchConsentCheckboxProps) {
  return (
    <div className="space-y-1.5">
      <label
        htmlFor="web-search-consent"
        className={cn(
          'flex w-full cursor-pointer items-center gap-3 rounded-md px-2 py-2 transition-colors',
          'bg-amber-500/10 hover:bg-amber-500/15',
          (invalid || error) && 'ring-1 ring-destructive/40',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <Checkbox
          id="web-search-consent"
          checked={checked}
          onCheckedChange={(value) => onCheckedChange(value === true)}
          disabled={disabled}
          aria-invalid={invalid || error ? true : undefined}
        />
        <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-amber-500/15 text-amber-700 dark:text-amber-400">
          <Globe aria-hidden className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium leading-tight">
            I consent to web search using parts or the whole document for this assessment
          </span>
          <span className="block text-[13px] leading-snug text-muted-foreground">
            Parts of the document are sent as search queries, so avoid confidential material. Don&apos;t proceed if you
            don&apos;t consent.
          </span>
        </span>
      </label>
      {error && <p className="px-2 text-xs text-destructive">{error}</p>}
    </div>
  );
}
