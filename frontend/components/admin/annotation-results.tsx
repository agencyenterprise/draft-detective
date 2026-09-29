'use client';

import { AnnotatedItemRow } from '@/components/admin/annotated-item-row';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { downloadFile } from '@/lib/file-download';
import type { AnnotationSetStats } from '@/lib/generated-api';
import { getErrorMessage } from '@/lib/api-error';
import { useAnnotatedItems, useAnnotationSetStats, useExportAnnotations } from '@/lib/hooks/use-annotations';
import { cn } from '@/lib/utils';
import { Download, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

function agreementRate(stats: AnnotationSetStats): string {
  const decided = stats.agreements + stats.disagreements;
  return decided ? `${Math.round((stats.agreements / decided) * 100)}%` : '–';
}

function StatsTable({
  sets,
  selected,
  onSelect,
}: {
  sets: AnnotationSetStats[];
  selected: string | null;
  onSelect: (slug: string) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Set</TableHead>
          <TableHead className="text-right">Items annotated</TableHead>
          <TableHead className="text-right">Annotations</TableHead>
          <TableHead className="text-right">Annotators</TableHead>
          <TableHead className="text-right">Agree with test case</TableHead>
          <TableHead className="text-right">Disagree</TableHead>
          <TableHead className="text-right">Not sure</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sets.map((set) => (
          <TableRow key={set.slug} className={cn('relative', selected === set.slug && 'bg-muted')}>
            <TableCell className="font-medium">
              {/* A real button, so the set can be picked by keyboard; its
                  overlay stretches over the row so the whole row stays clickable. */}
              <button
                type="button"
                aria-pressed={selected === set.slug}
                onClick={() => onSelect(set.slug)}
                className="cursor-pointer text-left after:absolute after:inset-0 focus-visible:underline focus-visible:outline-none"
              >
                {set.title}
              </button>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {set.annotated_items} / {set.item_count}
            </TableCell>
            <TableCell className="text-right tabular-nums">{set.annotation_count}</TableCell>
            <TableCell className="text-right tabular-nums">{set.annotator_count}</TableCell>
            <TableCell className="text-right tabular-nums">{agreementRate(set)}</TableCell>
            <TableCell className="text-right tabular-nums">{set.disagreements}</TableCell>
            <TableCell className="text-right tabular-nums">{set.abstentions}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function SetItems({ slug }: { slug: string }) {
  const [onlyDisagreements, setOnlyDisagreements] = useState(false);
  const { data: items, isLoading } = useAnnotatedItems(slug, onlyDisagreements);

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Annotated items</CardTitle>
          <CardDescription>Most contested first. Open an item to read the document and every answer.</CardDescription>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={onlyDisagreements} onCheckedChange={setOnlyDisagreements} />
          Only disagreements
        </label>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />
        ) : !items?.length ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No annotated items yet.</p>
        ) : (
          <div className="divide-y rounded-md border">
            {items.map((item) => (
              <AnnotatedItemRow key={item.item_id} item={item} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Downloads every set's results in one file, whichever set is on screen. */
function ExportAllButton() {
  const exportAll = useExportAnnotations();

  const download = () =>
    exportAll.mutate(undefined, {
      onSuccess: (sets) =>
        downloadFile({
          filename: `annotations-${new Date().toISOString().slice(0, 10)}.json`,
          blob: new Blob([JSON.stringify(sets, null, 2)], { type: 'application/json' }),
        }),
      onError: (error) => toast.error(getErrorMessage(error, 'Could not export the annotations')),
    });

  return (
    <Button variant="outline" size="sm" onClick={download} disabled={exportAll.isPending}>
      {exportAll.isPending ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
      Export all (JSON)
    </Button>
  );
}

/** Admin view of how people's answers compare with the eval datasets. */
export function AnnotationResults() {
  const { data: sets, isLoading, error } = useAnnotationSetStats();
  const [selected, setSelected] = useState<string | null>(null);
  const current = selected ?? sets?.[0]?.slug ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Annotation results</h1>
          <p className="mt-1 text-muted-foreground">
            How users&apos; answers compare with what each eval dataset expects. Disagreements point at a test case, or
            a rule, worth a second look.
          </p>
        </div>
        <ExportAllButton />
      </div>

      <Card>
        <CardContent>
          {isLoading ? (
            <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />
          ) : error ? (
            <p className="text-sm text-destructive">{error.message}</p>
          ) : (
            <StatsTable sets={sets ?? []} selected={current} onSelect={setSelected} />
          )}
        </CardContent>
      </Card>

      {current && <SetItems key={current} slug={current} />}
    </div>
  );
}
