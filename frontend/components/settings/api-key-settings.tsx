'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { USER_ME_QUERY_KEY, useUserMe } from '@/lib/hooks/use-user-me';
import { setApiKeyApiUsersMeApiKeyPut, removeApiKeyApiUsersMeApiKeyDelete } from '@/lib/generated-api';
import { Key, Loader2, Trash2 } from 'lucide-react';

export function ApiKeySettings() {
  const { data: user } = useUserMe();
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: (openai_api_key: string) => setApiKeyApiUsersMeApiKeyPut({ body: { openai_api_key } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USER_ME_QUERY_KEY });
      setApiKey('');
      setError(null);
    },
    onError: (err: unknown) => {
      const detail = (err as { detail?: string })?.detail;
      setError(detail ?? 'Failed to save API key. Please check that it is valid.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => removeApiKeyApiUsersMeApiKeyDelete(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USER_ME_QUERY_KEY });
      setError(null);
    },
  });

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    saveMutation.mutate(apiKey.trim());
  };

  const isBusy = saveMutation.isPending || deleteMutation.isPending;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Key className="h-4 w-4" />
          OpenAI API Key
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Store your OpenAI API key so it is used automatically when running analyses — including from MCP clients like
          Claude. The key is encrypted at rest and never exposed in API responses.
        </p>

        {user?.has_openai_api_key ? (
          <div className="flex items-center gap-3">
            <Badge variant="secondary" className="font-mono text-xs">
              Key saved
            </Badge>
            <Button variant="destructive" size="sm" onClick={() => deleteMutation.mutate()} disabled={isBusy}>
              {deleteMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <Trash2 className="h-4 w-4 mr-1" />
              )}
              Remove key
            </Button>
          </div>
        ) : (
          <Badge variant="outline" className="text-xs">
            No key saved
          </Badge>
        )}

        <form onSubmit={handleSave} className="flex items-start gap-2">
          <div className="flex-1 space-y-1">
            <Input
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
            {user?.has_openai_api_key ? 'Replace key' : 'Save key'}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
