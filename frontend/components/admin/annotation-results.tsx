'use client';

import { AnnotatedItemRow } from '@/components/admin/annotated-item-row';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { downloadFile } from '@/lib/file-download';
import type { AnnotationSetStats } from '@/lib/generated-api';
import { useAnnotatedItems, useAnnotationSetStats } from '@/lib/hooks/use-annotations';
import { cn } from '@/lib/utils';
import { Download, Loader2 } from 'lucide-react';
import { useState } from 'react';

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
          <TableRow
            key={set.slug}
            onClick={() => onSelect(set.slug)}
            className={cn('cursor-pointer', selected === set.slug && 'bg-muted')}
          >
            <TableCell className="font-medium">{set.title}</TableCell>
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

  const exportJson = () =>
    downloadFile({
      filename: `annotations-${slug}.json`,
      blob: new Blob([JSON.stringify(items ?? [], null, 2)], { type: 'application/json' }),
    });

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Annotated items</CardTitle>
          <CardDescription>Most contested first. Open an item to read the document and every answer.</CardDescription>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={onlyDisagreements} onCheckedChange={setOnlyDisagreements} />
            Only disagreements
          </label>
          <Button variant="outline" size="sm" onClick={exportJson} disabled={!items?.length}>
            <Download className="size-4" /> Export JSON
          </Button>
        </div>
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

/** Admin view of how people's answers compare with the eval datasets. */
export function AnnotationResults() {
  const { data: sets, isLoading, error } = useAnnotationSetStats();
  const [selected, setSelected] = useState<string | null>(null);
  const current = selected ?? sets?.[0]?.slug ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Annotation results</h1>
        <p className="mt-1 text-muted-foreground">
          How users&apos; answers compare with what each eval dataset expects. Disagreements point at a test case, or a
          rule, worth a second look.
        </p>
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
