'use client';

import { SectionLabel } from '@/components/annotate/section-label';
import { AppBar } from '@/components/results/app-bar';
import type { AnnotationSetSummary } from '@/lib/generated-api';
import { useAnnotationSets } from '@/lib/hooks/use-annotations';
import { cn } from '@/lib/utils';
import { ChevronRight, Loader2 } from 'lucide-react';
import Link from 'next/link';

const STEPS = [
  'Pick a check. Each one tests a single kind of problem, and its rules are beside every example.',
  'Read the highlighted passage in its short document and say whether Draft Detective should flag it.',
  'Add a note when the call is not obvious. Notes are the most useful part.',
];

/** One check, in the projects list's row style: what it asks, and how far you are through it. */
function SetRow({ set }: { set: AnnotationSetSummary }) {
  const done = set.item_count > 0 && set.answered_by_me >= set.item_count;
  const started = set.answered_by_me > 0;
  const percent = set.item_count ? Math.min(100, (set.answered_by_me / set.item_count) * 100) : 0;

  return (
    <div className="group hover:bg-accent/40 relative flex items-center gap-3 border-b px-4 py-3 transition-colors">
      <span
        className={cn(
          'block size-2 shrink-0 rounded-full',
          done ? 'bg-green-500' : started ? 'bg-amber-500' : 'bg-muted-foreground/40',
        )}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <Link href={`/annotate/${set.slug}`} className="block truncate text-[13.5px] font-medium hover:underline">
          {set.title}
          <span className="absolute inset-0" aria-hidden />
        </Link>
        <p className="mt-0.5 text-[11.5px] text-muted-foreground">{set.summary}</p>
      </div>
      <div className="hidden w-28 shrink-0 sm:block" aria-hidden>
        <div className="h-1 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-foreground/60" style={{ width: `${percent}%` }} />
        </div>
      </div>
      <span className="w-16 shrink-0 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
        {set.answered_by_me}/{set.item_count}
      </span>
      <span className="w-16 shrink-0 text-right text-[11.5px] text-muted-foreground">
        {done ? 'Done' : started ? 'Continue' : 'Start'}
      </span>
      <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
    </div>
  );
}

/** Where the call to action leads: why this helps, then one row per check. */
export function AnnotationSetList() {
  const { data: sets, isLoading, error } = useAnnotationSets();
  const examples = sets?.reduce((sum, s) => sum + s.item_count, 0) ?? 0;
  const answered = sets?.reduce((sum, s) => sum + s.answered_by_me, 0) ?? 0;

  return (
    <div className="bg-background text-foreground flex h-dvh flex-col">
      <AppBar />
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center border-b px-4">
          <div className="mx-auto w-full max-w-5xl text-xs text-muted-foreground">
            {sets ? `${sets.length} checks · ${examples} examples · ${answered} answered by you` : 'Loading…'}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid max-w-5xl gap-10 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_17rem]">
            <div className="min-w-0">
              <h1 className="text-lg font-semibold tracking-tight">Help make Draft Detective more accurate</h1>
              <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground">
                We test every Draft Detective check against short example documents we wrote ourselves. Each example
                highlights one passage, and the test decides whether the check should flag it. We want to know where
                editors and researchers would make a different call.
              </p>

              <SectionLabel className="mt-8">Checks</SectionLabel>
              <div className="mt-2 border-t">
                {isLoading ? (
                  <Loader2 className="mx-auto my-8 size-5 animate-spin text-muted-foreground" />
                ) : error ? (
                  <p className="py-6 text-sm text-destructive">{error.message}</p>
                ) : !sets?.length ? (
                  <p className="py-6 text-sm text-muted-foreground">There is nothing to annotate yet.</p>
                ) : (
                  sets.map((set) => <SetRow key={set.slug} set={set} />)
                )}
              </div>
            </div>

            <aside className="space-y-6">
              <section>
                <SectionLabel>How it works</SectionLabel>
                <ol className="mt-2 space-y-2.5">
                  {STEPS.map((step, index) => (
                    <li key={step} className="flex gap-2.5 text-[13px] leading-snug">
                      <span className="w-4 shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                        {index + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </section>
              <section>
                <SectionLabel>About the examples</SectionLabel>
                <p className="mt-2 text-[13px] leading-snug text-muted-foreground">
                  They are made up: none comes from anyone&apos;s documents. Each takes about 20 seconds, and you can
                  stop whenever you like.
                </p>
              </section>
            </aside>
          </div>
        </div>
      </main>
    </div>
  );
}
