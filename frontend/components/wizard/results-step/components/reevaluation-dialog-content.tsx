import { NumberRangeInput } from '@/components/number-range-input';
import { Button } from '@/components/ui/button';
import { DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useSessionStorage } from '@/lib/hooks/use-session-storage';
import { GlobalFormValidationError, useForm } from '@tanstack/react-form';
import { useEffect } from 'react';
import { useAgentSelection } from '../hooks/use-agent-selection';
import { useSupportedAgents } from '../hooks/use-supported-agents';
import { AgentSelector } from './agent-selector';

interface ReevaluationDialogContentProps {
  isPending: boolean;
  chunkIndex?: number;
  onConfirm: (values: ReevaluationFormValues) => void;
  onCancel: () => void;
}

export interface ReevaluationFormValues {
  openaiApiKey: string;
  selectedAgents: string[];
  targetChunkIndices: number[];
}

export function ReevaluationDialogContent({
  isPending,
  chunkIndex,
  onConfirm,
  onCancel,
}: ReevaluationDialogContentProps) {
  const { supportedAgents, supportedAgentsError } = useSupportedAgents();
  const agentSelection = useAgentSelection({ supportedAgents, supportedAgentsError });
  const [openaiApiKey, setOpenaiApiKey] = useSessionStorage<string>('openai-api-key', '');
  const hideOpenaiApiKeyInput = process.env.NEXT_PUBLIC_HIDE_CUSTOM_OPENAI_API_KEY_INPUT === 'true';

  const form = useForm({
    defaultValues: {
      openaiApiKey: openaiApiKey,
      selectedAgents: Array.from(agentSelection.selectedAgents),
      targetChunkIndices: chunkIndex !== undefined ? [chunkIndex] : [],
    } as ReevaluationFormValues,
    validators: {
      onChange: ({ value }) => {
        const errors: GlobalFormValidationError<ReevaluationFormValues> = { fields: {}, form: undefined };
        if (!hideOpenaiApiKeyInput && (!value.openaiApiKey || value.openaiApiKey.trim() === '')) {
          errors.fields.openaiApiKey = 'OpenAI API Key is required';
        }
        if (value.selectedAgents.length === 0) {
          errors.fields.selectedAgents = 'Please select at least one agent';
        }
        return errors;
      },
    },
    onSubmit: ({ value }) => {
      onConfirm(value);
    },
  });

  useEffect(() => {
    form.setFieldValue('targetChunkIndices', chunkIndex !== undefined ? [chunkIndex] : []);
  }, [form, chunkIndex]);

  useEffect(() => {
    form.setFieldValue('selectedAgents', Array.from(agentSelection.selectedAgents));
  }, [form, agentSelection.selectedAgents]);

  return (
    <DialogContent className="min-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>Re-evaluate</DialogTitle>
        <DialogDescription>
          {hideOpenaiApiKeyInput
            ? 'Select the agents to run.'
            : 'Select the agents to run and provide your OpenAI API key.'}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-6">
        {!hideOpenaiApiKeyInput && (
          <form.Field
            name="openaiApiKey"
            listeners={{
              onChange: ({ value }) => setOpenaiApiKey(value),
            }}
          >
            {(field) => (
              <div className="space-y-2">
                <Label htmlFor="reevaluate-openai-key" required>
                  OpenAI API Key
                </Label>
                <Input
                  id="reevaluate-openai-key"
                  type="text"
                  placeholder="sk-..."
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  disabled={isPending}
                  error={!field.state.meta.isValid}
                  required={true}
                />
                {!field.state.meta.isValid && (
                  <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
                )}
              </div>
            )}
          </form.Field>
        )}

        <form.Field name="targetChunkIndices">
          {(field) => (
            <div className="space-y-2">
              <Label htmlFor="target-chunk-indices" optional>
                Target Chunk Indices
              </Label>
              <NumberRangeInput
                value={field.state.value}
                placeholder="e.g., 3-5; 7; 9-10"
                onChange={(value) => field.handleChange(value)}
              />
              <p className="text-sm text-muted-foreground">
                The chunk indices to re-evaluate. If not provided, all chunks will be re-evaluated.
              </p>
            </div>
          )}
        </form.Field>

        <form.Field name="selectedAgents">
          {(field) => (
            <div className="space-y-4">
              <AgentSelector
                supportedAgents={supportedAgents}
                supportedAgentsError={supportedAgentsError}
                selectedAgents={agentSelection.selectedAgents}
                onAgentToggle={agentSelection.handleAgentToggle}
                onSelectAll={agentSelection.handleSelectAll}
                onDeselectAll={agentSelection.handleDeselectAll}
                disabled={isPending}
                title="Select Agents to Run:"
              />
              {!field.state.meta.isValid && (
                <p className="text-sm text-destructive">{field.state.meta.errors.join(', ')}</p>
              )}
            </div>
          )}
        </form.Field>

        {agentSelection.error && (
          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{agentSelection.error}</div>
        )}
      </div>

      <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
        {([canSubmit, isSubmitting]) => (
          <DialogFooter>
            <Button variant="outline" onClick={onCancel} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={() => form.handleSubmit()} disabled={!canSubmit || isSubmitting}>
              {isSubmitting ? 'Re-analyzing...' : 'Run Re-analysis'}
            </Button>
          </DialogFooter>
        )}
      </form.Subscribe>
    </DialogContent>
  );
}
