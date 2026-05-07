'use client';

import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { CostBreakdown } from '@/lib/generated-api';
import { cn } from '@/lib/utils';

interface WorkflowRunCostProps {
  cost: CostBreakdown | null | undefined;
  className?: string;
  /** Hide the "Cost:" label prefix (useful in compact contexts like history items). */
  compact?: boolean;
}

function formatUsd(value: number | string | null | undefined): string {
  const n = typeof value === 'string' ? parseFloat(value) : (value ?? 0);
  if (n === 0) return '$0.0000';
  if (n < 0.0001) return `<$0.0001`;
  return `$${n.toFixed(4)}`;
}

function formatTokens(n: number): string {
  return n.toLocaleString();
}

export function WorkflowRunCost({ cost, className, compact }: WorkflowRunCostProps) {
  if (!cost) return null;

  const total = Number(cost.total_cost_usd ?? 0);
  const inputTokens = cost.total_input_tokens ?? 0;
  const outputTokens = cost.total_output_tokens ?? 0;
  const cacheReadTokens = cost.total_cache_read_tokens ?? 0;
  const byModel = cost.by_model ?? {};
  const totalTokens = inputTokens + outputTokens + cacheReadTokens;

  return (
    <TooltipProvider delayDuration={0}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          <span className={cn('inline-flex items-center gap-1 cursor-help', className)}>
            {!compact && <span className="font-medium">Cost:</span>}
            <span>{formatUsd(total)}</span>
          </span>
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            sideOffset={4}
            className="z-50 max-w-md p-3 bg-white text-foreground border rounded-md shadow-md animate-in fade-in-0 zoom-in-95"
          >
            <div className="space-y-2 text-xs">
              <div className="font-medium border-b pb-1.5 mb-1.5">
                Total: {formatUsd(total)} · {formatTokens(totalTokens)} tokens
              </div>

              <CostRow label="Input" tokens={inputTokens} cost={cost.input_cost_usd ?? 0} />
              <CostRow label="Output" tokens={outputTokens} cost={cost.output_cost_usd ?? 0} />
              {cacheReadTokens > 0 && (
                <CostRow label="Cache read" tokens={cacheReadTokens} cost={cost.cache_read_cost_usd ?? 0} />
              )}

              {Object.keys(byModel).length > 1 && (
                <div className="pt-2 mt-2 border-t">
                  <div className="font-medium mb-1">By model</div>
                  {Object.entries(byModel).map(([model, breakdown]) => (
                    <div key={model} className="flex justify-between gap-4">
                      <span className="truncate">{model}</span>
                      <span>{formatUsd(breakdown.total_cost_usd ?? 0)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipProvider>
  );
}

function CostRow({ label, tokens, cost }: { label: string; tokens: number; cost: number | string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span>
        {formatTokens(tokens)} · {formatUsd(cost)}
      </span>
    </div>
  );
}
