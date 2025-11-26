interface PromptArgsSectionProps {
  promptKwargs: Record<string, unknown>;
}

export function PromptArgsSection({ promptKwargs }: PromptArgsSectionProps) {
  return (
    <div>
      <h4 className="font-medium mb-3">Prompt args</h4>
      <div className="bg-muted/30 p-3 rounded-lg space-y-2">
        {Object.entries(promptKwargs).map(([key, value]) => (
          <div key={key} className="space-y-1">
            <span className="font-medium text-sm">{key}:</span>
            <div className="text-sm text-muted-foreground bg-background p-2 rounded border max-h-32 overflow-y-auto whitespace-pre-wrap">
              {typeof value === 'string' ? value : JSON.stringify(value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
