'use client';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  AppConfigResponse,
  listAppConfigsApiAppConfigsGet,
  resetAppConfigApiAppConfigsKeyDelete,
  updateAppConfigApiAppConfigsKeyPut,
} from '@/lib/generated-api';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, RotateCcw, Save, Settings } from 'lucide-react';
import { useSession } from 'next-auth/react';
import { useState } from 'react';
import { toast } from 'sonner';

const QUERY_KEY = ['admin', 'app-configs'];

export function SettingsList() {
  const session = useSession();

  const {
    data: configs,
    isLoading,
    error,
  } = useQuery({
    queryKey: QUERY_KEY,
    enabled: !!session.data?.user,
    queryFn: () => listAppConfigsApiAppConfigsGet(),
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Application Settings</CardTitle>
          <CardDescription>Manage runtime configuration for workflows and agents</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Application Settings</CardTitle>
          <CardDescription>Manage runtime configuration for workflows and agents</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p className="text-destructive">{error.message}</p>
            <Button variant="outline" onClick={() => window.location.reload()} className="mt-4">
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Settings className="h-6 w-6" />
          Application Settings
        </h1>
        <p className="text-muted-foreground mt-1">
          Override runtime configuration values used by workflows and agents. Changes take effect on the next workflow
          run.
        </p>
      </div>

      {!configs || configs.length === 0 ? (
        <Card>
          <CardContent className="py-8">
            <div className="text-center text-muted-foreground">No configurable settings found</div>
          </CardContent>
        </Card>
      ) : (
        configs.map((config) => <ConfigCard key={config.id} config={config} />)
      )}
    </div>
  );
}

function ConfigCard({ config }: { config: AppConfigResponse }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(config.value);
  const [resetting, setResetting] = useState(false);
  const hasChanges = value !== config.value;

  const saveMutation = useMutation({
    mutationFn: () =>
      updateAppConfigApiAppConfigsKeyPut({
        path: { key: config.key },
        body: { value },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success('Setting saved');
    },
    onError: (err) => {
      toast.error(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`);
    },
  });

  const resetMutation = useMutation({
    mutationFn: () =>
      resetAppConfigApiAppConfigsKeyDelete({
        path: { key: config.key },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success('Setting reset to default');
      setResetting(false);
    },
    onError: (err) => {
      toast.error(`Failed to reset: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setResetting(false);
    },
  });

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-mono">{config.key}</CardTitle>
          <CardDescription>{config.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={12}
            className="font-mono text-xs leading-relaxed"
          />
          <div className="flex items-center justify-between">
            <Button variant="outline" size="sm" onClick={() => setResetting(true)} disabled={resetMutation.isPending}>
              <RotateCcw className="h-4 w-4 mr-1.5" />
              Reset to default
            </Button>
            <div className="flex items-center gap-2">
              {hasChanges && <span className="text-xs text-muted-foreground">Unsaved changes</span>}
              <Button size="sm" onClick={() => saveMutation.mutate()} disabled={!hasChanges || saveMutation.isPending}>
                {saveMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <Save className="h-4 w-4 mr-1.5" />
                )}
                Save
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <AlertDialog open={resetting} onOpenChange={(open) => !open && setResetting(false)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset to default?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove your custom value for <strong className="font-mono">{config.key}</strong> and revert to
              the built-in default. The change takes effect on the next workflow run.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={resetMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => resetMutation.mutate()} disabled={resetMutation.isPending}>
              {resetMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resetting...
                </>
              ) : (
                'Reset'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
