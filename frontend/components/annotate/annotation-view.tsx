'use client';

import { PassageDocument } from '@/components/annotate/passage-document';
import { QuestionPane } from '@/components/annotate/question-pane';
import { AppBar } from '@/components/results/app-bar';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useNextAnnotationTask } from '@/lib/hooks/use-annotations';
import { ArrowLeft, CircleCheck, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { ReactNode, useState } from 'react';

function Centred({ children }: { children: ReactNode }) {
  return <div className="flex h-full min-h-0 flex-1 items-center justify-center p-8 text-center">{children}</div>;
}

function SetFinished({ skippedCount, onRevisitSkipped }: { skippedCount: number; onRevisitSkipped: () => void }) {
  return (
    <Centred>
      <div className="max-w-xs">
        <CircleCheck className="mx-auto size-7 text-muted-foreground" />
        <p className="mt-2 text-sm font-medium">
          {skippedCount ? 'Only the ones you skipped are left.' : 'You have answered every example in this check.'}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Thank you. We use your answers to check and improve our test cases.
        </p>
        <div className="mt-3 flex justify-center gap-2">
          {skippedCount > 0 && (
            <Button size="sm" variant="outline" onClick={onRevisitSkipped}>
              Revisit {skippedCount} skipped
            </Button>
          )}
          <Button size="sm" asChild>
            <Link href="/annotate">Pick another check</Link>
          </Button>
        </div>
      </div>
    </Centred>
  );
}

/**
 * One check, an example at a time, laid out like the document explorer in two
 * columns: the document, and a right-hand pane with the question and the
 * check's guidance below it. Skipped items are remembered for this visit only, so a
 * skip never hides an item for good.
 */
export function AnnotationView({ slug }: { slug: string }) {
  const [skipped, setSkipped] = useState<string[]>([]);
  const [round, setRound] = useState(0);
  const { data, isLoading, isPlaceholderData, error } = useNextAnnotationTask(slug, skipped, round);
  const task = data?.task;
  const item = task?.item_id && task.passage ? { id: task.item_id, passage: task.passage } : null;

  let body: ReactNode;
  if (isLoading) {
    body = (
      <Centred>
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </Centred>
    );
  } else if (error || !task || !data) {
    body = (
      <Centred>
        <p className="text-sm text-destructive">{error?.message ?? 'Could not load this check.'}</p>
      </Centred>
    );
  } else {
    const percent = task.item_count ? (task.answered_by_me / task.item_count) * 100 : 0;
    body = (
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex h-10 shrink-0 items-center gap-2 border-b px-2">
            <Button variant="ghost" size="xs" asChild className="shrink-0 text-muted-foreground">
              <Link href="/annotate">
                <ArrowLeft className="size-3.5" /> All checks
              </Link>
            </Button>
            <span className="truncate text-xs text-muted-foreground">
              Example document
              {item?.passage.line ? ` · passage on line ${item.passage.line}` : ''}
            </span>
            <div className="ml-auto flex shrink-0 items-center gap-2 px-2">
              <Progress value={percent} className="hidden h-1 w-24 sm:block" />
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {task.answered_by_me}/{task.item_count} answered
              </span>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            {isPlaceholderData ? (
              <Centred>
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
              </Centred>
            ) : item ? (
              <PassageDocument
                key={item.id}
                document={item.passage.document}
                anchor={item.passage.anchor}
                className="h-full"
              />
            ) : (
              <SetFinished
                skippedCount={skipped.length}
                onRevisitSkipped={() => {
                  // A new round too: the empty skip list's first answer is cached and stale.
                  setSkipped([]);
                  setRound((r) => r + 1);
                }}
              />
            )}
          </div>
        </main>

        {item && !isPlaceholderData && (
          <aside className="flex max-h-[50%] shrink-0 flex-col border-t lg:max-h-none lg:w-[24rem] lg:border-t-0 lg:border-l xl:w-[26rem]">
            <div className="flex h-10 shrink-0 items-center border-b px-4 text-xs font-medium">Your judgment</div>
            <div className="min-h-0 flex-1">
              <QuestionPane
                key={item.id}
                itemId={item.id}
                passage={item.passage}
                questions={task.set.questions}
                guidance={task.set.guidance}
                shownAt={data.shownAt}
                onNext={() => setRound((r) => r + 1)}
                onSkip={() => setSkipped((ids) => [...ids, item.id])}
              />
            </div>
          </aside>
        )}
      </div>
    );
  }

  return (
    <div className="bg-background text-foreground flex h-dvh flex-col">
      <AppBar title={task ? <span className="truncate text-sm font-medium">{task.set.title}</span> : undefined} />
      {body}
    </div>
  );
}
