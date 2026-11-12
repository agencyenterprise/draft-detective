'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { setApiKeyApiUsersMeApiKeyPut } from '@/lib/generated-api';
import { USER_ME_QUERY_KEY } from '@/lib/hooks/use-user-me';
import { getErrorDetail } from '@/lib/api-error';
import { Loader2 } from 'lucide-react';

/** Lets the rest of the page see a save in flight (`useIsMutating`). */
export const SAVE_API_KEY_MUTATION_KEY = ['user', 'me', 'api-key', 'save'] as const;

interface ApiKeyFormProps {
  submitLabel?: string;
  /** Holds the form while something else on the page is busy with the key. */
  disabled?: boolean;
}

/**
 * Saves the user's OpenAI API key, then refetches the user so `has_openai_api_key` updates.
 * A rejected key keeps the field filled for a retry and shows the server's reason.
 */
export function ApiKeyForm({ submitLabel = 'Save key', disabled = false }: ApiKeyFormProps) {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationKey: SAVE_API_KEY_MUTATION_KEY,
    mutationFn: (openai_api_key: string) => setApiKeyApiUsersMeApiKeyPut({ body: { openai_api_key } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USER_ME_QUERY_KEY });
      setApiKey('');
      setError(null);
    },
    onError: (err: unknown) => setError(getErrorDetail(err, 'Failed to save API key. Please check that it is valid.')),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    saveMutation.mutate(apiKey.trim());
  };

  const isBusy = disabled || saveMutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="flex items-start gap-2">
      <div className="flex-1 space-y-1">
        <Label htmlFor="api-key-input" className="sr-only">
          OpenAI API Key
        </Label>
        <Input
          id="api-key-input"
          type="password"
          placeholder="sk-..."
          value={apiKey}
          onChange={(e) => {
            setApiKey(e.target.value);
            setError(null);
          }}
          disabled={isBusy}
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      <Button type="submit" disabled={isBusy || !apiKey.trim()}>
        {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
        {submitLabel}
      </Button>
    </form>
  );
}
