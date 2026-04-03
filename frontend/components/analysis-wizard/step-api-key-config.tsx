'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { setApiKeyApiUsersMeApiKeyPut } from '@/lib/generated-api';
import { USER_ME_QUERY_KEY } from '@/lib/hooks/use-user-me';
import { isApiError } from '@/lib/api-error';
import { Key, Loader2 } from 'lucide-react';

export function StepApiKeyConfig() {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: (openai_api_key: string) => setApiKeyApiUsersMeApiKeyPut({ body: { openai_api_key } }),
    onSuccess: () => {
      // Invalidating triggers a re-fetch of user data. Once has_openai_api_key becomes
      // true, new/page.tsx automatically transitions to the "Your Document" step.
      queryClient.invalidateQueries({ queryKey: USER_ME_QUERY_KEY });
      setApiKey('');
      setError(null);
    },
    onError: (err: unknown) => {
      const message = isApiError(err) ? err.message : 'Failed to save API key. Please check that it is valid.';
      setError(message);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    saveMutation.mutate(apiKey.trim());
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Set up your OpenAI API Key</h1>
        <p className="text-muted-foreground">
          This deployment requires an OpenAI API key to run analyses. Your key is encrypted at rest and never exposed in
          API responses. You can update or remove it at any time from your account settings.
        </p>
      </div>

      <div className="rounded-lg border p-6 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Key className="h-4 w-4" />
          OpenAI API Key
        </div>

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
              disabled={saveMutation.isPending}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          <Button type="submit" disabled={saveMutation.isPending || !apiKey.trim()}>
            {saveMutation.isPending && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Save key
          </Button>
        </form>

        <p className="text-sm text-muted-foreground">
          Once saved, you&apos;ll be taken to the next step automatically.
        </p>
      </div>
    </div>
  );
}
