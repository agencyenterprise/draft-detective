import * as React from 'react';
import { Input, InputProps } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export interface NumberRangeInputProps extends Omit<InputProps, 'onChange' | 'value' | 'type'> {
  value?: number[];
  onChange?: (numbers: number[]) => void;
  placeholder?: string;
}

/**
 * Parses a string input into an array of numbers.
 * Supports formats:
 * - "3" -> [3]
 * - "3, 4, 5" -> [3, 4, 5]
 * - "3-5" -> [3, 4, 5]
 * - "3-5; 7; 9-10" -> [3, 4, 5, 7, 9, 10]
 */
function parseNumberRange(input: string): number[] {
  if (!input.trim()) {
    return [];
  }

  const numbers = new Set<number>();

  // Split by semicolon first, then process each part
  const parts = input.split(';').map((part) => part.trim());

  for (const part of parts) {
    if (!part) continue;

    // Check if it's a range (contains dash)
    if (part.includes('-')) {
      const [startStr, endStr] = part.split('-').map((s) => s.trim());
      const start = parseInt(startStr, 10);
      const end = parseInt(endStr, 10);

      if (!isNaN(start) && !isNaN(end) && start <= end) {
        // Add all numbers in the range
        for (let i = start; i <= end; i++) {
          numbers.add(i);
        }
      }
    } else {
      // Split by comma and process individual numbers
      const numberStrings = part.split(',').map((s) => s.trim());
      for (const numStr of numberStrings) {
        const num = parseInt(numStr, 10);
        if (!isNaN(num)) {
          numbers.add(num);
        }
      }
    }
  }

  // Convert to sorted array
  return Array.from(numbers).sort((a, b) => a - b);
}

/**
 * Formats an array of numbers back into a string representation.
 * Groups consecutive numbers into ranges when possible.
 */
function formatNumberRange(numbers: number[]): string {
  if (numbers.length === 0) {
    return '';
  }

  const sorted = [...numbers].sort((a, b) => a - b);
  const parts: string[] = [];
  let rangeStart: number | null = null;
  let rangeEnd: number | null = null;

  for (let i = 0; i < sorted.length; i++) {
    const current = sorted[i];
    const next = sorted[i + 1];

    if (rangeStart === null) {
      rangeStart = current;
      rangeEnd = current;
    }

    if (next !== undefined && next === current + 1) {
      // Continue the range
      rangeEnd = next;
    } else {
      // End the range
      if (rangeStart === rangeEnd) {
        parts.push(rangeStart.toString());
      } else {
        parts.push(`${rangeStart}-${rangeEnd}`);
      }
      rangeStart = null;
      rangeEnd = null;
    }
  }

  return parts.join('; ');
}

export const NumberRangeInput = React.forwardRef<HTMLInputElement, NumberRangeInputProps>(
  ({ value = [], onChange, placeholder = 'e.g., 3-5; 7; 9-10', className, ...props }, ref) => {
    const [inputValue, setInputValue] = React.useState(() => {
      return value.length > 0 ? formatNumberRange(value) : '';
    });
    const isFocusedRef = React.useRef(false);

    // Update input value when prop value changes (only if not focused)
    React.useEffect(() => {
      if (!isFocusedRef.current) {
        if (value.length > 0) {
          const formatted = formatNumberRange(value);
          setInputValue(formatted);
        } else {
          setInputValue('');
        }
      }
    }, [value]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newInputValue = e.target.value;
      setInputValue(newInputValue);

      const parsed = parseNumberRange(newInputValue);
      onChange?.(parsed);
    };

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      isFocusedRef.current = true;
      props.onFocus?.(e);
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      isFocusedRef.current = false;
      // Optionally format on blur
      const parsed = parseNumberRange(inputValue);
      if (parsed.length > 0) {
        const formatted = formatNumberRange(parsed);
        setInputValue(formatted);
      }
      props.onBlur?.(e);
    };

    return (
      <Input
        ref={ref}
        type="text"
        value={inputValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        className={cn(className)}
        {...props}
      />
    );
  },
);

NumberRangeInput.displayName = 'NumberRangeInput';
