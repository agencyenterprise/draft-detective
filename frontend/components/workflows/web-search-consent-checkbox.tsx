'use client';

import { CheckboxWithDescription } from '../ui/checkbox-with-description';

interface WebSearchConsentCheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  error?: string;
}

export function WebSearchConsentCheckbox({
  checked,
  onCheckedChange,
  disabled = false,
  error,
}: WebSearchConsentCheckboxProps) {
  return (
    <div className="space-y-4">
      <div className="bg-yellow-50 border border-yellow-400 rounded-lg">
        <CheckboxWithDescription
          id="web-search-consent"
          checked={checked}
          onCheckedChange={(checked) => onCheckedChange(checked === true)}
          label="I consent to perform web search using parts or the whole document for this analysis"
          description="Web search is required to perform this analysis. Parts of the document will be used to perform web search, so we don't recommend using confidential information. Don't proceed if you don't consent to perform web search."
          disabled={disabled}
        />
      </div>
      {error && <p className="text-sm text-destructive pl-6">{error}</p>}
    </div>
  );
}
