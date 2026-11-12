'use client';

import { useState } from 'react';
import { useIsMutating, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { USER_ME_QUERY_KEY, useUserMe } from '@/lib/hooks/use-user-me';
import { removeApiKeyApiUsersMeApiKeyDelete } from '@/lib/generated-api';
import { getErrorDetail } from '@/lib/api-error';
import { Key, Loader2, Trash2 } from 'lucide-react';
import { ApiKeyForm, SAVE_API_KEY_MUTATION_KEY } from './api-key-form';

export function ApiKeySettings() {
  const { data: user } = useUserMe();
  const queryClient = useQueryClient();
  const [removeError, setRemoveError] = useState<string | null>(null);
  const hasKey = user?.has_openai_api_key ?? false;

  const deleteMutation = useMutation({
    mutationFn: () => removeApiKeyApiUsersMeApiKeyDelete(),
    onMutate: () => setRemoveError(null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: USER_ME_QUERY_KEY }),
    onError: (err: unknown) => setRemoveError(getErrorDetail(err, 'Failed to remove API key. Please try again.')),
  });
  const isSaving = useIsMutating({ mutationKey: SAVE_API_KEY_MUTATION_KEY }) > 0;

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
          Store your OpenAI API key so it is used automatically when running assessments — including from MCP clients
          like Claude. The key is encrypted at rest and never exposed in API responses.
        </p>

        {hasKey ? (
          <div className="flex items-center gap-3">
            <Badge variant="secondary" className="font-mono text-xs">
              Key saved
            </Badge>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => deleteMutation.mutate()}
              disabled={isSaving || deleteMutation.isPending}
            >
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

        {removeError && <p className="text-sm text-destructive">{removeError}</p>}

        {/* Keyed on whether a key is saved, so removing the key also clears a stale save error. */}
        <ApiKeyForm
          key={String(hasKey)}
          submitLabel={hasKey ? 'Replace key' : 'Save key'}
          disabled={deleteMutation.isPending}
        />
      </CardContent>
    </Card>
  );
}
